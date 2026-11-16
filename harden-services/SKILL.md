---
name: harden-services
description: >-
  Hardening of network services and data stores: Redis/Valkey, MongoDB,
  PostgreSQL, MySQL/MariaDB, Elasticsearch/OpenSearch, memcached, RabbitMQ,
  Kafka, etcd, ClickHouse, vector databases, Ollama, MinIO,
  Prometheus/Grafana, admin UIs, and nginx/Caddy TLS proxies, including
  default traps of official Docker images. Use when the user configures,
  deploys, or reviews one of these services, or asks about database or cache
  security, exposed DB ports, a ransom note in a database, or TLS and proxy
  headers.
last_updated: 2026-11-15
---

# Service & Data-Store Hardening

Exposed data stores are the most common cause of real VPS breaches, ahead of
SSH. Bots scan 6379, 27017, 5432, 9200 and 6333 around the clock, and they
find a fresh exposure within minutes. The universal rules below apply to
every service. The per-service references hold exact configs and the
attack-specific reasons for them.

**Reference files.** Read only the one(s) you need:

| File | Covers | Verification status |
| --- | --- | --- |
| `references/redis.md` | Redis / Valkey | Runtime-tested with `redis:8-alpine` |
| `references/postgresql.md` | PostgreSQL (+ PgBouncer) | Runtime-tested with `postgres:18-alpine` |
| `references/mongodb.md` | MongoDB | — |
| `references/mysql.md` | MySQL / MariaDB | — |
| `references/others.md` | Elasticsearch, OpenSearch, memcached, etcd, RabbitMQ, Kafka, ClickHouse, Qdrant & vector DBs, Ollama, MinIO, Prometheus/exporters, Grafana, Docker registry, admin UIs, Postfix, DNS, NTP | — |
| `references/web-proxy.md` | nginx, Caddy, TLS, headers, limits, CDN origins | `nginx -t` and `caddy validate` pass |

## Universal rules (apply to every service, in this order)

1. **Does it need to exist on this host?** A managed DB or a separate private
   VM often beats co-locating with the public web tier.
2. **Bind minimal.** A unix socket beats `127.0.0.1` beats a private
   interface. *Never* a public interface. In Docker: no `ports:`, an internal
   network, or `127.0.0.1:` publishing (`harden-docker` §4). Check what is
   actually bound with `ss -tulpn`, not what the config claims.
3. **Authenticate even on loopback and private networks.** SSRF, a
   compromised neighbor container, or a local user all reach "internal"
   services. Disable passwordless default accounts:
   - Redis `default`
   - the MongoDB localhost exception after bootstrap
   - Postgres `trust`
   - ClickHouse `default`
   - RabbitMQ `guest` stays loopback-only
4. **Least-privilege identities.** Use one identity per application, scoped
   to its database, keyspace or index. Separate the migration/owner role from
   the runtime role. Operators use separate admin identities, interactively.
5. **Turn off the features that turn data access into code execution:**
   - Redis `CONFIG`, `MODULE`, `DEBUG` and (where possible) Lua
   - Postgres superuser, `COPY ... PROGRAM` and untrusted languages
   - MySQL `FILE`, `LOCAL INFILE` and a permissive `secure_file_priv`
   - MongoDB server-side JS
   - Elasticsearch/OpenSearch: script types you don't use
6. **TLS on any hop that leaves the host,** including "private" provider
   networks. They are shared infrastructure.
7. **Resource limits.** Max memory, connections, timeouts and query or
   statement timeouts. These contain DoS and runaway apps, and give
   predictable memory on small VPSes.
8. **Patch on the service's own cadence.** Pre-auth bugs (MongoBleed
   CVE-2025-14847, Dec 2025) and authenticated RCEs (Redis RediShell
   CVE-2025-49844, Oct 2025) both happened recently. Rule 2 is what saves you
   from pre-auth bugs. Subscribe to each project's security advisories.
9. **Run as a dedicated user under a sandbox.** Use systemd sandboxing for
   host installs (`harden-host` §6), or the container flags (`harden-docker` §5).
10. **Log authentication and ship it off-host.** Failed-auth spikes against a
    DB are an early warning.
11. **Backups are encrypted, off-host, immutable or append-only, and
    restore-tested.** A backup the host can delete is not a ransomware
    control.
12. **Secrets come from files or a secret store,** never from command lines
    (visible in `ps`), env vars in compose files, or VCS. Rotate on any
    suspicion.

## Official Docker image traps (verified)

| Image | Default behavior | Consequence if a port is published | Fix |
| --- | --- | --- | --- |
| `redis` | Compiled with **protected-mode off**. Default user has no password. Redis 8 auto-loads bundled modules (search, JSON, timeseries, bloom, vectorset). | Unauthenticated Redis on the internet: file write, RCE paths, wipe | Config file with `protected-mode yes`, `user default off`, ACL users. No published port. |
| `mongo` | Adds `--bind_ip_all`. `--auth` **only if both** `MONGO_INITDB_ROOT_USERNAME`/`_PASSWORD` are set. | Unauthenticated MongoDB on every interface | Set both via `_FILE` secrets. No published port. |
| `postgres` | initdb writes **`trust` for the local socket and loopback**. Only the final `host all all all` line is scram-sha-256. `POSTGRES_HOST_AUTH_METHOD=trust` is a copy-paste favorite. | Any process in the container or its netns is superuser without a password. With `trust` + published port: anyone. | `POSTGRES_INITDB_ARGS="--auth-local=scram-sha-256 --auth-host=scram-sha-256"`, `POSTGRES_PASSWORD_FILE` |
| `mysql` / `mariadb` | `*_ALLOW_EMPTY_PASSWORD` / random-root options exist | Empty root password | `*_ROOT_PASSWORD_FILE`. No published port. |
| `qdrant`, `chroma`, `ollama`, `registry`, `memcached` | No auth | Free access, or poisoned images (registry) | See `others.md` |

## Workflow

1. **Inventory.** From `harden-audit`: listeners on service ports, Docker port
   bindings, the outside scan.
2. **Per service,** open the reference file. Compare the effective runtime
   config (not just the file) using the audit queries and commands given there.
3. **Write findings** in the `harden` format. Exposure plus no auth is
   Critical. Exposure with auth is High. Over-privileged app identity is
   Medium to High depending on reachability.
4. **Propose config as drop-ins or mounted files.** Include migration steps
   that don't lose data:
   - Create users before enabling auth.
   - Update app connection strings before closing ports.
   - Keep a maintenance window for restarts.
5. **Verify** with the reference's verification block, from inside *and*
   outside, IPv4 and IPv6.
