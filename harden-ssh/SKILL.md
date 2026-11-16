---
name: harden-ssh
description: >-
  OpenSSH and Dropbear hardening: admin-access model (public SSH, WireGuard,
  bastion, SSH certificates), key-only sshd drop-in, FIDO2 keys, SFTP chroots,
  brute-force handling, and lockout-safe rollout. Use when the user mentions
  sshd_config, SSH keys, brute-force or bot logins, fail2ban, changing the SSH
  port, disabling root or password login, ssh-audit, bastions or jump hosts,
  or SSH on OpenWrt or embedded devices.
last_updated: 2026-11-15
---

# SSH Hardening

SSH is the front door of almost every VPS, and the change most likely to lock
the operator out. Make decisions in this order:

1. The access model.
2. Authentication.
3. Exposure reduction.
4. Crypto (mostly: get out of the way of good defaults).

Then roll out with the safety procedure below.

**Reference files** (validated with `sshd -t` / `sshd -T` on OpenSSH 10.2
(Ubuntu, glibc+PAM) and 10.3 (Alpine, musl, no PAM). On Alpine, a 300-char
password against a `*` account was refused with `Permission denied (publickey)`):

- `references/00-hardening.conf` → `/etc/ssh/sshd_config.d/00-hardening.conf`
- `references/90-match-examples.conf` → per-user exceptions (tunnel-only, SFTP chroot)

## 1. Discover first

```sh
ssh -V                                          # version decides which options exist
sshd -T | sort > /root/harden/sshd-T.before     # EFFECTIVE config: the only truth
ls -la /etc/ssh/sshd_config.d/                  # cloud-init's 50-cloud-init.conf lives here
grep -n Include /etc/ssh/sshd_config            # where drop-ins are read (top of file on Debian/Ubuntu/Fedora)
systemctl status ssh.socket ssh.service sshd.service 2>/dev/null | grep -E 'Loaded|Active|Listen'
for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done
```

Facts that bite:

- **First value wins.** For most keywords, sshd uses the *first* value it reads.
  The `Include` sits at the top of the main file, so a drop-in beats the main
  file, and `00-` beats cloud-init's `50-cloud-init.conf` (which often sets
  `PasswordAuthentication yes`). Always confirm with `sshd -T`, never by
  reading files.
- **Socket activation** (Ubuntu ≥ 22.10). `ssh.socket` owns the listening port.
  After changing `Port` or `ListenAddress`, run
  `systemctl daemon-reload && systemctl restart ssh.socket`. A generator
  translates the sshd_config values into the socket unit. Merely reloading
  `ssh.service` leaves the old port listening.
- **Process split.** OpenSSH **9.8** moved per-connection work into
  `sshd-session`, and 10.0 added `sshd-auth`. Logs come from `sshd-session`
  from 9.8 on, so journal and fail2ban filters on `sshd` alone miss them
  (`journalctl -t sshd -t sshd-session`).
- **OpenSSH 10.0** removed DSA and made `mlkem768x25519-sha256`
  (post-quantum hybrid) the default KEX.
- **`PerSourcePenalties`** (≥ 9.8, on by default) already penalizes sources
  that fail auth, don't authenticate, or crash sshd. Most of what people
  install fail2ban for is now built in.

## 2. Choose the access model (biggest win first)

| Model | Exposure | When |
| --- | --- | --- |
| **SSH only over WireGuard/Tailscale/Headscale.** The firewall allows 22 only on `wg0` (or the tailnet interface). | Port 22 is invisible to the internet. WireGuard does not answer unauthenticated packets. | **Default recommendation** for personal and small-team VPSes |
| **Bastion / jump host** (`ProxyJump`). App hosts accept SSH only from the bastion IP. | One hardened public host | Fleets; when a VPN client is not an option |
| **Public SSH + key-only + allow-list + penalties** | Port reachable, auth surface minimal | When the above are impossible. Fine if done right. |
| **SSH certificates** (`TrustedUserCAKeys`, short-lived certs) | Same as above; no authorized_keys sprawl | Teams and fleets; also gives clean revocation and expiry |

**Changing the port** (e.g. 22 → 52222) is *noise reduction*, not security. It
cuts log spam and drive-by credential stuffing, and stops nothing targeted.
Do it if logs matter to the user, and remember the socket-activation note, the
firewall rule, and SELinux (`semanage port -a -t ssh_port_t -p tcp 52222`).

Port knocking and single-packet authorization add operational fragility for
little gain over WireGuard. Do not recommend them.

## 3. Authentication

- **Keys only.** Set `AuthenticationMethods publickey`,
  `PasswordAuthentication no` and `KbdInteractiveAuthentication no`.
  `UsePAM yes` can stay, so PAM account and session modules still run.
- **Key types:**
  - **FIDO2 hardware keys** are best:
    `ssh-keygen -t ed25519-sk -O resident -O verify-required`. The private key
    can't be exfiltrated from a laptop. Add `PubkeyAuthOptions verify-required`
    on the server to demand a PIN or biometric.
  - **Otherwise Ed25519** with a passphrase, held in an agent.
  - **RSA ≥ 3072** only for legacy clients. Set `RequiredRSASize 3072` (≥ 9.1).
  - **Hardware-backed client keys** (Android Keystore, PIV, Secure Enclave) are
    often ECDSA P-256. Keep ECDSA in the default `PubkeyAcceptedAlgorithms`.
- **Allow-list.** `AllowGroups ssh-users` makes new accounts unable to SSH by
  default. **Add admins to the group before reloading.** This is the classic
  lockout.
- **No root login.** `PermitRootLogin no`. Admins use `sudo`.
  `prohibit-password` is acceptable only for a deliberate automation root key
  that carries a `from=` restriction.
- **authorized_keys hygiene:**
  - One key per device, with a comment naming device and owner. Review keys
    quarterly. `harden-audit` lists fingerprints.
  - Automation keys get options:
    `restrict,from="198.51.100.7",command="/usr/local/bin/deploy" ssh-ed25519 AAAA... ci-deploy`.
    `restrict` disables pty, forwarding, X11, agent and rc in one word.
  - **Root-managed keys** for high-value hosts:
    `AuthorizedKeysFile /etc/ssh/authorized_keys/%u` with root-owned `0644`
    files. An attacker with a user shell (or a compromised app running as that
    user) cannot add a persistence key.
  - Drop `authorized_keys2` (deprecated) by setting `AuthorizedKeysFile` explicitly.
- **Why "keys only" is attack-surface removal, not hygiene: sshhole (Nov 2026).**
  - **The bug.** On sshd builds that check passwords themselves (musl libc
    without PAM, or any build running `UsePAM no`), musl's `crypt()` returns
    `"*"` on failure, and it fails for keys longer than 256 bytes. sshd
    compared that against the stored hash. Accounts whose shadow field is
    exactly `*` therefore accepted **any 257–1024-character password**.
    That covers key-only users, LDAP users, root on Alpine, and the default
    Alpine cloud user, which has passwordless doas.
  - **Affected:** Alpine, OpenWrt with OpenSSH, Buildroot, Yocto, and
    Alpine-based images running sshd.
  - **The fix:** OpenSSH 10.6p2 (2026-11-05) refuses any match against a
    stored field shorter than 4 characters. **Restart sshd after upgrading**:
    the package upgrade alone leaves the vulnerable daemon running.
  - **This drop-in was immune before the fix existed.**
    `AuthenticationMethods publickey` and `PasswordAuthentication no` remove
    the code path. `PermitRootLogin no` and `AllowGroups` would still have
    kept root and service accounts out even with passwords on.
  - **Don't "fix" it by changing `*` to `!` in shadow.** Without PAM, sshd
    treats `!` as a locked account and refuses key logins too.
  - **The general lesson:** embedded, musl and no-PAM builds take auth code
    paths mainstream glibc+PAM distros never exercise. Audit them as separate
    platforms.
- **2FA beyond FIDO2**, if policy demands it:
  `AuthenticationMethods publickey,keyboard-interactive:pam` with a TOTP PAM
  module. Know that this re-enables PAM auth prompts, so configure PAM to ask
  *only* for the OTP.
- **Certificates for teams.** Sign user keys with a CA:
  `ssh-keygen -s user_ca -I alice -n alice -V +8h id_ed25519.pub`. Set
  `TrustedUserCAKeys /etc/ssh/user_ca.pub`, and optionally
  `AuthorizedPrincipalsFile`. Short validity is the revocation story. Also
  sign host keys, so clients trust a `@cert-authority` line and never see TOFU
  prompts.

## 4. Reduce what an authenticated session can do

- `DisableForwarding yes` turns off TCP, agent, X11 and unix-socket forwarding.
  Re-enable per user or group in a `Match` block (see
  `90-match-examples.conf`: a tunnel-only user limited by
  `PermitOpen 127.0.0.1:5432`, and a chrooted SFTP group).
- `PermitTunnel no`, `PermitUserEnvironment no`, `PermitUserRC no`. Both
  `~/.ssh/environment` and `~/.ssh/rc` are quiet persistence and abuse points.
- **Agent forwarding is a liability.** Root on the remote host can use your
  agent while you are connected. Use `ssh -J bastion host` (ProxyJump)
  instead. It never exposes the agent.
- `MaxAuthTries 3`, `LoginGraceTime 20`, `MaxStartups 10:30:60`,
  `MaxSessions 4`. These bound pre-auth resource use.
- `LogLevel VERBOSE` logs the key fingerprint for each login. That is
  essential forensics when one of five keys turns out stolen.

## 5. Crypto: subtract, don't enumerate

Current OpenSSH defaults are strong and improve with each release. Hard-coded
algorithm lists copied from 2019 blog posts *remove* post-quantum KEX and
break on upgrades. Use the `-` prefix to drop legacy algorithms and keep
everything else:

```
KexAlgorithms -ecdh-sha2-*,diffie-hellman-group14-sha256,diffie-hellman-group-exchange-sha256
Ciphers -*-ctr
MACs -hmac-sha1*,umac-64*,hmac-sha2-256,hmac-sha2-512,umac-128@openssh.com
```

On 10.2 the effective KEX becomes `mlkem768x25519-sha256`,
`sntrup761x25519-sha512`, `curve25519-sha256`; the ciphers become
chacha20-poly1305 and AES-GCM; the MACs are ETM-only.

- Removing NIST ECDH is optional hygiene. Before applying it, check that every
  client still negotiates: `ssh -vv host 2>&1 | grep 'kex: algorithm'`.
- Serve only Ed25519 and RSA-3072+ host keys via explicit `HostKey` lines.
  Regenerate any weak RSA host key, and warn users about the fingerprint change.
- If DH group exchange is kept, filter `/etc/ssh/moduli` to ≥ 3071 bits.
- Verify from outside with `ssh-audit <host>`.
- Terrapin (CVE-2023-48795) is mitigated by strict KEX when *both* sides run
  ≥ 9.6. Old clients are the remaining exposure.

## 6. Brute force: native first

Per-attempt cost order, cheapest first:

1. **WireGuard-only SSH.** Zero attempts.
2. **nftables per-source rate limit** on new connections to the SSH port. A
   kernel-side dynamic set; no daemon. See `harden-firewall`'s `host_fw.nft`.
3. **`PerSourcePenalties`** in sshd (≥ 9.8, default on). Tighten for public
   SSH with `authfail:30 noauth:5 max:3600`. Exempt your monitoring and
   bastion addresses with `PerSourcePenaltyExemptList`.
4. **fail2ban or CrowdSec.** Only when you need log-driven bans across
   *several* services (mail, web logins), or shared blocklists. fail2ban is a
   Python daemon that parses logs: RAM and CPU on small VPSes, plus another
   root-running dependency. If used, ban via nftables sets (`banaction = nftables[type=multiport]`).
   For OpenSSH ≥ 9.8, filter on the journal (`backend = systemd`) so
   `sshd-session` entries are seen.

## 7. Lockout-safe rollout (follow exactly)

```sh
# 0. Preconditions: you have a WORKING key login as a non-root admin who is in the
#    allow-listed group; a provider console/rescue path is known.
groupadd -f ssh-users && usermod -aG ssh-users <admin>    # also every automation/deploy/tunnel account
#    RequiredRSASize 3072 rejects 2048-bit RSA keys (the AWS key-pair default!). List them first and
#    replace them, or comment that line out. Step 5 only tests YOUR key, not CI/deploy keys:
for f in /root/.ssh/authorized_keys /home/*/.ssh/authorized_keys /etc/ssh/authorized_keys/*; do
  [ -f "$f" ] && ssh-keygen -lf "$f" 2>/dev/null | grep ' (RSA)$' |
    while read -r bits rest; do if [ "$bits" -lt 3072 ]; then echo "WEAK RSA: $f $bits $rest"; fi; done
done
# 1. Snapshot
mkdir -p /root/harden && cp -a /etc/ssh /root/harden/ssh.$(date +%F-%H%M)
# 2. Install the drop-in, then validate the effective config
install -m 0644 00-hardening.conf /etc/ssh/sshd_config.d/00-hardening.conf
sshd -t && sshd -T -C user=<admin>,host=x,addr=<your-ip> | grep -Ei '^(passwordauth|permitroot|allowgroups|authenticationmethods)'
# 3. Dead-man switch: auto-revert in 5 minutes unless cancelled
systemd-run --collect --on-active=5min --unit=harden-ssh-rollback /bin/sh -c \
  'rm -f /etc/ssh/sshd_config.d/00-hardening.conf; systemctl reload ssh || systemctl reload sshd'
# 4. Apply (existing sessions survive a reload)
systemctl reload ssh 2>/dev/null || systemctl reload sshd
#    If Port/ListenAddress changed on a socket-activated host:
#    systemctl daemon-reload && systemctl restart ssh.socket   (and open the new port in the firewall FIRST)
# 5. From a NEW terminal — and NOT through a multiplexed master connection, which would reuse
#    the old authenticated channel and prove nothing: must succeed with your key...
ssh -o ControlMaster=no -o ControlPath=none -o IdentitiesOnly=yes -i ~/.ssh/<key> <admin>@<host> true
#    ...and must FAIL with "Permission denied (publickey)":
ssh -o ControlMaster=no -o ControlPath=none -o PubkeyAuthentication=no -o PreferredAuthentications=password,keyboard-interactive <admin>@<host>
ssh -o ControlMaster=no -o ControlPath=none root@<host>
# 6. Only now cancel the rollback
systemctl stop harden-ssh-rollback.timer
systemctl reset-failed harden-ssh-rollback.service harden-ssh-rollback.timer 2>/dev/null || true
```

- The drop-in is live in `sshd_config.d` as soon as it's installed, and the
  rollback timer doesn't survive a reboot. **Don't reboot inside the window.**
  For extra-cautious changes, first run a test instance on a spare port:
  `/usr/sbin/sshd -D -p 2222 -f /root/harden/sshd_config.test`, and log in
  there. That needs a temporary firewall rule.
- Never combine this with firewall changes in the same step. A rollback of one
  must not depend on the other.

## 8. Client side (the admin's laptop matters too)

In `~/.ssh/config`:

```
Host *
    HashKnownHosts yes
    ForwardAgent no
    ForwardX11 no
    UpdateHostKeys yes
    StrictHostKeyChecking ask
    IdentitiesOnly yes
    AddKeysToAgent confirm
Host app-*
    ProxyJump bastion
```

- `AddKeysToAgent confirm` makes every agent use pop up a confirmation, which
  blunts agent hijacking.
- Verify new host fingerprints out of band, from the provider console or the
  cloud-init output. Better still, use host certificates or SSHFP DNS records
  with DNSSEC.
- Remote Docker over SSH (`DOCKER_HOST=ssh://admin@host`) reuses all of this.
  Never expose the Docker API on TCP for convenience.

## 9. Dropbear (OpenWrt, Buildroot, embedded)

Dropbear is OpenWrt's default SSH server and common on embedded Linux. It was
not affected by sshhole. It has no `sshd_config`: policy is set with
command-line flags. Algorithms are fixed at **compile time**
(`localoptions.h`), so crypto hardening means building or choosing a current
release (`dropbear -V`), not editing config.

| Goal | Dropbear flag | OpenWrt `/etc/config/dropbear` (UCI) |
| --- | --- | --- |
| Keys only | `-s` (no password logins) | `option PasswordAuth 'off'` |
| No root password login | `-g` | `option RootPasswordAuth 'off'` |
| No root at all (needs a non-root admin; rare on OpenWrt) | `-w` | `option RootLogin 'off'` |
| Bind to the LAN, never WAN | `-p 192.168.1.1:22` | `option Interface 'lan'` |
| Fewer guesses per connection | `-T 3` | `option MaxAuthTries '3'` |
| No forwarding | `-j` (local), `-k` (remote) | (flags only) |
| Forwarded ports stay local | don't pass `-a` | `option GatewayPorts 'off'` |
| Drop idle sessions | `-I 600` | `option IdleTimeout '600'` |
| Restrict to a group | `-G <group>` (recent releases) | (flags only) |
| Never | `-B` (blank passwords) | — |

- **Keys.** On OpenWrt, root's keys live in `/etc/dropbear/authorized_keys`,
  not `~/.ssh`. Dropbear supports `restrict`-style options there
  (`no-port-forwarding,no-pty,command="..."`) for automation keys. Use
  Ed25519 keys.
- **WAN exposure.** OpenWrt's default firewall (fw4/nftables) rejects WAN
  input. Keep it that way, and use WireGuard on the router for remote admin
  (§2), plus `Interface 'lan'` so Dropbear doesn't even listen on WAN.
- **Apply and verify.** Run `uci commit dropbear && /etc/init.d/dropbear
  restart`, keeping the current session open. Then:
  - from a new connection, `ssh -o PubkeyAuthentication=no root@router`
    must fail;
  - `netstat -tln` (or `ss -tln`) must show only the LAN address.
- **If you ship OpenSSH instead** (`openssh-server` / `openssh-without-pam`),
  everything above applies, including sshhole. Those builds are musl and often
  PAM-less.

## Verification checklist

- `sshd -T` shows the intended values for a normal admin and for each Match
  case (`-C user=...,addr=...`).
- Password and kbd-interactive attempts fail. Root login fails. A non-group
  user fails. The admin key works.
- Outside view: `ssh-audit <host>` shows no legacy KEX, ciphers or MACs, and
  the PQ KEX is offered. With WireGuard-only SSH, `nmap -Pn -p 22 <public-ip>`
  shows filtered.
- `journalctl -t sshd -t sshd-session --since -1h` shows `LogLevel VERBOSE`
  fingerprints on login.
- `harden-audit` SSH section: no flags.
