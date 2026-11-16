# PostgreSQL hardening

## Attack primer

- **Superuser equals OS command execution** as the `postgres` OS user, via
  `COPY ... FROM PROGRAM`, untrusted languages (`plpython3u`), `lo_export`, or
  `ALTER SYSTEM` plus `archive_command`. Members of `pg_execute_server_program`
  (PG ≥ 11) get the same.
- **`trust` lines in pg_hba.conf** mean no password at all. They show up in copied
  tutorials and in `POSTGRES_HOST_AUTH_METHOD=trust`.
- **Weak passwords on a public 5432.** Botnets brute-force `postgres` constantly,
  then use `COPY FROM PROGRAM` to drop miners.

## postgresql.conf (relevant lines)

```conf
listen_addresses = 'localhost'          # add a private IP only if remote clients exist: 'localhost,10.0.0.5'
port = 5432
password_encryption = scram-sha-256     # default since PG14; MD5 password auth is deprecated as of PG18
ssl = on                                # required for any non-loopback client
ssl_cert_file = '/etc/postgresql/tls/server.crt'
ssl_key_file  = '/etc/postgresql/tls/server.key'
ssl_min_protocol_version = 'TLSv1.2'    # TLSv1.3 if all clients support it
log_connections = on                    # PG18 also accepts a list, e.g. 'authentication,authorization'
log_disconnections = on
log_line_prefix = '%m [%p] %q%u@%d %h '
log_statement = 'ddl'                   # schema changes are audit-relevant; 'all' is costly and logs secrets
allow_alter_system = off                # PG17+: config changes only via files/config management
idle_session_timeout = '1h'             # PG14+
#shared_preload_libraries = 'pgaudit'   # when an audit trail is a requirement
```

## pg_hba.conf: first matching line wins, so order matters

```conf
# TYPE   DATABASE   USER          ADDRESS          METHOD
local    all        postgres                       peer
local    all        all                            scram-sha-256
hostssl  app        app_rw        10.0.0.0/24      scram-sha-256
hostssl  app        app_migrator  10.0.0.10/32     scram-sha-256
host     all        all           127.0.0.1/32     scram-sha-256
host     all        all           ::1/128          scram-sha-256
# everything else, explicitly:
host     all        all           0.0.0.0/0        reject
host     all        all           ::/0             reject
```

- `hostssl` refuses non-TLS connections for that rule. Add `clientcert=verify-full`
  for mTLS.
- No `trust` anywhere. `peer` (OS-user mapping) is fine for local admin.
- **Docker image trap (verified on `postgres:18-alpine`).** The generated
  `pg_hba.conf` **trusts** the local socket and `127.0.0.1`/`::1`, and only the
  final `host all all all` line uses scram-sha-256. Any process inside the
  container, or in a container sharing its network namespace
  (`network_mode: service:db`, sidecars), is superuser with no password. Fix it
  at first init with
  `POSTGRES_INITDB_ARGS="--auth-local=scram-sha-256 --auth-host=scram-sha-256"`.
  With that set, every line is SCRAM, init scripts still run, and the
  `pg_isready` healthcheck still works. For an existing volume, edit
  `$PGDATA/pg_hba.conf`. For full control, mount your own pg_hba.
- Reload with `SELECT pg_reload_conf();`. Inspect with
  `SELECT * FROM pg_hba_file_rules;`, where errors show up in the `error` column.

## Roles: owner vs runtime separation

The runtime app role must not own the schema. Otherwise SQL injection can
`DROP TABLE` or `ALTER` anything.

```sql
-- as superuser; set passwords with psql's \password (keeps them out of logs/history)
REVOKE ALL ON DATABASE app FROM PUBLIC;
\c app
REVOKE CREATE ON SCHEMA public FROM PUBLIC;          -- default since PG15; explicit for older
CREATE ROLE app_owner NOLOGIN;
CREATE SCHEMA app AUTHORIZATION app_owner;
CREATE ROLE app_migrator LOGIN IN ROLE app_owner;    -- runs migrations (DDL)
-- Migrator sessions act AS app_owner, so the tables they create are owned by app_owner and the
-- ALTER DEFAULT PRIVILEGES below apply. (Otherwise new tables belong to app_migrator, app_rw
-- gets "permission denied", and someone "fixes" it by over-granting.)
ALTER ROLE app_migrator SET role = 'app_owner';
CREATE ROLE app_rw LOGIN CONNECTION LIMIT 50;        -- runtime: DML only
GRANT CONNECT ON DATABASE app TO app_rw;
GRANT USAGE ON SCHEMA app TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA app GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO app_rw;
ALTER ROLE app_rw SET search_path = app;
ALTER ROLE app_rw SET statement_timeout = '30s';
\password app_migrator
\password app_rw
```

Docker init script (`/docker-entrypoint-initdb.d/10-roles.sh`, runs only on an
empty data dir). It reads the password from the secret file via psql's `\set`
backticks, so it never appears in argv:

```sh
#!/bin/sh
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<'SQL'
\set app_pw `cat /run/secrets/db_app_password`
REVOKE ALL ON DATABASE :"DBNAME" FROM PUBLIC;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE ROLE app_owner NOLOGIN;
CREATE SCHEMA app AUTHORIZATION app_owner;
CREATE ROLE app_rw LOGIN PASSWORD :'app_pw' CONNECTION LIMIT 50;
GRANT CONNECT ON DATABASE :"DBNAME" TO app_rw;
GRANT USAGE ON SCHEMA app TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA app GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_rw;
ALTER DEFAULT PRIVILEGES FOR ROLE app_owner IN SCHEMA app GRANT USAGE, SELECT ON SEQUENCES TO app_rw;
ALTER ROLE app_rw SET search_path = app;
ALTER ROLE app_rw SET statement_timeout = '30s';
SQL
```

Never grant to app roles:

- `SUPERUSER`, `CREATEROLE`, `CREATEDB`, `REPLICATION`, `BYPASSRLS`
- `pg_execute_server_program`, `pg_read_server_files`, `pg_write_server_files`
- ownership of app tables
- untrusted languages

## Audit queries

```sql
SHOW listen_addresses; SHOW ssl; SHOW password_encryption;
SELECT rolname FROM pg_roles WHERE rolsuper OR rolcreaterole OR rolreplication OR rolbypassrls;
SELECT r.rolname AS member, g.rolname AS role FROM pg_auth_members m
  JOIN pg_roles r ON r.oid = m.member JOIN pg_roles g ON g.oid = m.roleid
  WHERE g.rolname IN ('pg_execute_server_program','pg_read_server_files','pg_write_server_files');
SELECT rolname FROM pg_authid WHERE rolpassword LIKE 'md5%';          -- migrate these to SCRAM
SELECT type, database, user_name, address, auth_method FROM pg_hba_file_rules WHERE auth_method IN ('trust','password','md5');
SELECT lanname FROM pg_language WHERE NOT lanpltrusted AND lanname <> 'c' AND lanname <> 'internal';
```

## Operations

- **Connection poolers:** PgBouncer binds localhost or private, with
  `auth_type = scram-sha-256` and its own TLS settings.
- **Backups:** pgBackRest or WAL-G with encryption at rest and an off-host
  repository. Test restores. `pg_dump` files contain everything, so protect
  them like the database.
- **Patch minor versions promptly.** They are binary-compatible security and
  bug-fix releases. Know your major version's EOL (5 years).
