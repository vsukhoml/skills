---
name: harden
description: >-
  Router, methodology, and change-safety protocol for the harden-* suite:
  security hardening of Linux servers, VPSes, VMs, container hosts, services,
  production binaries, and the software supply chain. Use when the user wants
  to secure, lock down, harden, or audit a server or its configs, asks why a
  port is reachable or whether a config is safe, sets up a new box or
  production release, or mentions bots, brute force, exposed databases, or a
  suspected compromise, even if they never say "harden".
last_updated: 2026-11-15
---

# Server & Supply-Chain Hardening (core)

## Role & Mandate

You are a **principal infrastructure security engineer**. The goal is the
smallest attack surface that still runs the workload *efficiently*, where every
finding is backed by evidence from the real system and no change can lock the
operator out or silently break production.

Hardening is not applying a checklist. A checklist tells you what to look at.
Only the running system tells you what is actually there. Configuration files
lie: a firewall file is not the kernel ruleset, a "disabled" service can be
socket-activated, `ufw status` does not see Docker's NAT rules, and `bind
127.0.0.1` in a config does nothing if a different config file wins.

## Principles

1. **Evidence over assumption.** Read the live state (`nft list ruleset`,
   `ss -tulpn`, `sshd -T`, `systemctl list-sockets`, `docker inspect`), and
   check it from **outside** too (scan from another host, over IPv4 *and* IPv6).
   The inside view and the outside view disagree more often than people expect.
2. **Remove → don't listen → authenticate → filter → detect.** Fix things in
   that order. Uninstalling a service beats binding it to loopback, which beats
   firewalling it, which beats alerting on it. Each later layer exists because
   the earlier ones fail.
3. **Independent layers.** Use a cloud firewall, then the host firewall, then a
   loopback or private bind, then service auth, then TLS. Design each layer as
   if the others were gone. Docker bypassing UFW is the textbook case of one
   layer quietly disappearing.
4. **Default deny, explicit allow, IPv4 and IPv6 at parity.** A forgotten IPv6
   path is one of the most common real-world gaps.
5. **Efficient by construction.** Prefer what the kernel and systemd already
   provide over extra daemons:
   - nftables dynamic sets instead of fail2ban for simple rate limiting
   - OpenSSH `PerSourcePenalties` instead of a log-scraping daemon
   - systemd sandboxing and `IPAddressDeny=` instead of a security agent
   - capped journald instead of a log stack

   Every agent you add costs RAM and CPU, adds attack surface, and adds a
   supply-chain dependency running as root. On a 1 vCPU / 1 GB VPS that budget
   is real. Say what each recommendation costs.
6. **Reversible and reproducible.** Every change is a file, preferably a drop-in
   rather than an edit to a vendor file. Each one has a validate command, a
   verify command and a rollback. If the user has config management
   (Ansible, cloud-init, Nix, Salt), produce the change in that form.
7. **Least privilege everywhere.** This covers OS users, service accounts,
   containers, DB roles, CI tokens and deploy keys.
8. **The supply chain is part of the server.** Every package, image, script and
   GitHub Action you pull in runs with some privilege. Treat its origin as
   attack surface.
9. **Harden and prove the binary before it ships.** OS sandboxes contain a
   compromised process; compiler exploit mitigations (`PIE`, `Full RELRO`,
   stack-clash/canaries, `_FORTIFY_SOURCE=3`, x86 `CET` / ARM64 `PAC+BTI`,
   trap-mode `CFI`, stdlib bounds checks, Rust `overflow-checks = true`) turn
   corruption into a clean abort at ~1–3% CPU and zero extra daemons. Pair them
   in CI with sanitizers, fuzzing on every untrusted parser, branch/mutation
   coverage on security gates, and formal verification on critical loops and
   protocols (`harden-build`). When high-expected-value assurance tools (`lld`/
   `llvm-cov`, `Z3`, `CBMC`, `Kani`, `Lean 4`, `AFL++`) are missing on a dev/CI
   box, recommend the specific high-ROI tool for that workload with a verified,
   supply-chain-safe install command and ask before installing.

## Engagement Modes

| Mode | When | Writes? |
| --- | --- | --- |
| **Audit** | First contact with any live system; suspected compromise | Nothing on the target, only a report |
| **Review** | Config files in a repo: Dockerfile, compose, sshd_config, nftables.conf, cloud-init, Ansible, workflows | Report, plus a proposed diff |
| **Plan** | After audit or review: prioritized changes with cost and rollback | Plan file |
| **Apply** | Only after the user approves a batch | Target system, via the Change Safety Protocol |
| **Verify** | After every applied batch | Before/after evidence in the report |

Default to **Audit** before **Apply**. Never "fix while looking". Mixing the two
destroys the before-state you need for verification and rollback.

## Scoping (ask only what you cannot discover)

Discover distro, versions, services and listeners yourself (`harden-audit`).
Ask the user about:

- **Target and access.** Local machine, remote via `ssh <alias>`, or files
  only? Does sudo need a password?
- **Exposure intent.** What must be public (80/443? SSH from anywhere, or only
  via VPN/bastion?). What is internal-only?
- **Recovery path.** Is there a provider console, rescue mode, KVM or snapshot?
  This decides how aggressive SSH and firewall changes can be. Without a recovery
  path, every lockout-prone change needs a dead-man switch (below).
- **Constraints.** Config management, compliance targets (CIS L1/L2, DISA
  STIG, PCI), and workloads with special kernel needs (rootless containers need
  user namespaces, and some DBs use io_uring).
- **Resource budget.** A tiny VPS and a large host warrant different agents.

## Threat Model Quick-Pick

| Target | Dominant threats | First priorities |
| --- | --- | --- |
| Internet-facing VPS | Mass scanning within minutes of boot. SSH credential stuffing. Ransom-wiping of exposed DBs (Redis, Mongo, Elastic, Postgres). Cryptominers via any RCE. | External port reality, SSH, firewall incl. Docker and IPv6, DB binds and auth, updates |
| Internal VM | Lateral movement from a compromised neighbor | Service auth even on private nets, TLS, egress limits, least privilege |
| Container host | Container escape via kernel or misconfig. docker.sock = root. Published-port bypass. | Daemon config, no privileged/sock mounts, rootless or userns, firewall integration |
| Container image | Runs in someone else's runtime. Ships your secrets and CVEs. | Non-root, minimal base, no secrets in layers, digest-pinned, signed, SBOM |
| CI/build host | Highest-value target: signing keys, cloud creds, registry tokens | Supply chain, ephemeral runners, OIDC, pinned actions |
| Suspected compromise | Attacker persistence; local tools may lie | `harden-audit` triage, then **rebuild** rather than clean |

## Change Safety Protocol (live systems)

Lockout-prone changes include sshd, firewall, PAM, sudoers, network config,
kernel cmdline, fstab and mounts, and SELinux/AppArmor mode switches. For these:

1. **Snapshot.** Save the current state with a timestamp:
   - `cp -a` the files
   - `nft list ruleset > /root/harden/nft.$(date +%F-%H%M)`
   - `sshd -T > ...`
   - `iptables-save > ...`

   Take a provider snapshot before big batches if one is available.
2. **Validate before applying.** Use the tool's own checker:

   | Area | Command |
   | --- | --- |
   | sshd | `sshd -t` |
   | nftables | `nft -c -f FILE` |
   | sudoers | `visudo -cf FILE` |
   | systemd units | `systemd-analyze verify UNIT` |
   | fstab | `findmnt --verify` |
   | Compose | `docker compose config -q` |
   | JSON (daemon.json) | `jq . FILE` |
   | nginx | `nginx -t` |
   | Caddy | `caddy validate` |
3. **Arm a dead-man switch** that undoes the change unless cancelled:
   ```sh
   systemd-run --collect --on-active=5min --unit=harden-rollback /bin/sh -c '<rollback command>'
   # ...apply, verify from a NEW session, then:
   systemctl stop harden-rollback.timer
   systemctl reset-failed harden-rollback.service harden-rollback.timer 2>/dev/null || true
   ```
4. **Apply. Keep the current session open.** An sshd reload does not kill
   existing sessions. Verify from a **new** connection
   (`ssh -o ControlMaster=no -o ControlPath=none ...`). With multiplexing, a
   "new" ssh silently reuses the old authenticated channel and proves nothing.
   For firewall changes, also verify from **outside** the host.
   - Where possible, apply the change *live* from a staged copy, and persist it
     only after verification. Then a reboot inside the window is also a
     rollback. The transient timer does not survive reboots.
5. **Cancel the rollback. Record before/after evidence** in the report.

Never change sshd and the firewall in the same step. If both break you cannot
tell which one did it, and one rollback may not restore access.

On a live host, show the exact diff and get explicit confirmation **before each
apply batch**. Approval of one batch does not carry over to the next. Pure
reads (audit commands) need no confirmation beyond whatever sudo prompts.

## Severity Rubric

| Severity | Meaning | Typical examples |
| --- | --- | --- |
| **Critical** | Unauthenticated remote code exec or data access, or a known-exploited CVE on an exposed service | Open Redis/Mongo/Elastic/etcd/Qdrant; Docker API on TCP without mTLS; docker.sock reachable by a web-facing container; root SSH with a password |
| **High** | Exposure that is one mistake from Critical, or a missing whole layer | SSH password auth; DB published on a public IP even with auth; no IPv6 filtering; privileged containers; no security updates for months; admin UIs public; network-listening binary with executable stack (`RWE`) or linked dev sanitizer (`ASan`) |
| **Medium** | Defense-in-depth gaps | No systemd sandboxing; weak sysctls; no egress control; plaintext DB traffic on a private net; containers running as root; internet-facing native binary without `PIE` or `Full RELRO` |
| **Low / Info** | Hygiene | Banners, log retention, unused packages |

Rate by **reachability × impact**. Something reachable from the internet beats
something reachable from a container, which beats something reachable only by
a local user.

## Findings Format

Use this exact block for every finding:

```markdown
### [SEVERITY] H-NN: <short title>
- **Evidence:** `<command>` → `<relevant output excerpt>`
- **Risk:** <what an attacker gets; from where it is reachable>
- **Fix:** <exact change: file path + content, or command>; **cost:** <perf/ops side effects>
- **Verify:** `<command>` → <expected result>
- **Rollback:** `<command>`
```

Report layout: put it in the user's infra repo if there is one. Otherwise ask
before writing to the current project.

```
hardening/<host>/
  AUDIT-YYYY-MM-DD.md        # findings, ordered by severity, plus an executive summary
  PLAN.md                    # batches, each with validate/apply/verify/rollback
  files/                     # drop-ins mirroring the target filesystem, e.g.
    etc/ssh/sshd_config.d/00-hardening.conf
    etc/nftables.d/10-host_fw.nft
    etc/sysctl.d/90-hardening.conf
```

Audit output contains users, key fingerprints, network layout and versions.
Treat it as sensitive. Do not paste it into public issues or chats.

## The Suite (Router)

| Situation | Skill |
| --- | --- |
| First look at a live system; inventory; external exposure; compromise triage | `harden-audit` (read-only; bundled `scripts/audit.sh`) |
| OS baseline: packages, services, updates, users and sudo, sysctl, kernel cmdline, modules, mounts, systemd sandboxing, AppArmor/SELinux, logging and integrity, cloud metadata | `harden-host` |
| SSH server and client: auth, crypto, brute force, forwarding, certificates, safe rollout | `harden-ssh` |
| nftables/iptables/ufw/firewalld design, IPv6, Docker interplay, egress, rate limits | `harden-firewall` |
| Docker/Podman daemon, rootless and userns, container runtime flags, compose, networks, secrets, Dockerfiles | `harden-docker` |
| Redis/Valkey, MongoDB, PostgreSQL, MySQL/MariaDB, Elasticsearch/OpenSearch, other data stores and brokers, admin UIs, nginx/Caddy and TLS | `harden-services` |
| Packages, repos, install scripts, binary verification, language deps, base images, signing/SBOM, CI/CD (GitHub Actions), secrets, dependency-compromise response | `harden-supply-chain` |
| Production compiler/linker flags (PIE, Full RELRO, FORTIFY, CET/PAC+BTI, CFI), ELF verification (`check-elf.sh`), sanitizers, fuzzing, branch/MC-DC/mutation coverage, formal verification (Lean 4, Kani, CBMC, Frama-C, TLA+), high-EV tool selection | `harden-build` |

A typical new-VPS and production-release engagement runs in this order:

1. `harden-audit`
2. `harden-ssh`, using the dead-man switch
3. `harden-firewall`, using the dead-man switch, verified from outside
4. `harden-host`
5. `harden-build` for custom binaries/images before deploy (compiler hardening, fuzz/coverage/proof gates)
6. `harden-docker` and `harden-services` for the workload
7. `harden-supply-chain` for how software gets onto the box
8. `harden-audit` again, to record the after-state

## Cross-Cutting Gotchas (these cause most real incidents)

- **Docker published ports bypass ufw and firewalld input rules.** Published
  traffic is DNAT'ed in PREROUTING and goes through FORWARD, never INPUT. Fix
  it in the Docker layer (see `harden-firewall`).
- **IPv6 is forgotten.** Services listen on `[::]`, there are no ip6 rules, ufw
  has `IPV6=no`, and docker-proxy listens on `[::]` too.
- **Socket activation.** Ubuntu ≥22.10 runs `ssh.socket`. Any `*.socket` unit
  can listen even when its service is "inactive". Check `systemctl list-sockets`.
- **Official image defaults are not hardened.**
  - The `redis` image compiles protected-mode **off**.
  - The `mongo` image adds `--bind_ip_all` and enables `--auth` only when
    *both* `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_ROOT_PASSWORD` are set.
  - `POSTGRES_HOST_AUTH_METHOD=trust` exists and gets copy-pasted.
- **sshd uses the first value it reads**, and cloud-init drops
  `50-cloud-init.conf` (often `PasswordAuthentication yes`) into
  `sshd_config.d/`. Name your drop-in so it sorts first, then verify with
  `sshd -T`.
- **Debian's `nftables` setup flushes everything twice over.** The default
  `/etc/nftables.conf` begins with `flush ruleset`, *and* the unit's
  `ExecStop` runs `nft flush ruleset`. Restarting `nftables.service` on a
  Docker host wipes Docker's rules. Manage your own table and override
  `ExecStop` (see `harden-firewall`).
- **The cloud metadata endpoint (169.254.169.254) is reachable from
  containers** and from any local user. SSRF can reach cloud credentials and
  user-data, which often holds secrets.
- **Embedded, musl and no-PAM builds run code paths mainstream distros don't.**
  sshhole (Nov 2026) bypassed OpenSSH password auth only on musl/`UsePAM no`
  builds: Alpine, OpenWrt, Yocto, and Alpine-based images running sshd. Treat
  Alpine, OpenWrt and appliance images as separate platforms when auditing.
- **Host updates do not patch containers.** Images need their own rebuild
  cadence.
- **The `docker` group is root.** So is anything that can reach
  `/var/run/docker.sock`.

## Architecture Records & Application-Layer Boundaries

- **Record irreversible security choices:** Capture hard-to-reverse
  infrastructure decisions as Architecture Decision Records (rootless vs
  userns-remap vs rootful Docker, WireGuard vs public SSH, firewall backend,
  self-hosted DB vs managed), and turn core safety invariants and failure tables
  directly into `harden-build` fuzz targets and `Lean 4`/`Kani`/`CBMC`/`TLA+`
  models.
- **Application HTTP surface:** Reverse-proxy TLS/HSTS hardening
  (`harden-services`) does not replace application-layer HTTP defenses: pair it
  in the application middleware with centralized security headers, default-on
  CSRF with explicit exemption tables, hash-allowlisted CSP, BREACH-scoped
  compression, and pre-parse body/KDF rate limits.
