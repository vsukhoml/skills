# MySQL / MariaDB hardening

## Attack primer

- **Anonymous users, the `test` DB and remote root** were installed by default for
  decades. `mysql_secure_installation`, or the SQL below, removes them.
- **`FILE` privilege plus a permissive `secure_file_priv`** allows
  `SELECT ... INTO OUTFILE` (webshell drop) and `LOAD_FILE('/etc/...')`.
  `LOCAL INFILE` lets a malicious or impersonated *server* request arbitrary
  files from connecting *clients* (the "rogue MySQL server" attack). Disable it
  server-side, and in client libraries.
- **MySQL 8's X Protocol listens separately on 33060** with its own bind
  setting. It is a frequently forgotten second port.
- Public 3306 with weak passwords means constant brute force.

## my.cnf (`[mysqld]`, relevant lines)

Works for both MySQL and MariaDB. An unknown option aborts `mysqld`/`mariadbd`
at startup, so options that exist in only one of them use the **`loose-`**
prefix, which both servers silently ignore when they don't know the option.

```ini
[mysqld]
# or a private IP; never 0.0.0.0 on a public host
bind-address = 127.0.0.1
# MySQL 8+ X Protocol (33060) has its own bind; MariaDB has no X Protocol, hence loose-
loose-mysqlx-bind-address = 127.0.0.1
local_infile = 0
# A dedicated dir that MUST exist (startup aborts otherwise); NULL disables import/export
# entirely; "" means anywhere (never).
secure_file_priv = /var/lib/mysql-files
# Rejects every non-TLS TCP connection, including to 127.0.0.1; only the unix socket (and
# Windows shared memory) are exempt. Local apps on TCP need TLS, or use the socket.
require_secure_transport = ON
tls_version = TLSv1.2,TLSv1.3
# grants by IP; avoids DNS-based spoofing and latency
skip_name_resolve = ON
max_connect_errors = 100
# MySQL-only option, hence loose-
loose-log_error_verbosity = 3
# MySQL 8.4: mysql_native_password disabled by default; removed in 9.0. Migrate to caching_sha2_password.
```

## Accounts

```sql
-- Use account-management statements, never DML on mysql.user (it is a VIEW on MariaDB >= 10.4).
SELECT user, host FROM mysql.user WHERE user = '' OR (user = 'root' AND host NOT IN ('localhost','127.0.0.1','::1'));
DROP USER IF EXISTS ''@'localhost', ''@'%';          -- anonymous users (repeat for each host listed above)
DROP USER IF EXISTS 'root'@'%';                      -- remote root (repeat for each host listed above)
DROP DATABASE IF EXISTS test;
-- application user: scoped by host and database, TLS required
CREATE USER 'app'@'10.0.0.%' IDENTIFIED BY '<generated>' REQUIRE SSL;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.* TO 'app'@'10.0.0.%';
-- migrations get DDL on app.* only, as a separate account
```

- MariaDB ≥ 10.4: `root@localhost` uses `unix_socket` auth by default. Keep it.
  That means no root password to steal.
- Never give apps `ALL ON *.*`, `FILE`, `SUPER`, `PROCESS`, `SHUTDOWN`,
  `GRANT OPTION`, or `CREATE USER`.

## Audit queries

```sql
SELECT user, host, plugin FROM mysql.user;
SELECT grantee, privilege_type FROM information_schema.user_privileges
 WHERE privilege_type IN ('FILE','SUPER','PROCESS','SHUTDOWN','CREATE USER','GRANT OPTION');
SHOW VARIABLES WHERE Variable_name IN ('bind_address','mysqlx_bind_address','local_infile','secure_file_priv','require_secure_transport','have_ssl');
```

## Docker image traps

- `MYSQL_ALLOW_EMPTY_PASSWORD` and `MYSQL_RANDOM_ROOT_PASSWORD` (or the MariaDB
  equivalents) with published ports.
- Use `MYSQL_ROOT_PASSWORD_FILE` / `MARIADB_ROOT_PASSWORD_FILE` with secrets.
- Put no `ports:` on the DB service and use an internal network
  (`harden-docker` §4).
