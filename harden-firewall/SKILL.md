---
name: harden-firewall
description: >-
  Host firewall design and packet-filter review: nftables at IPv4/IPv6 parity,
  iptables, ufw, and firewalld pitfalls, the Docker published-port bypass,
  rate limiting, egress filtering, and lockout-safe apply with timed rollback.
  Use when the user mentions iptables, nftables, ufw, firewalld, security
  groups, open or unexpectedly reachable ports, Docker ignoring the firewall,
  or IPv6 exposure, or wants to restrict which ports a server exposes.
last_updated: 2026-11-15
---

# Firewall Hardening

The firewall is the layer that silently disappears. Docker routes around it,
IPv6 bypasses it, a second backend shadows it, and a service restart flushes
it. This skill is about knowing the **real kernel ruleset** and making it
survive all of those.

**Reference files** (validated with `nft -c` and loaded twice for idempotency
on nftables 1.1.3; the iptables script was run against iptables-nft):

| File | Install as | Purpose |
| --- | --- | --- |
| `references/host_fw.nft` | `/etc/nftables.d/10-host_fw.nft` | Input/forward/output for the host, inet family |
| `references/docker_guard.nft` | `/etc/nftables.d/20-docker_guard.nft` | Restrict Docker-published ports. Works with both Docker backends. |
| `references/docker-user-fw.sh` + `references/docker-user-fw.service` | `/usr/local/sbin/`, `/etc/systemd/system/` | Same goal via DOCKER-USER, for iptables-centric hosts |
| `references/nftables-service-override.conf` | `/etc/systemd/system/nftables.service.d/override.conf` | Stop/restart of `nftables.service` no longer flushes Docker's tables |

## 1. Find out what is really loaded

```sh
nft list ruleset                       # everything nf_tables evaluates (incl. iptables-nft tables)
iptables -V                            # "(nf_tables)" or "(legacy)"
iptables-legacy-save; ip6tables-legacy-save   # legacy rules are evaluated IN ADDITION to nft
ufw status verbose; grep IPV6 /etc/default/ufw
firewall-cmd --state && firewall-cmd --list-all-zones
iptables -t nat -S DOCKER | grep DNAT  # Docker-published ports, even with no listener in ss
```

Rules of the road:

- **One owner per concern.** Many tools write rules: Docker, libvirt, k3s,
  Tailscale, WireGuard PostUp, fail2ban, CrowdSec, ufw, firewalld. List who
  owns which table. Each tool must manage **only its own table**. Nobody may
  `flush ruleset`.
- **Legacy and nft backends both apply.** A `DROP` in either one drops the
  packet. If `iptables-legacy-save` is non-empty on an nft host, consolidate.
- **Frontends:**
  - **ufw** is fine for a single host without Docker. It doesn't know Docker
    exists, and its `IPV6=no` silently leaves IPv6 open.
  - **firewalld** integrates with Docker by creating a `docker` zone with
    target `ACCEPT` and a `docker-forwarding` policy. Its zones don't restrict
    published ports either.
  - Raw nftables gives full control at the lowest overhead.

## 2. Design rules

1. **Default-drop on input *and* forward, for both families.** An `inet` table
   covers IPv4 and IPv6 with one ruleset. Use it, and parity happens by
   construction.
2. Accept loopback, then `ct state established,related`. Drop `invalid` early.
3. **ICMP:** never drop all ICMPv6. Neighbor discovery and `packet-too-big`
   are required, or IPv6 dies in confusing ways. For IPv4, allow
   `destination-unreachable`, which carries PMTU "frag needed". Rate-limit
   echo; don't block it, because it is useful for ops and hides nothing.
4. **Admin plane separate from service plane.** Best is SSH only on `wg0`
   (WireGuard does not answer unauthenticated packets, so the port looks
   closed). Next is an allow-list of admin sets. Last resort is public SSH
   with a per-source rate limit. See `harden-ssh` §2.
5. **Allow-lists as named sets** (`flags interval`). Update them atomically
   with `nft add element`. No rule rewrites needed.
6. **Rate limiting in the kernel:** dynamic sets with per-element `limit`
   statements (see `ssh_meter_v4`/`_v6` in `host_fw.nft`). Key IPv6 limits by
   **/64**: one customer owns 2^64 addresses, so per-address limits are
   useless.
7. **Log drops at a limited rate**, or the log becomes the DoS.
8. **Egress is policy too.** Default-allow output is normal. Decide
   explicitly about:
   - **Cloud metadata** (`169.254.169.254`, `fd00:ec2::254`): root only, and
     never containers. Both reference files do this, **for TCP/80 only**. On
     GCE and OCI the same address is also the DNS resolver (and NTP on GCE),
     used by non-root `systemd-resolved`/`chrony` and by containers, so a full
     block breaks resolution and time.
   - **AWS EC2 Instance Connect** fetches SSH keys from IMDS as user
     `ec2-instance-connect`. Allow that user first (the commented rule in
     `host_fw.nft`), or the metadata block becomes an SSH lockout.
   - **Service users:** use `meta skuid` rules, or simpler and cheaper,
     systemd `IPAddressDeny=`/`IPAddressAllow=` per unit (`harden-host` §6).
     Egress allow-lists stop the post-RCE "download a miner / reverse shell"
     step.
   - **Mail:** block outbound 25 for everything except the MTA on hosts that
     shouldn't send mail. This stops spam relays.
9. **Conntrack sizing.** A full conntrack table drops *new* connections, which
   means an outage during scan floods. Watch for `nf_conntrack: table full` in
   dmesg and use `conntrack -S`. Size `net.netfilter.nf_conntrack_max` to
   memory; each entry is about 300 B. Use `ct count over N` per source for
   connection caps if needed.

## 3. The ruleset (`host_fw.nft`)

- Atomic per-table replace idiom: `table inet host_fw` / `delete table inet
  host_fw` / `table inet host_fw { ... }`. It loads in one transaction and
  never touches Docker's or anyone else's tables.
- **Persistence on Debian/Ubuntu.** `nftables.service` loads
  `/etc/nftables.conf`, and **its default content begins with
  `flush ruleset`**. On a Docker host, `systemctl restart nftables` then wipes
  Docker's rules and container networking breaks until Docker restarts.
  Replace the file with:
  ```
  #!/usr/sbin/nft -f
  include "/etc/nftables.d/*.nft"
  ```
  Then `systemctl enable nftables`. The unit orders itself before
  `network-pre.target`, so the firewall is up before interfaces.
- **The unit flushes on stop.** Debian/Ubuntu's `nftables.service` also has
  `ExecStop=/usr/sbin/nft flush ruleset`, so `systemctl restart nftables`
  wipes Docker's tables no matter what the config says. Install
  `references/nftables-service-override.conf` as a drop-in. It deletes only
  this suite's tables. On RHEL, check `systemctl cat nftables` for `flush` in
  `ExecReload`/`ExecStop` and override those the same way.
- **RHEL family:** firewalld is the default. Either manage it with
  `firewall-cmd --permanent` (policies, rich rules, `--zone=docker`), or
  disable it and use `nftables.service` with `/etc/sysconfig/nftables.conf`
  including the same files. Never run both on the same tables.

## 4. Docker and the firewall (the classic bypass)

**Mechanism.** `-p 5432:5432` installs a DNAT rule in `nat PREROUTING`. The
packet is rewritten to the container IP *before* routing, so it goes
**PREROUTING → FORWARD → container** and never reaches the INPUT chain where
ufw, firewalld zones and `host_fw input` live. In FORWARD, Docker's chains
(and `DOCKER-USER`) come before ufw's. `ufw status` shows 22/80/443 while
5432 is open to the world. IPv6 behaves the same, plus docker-proxy may listen
on `[::]`.

Fixes, best first:

1. **Don't publish.** Put DBs and caches on an `internal: true` compose network
   with no `ports:` (`harden-docker` §4). Only the reverse proxy publishes 80/443.
2. **Publish to loopback** when the host or an SSH tunnel needs access:
   `"127.0.0.1:5432:5432"`. Make it the default for every port without an
   explicit host IP with daemon `"ip": "127.0.0.1"` (`harden-docker`).
   - Note that `"ip": "127.0.0.1"` sets only the default **IPv4** bind address:
     publish `"[::1]:5432:5432"` explicitly when IPv6 loopback is needed, and
     keep `docker_guard.nft` loaded for IPv6 forward-chain parity.
   - Docker ≥ 28.0 blocks remote hosts on the same L2 segment from reaching
     loopback-published ports. Earlier versions were bypassable.
   - Docker ≥ 28.0 drops direct-routed access to *unpublished* container ports.
3. **Restrict published ports in the forward path:**
   - **`docker_guard.nft`** (works with *both* backends) is its own table with
     a forward-hook chain at `priority filter - 10`. It is **fail-closed**: it
     doesn't depend on the external interface name (`eth0` vs `ens3` vs
     `enp1s0`). Traffic *from* container bridges is left to Docker. Traffic
     *to* them from anywhere else needs an explicit allow. A `drop` in any base chain
     is final. An `accept` only ends that chain. So this chain can **only
     restrict**, which is exactly the job.
   - Match the client's original port with `ct original proto-dst`. Plain
     `tcp dport` sees the container port after DNAT.
   - **`docker-user-fw.sh`** (iptables backend) fills `DOCKER-USER` using
     `-m conntrack --ctorigdstport`. Run it from a oneshot unit with
     `After=`/`PartOf=docker.service`. Docker keeps DOCKER-USER contents across
     daemon restarts but not reboots. Never persist Docker's own rules with
     `netfilter-persistent save`.
4. **Docker 29+ nftables backend** (`"firewall-backend": "nftables"`, still
   experimental in 29.x):
   - Docker creates `ip docker-bridges` / `ip6 docker-bridges`.
   - There is **no DOCKER-USER chain**. Use your own table (`docker_guard.nft`).
   - Docker **will not enable IP forwarding** itself. Set
     `net.ipv4.ip_forward=1` and `net.ipv6.conf.all.forwarding=1`, and keep a
     forward-drop for non-Docker interfaces.
   - It can't be used with Swarm.
   - To *allow* something Docker drops, you need Docker's
     `--bridge-accept-fwmark` plus a mark set at `priority filter - 1` or lower.
5. **ufw users:** the `ufw-docker` approach adds `DOCKER-USER` rules to
   `/etc/ufw/after.rules` and `after6.rules`. Then `ufw route allow proto tcp
   from <src> to any port <container-port>`. Note it uses the post-DNAT
   container port, and "to any" means every container.
6. **Rootless Docker or Podman:** published ports are opened by a userspace
   process on the host, so they *do* hit INPUT and the normal firewall applies.
   With the default port driver, apps see `127.0.0.1` as the client IP. Use
   the `slirp4netns` or `pasta` port drivers to keep real source IPs.

**Never** set `"iptables": false` in `daemon.json` to "fix" this. Docker then
installs no NAT or isolation rules at all: containers lose egress, builds fail,
inter-network isolation is gone, and you are hand-maintaining Docker's
networking.

**Verify with a canary**, using the user's approval:

```sh
docker run -d --rm -p 0.0.0.0:18080:80 -p '[::]:18080:80' --name fw-canary nginx:alpine
# from OUTSIDE, over IPv4 and IPv6
nmap -Pn -p 18080 <ipv4>
nmap -6 -Pn -p 18080 <ipv6>
docker stop fw-canary
```

Port 18080 must be filtered on both families. The `[::]` mapping matters:
without it the IPv6 scan is trivially "filtered", which is false assurance. If
Docker refuses the IPv6 binding, record that IPv6 publishing isn't possible in
this setup. Repeat after every Docker or firewall upgrade:
Docker 28 and 29 both changed the generated rules.

## 5. Outer layer: the cloud / provider firewall

Use security groups, Hetzner/DO/Vultr firewalls, or OCI/GCP VPC rules in
front of the host firewall. They stop floods before they hit your conntrack
table, and they survive a host misconfiguration. Don't rely on them alone:

- Rules drift.
- Private-network rules are often permissive.
- Some providers don't filter IPv6 or inter-VM traffic by default.
- A host migration can drop the attachment.

Keep both layers, and **mirror the intent**.

## 6. Apply safely (lockout protocol)

```sh
install -d -m 700 /root/harden
cp host_fw.nft /root/harden/host_fw.new.nft                    # 0. stage OUTSIDE /etc/nftables.d
nft -c -f /root/harden/host_fw.new.nft                         # 1. validate (no change)
nft list table inet host_fw > /root/harden/host_fw.prev.nft 2>/dev/null || true   # 2. snapshot live table
# 3. dead-man switch: restore the previous table (or remove ours) in 3 minutes
systemd-run --collect --on-active=3min --unit=harden-fw-rollback /bin/sh -c \
  'nft delete table inet host_fw 2>/dev/null || true; [ -s /root/harden/host_fw.prev.nft ] && nft -f /root/harden/host_fw.prev.nft || true'
nft -f /root/harden/host_fw.new.nft                            # 4. apply LIVE only (atomic)
# 5. verify: NEW SSH session (ssh -o ControlMaster=no -o ControlPath=none ...) + outside scan, IPv4 + IPv6
systemctl stop harden-fw-rollback.timer                        # 6. keep it
systemctl reset-failed harden-fw-rollback.service harden-fw-rollback.timer 2>/dev/null || true
install -m 0644 /root/harden/host_fw.new.nft /etc/nftables.d/10-host_fw.nft   # 7. persist only now
nft -c -f /etc/nftables.conf                                   # 8. the boot config still parses
```

- **Why stage outside the config dir.** Until step 7 the boot configuration is
  unchanged, so a reboot inside the window (the transient timer does not
  survive reboots) is also a rollback. A broken file already in
  `/etc/nftables.d` would re-lock you on the next boot or `nftables` reload.
- **`ControlMaster=no -o ControlPath=none`.** With SSH connection multiplexing
  configured, a "new" ssh silently reuses the old authenticated connection.
  The test then passes even though fresh logins are blocked.

- Change the SSH port *and* the firewall in separate batches. First open the
  new port, then move sshd, then close the old port.
- Watch counters while testing: `nft list table inet host_fw`. The rules that
  should match must increment.

## 7. Verification checklist

- `nft list ruleset` shows exactly the tables of known owners. There is no
  `iptables-legacy` residue.
- The input policy is drop for both families. ICMPv6 ND works:
  `ping -6 <gateway>`, and IPv6 egress (`curl -6 https://example.com`) works.
- The outside full-port scan over IPv4 and IPv6 matches the intended exposure
  map in the audit report.
- The Docker canary is filtered. Published DB ports are unreachable from
  outside.
- Metadata is blocked for non-root users and containers:
  `sudo -u nobody curl -m2 http://169.254.169.254/` fails, and so does
  `docker run --rm curlimages/curl -m2 http://169.254.169.254/`.
- After a reboot, the ruleset is identical (diff `nft list ruleset` before
  and after). After `systemctl restart docker`, the guard rules are still
  present.
