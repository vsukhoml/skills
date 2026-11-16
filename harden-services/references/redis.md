# Redis / Valkey hardening

Valkey is the BSD-licensed Linux Foundation fork. It is config- and ACL-compatible,
and everything below applies to both.

## Why each control exists (attack primer)

An attacker who can send commands to Redis, unauthenticated or as an over-privileged
user, can do all of the following:

- **Write files as the redis user.** `CONFIG SET dir /var/spool/cron/crontabs`, then
  `CONFIG SET dbfilename root`, then `SAVE`. Variants drop SSH keys or webshells.
- **Load native code.** `REPLICAOF <attacker> 6379` pushes a malicious module as the
  RDB, then `MODULE LOAD` runs it.
- **Escape the Lua sandbox.** CVE-2022-0543 hit Debian/Ubuntu packages.
  **CVE-2025-49844 "RediShell"** (Oct 2025) is a use-after-free in the Lua parser:
  *authenticated* RCE, CVSS 10, fixed in 8.2.2 / 8.0.4 / 7.4.6 / 7.2.11 / 6.2.20.
- **Wipe or ransom data.** `FLUSHALL`, then leave a ransom note key.

Bots scan 6379 continuously. A Redis published without auth is found within minutes.

**Docker trap.** The official `redis` image is *compiled with protected-mode
disabled*, because "ports are not exposed unless -p". So `-p 6379:6379` with no
config means an unauthenticated Redis on the internet. Redis' own protected-mode
safety net does not apply in the official image unless you set it in a config file.

## Configuration

`redis.conf` (host install: `/etc/redis/redis.conf`; container: mount it and run
`redis-server /path/redis.conf`):

```conf
# --- Network exposure
# Host install: loopback only ("-" = don't fail if ::1 is unavailable).
bind 127.0.0.1 -::1
# In a container on an internal compose network, listen on the container interface instead
# and rely on the network + ACLs:
#bind * -::*
protected-mode yes
port 6379
# Same-host clients only? Prefer a unix socket and no TCP at all:
#port 0
#unixsocket /run/redis/redis.sock
#unixsocketperm 770
# Cross-host traffic: TLS (and keep the plaintext port off)
#port 0
#tls-port 6379
#tls-cert-file /etc/redis/tls/redis.crt
#tls-key-file /etc/redis/tls/redis.key
#tls-ca-cert-file /etc/redis/tls/ca.crt
#tls-auth-clients optional

# --- Dangerous runtime capabilities: off for every connection (immutable at runtime)
enable-protected-configs no
enable-debug-command no
enable-module-command no

# --- Authentication & authorization: ACL file (replaces requirepass/rename-command)
aclfile /usr/local/etc/redis/users.acl

# --- Resource limits (DoS containment + predictable memory on small hosts)
maxmemory 256mb
# cache: allkeys-lru | data store: noeviction (writes fail instead of silently dropping data)
maxmemory-policy allkeys-lru
maxclients 1000
timeout 300

# --- Persistence: keep files private to the redis user
dir /data
```

`users.acl`. Passwords are stored as SHA-256 (`#<hex>`), never in plaintext.
Generate a hash with `printf '%s' "$PW" | sha256sum | cut -d' ' -f1`:

```acl
# Disable the passwordless, all-powerful default user.
user default off
# Application: own key/channel namespace, no admin/dangerous commands, no Lua.
# Drop "-@scripting" ONLY if the client library needs Lua (BullMQ, Sidekiq, many rate
# limiters use EVALSHA) — then patching for CVE-2025-49844 is mandatory.
# If the app doesn't prefix keys, use ~* instead of ~app:* (but keep the command limits).
user app on #<sha256-hex-of-app-password> ~app:* &app:* +@all -@dangerous -@admin -@scripting
# Operator: full access, used interactively only, ideally only over a unix socket/SSH tunnel.
user admin on #<sha256-hex-of-admin-password> ~* &* +@all
# Replica (if replicating): only what replication needs.
#user replica on #<sha256-hex> +psync +replconf +ping
```

- `-@dangerous` removes FLUSHALL, FLUSHDB, KEYS, CONFIG, DEBUG, MODULE, REPLICAOF,
  MIGRATE, SHUTDOWN, CLIENT KILL and more. `-@admin` overlaps it and is stated
  for clarity.
- Health checks: `redis-cli` reads the password from `REDISCLI_AUTH`. Never put it
  in argv, where `ps` can see it: `REDISCLI_AUTH=... redis-cli --user app ping`.
- Apply ACL changes with `ACL LOAD` (as admin). Inspect with `ACL LIST`, and
  `ACL LOG` shows denied commands, which is great for tuning.

## Verification

```sh
# from outside the host / from another container on a non-backend network: must fail to connect
redis-cli -h <public-ip> -p 6379 ping
# default user disabled
redis-cli -h 127.0.0.1 ping                        # → NOAUTH / -NOPERM / auth required
# app user cannot reconfigure or wipe
REDISCLI_AUTH=$APP_PW redis-cli --user app CONFIG GET dir     # → NOPERM
REDISCLI_AUTH=$APP_PW redis-cli --user app FLUSHALL           # → NOPERM
REDISCLI_AUTH=$APP_PW redis-cli --user app SET app:x 1        # → OK
REDISCLI_AUTH=$APP_PW redis-cli --user app SET other 1        # → NOPERM (key pattern)
REDISCLI_AUTH=$ADMIN_PW redis-cli --user admin CONFIG GET protected-mode   # → yes
redis-server --version                                         # ≥ the RediShell fix for your branch
```

## Operations

- **Bundled modules (Redis 8 official image).** `MODULE LIST` shows search
  (RediSearch), ReJSON, timeseries, bf (bloom) and vectorset loaded at startup,
  even with your own config and `enable-module-command no`. That setting only
  blocks *runtime* `MODULE LOAD`. If you don't use them, they are pure extra
  attack surface. Use an image or build without them (Valkey's image, or a
  distro package), and check with `MODULE LIST` as admin.
- Redis logs a warning unless `vm.overcommit_memory = 1`. Set it on dedicated
  Redis hosts so background saves don't fail. On shared hosts, weigh it against
  the OOM behavior you want.
- Patch promptly: Redis and Valkey ship security releases per branch.
  Subscribe to their advisories.
- Backups: RDB/AOF files contain all data. Encrypt them off-host. `dir` must
  not be world-readable.
- Sentinel and Cluster have their own ports (26379, 16379 bus). Apply the same
  rules: ACLs (`sentinel auth-user` / `masteruser`), a private network, TLS.
