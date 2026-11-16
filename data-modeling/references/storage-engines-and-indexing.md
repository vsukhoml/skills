# Storage Engine Selection, Physical Layout & Indexing Reference (`data-modeling`)

---

## 1. Purpose-First Storage Selection Matrix (Files Before Databases)

Derive storage from **Consistency, Performance, Scalability, Availability, and
Supply-Chain Cost** — starting at plain OS files and adding database engines only
when a concrete requirement disqualifies simpler rungs:

| Workload & Requirements | Storage Archetype | Representative Examples | Disqualifiers (`When to Step Up`) |
| --- | --- | --- | --- |
| **Configs, state snapshots, CLI/desktop state, small catalogs (`<= 100 MiB`), append logs, immutable blobs** | **Plain OS Files + Kernel Primitives** (`0` 3rd-party deps!) | Atomic `fsync`+`rename` files (`JSON`/binary), framed `CRC32`/`JSONL` append log + RAM index, `ab/<sha256>` blob dirs | Dataset exceeds comfortable RAM index, needs complex ad-hoc secondary-index joins, or faces heavy multi-process/multi-host concurrent writes. |
| **Single-Host Multi-Index Queries, Larger-Than-RAM State, Desktop/Mobile/CLI/Edge ACID** | **Embedded Relational (`WAL`)** (`0` daemons, `1` library) | `SQLite` (`WAL` + `STRICT`) | Multi-host network writers over NFS/SMB (corrupts locks!) or cross-machine HA failover (`RTO < 1 min`) / `> ~10k` concurrent write tx/s. |
| **Multi-Host Stateless Services, High Availability, Concurrent ACID Transactions & Queues (`< 10k jobs/s`)** | **Server Relational OLTP** (row-oriented B-tree + MVCC + WAL) | `PostgreSQL`, `MySQL`/`InnoDB`, distributed SQL (`CockroachDB`, `Spanner` only if multi-region active-active writes are mandatory) | Single-user/single-node tools where a DB daemon is pure ops bloat; or `10^8+`-row wide analytical scans without pre-aggregation. |
| **High-Volume Telemetry, Wide Events, Time-Series, OLAP Aggregations (`10^7–10^11` rows)** | **Columnar / Log-Structured Merge (LSM) / Parquet Lake** | `ClickHouse`, `DuckDB` (in-process/embedded OLAP!), `TimescaleDB`, `Apache Parquet` on object storage | High-frequency single-row point `UPDATE`/`DELETE` mutations or multi-table `SERIALIZABLE` OLTP row locking. |
| **Sub-ms Ephemeral Cache, Rate-Limit Token Buckets, Pub/Sub Lease Locks** | **In-Memory / Embedded KV** | `Valkey`/`Redis`, in-process cache, embedded `LMDB`/`redb`/`RocksDB` | Authoritative source of truth for unrecoverable business/financial records without synchronous durability. |
| **High-Fanout Event Replay, Cross-Service Decoupling (`> 10k msgs/s`)** | **Append-Only Partitioned Log** | `Kafka`, `Redpanda`, `NATS JetStream` *(below `~5k/s`, prefer `PostgreSQL` `FOR UPDATE SKIP LOCKED` queue first!)* | Ad-hoc relational queries or complex secondary-key lookups. |
| **Bare-Metal / RTOS Firmware Config, Calibration & Crash Slots** | **Wear-Leveled Flash FS / NVS KV** | `LittleFS`, Zephyr `NVS` / `FCB`, ESP `NVS`, dual-sector CRC ring | Unwear-leveled fixed-sector FAT12/raw flash rewrites on high-rate telemetry (`destroys flash blocks!`). |

---

## 2. Physical Page Physics: Why `UUIDv7` / `BIGINT` Beats `UUIDv4`

Relational B-trees (`8 KiB` pages in PostgreSQL, `16 KiB` in InnoDB, `4 KiB` in
SQLite) keep rows/entries sorted by key:

* **Random `UUIDv4` (`122` random bits):** Every `INSERT` lands on a uniformly
  random leaf page across the entire index. Once index size exceeds RAM:
  1. Every insert triggers a **random disk read + dirty page write**;
  2. Pages split at `~50–65%` fill factor (`35–50%` wasted space in RAM and disk);
  3. WAL full-page-image (`FPI`) volume explodes after every checkpoint!
* **Sequential `BIGINT` (`8 B`) or `UUIDv7` (`16 B`: `48-bit` ms Unix timestamp +
  randomness):** Inserts always hit the **single rightmost hot leaf page** already
  pinned in L1/buffer cache — achieving **`90%+` page density**, minimal WAL bytes,
  and **`3–10x` higher sustained insert throughput** at scale!

---

## 3. Index Design Patterns & Anti-Patterns

### 3.1 Composite Index Column Order (`Equality -> Sort -> Range`)

Given a critical multi-tenant dashboard query:

```sql
-- Query: latest failed jobs for a tenant in the last 24 hours
SELECT id, job_type, error_code, created_at
FROM jobs
WHERE tenant_id = $1
  AND status = 'failed'
  AND created_at >= $2
ORDER BY created_at DESC, id DESC
LIMIT 50;
```

* **Optimal covering partial index:**
  ```sql
  CREATE INDEX CONCURRENTLY idx_jobs_tenant_failed_recent
  ON jobs (tenant_id, created_at DESC, id DESC)
  INCLUDE (job_type, error_code)
  WHERE status = 'failed';
  ```
  * `tenant_id` (`Equality`) narrows immediately to one tenant;
  * `status = 'failed'` (`Partial WHERE`) shrinks index size by `98%` if `98%` of
    jobs succeed;
  * `(created_at DESC, id DESC)` satisfies both the `>= $2` range **and** `ORDER BY
    ... LIMIT 50` with **zero sort step**, stopping after reading `50` entries;
  * `INCLUDE (job_type, error_code)` satisfies the `SELECT` list via **Index-Only
    Scan** (`0` heap fetches on all-visible pages)!

### 3.2 Classic Index Killers (SARGability Traps)

Wrapping an indexed column in a function or implicit cast disables standard B-tree
lookup unless a matching **expression index** exists:

| Non-SARGable Anti-Pattern (Full Scan!) | Index-Friendly Rewrite |
| --- | --- |
| `WHERE LOWER(email) = LOWER($1)` *(without expression index)* | Create `UNIQUE INDEX ON users (LOWER(email))` or normalize to NFKC-lowercase on write |
| `WHERE DATE(created_at) = '2026-11-15'` | `WHERE created_at >= '2026-11-15T00:00:00Z' AND created_at < '2026-11-16T00:00:00Z'` |
| `WHERE payload->>'external_id' = $1` *(unindexed JSONB)* | Add `CREATE INDEX ON events ((payload->>'external_id'))` or promote `external_id` column |
| `WHERE name LIKE '%billing%'` *(leading wildcard on B-tree)* | Use trigram `GIN` index (`pg_trgm`), full-text `tsvector` / `FTS5`, or prefix `LIKE 'billing%'` |
| Unindexed `FOREIGN KEY` child column (`order_items.order_id`) | **Always index FK columns** — otherwise `DELETE`/`UPDATE` on parent `orders` full-scans `order_items`! |

---

## 4. Reading `EXPLAIN (ANALYZE, BUFFERS)` Like a Systems Engineer

Check four numbers on every critical query plan:

1. **Estimated rows vs. Actual rows:** `rows=1` estimated vs. `actual rows=84,000`
   means stale statistics (`ANALYZE`) or correlated columns causing catastrophic
   nested-loop choices.
2. **`Rows Removed by Filter`:** `actual rows=20` with `Rows Removed by Filter:
   450000` proves the index lacks a selective predicate column — `99.99%` of I/O was
   wasted!
3. **`Buffers: shared hit` vs. `read`:** Even `50,000` cached `shared hit`s (`400
   MiB` of buffer churn!) will collapse into `50,000` disk IOPS under production
   memory pressure. Optimize **buffer count**, not just warm-cache milliseconds!
4. **Sort `external merge Disk`:** Means `Sort` spilled `work_mem` to temp files —
   align index sort order to eliminate the sort node altogether.
