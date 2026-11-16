---
name: data-modeling
description: >-
  Data modeling and minimal storage selection (plain files, SQLite/DuckDB,
  PostgreSQL/ClickHouse, MCU flash), indexing, concurrency, and zero-downtime
  schema evolution; challenges unnecessary databases and entities. Use when
  choosing persistence, designing file or database schemas, writing
  migrations, or tuning queries.
last_updated: 2026-11-15
---

# First-Principles Data Modeling, Storage & Schema Evolution (`data-modeling`)

Code can be rolled back in seconds; **corrupted data, locked production tables,
and unindexed multi-terabyte schemas cannot.** Design every persistent structure
from **access patterns, physical page/flash geometry, concurrency invariants, and
online-evolution constraints** — across server databases, local-first desktop/
mobile stores, analytical/telemetry lakes, and constrained MCU flash.

* Consult [references/storage-engines-and-indexing.md](references/storage-engines-and-indexing.md)
  for the storage-engine selection matrix, `UUIDv7` vs. `UUIDv4` B-tree physics,
  `ESR` composite/partial/covering index geometry, and `EXPLAIN ANALYZE` checks.
* Consult [references/migrations-concurrency-and-embedded.md](references/migrations-concurrency-and-embedded.md)
  for zero-downtime `Expand -> Backfill -> Contract` DDL playbooks, isolation &
  Transactional Outbox patterns, production `SQLite` settings, and power-fail-safe
  embedded Flash/NVS layouts.

---

## 1. Challenge the Database Assumption (The Storage Escalation Ladder)

Every external daemon or third-party storage library adds **supply-chain attack
surface, operational cost, failure modes, and upgrade toil**. Everything that can
be avoided **must** be avoided — derive storage strictly from quantitative
requirements for **Consistency, Performance, Scalability, and Availability**,
starting at **Rung 0** and climbing *only* when a lower rung is disqualified:

| Rung | Mechanism | Supply-Chain & Ops Cost | Stay Here Whenever... |
| --- | --- | --- | --- |
| **0. Ephemeral / Derived in RAM** | Recompute from inputs/git/config on boot | **`0` deps · `0` state** | State rebuilds in `< 50–200 ms` or needs no cross-restart durability. |
| **1. Plain OS Files + Atomic FS Primitives** | Atomic temp-`fsync`-`rename` snapshots, framed `CRC32`/`JSONL` append logs + RAM index, or content-addressed `ab/<sha256>` directories | **`0` 3rd-party deps · `0` daemons** *(strongest supply-chain posture!)* | Single-host availability suffices, working set fits in RAM (`<=` hundreds of MiB) or key-addressed blobs, and writes are single-process or low-rate (`flock`). |
| **2. In-Process Embedded Engine** | `SQLite` (`WAL` + `STRICT`), `DuckDB`, `LMDB`/`redb`, `LittleFS`/NVS | **`0` daemons · `1` vetted library** | Single-host/client app needs multi-index queries, larger-than-RAM B-trees, or multi-process ACID concurrency without running a server. |
| **3. Single Networked ACID Store / Object Lake** | `PostgreSQL` / `MySQL` or object storage + `Parquet` | **`1` managed/operated service** | Multi-host stateless scaling, cross-machine High Availability (`RTO`), or concurrent remote writers disqualify single-node files/`SQLite`. |
| **4. Specialized Secondary Engines** | `ClickHouse`, `Valkey`/`Redis`, `Kafka` | **Multi-system sync & ops tax** | Measured `p99` latency or `10^8+`-row scan volume disqualifies Rungs 1–3 (`SKIP LOCKED`, `JSONB`, partitions). |

* **Plain-file durability rule (never write naive `O_TRUNC` in place!):** When
  Rung 1 fits, get real crash atomicity from the OS kernel: stage `.tmp.<pid>` in
  the **same directory**, `write -> fsync(tmp_fd) -> rename -> fsync(parent_dir)`,
  and frame append-only logs with `(length, crc32)` so torn power-loss tails
  truncate cleanly on boot (see [references/migrations-concurrency-and-embedded.md](references/migrations-concurrency-and-embedded.md)).

---

## 2. Entity Minimalism & Canonical Exact Types (Schema Poka-Yoke)

Make illegal domain states unrepresentable (`CHECK`, `FOREIGN KEY`, `NOT NULL`,
`UNIQUE`, or typed file schemas) while keeping entity count minimal:

1. **Earn every entity, table & column (Zero speculative modeling):**
   * Introduce a new entity/table **only** when it represents a distinct domain
     lifecycle, `1:N` / `M:N` cardinality, concurrency lock boundary, or
     security/retention scope. Reject `1:1` speculative split tables, generic
     `Entity-Attribute-Value (EAV)` meta-tables, and "future-proof" unused columns.
   * Give every mutable fact **one authoritative home** (`3NF`/`BCNF`); add
     denormalized summaries/caches *only* for proven read budgets with an explicit
     rebuild/sync invariant.
2. **B-Tree-Friendly Identity (`BIGINT` / `UUIDv7` Over `UUIDv4`):**
   * Random `UUIDv4` primary keys scatter inserts across every page of a B-tree,
     causing `50%-full` page splits, `2–3x` index bloat, and severe disk/WAL write
     amplification once tables exceed RAM!
   * Use **`BIGINT GENERATED ALWAYS AS IDENTITY`** or **time-ordered `128-bit`
     `UUIDv7` / `ULID`** so new rows append monotonically to rightmost B-tree
     pages. (If hiding sequential volume externally, pair internal `BIGINT` PKs
     with an indexed public `UUIDv7` / prefixed token `ord_01J...`.)
3. **Canonical, Locale-Neutral Column Types:**
   * **Money & exact quantities:** Store integer minor units (`BIGINT` cents/micros)
     or exact fixed-point `NUMERIC(p, s)` **plus an explicit `ISO-4217` currency
     column** — **never** IEEE-754 `FLOAT` / `REAL` / `DOUBLE PRECISION`!
   * **Timestamps:** Store **UTC instants** (`TIMESTAMPTZ` / `INT64` Unix epoch
     ticks) plus a separate IANA timezone column (`America/Los_Angeles`) whenever
     wall-clock calendar rules (billing cycles, schedules) matter.
   * **Text & identifiers:** Enforce valid `UTF-8`, normalize identifiers (`NFC` /
     `NFKC` + casefolding where case-insensitive uniqueness applies), default
     columns to `NOT NULL`, and attach `CHECK (octet_length(...) <= max)` bounds.
   * **Semi-structured `JSONB`:** Reserve for sparse/extensible metadata; promote
     any field used in `JOIN`, `FOREIGN KEY`, or hot `WHERE` predicates to a typed
     column (or generated/expression-indexed column).
4. **Immutable Ledgers & Honest Deletion:**
   * **Financial, inventory & audit balances:** Model as **append-only journal
     entries** (`debit`/`credit` or signed delta rows with `idempotency_key`),
     never destructive `UPDATE account SET balance = ...` with no trail!
   * **Avoid reflexive `deleted_at` soft-delete everywhere:** Soft-delete silently
     poisons `SELECT` queries (forgotten `WHERE deleted_at IS NULL` leaks deleted
     data!) and breaks standard `UNIQUE (email)` constraints. Prefer explicit
     domain states (`status = 'archived'`), dedicated history/tombstone tables, or
     — when soft-delete is truly required — **partial unique indexes**
     (`CREATE UNIQUE INDEX ... ON users (email) WHERE deleted_at IS NULL`).

---

## 3. Index Geometry, Pagination & `EXPLAIN ANALYZE` Proof

An unindexed predicate turns a `0.2 ms` lookup at `1,000` rows into a `14 s` full-
table scan at `50,000,000` rows — while unused indexes tax every `INSERT`/`UPDATE`:

1. **Composite Index `ESR` Rule (`Equality -> Sort -> Range`):**
   * Order multi-column B-tree keys strictly as: **(1) exact `=` columns**
     (starting with `tenant_id` in multi-tenant tables!), **(2) `ORDER BY`
     columns** (matching `ASC`/`DESC` direction to eliminate sort passes), and
     **(3) range `<`/`>`/`BETWEEN` column last** (a range predicate stops B-tree
     prefix matching for subsequent columns!).
2. **Covering (`INCLUDE`) & Partial (`WHERE`) Indexes:**
   * Append small read-frequently payload columns via `INCLUDE (...)` to enable
     zero-heap **Index-Only Scans** on hot paths.
   * Scope skewed state queues with **partial indexes** (`WHERE status = 'pending'`)
     so a `99.9%`-completed `100M`-row table keeps a tiny `5 MB` hot index in RAM!
3. **Keyset / Seek Pagination ($O(\log N)$) Over `OFFSET` ($O(N)$):**
   * Ban `OFFSET N` beyond shallow admin pages (`OFFSET 200000` reads and discards
     `200,000` rows on every request and skips/duplicates rows under concurrent
     writes!). Paginate via deterministic tie-breaker cursors:
     `WHERE (created_at, id) < ($last_ts, $last_id) ORDER BY created_at DESC, id DESC LIMIT 50`.
4. **Verify With `EXPLAIN (ANALYZE, BUFFERS)`:**
   * Never ship a critical query without inspecting its actual execution plan and
     buffer reads at realistic (`p95`) row counts and data skew; eliminate ORM/loop
     **N+1 queries** via batch `= ANY($ids)` or explicit joins.

---

## 4. Concurrency, Isolation, Deadlocks & Transactional Outbox

1. **Prevent Lost Updates & Write Skew Explicitly:**
   * Never read a row into app memory, compute `new_val = old_val - 1`, and write
     it back under default `READ COMMITTED`! Use **atomic conditional `UPDATE`**
     (`SET stock = stock - $n WHERE id = $id AND stock >= $n`), **optimistic
     version CAS** (`WHERE id = $id AND version = $v`), **`SELECT ... FOR UPDATE`**
     (`SKIP LOCKED` for worker queues), or **`SERIALIZABLE`** with bounded retry.
   * Guard every retriable client/webhook mutation with a `UNIQUE (tenant_id,
     idempotency_key)` constraint persisted in the **same transaction** as the
     state change.
2. **Keep Transactions Tiny (Zero Network I/O Inside `BEGIN..COMMIT`):**
   * **Never** call an external HTTP API, payment gateway, message broker, or LLM
     while holding an open DB transaction — one slow `5 s` downstream stall
     exhausts the entire DB connection pool!
   * Acquire multi-row locks in **sorted primary-key order** to make cyclic
     deadlocks structurally impossible, and configure connection `statement_timeout`
     and `lock_timeout` on every pool.
3. **Cross-System Atomicity via Transactional Outbox:**
   * Never dual-write (`COMMIT` to DB then `publish()` to queue/bus — crashes in
     between silently drop events!). Insert an `outbox` row inside the **same local
     ACID transaction** and relay asynchronously via `SKIP LOCKED` pollers or WAL/
     CDC tailing into **idempotent** consumers.

---

## 5. Zero-Downtime Schema Evolution (`Expand -> Backfill -> Contract`)

During rolling deploys and rollbacks, **old (`N-1`) and new (`N`) binaries run
concurrently against the same database**, and naive `ALTER TABLE` statements queue
behind active queries behind an `AccessExclusiveLock` — freezing **all** `SELECT`s
and taking down production in seconds!

1. **Mandatory `lock_timeout` + Fast-Fail Retry on Every Online DDL:**
   * Wrap every migration step in a short lock timeout (e.g., `SET lock_timeout =
     '2s'` with bounded backoff retries) so blocked DDL aborts harmlessly instead
     of forming a catastrophic lock queue.
2. **Four-Step Parallel Change for Breaking Edits (Renames, Type Splits, `NOT NULL`):**
   * **Phase 1 — Expand:** Add nullable column/new table; create indexes
     **`CONCURRENTLY`** / online; add `CHECK`/`FOREIGN KEY` constraints as **`NOT
     VALID`** first, then `VALIDATE CONSTRAINT` in a non-blocking scan!
   * **Phase 2 — Dual-Write & Throttled Batch Backfill:** Deploy code writing both
     old and new shapes; backfill historical rows in small key-ranged batches
     (`1,000–10,000` rows per tx with replication/vacuum lag pacing — never one
     `50M`-row `UPDATE`!).
   * **Phase 3 — Cut Over Reads:** Verify parity, switch reads to the new schema,
     and enforce `NOT NULL` once zero nulls remain and `N-1` writers are gone.
   * **Phase 4 — Contract:** Remove old dual-write code first; drop the obsolete
     column/table in a **subsequent** release so instant binary rollback stays safe!

---

## 6. Lifecycle Retention, Partitioning, Embedded Stores & Tested Backups

* **Drop partitions, don't `DELETE` millions of rows:** Partition high-volume
  append tables (events, audit logs, telemetry) by time (`daily`/`monthly`) so
  expiring old data is an instant $O(1)$ `DETACH / DROP PARTITION` rather than a
  WAL-saturating `DELETE` + `VACUUM` storm. Keep raw PII out of immutable/append
  partitions (or encrypt per-subject for crypto-shredding).
* **Client `SQLite` & Firmware Flash/NVS discipline:** Enable `WAL` + `busy_timeout`
  + `foreign_keys = ON` + `STRICT` tables + single serialized writer on `SQLite`;
  on embedded MCUs, never write unversioned raw C `struct` bytes to Flash/EEPROM —
  prefix every record with `(magic, schema_version, length, payload, crc32)` over
  power-loss-atomic dual-sector/journaled storage (`LittleFS`/NVS).
* **Untested backups do not exist:** Automate periodic backup restoration + WAL/
  binlog Point-In-Time Recovery (`PITR`) into an isolated environment and assert
  row/checksum integrity against target `RPO` and `RTO`.

---

## Before You Finish (`data-modeling` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| `FLOAT` / `DOUBLE` column storing money, prices, tax rates, or ledger balances | Use integer minor units (`BIGINT`) or `NUMERIC(p, s)` + `ISO-4217` currency |
| Random `UUIDv4` primary key on high-insert B-tree table | Switch to `BIGINT` identity or k-sortable `UUIDv7` / `ULID` |
| `ALTER TABLE` / `CREATE INDEX` run in prod without `lock_timeout` or `CONCURRENTLY` | Set `lock_timeout = '2s'`, use `CONCURRENTLY` & `NOT VALID -> VALIDATE`, split Expand/Contract |
| Column renamed or dropped in the same deploy that updates application code | Split into Expand -> Dual-write/Backfill -> Cutover -> Contract across deploys |
| `OFFSET 50000 LIMIT 50` pagination or N+1 query inside a `for` loop | Replace with keyset `(sort_col, id) < ($1, $2)` cursor and batch `= ANY($ids)` |
| Outbound HTTP / queue / LLM call executed inside an open DB transaction | Move external I/O outside tx; use idempotency keys + Transactional Outbox |
| Million-row nightly `DELETE FROM events WHERE created_at < ...` | Range-partition by time and `DROP / DETACH PARTITION` in $O(1)$ |
| `SQLite` opened with default rollback journal, `busy_timeout = 0`, or `FK = OFF` | Set `journal_mode = WAL`, `busy_timeout = 5000`, `foreign_keys = ON`, `STRICT` |
| Raw C `struct` dumped to MCU Flash/EEPROM without version header or CRC | Add `(schema_version, length, crc32)` framing + power-fail atomic sector swap |
