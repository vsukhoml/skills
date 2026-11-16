# Zero-Downtime Migrations, Concurrency & Client/Embedded Storage (`data-modeling`)

---

## 1. Zero-Downtime Relational Migration Playbook

### 1.1 The Lock-Queue Outage Mechanism (Why `lock_timeout` Is Mandatory)

In PostgreSQL/MySQL, `ALTER TABLE` requests an `AccessExclusiveLock` / metadata lock.
If a `4 s` reporting query currently holds `AccessShareLock` on `orders`, the `ALTER
TABLE` waits behind it — **and every new `SELECT` or `INSERT` on `orders` queues
behind the waiting `ALTER TABLE`**, taking down `100%` of traffic in `< 2 s`!

**Safe migration wrapper pattern:**

```sql
-- Retry loop in migration runner (e.g., 5 attempts with jittered backoff):
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '10s';
ALTER TABLE orders ADD COLUMN tax_jurisdiction TEXT;
COMMIT;

-- Non-transactional DDL (CREATE INDEX CONCURRENTLY cannot run inside BEGIN..COMMIT):
SET lock_timeout = '2s';
CREATE INDEX CONCURRENTLY idx_orders_tax_jurisdiction ON orders (tax_jurisdiction);
RESET lock_timeout;
```

### 1.2 Safe vs. Hazardous DDL Operations & Online Equivalents

| Desired Schema Change | Hazardous Naive DDL (Blocks / Breaks N-1) | Zero-Downtime Online Sequence |
| --- | --- | --- |
| **Add index** | `CREATE INDEX ...` (locks all writes!) | `CREATE INDEX CONCURRENTLY ...` (outside tx block; check `pg_index.indisvalid` after!) |
| **Add `FOREIGN KEY` or `CHECK`** | `ALTER TABLE t ADD CONSTRAINT ...` (full table scan under exclusive lock!) | 1. `ALTER TABLE t ADD CONSTRAINT c CHECK (...) NOT VALID;` (instant metadata)<br>2. `ALTER TABLE t VALIDATE CONSTRAINT c;` (non-blocking `ShareUpdateExclusiveLock`!) |
| **Add `NOT NULL` to existing column** | `ALTER TABLE t ALTER COL SET NOT NULL` (full scan lock on large tables!) | 1. Add `CHECK (col IS NOT NULL) NOT VALID`<br>2. `VALIDATE CONSTRAINT`<br>3. `SET NOT NULL` (instant once proven by valid `CHECK` in PG 12+!) + drop redundant check |
| **Rename column (`fname -> given_name`)** | `ALTER TABLE RENAME COLUMN` (instantly crashes running `N-1` pods!) | 1. **Expand:** Add `given_name` nullable<br>2. **Dual-write + batched backfill**<br>3. **Switch reads** to `given_name`<br>4. **Contract (next release):** Stop writing `fname`, then drop `fname` |
| **Drop column** | Dropping column while `N-1` ORM runs `SELECT *` or `INSERT` naming it | 1. Deploy app ignoring column (`explicit SELECT list`, ORM ignore annotation)<br>2. Drop column in the **next** deployment |
| **Backfill `50M` rows** | Single `UPDATE t SET x = y;` (holds row locks for minutes, explodes WAL/replication lag & dead tuples!) | Keyset loop (`WHERE id > $cursor ORDER BY id LIMIT 5000`) committing per batch, sleeping `50–200 ms` when replica lag or DB CPU rises |

---

## 2. Concurrency, Idempotency & Transactional Outbox Patterns

### 2.1 Choosing the Right Concurrency Guard

| Anomaly / Scenario | Exact SQL / Storage Pattern |
| --- | --- |
| **Quota / Inventory decrement** | Single-statement guard: `UPDATE quotas SET used = used + $n WHERE tenant_id = $t AND used + $n <= quota_limit RETURNING used;` (`0` rows updated = quota exceeded, atomic under any isolation!). |
| **Collaborative human form edit** | Optimistic `version` CAS: `UPDATE docs SET body = $b, version = version + 1 WHERE id = $id AND version = $expected_v;` (`0` rows = HTTP `409 Conflict` rather than silent overwrite!). |
| **Multi-row invariant (`Write Skew`, e.g. "at least 1 on-call engineer must remain")** | Lock parent schedule row `SELECT 1 FROM schedules WHERE id = $s FOR UPDATE;` before checking count, or run in `SERIALIZABLE` isolation with serialization-failure (`SQLSTATE 40001`) retry loop. |
| **Retriable API / Webhook mutation** | Insert into `idempotency_keys (tenant_id, key, request_hash, status, response_body)` with `UNIQUE (tenant_id, key)` inside the **same** transaction as the domain write. |
| **Competing background workers** | `SELECT id, payload FROM outbox_events WHERE published_at IS NULL AND next_attempt_at <= now() ORDER BY next_attempt_at, id LIMIT 32 FOR UPDATE SKIP LOCKED;` |

### 2.2 Transactional Outbox Schema (Zero Lost Events Without 2PC)

```sql
CREATE TABLE outbox_events (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aggregate_type  TEXT        NOT NULL,
    aggregate_id    TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    trace_context   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at    TIMESTAMPTZ
);

-- Tiny partial index: only unpublished rows occupy index pages!
CREATE INDEX idx_outbox_unpublished
ON outbox_events (next_attempt_at, id)
WHERE published_at IS NULL;
```

* Downstream consumers **must** deduplicate on `outbox_events.id` (`at-least-once`
  delivery + idempotent consumer = effectively-once outcome).

---

## 3. Plain-File Databases, Production `SQLite` & Firmware Storage

### 3.0 Plain OS Files as a Crash-Safe Database (`0` Supply-Chain Dependencies)

When single-host availability suffices and the hot index fits in RAM (`10^3–10^6`
records load in `5–80 ms`), plain files eliminate SQL/C-parser CVEs, daemon ops, and
version lock-in — **provided you obey four kernel durability rules**:

1. **Atomic Snapshot Replacement (Configs, State Tables, Compacted Indexes):**
   * **Never** `open(path, O_WRONLY | O_TRUNC)` in place (a crash mid-write leaves a
     `0`-byte or half-written file!).
   * Stage `.filename.tmp.<pid>.<nonce>` in the **same directory** as `filename`
     (guarantees same filesystem mount so `rename()` never fails with `EXDEV`),
     `write_all -> fsync(tmp_fd) -> close(tmp_fd) -> rename(tmp, filename) ->
     fsync(parent_dir_fd)`. Readers see 100% old or 100% new bytes with zero locks!
2. **Framed Append-Only Log + In-Memory Index (Events, Ledgers, Queues, WAL):**
   * Append records as `[magic_u16 | schema_ver_u16 | len_u32 | crc32_u32 | seq_u64
     | payload]` (or `JSONL` with per-line checksum/newline check) + `fsync` per
     durability policy.
   * On startup, scan sequentially into an in-memory `HashMap`/`BTreeMap`; if the
     final tail frame has a truncated length or bad `crc32` from a power cut,
     `ftruncate` back to the last valid frame offset! Compact periodically by
     writing an atomic snapshot (Rule 1) and rotating the old log segment.
3. **Content-Addressable & Sharded Directories (Blobs, Artifacts, Partitioned Logs):**
   * Store immutable blobs by cryptographic digest (`objects/ab/<sha256>`) or time
     bucket (`events/2026-11-15/segment-001.zst`): lock-free writes, instant $O(1)$
     retention (`rm -rf events/2025-*`), and `rsync`/`tar` backup simplicity.
4. **Explicit Writer Coordination & Step-Up Boundary:**
   * Enforce single-writer discipline via an advisory lockfile (`flock` / `fcntl` /
     `LockFileEx`) before mutating snapshot/log files. If concurrent multi-writer
     contention or secondary-index disk lookups grow non-trivial, step up cleanly
     to `SQLite WAL` instead of writing a custom page manager!

### 3.1 Production `SQLite` Initialization Contract (CLI, Desktop, Mobile, Single-Node)

Default `SQLite` connection settings optimize for 2004 backwards compatibility (foreign
keys **disabled** by default, `SQLITE_BUSY` thrown after `0 ms` lock wait, rollback
journal blocking readers!). Apply per-connection pragmas on open:

```sql
PRAGMA journal_mode = WAL;          -- Concurrent readers + fast sequential appends
PRAGMA synchronous = NORMAL;        -- Crash-safe in WAL mode (use FULL if RPO=0 across OS power loss)
PRAGMA busy_timeout = 5000;         -- Wait up to 5s on writer lock instead of instant SQLITE_BUSY
PRAGMA foreign_keys = ON;           -- Default is OFF per connection!
PRAGMA temp_store = MEMORY;
PRAGMA cache_size = -32000;         -- 32 MiB page cache (negative = KiB)
```

* **Architecture rule for `SQLite` concurrency:** Open **1 dedicated `MAX_CONNS=1`
  writer pool** and enable `PRAGMA journal_mode = WAL;` on that writer connection
  **before** opening the separate **`N`-connection read-only pool** (`?mode=ro`
  connections cannot switch a database into WAL mode or initialize missing
  `-wal`/`-shm` files; apply `busy_timeout`, `foreign_keys`, `temp_store`, and
  `cache_size` on every connection). Start write transactions with **`BEGIN
  IMMEDIATE`** so the write lock is acquired upfront instead of failing
  mid-transaction with `SQLITE_BUSY_SNAPSHOT`, and declare new tables as **`CREATE
  TABLE ... (...) STRICT;`** so string `'abc'` cannot silently insert into an
  `INTEGER` column!

### 3.2 Embedded / Firmware Non-Volatile Storage (`Flash` / `EEPROM` / `FRAM`)

Never `memcpy(&config_struct, flash_addr, sizeof(config_struct))` directly:
compiler padding changes, struct field additions across OTA updates, or a brownout
mid-erase silently corrupts device state!

1. **Framed, Versioned, Self-Checking Records:**
   * Header: `[magic_u16 | schema_ver_u16 | payload_len_u16 | seq_u32 | payload... | crc32_u32]`.
   * On firmware upgrade (`v1 -> v2`), read `schema_ver == 1`, migrate fields
     explicitly in RAM with safe defaults, and write `schema_ver = 2`.
2. **Power-Cut Atomicity (Zero Torn Writes):**
   * Use **ping-pong dual sectors (`Slot A` / `Slot B`)** or an append-only
     wear-leveled KV/filesystem (`LittleFS`, Zephyr `NVS`): write new record +
     `crc32` to the inactive slot **before** incrementing `seq_u32`; on boot, select
     the highest-`seq` slot whose `crc32` validates!
3. **Endurance Arithmetic in Storage Specifications:**
   * Always compute:
     $$\text{Lifetime Writes} = \frac{\text{Physical Sectors} \times \text{Erase Endurance}}{\text{Write Amplification}} \ge \text{Writes/Day} \times 365 \times \text{Target Years} \times 3\times\text{safety}$$
   * If frequent counters exceed NOR flash endurance, move hot counters to `FRAM` /
     `.noinit` battery-backed SRAM or flush dirty deltas only on clean shutdown /
     coarse intervals.
