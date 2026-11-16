# MongoDB hardening

## Attack primer

- **No auth plus a reachable 27017 means the data is gone.** Automated ransom and
  wipe campaigns have hit open MongoDBs continuously since 2017.
- **MongoBleed, CVE-2025-14847 (Dec 2025).** A *pre-authentication* heap memory
  disclosure through zlib-compressed wire messages. It is in CISA KEV and is
  actively exploited.
  - Fixed in 8.2.3, 8.0.17, 7.0.28, 6.0.27, 5.0.32 and 4.4.30.
  - End-of-life branches (4.2, 4.0, 3.6) are not fixed. Upgrade off them.

  The lesson generalizes: **authentication does not protect you from pre-auth
  bugs. Network exposure does.**
- Server-side JavaScript (`$where`, `mapReduce`, `$function`, `$accumulator`)
  widens the injection blast radius.

**Docker trap (verified in `docker-library/mongo` `docker-entrypoint.sh`).** The
official image adds `--bind_ip_all` unless you pass a bind option. It enables
`--auth` **only** when *both* `MONGO_INITDB_ROOT_USERNAME` and
`MONGO_INITDB_ROOT_PASSWORD` (or their `_FILE` variants) are set. A plain
`docker run -p 27017:27017 mongo` is an unauthenticated database on every
interface.

## mongod.conf (relevant sections)

```yaml
net:
  port: 27017
  bindIp: 127.0.0.1            # add a private IP only for remote clients: 127.0.0.1,10.0.0.5 — never 0.0.0.0 on a public host
  # MongoBleed interim mitigation and good hygiene: no zlib on the wire
  compression:
    compressors: snappy,zstd
  tls:
    mode: requireTLS           # for any non-loopback client
    certificateKeyFile: /etc/mongodb/tls/server.pem
    CAFile: /etc/mongodb/tls/ca.pem
    disabledProtocols: TLS1_0,TLS1_1
    # allowConnectionsWithoutCertificates: true   # if clients authenticate with SCRAM, not x509
security:
  authorization: enabled
  javascriptEnabled: false     # disables $where, mapReduce JS, $function, $accumulator
  # Replica sets/sharding: internal member auth
  # keyFile: /etc/mongodb/keyfile          # 600, owned by mongodb; or clusterAuthMode: x509
setParameter:
  # Uncomment only AFTER the first admin user exists (bootstrap step 5); with it set from the
  # start, nobody can create that first user.
  # enableLocalhostAuthBypass: false
  authenticationMechanisms: SCRAM-SHA-256  # add MONGODB-X509 if using certificate auth
```

## Bootstrap order (users)

1. Start with `authorization: enabled`. The localhost exception allows creating
   the *first* user, from 127.0.0.1 only.
2. Create an admin in `admin`:
   `db.createUser({user:"admin", pwd: passwordPrompt(), roles:["root"]})`.
   Keep it for break-glass use. Note that `userAdminAnyDatabase` is
   *effectively root*: it can grant itself any role. For daily operations,
   use genuinely narrow roles (`clusterMonitor`, `readAnyDatabase`, `backup`).
3. Create one user per application, scoped to its database:
   `use app; db.createUser({user:"app", pwd: passwordPrompt(), roles:[{role:"readWrite", db:"app"}]})`.
   No `dbAdmin`, `clusterAdmin` or `root` for apps.
4. Create a backup user with the `backup` role. Use `clusterMonitor` for
   exporters.
5. Uncomment `enableLocalhostAuthBypass: false`, then restart.

In Docker, use `MONGO_INITDB_ROOT_USERNAME_FILE` and
`MONGO_INITDB_ROOT_PASSWORD_FILE` with compose secrets. Put app-user creation in
`/docker-entrypoint-initdb.d/*.js`. Those scripts run only on an empty data
directory. Add `--bind_ip_all` deliberately and only on an internal network
with no published ports.

## Verification

```sh
mongosh --quiet --eval 'db.adminCommand({getCmdLineOpts:1}).parsed' | grep -E 'bindIp|authorization|javascriptEnabled|compressors'
mongosh --quiet --eval 'db.runCommand({connectionStatus:1})'          # unauthenticated: no roles
mongosh "mongodb://<public-ip>:27017" --eval 'db.adminCommand({listDatabases:1})'   # from outside: must not connect at all
mongod --version                                                       # >= the MongoBleed fix for your branch
```

## Operations

- **Auditing:** `auditLog` is in Enterprise and Percona Server for MongoDB. In
  Community, at least log authentication events (`systemLog.verbosity` is
  coarse) and ship the logs off-host.
- **Backups:** `mongodump` or filesystem snapshots, encrypted and off-host.
  Test restores.
- Field-level or Queryable Encryption for highly sensitive fields, when the
  threat includes DB admins or backups.
