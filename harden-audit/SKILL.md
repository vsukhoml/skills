---
name: harden-audit
description: >-
  Read-only security audit and attack-surface inventory of a Linux server,
  VPS, VM, or container host, with a bundled evidence-collector script, an
  outside-in port scan, and light compromise triage. Use before changing a
  live system, when asked "is my server secure", "what is exposed", or "audit
  this box", or when a compromise, cryptominer, or unexplained traffic or CPU
  is suspected.
last_updated: 2026-11-15
---

# Hardening Audit (read-only)

You are collecting **evidence**, not opinions. Every finding you report must
point to command output from the target. This mode never modifies the target:
no package installs, no config edits, no service restarts. If the user wants
fixes, finish the audit report first, then hand off (see the router in `harden`).

## Inputs

- **Target:** the local host, a remote host the user can SSH to (`ssh <alias>`),
  or a collected report file the user pastes or points to.
- **Privilege:** root gives a complete picture. Without it the script still
  runs, but marks the root-only sections incomplete. Say which sections are
  incomplete in the report.
- **Authorization:** only audit and scan hosts the user owns or is explicitly
  authorized to test. External scans of third-party IPs are out of scope.

## Step 1: Collect inside evidence with the bundled script

`scripts/audit.sh` (next to this file) is read-only. It makes no network
connections other than to the local Docker socket and never prints secret
values. Read it before first use on a new kind of host; it is short enough to
review.

```sh
# local
sudo bash <skill-dir>/scripts/audit.sh > audit-$(hostname)-$(date +%F).txt
# remote (sudo needs a TTY for its password prompt)
scp <skill-dir>/scripts/audit.sh HOST:/tmp/harden-audit.sh
ssh -t HOST 'sudo bash /tmp/harden-audit.sh > /tmp/harden-audit.txt; rm /tmp/harden-audit.sh'
scp HOST:/tmp/harden-audit.txt . && ssh HOST 'rm /tmp/harden-audit.txt'
```

Options:

- `--deep` adds package integrity checks (`dpkg --verify` / `rpm -Va`),
  package ownership of SUID and `/usr/local` binaries, and hashes of unmanaged
  executables. It is slow on large hosts. Use it on suspected compromise and
  on first audits of inherited servers.
- `--no-docker` skips container inspection.

The report ends with a **FLAGS SUMMARY** sorted by severity. Flags are
heuristics that point you where to look. Confirm each one against the detailed
section above it, and against intent, before it becomes a finding. For
example, a SUID binary inside a build tree in `/home` is benign, and a Redis
listener on a private interface of a dedicated DB VM may be fine.

If you cannot run the script (no shell, an appliance, BusyBox-only), run the
equivalent commands from the sections below by hand. The script needs bash 4
and GNU tools, which Alpine and OpenWrt lack by default. Those platforms are
exactly where the musl/no-PAM sshhole bypass lived, so run at least this check
there:

```sh
# sshhole (Nov 2026): musl or UsePAM-no sshd < 10.6p2 + password auth on + accounts with hash "*"
ssh -V; ls /lib/ld-musl-*.so.1 2>/dev/null && echo musl
sshd -T | grep -Ei '^(usepam|passwordauthentication|kbdinteractiveauthentication|permitrootlogin|allowgroups|allowusers) '
grep -E '^[^:]+:\*:' /etc/shadow | cut -d: -f1 | sed 's/^/star-hash account: /'
# vulnerable = musl (or usepam no) AND password/kbd auth yes AND OpenSSH < 10.6p2 AND a '*' account can log in
# also check whether the running daemon predates the upgrade (restart needed):
ps -o pid,lstart,args -C sshd 2>/dev/null || ps | grep '[s]shd'
```

## Step 2: Confirm the outside view (the step most audits skip)

The inside view shows what *listens*. Only an outside scan shows what is
*reachable*. Docker DNAT, cloud firewalls and IPv6 make the two diverge. Scan
from a different network than the target, such as a laptop on another
connection or a second VPS:

```sh
nmap -Pn -n -sS -p- --open -T4 --reason <IPv4>      # all TCP ports
nmap -6 -Pn -n -sS -p- --open -T4 --reason <IPv6>   # IPv6 is a separate attack surface
nmap -Pn -n -sU --top-ports 50 --open <IPv4>        # UDP: DNS, NTP, SNMP, memcached, mDNS, 631
nmap -Pn -n -sV -p <open-ports> <IP>                # versions of what is open
```

- Get the target's IPv6 address from `ip -6 addr show scope global`. A host
  with a global IPv6 address and no IPv6 scan is not audited.
- `-sS` needs root on the scanning machine. Use `-sT` otherwise.
- For SSH crypto posture, run `ssh-audit <host>` from outside, or
  `nmap --script ssh2-enum-algos -p <port> <host>`.
- For TLS endpoints, use `testssl.sh <host>:443`, or
  `nmap --script ssl-enum-ciphers -p 443 <host>`.
- Pin these tools to known versions from a trusted source. Security tools are
  prime supply-chain targets (see `harden-supply-chain`).

**Diff inside against outside.** For each externally open port, name the owning
process (from `ss -tulpn` or the Docker DNAT rules) and decide whether it is
intended. For each sensitive inside listener, confirm it is *not* reachable
from outside.

**Docker canary.** On a Docker host, prove the firewall actually filters
published ports. This needs the user's approval because it opens a port
briefly:

```sh
docker run -d --rm --name fw-canary -p 0.0.0.0:18080:80 -p '[::]:18080:80' nginx:alpine
# scan 18080 from outside on IPv4 AND IPv6: it must be filtered unless you intend it open.
# (Without the [::] mapping the IPv6 scan is "filtered" by construction: false assurance.)
docker stop fw-canary
```

## Step 3: Interpret by area

Read each section of the report against the matching skill's baseline:

| Report section | What "bad" looks like | Deep-dive skill |
| --- | --- | --- |
| LISTENING SOCKETS | DB, admin, or API ports on `0.0.0.0` / `[::]`; anything unexpected on a public IP | `harden-services`, `harden-firewall` |
| FIREWALL | No default-drop input for IPv4 *or* IPv6. Legacy and nft rules coexisting. ufw active while Docker publishes. Empty `DOCKER-USER`. | `harden-firewall` |
| SYSCTL | `!!` lines; review informational keys against the workload | `harden-host` |
| SERVICES | Desktop or legacy daemons on a server (avahi, cups, rpcbind, ModemManager); listening `*.socket` units; poor `systemd-analyze security` exposure for internet-facing services | `harden-host` |
| SSH SERVER | Password or kbd-interactive auth, root login, no allow-list, legacy crypto, socket activation surprises | `harden-ssh` |
| USERS | Extra UID 0, empty passwords, NOPASSWD sudo, members of docker/lxd/disk, stale or unknown authorized keys | `harden-host`, `harden-ssh` |
| PERSISTENCE | Unknown cron, systemd units, `ld.so.preload`, `pam_exec`, `rc.local` | Step 4 below |
| FILESYSTEMS | `/tmp` and `/dev/shm` without nosuid/nodev/noexec; world-writable paths; unexpected SUID | `harden-host` |
| PACKAGES | `trusted=yes`, legacy `trusted.gpg`, third-party repos without `Signed-By`, unmanaged binaries in `/usr/local` or `/opt` | `harden-supply-chain` |
| BINARY HARDENING | Network-listening or `/usr/local` ELF with executable stack (`RWE`), linked dev sanitizer (`ASan`), dynamic `NO-PIE`, or missing/partial `RELRO` / hardware CFI (`CET` / `PAC+BTI`) | `harden-build` |
| DOCKER | TCP API, docker.sock mounts, privileged/host-namespace containers, sensitive ports published on all interfaces, secrets in env | `harden-docker`, `harden-firewall` |
| CLOUD | Secrets in user-data; metadata endpoint reachable from containers | `harden-host`, `harden-firewall` |
| LOGGING | Non-persistent journald, no remote shipping, no auditd on high-value hosts | `harden-host` |

Things the script cannot know. Ask the user, or check these manually:

- The cloud/provider firewall configuration.
- Whether the metadata endpoint is reachable from containers:
  `docker run --rm curlimages/curl -s -m2 http://169.254.169.254/`
- Backup existence, encryption and restore tests.
- Which listeners are intended to be public.

## Step 4: Compromise triage (when something smells wrong)

Signs of compromise:

- Unexplained CPU usage (miners)
- Outbound connections to odd ports (miners use 3333/4444/5555/7777/14444, Tor, IRC)
- New users or keys
- Unknown cron entries or systemd units
- Processes running from `/tmp` or `/dev/shm`, or with deleted executables
- A non-empty `/etc/ld.so.preload`
- Modified packaged binaries (`--deep`)
- Bot recon in shell histories (`uname -a; lscpu; nvidia-smi -L; free -m`)

Rules of engagement:

1. **Assume local tools may lie.** A root-level attacker can hide processes,
   files and connections from `ps`, `ss` and `ls`. For a trusted view:
   - boot the provider rescue system and inspect the disk offline,
   - compare the disk against a pre-incident snapshot, or
   - use statically linked tools from read-only media.
2. **Preserve before you poke.** Snapshot the disk via the provider and copy
   volatile data (`ss -tanp`, `ps auxwwf`, `/proc/*/exe` hashes) to another
   host *before* killing anything. Killing a miner first destroys the evidence
   of how it got in.
3. **Find the entry point.** Exposed DB or Docker API? Weak SSH password?
   Vulnerable web app? Leaked CI secret? If you rebuild without closing the
   entry point, the attacker is back within minutes.
4. **Rebuild, don't clean.** After root compromise, reinstall from a known-good
   image, restore *data* (not binaries or configs) from backups that predate
   the compromise, and rotate **every** credential the host could read: SSH
   keys, API tokens, DB passwords, cloud keys, and secrets in cloud-init
   user-data.
5. Report findings in the standard format with an **Incident timeline** section.

## Output

Write `hardening/<host>/AUDIT-YYYY-MM-DD.md` in the format defined in `harden`.
Structure:

1. **Executive summary.** Three to six bullets: overall posture, the top
   risks, and what is reachable from the internet.
2. **Exposure map.** A table with one row per externally reachable port and
   these columns: port/proto, IPv4/IPv6, owning process or container,
   intended?, finding ID.
3. **Findings.** Ordered Critical → Low, each with Evidence / Risk / Fix /
   Verify / Rollback.
4. **Not assessed.** Incomplete sections, unscanned address families, and
   questions for the user.

Keep the raw script output next to the report as evidence. Don't inline it.
After fixes are applied, re-run the script and the outside scan and add an
**After** column to the exposure map.
