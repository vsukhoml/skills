---
name: harden-host
description: >-
  Linux OS hardening baseline for Debian, Ubuntu, and RHEL-family servers,
  VPSes, and VMs: package and service minimization, automatic security
  updates, users and sudo, sysctl and kernel parameters, systemd sandboxing,
  AppArmor/SELinux, and logging. Use when setting up or locking down a host,
  when asked about sysctl, unattended-upgrades, sudo, systemd hardening, or
  CIS/STIG baselines, or when an audit flags OS-level issues.
last_updated: 2026-11-15
---

# Host Baseline Hardening

**Scope:** the operating system underneath everything else. SSH, firewall,
containers and data services each have their own skill. This one makes them
sit on a minimal, patched, sandboxed and observable OS. Follow the Change
Safety Protocol from `harden` for anything lockout-prone: PAM, sudoers, fstab,
kernel cmdline, MAC mode switches.

**Reference files** (copy, then edit the lines marked `[WORKLOAD]`):

- `references/sysctl-hardening.conf` → `/etc/sysctl.d/90-hardening.conf`
- `references/modprobe-hardening.conf` → `/etc/modprobe.d/90-hardening.conf`
- `references/systemd-sandbox.conf` → per-unit drop-in via `systemctl edit`
- `references/audit.rules` → `/etc/audit/rules.d/50-harden.rules`

**Baselines as cross-checks, not scripts.** CIS Benchmarks (L1/L2), DISA STIG,
OpenSCAP (`oscap xccdf eval --profile ...`), Ubuntu Pro `usg` and Lynis
(`lynis audit system`) are good at finding gaps. Applied blindly they break
things: CIS L2 on a Docker host, or a STIG that turns off IPv6 forwarding a
VPN needs. Use them to find gaps, then decide each item with this skill.

## 1. Minimize what is installed and running

The cheapest hardening is a smaller system: fewer packages, fewer CVEs, fewer
update reboots, less RAM.

- **Start minimal.** Use the provider's minimal or cloud image, and set
  `APT::Install-Recommends "false";` in `/etc/apt/apt.conf.d/90norecommends`.
  On RHEL-family, use `dnf --setopt=install_weak_deps=False`.
- **Inventory:**
  - `systemctl list-units --type=service --state=running`
  - `systemctl list-sockets` (socket units listen even while the service is "inactive")
  - `systemctl list-timers`
  - `ss -tulpn`
- **Usual suspects on servers.** Purge if unused, otherwise `systemctl mask --now`:

  | Service | Why it goes |
  | --- | --- |
  | `avahi-daemon` | mDNS on 5353 |
  | `cups`, `cups-browsed` | Printing. cups-browsed was the 2024 UDP 631 RCE chain. |
  | `rpcbind`, `nfs-*` | NFS/RPC on servers that don't use it |
  | `ModemManager`, `bluetooth`, `wpa_supplicant` | No hardware on a VPS |
  | `multipathd`, `iscsid`/`open-iscsi` | No SAN on a VPS |
  | `fwupd` | No firmware updates on a VM |
  | `udisks2`, `packagekit`, `accounts-daemon` | Desktop plumbing |
  | `apport`, `whoopsie`, `popularity-contest` | Crash reports and telemetry |
  | `motd-news.timer` | Outbound fetch on every login |
  | `snapd` | Only if no snaps are used. Note it auto-refreshes from the store, which is a supply-chain channel. |
  | `exim4`/`postfix` listening beyond loopback | Set `inet_interfaces = loopback-only` |
  | `telnet`, `ftp`, `rsh`, `xinetd`, `tftp`, `nis`, `talk` | Legacy cleartext services |
- **Keep, but understand.**
  - `qemu-guest-agent`: the hypervisor can run commands in the guest
    (`guest-exec`). The provider is already trusted, but it is a channel.
  - `cloud-init`: some providers need it for networking on every boot. Don't
    disable it blindly. Do clean secrets out of user-data (section 7).
- **Compilers and network tools** (`gcc`, `make`, `nc`, `nmap`, `tcpdump`) on
  production hosts help attackers more than operators. Remove them from
  immutable/app hosts and keep them on a bastion.

## 2. Updates and reboots

A patched kernel that has not been rebooted into is not patched. Decide the
reboot policy explicitly.

- **Debian/Ubuntu:** install `unattended-upgrades` (and `needrestart`). Keep
  the distro's `50unattended-upgrades` origin list. It selects the security
  origins (on Debian, also stable point releases). Put only overrides in
  `/etc/apt/apt.conf.d/52unattended-upgrades-local`:
  ```
  Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
  Unattended-Upgrade::Remove-Unused-Dependencies "true";
  Unattended-Upgrade::Automatic-Reboot "true";          // or "false" + monitored reboot-required
  Unattended-Upgrade::Automatic-Reboot-Time "04:30";
  ```
  `/etc/apt/apt.conf.d/20auto-upgrades` needs `APT::Periodic::Update-Package-Lists "1";`
  and `APT::Periodic::Unattended-Upgrade "1";`. Check with
  `unattended-upgrade --dry-run -d`.
- **RHEL/Fedora:** use `dnf-automatic` (dnf5: the `dnf5-plugin-automatic`
  package). Set `upgrade_type = security` and `apply_updates = yes`, and
  enable its timer. Use `needs-restarting -r` for the reboot decision.
- **Services after library updates:** `needrestart` restarts services using
  replaced libraries. Set `$nrconf{restart} = 'a';` for unattended hosts.
- **Livepatch** (Ubuntu Pro, kpatch, kernelcare) shrinks the reboot window. It
  does not remove reboots.
- **Containers are separate.** Host updates never patch images. See
  `harden-docker` for rebuild cadence.
- **Rate the risk of auto-updates honestly.** Security-only origins from the
  distro are low-risk and high-value. Auto-updating third-party repos is a
  supply-chain decision (see `harden-supply-chain`).

## 3. Users, root, sudo

- **One named admin account per human, with key-only SSH.** No shared accounts.
  Service accounts get `--system --shell /usr/sbin/nologin --no-create-home`.
- **Root:** disable SSH login (`harden-ssh`). Locking the root *password*
  (`passwd -l root`) is a trade-off. It blocks console recovery unless the
  provider's rescue mode works. Confirm the recovery path before locking it.
- **sudo** (validate every edit with `visudo -cf FILE`; never edit without it):
  ```
  # /etc/sudoers.d/10-hardening
  Defaults use_pty
  Defaults timestamp_timeout=5
  Defaults !visiblepw
  Defaults passwd_tries=3
  %sudo ALL=(ALL:ALL) ALL
  ```
  - Remove cloud-init's `90-cloud-init-users` `NOPASSWD:ALL` for humans. With
    NOPASSWD, a stolen SSH key equals root. With a sudo password (the user
    must have a password; it is only usable for sudo, since SSH is key-only),
    a stolen key gets a user shell.
  - Automation accounts that need NOPASSWD get **specific commands**, not `ALL`.
  - **Ubuntu ≥ 25.10 ships `sudo-rs` as `sudo`.** It implements a subset of
    sudoers and **rejects unknown settings, which invalidates the whole
    file**. A broken sudoers file means no sudo at all.
    - `Defaults logfile=...` is one such setting: sudo-rs logs to the journal
      instead. Add `logfile` only with classic sudo (`sudo.ws`).
    - Always run `visudo -cf` with the *installed* implementation, then test
      with `sudo -l -U <user>` from a second session before closing the first.
- **Root-equivalent groups.** Membership in `docker`, `lxd`/`incus-admin`,
  `libvirt` or `disk` is root. Keep these groups empty or limited to admins.
- **Hygiene:**
  - `umask 027` in `/etc/login.defs` (`UMASK 027`)
  - `/etc/security/limits.d/` (`* hard core 0`)
  - delete unused default users (`ubuntu`, `debian`, `admin`) once your own
    account works
  - `pam_faillock` only matters if password auth exists anywhere
  - restrict `su` with `auth required pam_wheel.so use_uid group=sudo` in
    `/etc/pam.d/su`

## 4. Kernel: sysctl, cmdline, modules

- **sysctl:** start from `references/sysctl-hardening.conf`. Every line states
  its cost. The `[WORKLOAD]` items need a decision:
  - io_uring
  - unprivileged user namespaces (rootless containers need them)
  - `rp_filter` on multi-homed hosts
  - `accept_ra` (SLAAC VPSes need RA)
  - `kexec` (kdump)

  Apply with `sysctl --system` and check with `harden-audit`'s sysctl section.
- **Kernel cmdline** (`/etc/default/grub` `GRUB_CMDLINE_LINUX`, then
  `update-grub`; or `grubby --update-kernel=ALL --args=...`). Test on a
  snapshot first.

  | Parameter | Effect | Cost |
  | --- | --- | --- |
  | `init_on_alloc=1` | Zero heap on allocation (default on Ubuntu/Fedora kernels) | ~1% |
  | `init_on_free=1` | Zero heap on free | Several % on alloc-heavy loads. Skip on busy DB hosts. |
  | `slab_nomerge` | Harder heap exploitation | Small RAM cost |
  | `page_alloc.shuffle=1` | Randomizes page allocator | ~0 |
  | `randomize_kstack_offset=on` | Randomizes kernel stack offset | ~0 |
  | `vsyscall=none` | Removes a fixed-address gadget | Breaks only ancient static binaries |
  | `debugfs=off` | Removes debugfs attack surface | No debugfs-based tracing |
  | `lockdown=integrity` | Root can't modify the running kernel | Blocks unsigned modules (DKMS without MOK), hibernation, `/dev/mem` |
  | `module.sig_enforce=1` | Only signed modules load | Same as above for DKMS |
  | `oops=panic` | Stop instead of continuing after a kernel oops | Availability. Pair with `panic=10` for auto-reboot. |

  - **Never** set `mitigations=off` on a VPS or any multi-tenant hypervisor.
  - Linux ≥ 6.17 supports attack-vector controls for narrowly disabling
    mitigations on single-tenant bare metal, if perf demands it (see the
    kernel's `attack_vector_controls` docs).
  - Verify with `cat /proc/cmdline`, `cat /sys/kernel/security/lockdown`
    and `grep . /sys/devices/system/cpu/vulnerabilities/*`.
- **Hardware userspace CFI & memory tagging (`harden-build` §1):** Compiler flags
  (`-fcf-protection=full`, `-mbranch-protection=standard`) only emit ELF notes
  and instructions; the CPU, kernel, and glibc enforce them at runtime:
  - **x86-64 CET Shadow Stack (`user_shstk`):** Active on Linux ≥ 6.6 + glibc
    ≥ 2.39 (Zen 3+, Tiger Lake+) when the executable and every linked `.so`
    carry the `SHSTK` note. Confirm on a running daemon via
    `grep x86_Thread_features /proc/<pid>/status` (`shstk`). One unannotated
    plugin loaded via `dlopen` disables `shstk` unless locked via
    `GLIBC_TUNABLES=glibc.cpu.hwcaps=...` / `cet` tunable.
  - **AArch64 PAC + BTI + MTE:** Kernel enforces `BTI` and `PAC-RET`
    transparently on v8.3+/v8.5+ silicon; on MTE-capable ARMv8.5+ hosts, enable
    heap tag checks on exposed C/C++ daemons via systemd
    `Environment="GLIBC_TUNABLES=glibc.mem.tagging=3"`.
- **Modules:** use `references/modprobe-hardening.conf` to block auto-loading
  of rare protocol and filesystem modules. Unprivileged users can trigger
  auto-loading just by opening a socket, which is how many LPEs start.
  - For immutable app hosts: load everything needed at boot (`overlay`,
    `br_netfilter`, `nf_*`, `wireguard`), then set `kernel.modules_disabled=1`
    from a late boot unit. It is one-way until reboot.

## 5. Filesystems and mounts

- **`/tmp`:** a tmpfs with `nosuid,nodev`. Debian 13, Ubuntu 26.04 and Fedora
  already use tmpfs. On Debian 12 / Ubuntu 24.04 the unit ships disabled in
  `/usr/share/systemd/`: run
  `cp /usr/share/systemd/tmp.mount /etc/systemd/system/ && systemctl enable --now tmp.mount`.
  - Add `noexec` only after testing. Some installers and package maintainer
    scripts execute from `/tmp`. Use `noexec` together with
    `APT::ExtractTemplates::TempDir` pointing elsewhere, or skip it.
  - Prefer `PrivateTmp=yes` per service (section 6). It is stronger than
    mount flags.
- **`/dev/shm`:** `nosuid,nodev,noexec`. Use a systemd `dev-shm.mount` drop-in
  or fstab: `tmpfs /dev/shm tmpfs defaults,nosuid,nodev,noexec 0 0`.
- **`/proc` `hidepid=invisible`:** users can't see others' processes.
  systemd-logind and polkit need an exemption group: use
  `gid=proc` plus `SupplementaryGroups=proc` in a `systemd-logind` drop-in.
  Test before relying on it. `ProtectProc=` per service is the safer
  alternative.
- **Validate fstab** with `findmnt --verify` before rebooting. A bad fstab
  means an emergency-shell boot.
- **SUID inventory.** `harden-audit` lists the SUID files. Remove SUID from
  tools no one uses, persistently and package-aware with
  `dpkg-statoverride --update --add root root 0755 /usr/bin/<tool>`.
- **Core dumps:** `fs.suid_dumpable=0`, plus `Storage=none` in
  `/etc/systemd/coredump.conf.d/` on production. Dumps contain secrets.
- **Encryption at rest** on a VPS protects against disk-image theft and
  snapshot leaks, not a running-host compromise. Ubuntu 26.04 makes TPM-backed
  FDE generally available on bare metal. Use it for the threat it addresses.

## 6. systemd service sandboxing: the best value per effort

For any service you run directly (not in a container), a drop-in from
`references/systemd-sandbox.conf` gives namespace, seccomp, capability and
cgroup isolation at essentially zero runtime cost.

1. Measure with `systemd-analyze security <unit>`. Exposure 9+ is "UNSAFE".
   Aim for under 4 on internet-facing units.
2. Run `systemctl edit <unit>` and add one block at a time from the template.
   Then restart, exercise the service, and watch `journalctl -u <unit> -f`.
   EPERM, EACCES or read-only errors tell you which line to relax
   (`ReadWritePaths=`, drop `MemoryDenyWriteExecute=` for JITs, and so on).
3. **Egress control per service** without a firewall daemon:
   `IPAddressDeny=any` + `IPAddressAllow=localhost 10.0.0.0/24`. Use
   `SocketBindAllow=` to restrict binds. This blocks the "download a miner /
   open a reverse shell" step after an RCE.
4. **Resource containment** (`MemoryMax=`, `TasksMax=`, `CPUQuota=`) turns a
   compromised or runaway service from a host outage into a service restart.
   It is also the efficiency win on small boxes.
5. **Pair with binary hardening (`harden-build`):** `MemoryDenyWriteExecute=yes`
   and `LockPersonality=yes` enforce kernel-side W^X alongside `-Wl,-z,noexecstack`.
   For high-risk internet-facing C/C++ daemons you cannot recompile, you can
   also preload a hardened allocator (`Environment="LD_PRELOAD=..."` with
   `libhardened_malloc` or `mimalloc-secure`) per unit after measuring its RAM
   overhead.

A single app on a VPS often needs no container at all. A sandboxed systemd unit
is lighter, and as isolated for that threat model.

## 7. Cloud and VM specifics

- **Metadata endpoint** (`169.254.169.254`, AWS also `fd00:ec2::254`). Any
  process or container that can reach it can read instance credentials and
  user-data. SSRF bugs target it first.
  - AWS: enforce IMDSv2 with hop limit 1. That blocks bridged containers.
  - Everywhere: block non-root and container access with nftables
    (`harden-firewall` has the rules).
- **cloud-init user-data often contains secrets** (passwords, tokens, keys)
  and stays readable via the metadata service for the instance's lifetime.
  Deliver secrets another way, and rotate any that were ever in user-data.
  Check `/var/lib/cloud/instance/user-data.txt`.
- **Provider firewall** as the outer layer (`harden-firewall`), plus
  provider-side **snapshots/backups**. See below for why backups are a
  security control.
- **Backups are part of hardening.** Against ransomware and wipers they are the
  control that matters.
  - Encrypted.
  - Off-host.
  - **Immutable or append-only**: restic to a `--append-only` rest-server, or
    S3 Object Lock. Credentials on the host must not be able to delete old
    snapshots.
  - Restore-tested on a schedule.

## 8. Mandatory access control

- **AppArmor** (Debian/Ubuntu/SUSE): `aa-status`. Keep shipped profiles in
  enforce mode. Profile internet-facing custom services (`aa-genprof`, then
  enforce). Ubuntu 26.04 also enforces profiles for more system services.
- **SELinux** (RHEL family): stay in Enforcing (`getenforce`). When something
  is denied, read `ausearch -m avc -ts recent` and fix with booleans or
  file-context labels (`semanage fcontext`, `restorecon`). Use
  `audit2allow` only for small, understood policy modules. **Never** "fix" a
  denial by switching to permissive.

## 9. Time, logging, detection, integrity (efficient by design)

- **Time:** use chrony with NTS where supported
  (`server time.cloudflare.com iburst nts`). Correct time matters for TLS,
  TOTP, logs and Kerberos. chrony serves no clients unless `allow` is set;
  keep it that way.
- **journald:** `Storage=persistent`, `SystemMaxUse=500M` (or about 5% of
  disk), `RateLimitBurst=` defaults. Forward off-host with
  `systemd-journal-upload`, rsyslog over TLS, or a light shipper (vector,
  fluent-bit). Local logs are the first thing a root attacker deletes.
- **auditd** with `references/audit.rules`: focused watches on identity,
  sudo, sshd, keys, cron, systemd units, `ld.so.preload`, module loads, and
  exec from temp dirs. Log *these*, not every `execve`. Full exec logging
  costs real CPU and disk on a 1 vCPU VPS and buries the signal.
- **Integrity:**
  - `dpkg --verify` / `rpm -Va` cover packaged files for free
    (`harden-audit --deep`).
  - AIDE with a *narrow* config (`/etc`, `/usr/local`, `/boot`, `/root/.ssh`)
    on a weekly timer with `Nice=19` and `IOSchedulingClass=idle`.
  - rkhunter and chkrootkit are noisy and low-signal. Skip them.
- **Runtime detection** (Falco, Tetragon, Wazuh) earns its RAM on fleets and
  multi-tenant container hosts. On a single small VPS, auditd + remote logs +
  external uptime and port monitoring is the proportionate choice.
- **Someone must read alerts.** A daily digest (logwatch-style, or a query in
  your log backend) beats a SIEM nobody opens.

## 10. Efficiency knobs that cost no security

- **zram swap** (`systemd-zram-generator`) instead of disk swap on small VPSes.
  No swap file with secrets on disk, and it is faster.
- **fq + BBR** congestion control. Right-sized `nf_conntrack_max`: a full
  conntrack table drops new connections under scan floods.
- **Disable** apt/dnf "download updates" timers that duplicate the
  unattended-upgrades run. Disable `motd-news` and telemetry timers.
- **journald caps, and `log-driver local` for Docker.** Disk-full is the most
  common self-inflicted VPS outage.
- **Sandboxed systemd units over containers** for single-binary services
  (section 6).

## Verification checklist (record before/after in the audit report)

- `harden-audit` re-run: SYSCTL shows no `!!` lines except deliberate ones,
  the SERVICES section shows only intended units, and the flags are cleared.
- `systemd-analyze security` for each internet-facing unit is under 4.
- `sudo -l -U <each human>` shows exactly the intended rules.
  `getent group docker sudo` shows exactly the intended members.
- `cat /proc/cmdline` shows the intended params. `findmnt /tmp /dev/shm`
  shows the flags.
- `unattended-upgrade --dry-run -d` (or `dnf-automatic --timer` logs) shows
  security updates being selected.
- Remote log shipping: generate a test entry with `logger harden-test`, then
  confirm it arrives off-host.
