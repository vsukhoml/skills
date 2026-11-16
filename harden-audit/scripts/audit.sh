#!/usr/bin/env bash
# harden-audit/scripts/audit.sh — READ-ONLY security inventory of a Linux host.
#
# Collects evidence for the harden-* skills: listeners, firewall kernel state
# (nft/iptables/ufw/firewalld), sysctl baseline diff, services/sockets/timers,
# effective sshd config, users/sudo/keys, persistence points, SUID and
# world-writable files, packages/repos, Docker daemon + containers, logging,
# and light compromise indicators. Ends with a severity-sorted FLAGS summary.
#
# It changes nothing and installs nothing (one temp file, removed on exit), and
# makes no network connections: Docker is queried ONLY via the local socket
# (DOCKER_HOST/contexts that point at remote daemons are overridden). Container
# env values and shadow hashes are never printed; a redaction filter masks
# credential-looking values (key=..., --password ..., user:pass@ in URLs) in
# crontabs, command lines and configs, best effort. The report is still
# sensitive: users, key fingerprints, topology, versions.
#
# Usage:  sudo bash audit.sh [--deep] [--no-docker] > audit-$(hostname)-$(date +%F).txt
#   --deep       also verify packaged files (dpkg --verify / rpm -Va), package
#                ownership of SUID and /usr/local binaries, and hash unmanaged
#                executables (slow on big hosts)
#   --no-docker  skip container inspection
# Remote:  scp audit.sh HOST:/tmp/ && ssh -t HOST 'sudo bash /tmp/audit.sh > /tmp/audit.txt' && scp HOST:/tmp/audit.txt .
# Without root it still runs; root-only sections are marked incomplete.
# Requires bash 4+, GNU coreutils/findutils, iproute2 (best effort elsewhere).

export LC_ALL=C
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
umask 077

DEEP=0
DOCKER=1
usage() { sed -n '2,/^$/s/^# \{0,1\}//p' "$0" 2>/dev/null; }
for a in "$@"; do
  case "$a" in
    --deep) DEEP=1 ;;
    --no-docker) DOCKER=0 ;;
    -h | --help) usage; exit 0 ;;
    *) echo "unknown option: $a" >&2; usage >&2; exit 2 ;;
  esac
done

# Talk only to the LOCAL rootful daemon, never a remote one via env or docker contexts.
unset DOCKER_CONTEXT
export DOCKER_HOST=unix:///var/run/docker.sock

# Best-effort masking of credential-looking values in everything this script prints.
# Test GNU `sed -u -E` + `/I` first; BusyBox/BSD `sed` lacks `-u` and would break the stdout pipe.
SED_REDACT=0
if printf 'a=1\n' | sed -u -E -e 's/(a=)[0-9]+/\1x/Ig' >/dev/null 2>&1; then
  SED_REDACT=1
fi
redact_stream() {
  if [ "$SED_REDACT" = 1 ]; then
    sed -u -E \
      -e 's#(://[^/:@[:space:]]+:)[^@/[:space:]]+@#\1<redacted>@#g' \
      -e 's/((pass(word|wd)?|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|auth[_-]?(token|key|secret|pass))[A-Za-z_]*["'"'"']?[[:space:]]*=[[:space:]]*["'"'"']?)[^[:space:]"'"'"';&]+/\1<redacted>/Ig' \
      -e 's/(--?(pass(word)?|secret|token|api-?key|auth-?(token|key|secret|pass))[= ])[^[:space:]]+/\1<redacted>/Ig'
  else
    awk '
      function redact_ci(s, pre, val,    out, lo, rstart, mlen, plen) {
        out = ""
        while (match(tolower(s), pre val)) {
          rstart = RSTART
          mlen = RLENGTH
          lo = substr(tolower(s), rstart, mlen)
          match(lo, "^" pre)
          plen = RLENGTH
          out = out substr(s, 1, rstart - 1 + plen) "<redacted>"
          s = substr(s, rstart + mlen)
        }
        return out s
      }
      {
        s = $0; out = ""
        while (match(s, /:\/\/[^\/:@ \t]+:[^@\/ \t]+@/)) {
          rstart = RSTART
          mlen = RLENGTH
          m = substr(s, rstart, mlen)
          match(m, /^:\/\/[^\/:@ \t]+:/)
          out = out substr(s, 1, rstart - 1 + RLENGTH) "<redacted>@"
          s = substr(s, rstart + mlen)
        }
        s = out s
        s = redact_ci(s, "(pass(word|wd)?|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|auth[_-]?(token|key|secret|pass))[a-z_]*[\"'\'']?[ \t]*=[ \t]*[\"'\'']?", "[^ \t\"'\'';&]+")
        s = redact_ci(s, "--?(pass(word)?|secret|token|api-?key|auth-?(token|key|secret|pass))[= ]", "[^ \t]+")
        print s
        fflush()
      }'
  fi
}
exec > >(redact_stream) 2>&1
REDACT_PID=$!

IS_ROOT=0
[ "$(id -u)" -eq 0 ] && IS_ROOT=1
FLAGS_FILE=$(mktemp) || exit 1
trap 'rm -f "$FLAGS_FILE"' EXIT

have() { command -v "$1" >/dev/null 2>&1; }
sec() { printf '\n\n########## %s ##########\n' "$*"; }
sub() { printf '\n--- %s\n' "$*"; }
# flag SEVERITY message: printed inline and collected for the summary.
flag() {
  printf '%s\t%s\n' "$1" "$2" >>"$FLAGS_FILE"
  printf '  >> [%s] %s\n' "$1" "$2"
}
# run 'shell command' [timeout-seconds]: echo the command, then capped output.
run() {
  printf '\n$ %s\n' "$1"
  timeout "${2:-60}" bash -c "$1" 2>&1 |
    awk -v m="${MAXLINES:-300}" 'NR<=m{print} NR==m+1{print "... (truncated at " m " lines)"}'
}
needroot() { [ "$IS_ROOT" -eq 1 ] || printf '  (incomplete: needs root)\n'; }

# Real (disk-backed) filesystems; container/snap trees pruned to avoid noise.
REALFS=$(findmnt -rn -o TARGET -t ext2,ext3,ext4,xfs,btrfs,zfs,f2fs,jfs 2>/dev/null | grep -vE '^/(var/lib/(docker|containerd|containers|lxd|incus)|snap|var/snap)(/|$)' | sort -u)
[ -n "$REALFS" ] || REALFS=/
FIND_PRUNE=(\( -path /proc -o -path /sys -o -path /dev -o -path /run
  -o -path /var/lib/docker -o -path /var/lib/containerd -o -path /var/lib/containers
  -o -path /snap -o -path /var/snap -o -path /var/lib/lxd -o -path /var/lib/incus \) -prune -o)
fs_find() {
  local m
  for m in $REALFS; do
    timeout 120 find "$m" -xdev "${FIND_PRUNE[@]}" "$@" -print 2>/dev/null
  done | sort -u
}

printf 'harden-audit report — %s — host %s — root=%s deep=%s\n' \
  "$(date -u +%FT%TZ)" "$(hostname)" "$IS_ROOT" "$DEEP"
[ "$IS_ROOT" -eq 1 ] || printf 'WARNING: not running as root; several sections will be incomplete.\n'

###############################################################################
sec "HOST"
run 'grep -E "^(PRETTY_NAME|VERSION_ID)=" /etc/os-release'
run 'uname -srvm; v=$(systemd-detect-virt 2>/dev/null); echo "virt: ${v:-unknown}"; uptime'
run 'cat /proc/cmdline'
grep -qw 'mitigations=off' /proc/cmdline 2>/dev/null &&
  flag HIGH "Kernel booted with mitigations=off (CPU speculative-execution mitigations disabled)"
run 'echo "tainted=$(cat /proc/sys/kernel/tainted)"; echo "lockdown=$(cat /sys/kernel/security/lockdown 2>/dev/null)"; echo "lsm=$(cat /sys/kernel/security/lsm 2>/dev/null)"'
HWCFI_CPU=$(grep -m1 -E '^(flags|Features)\b' /proc/cpuinfo 2>/dev/null | tr ' ' '\n' | grep -xE 'user_shstk|shstk|ibt|paca|pacg|bti|mte|mte3' | sort -u | tr '\n' ' ')
printf '  cpu hardware CFI/tag features: %s\n' "${HWCFI_CPU:-none advertised}"
VULN_CPU=$(grep -H '^Vulnerable' /sys/devices/system/cpu/vulnerabilities/* 2>/dev/null | sed 's#.*/##')
if [ -n "$VULN_CPU" ]; then
  printf '%s\n' "$VULN_CPU" | sed 's/^/  cpu-vuln: /'
  flag MEDIUM "Unmitigated CPU hardware vulnerabilities reported: $(printf '%s' "$VULN_CPU" | cut -d: -f1 | tr '\n' ' ')"
fi
LSM=$(cat /sys/kernel/security/lsm 2>/dev/null)
case "$LSM" in
  *apparmor*) if have aa-status; then
      run 'aa-status 2>&1 | head -12'
      aa-status --enabled 2>/dev/null || flag MEDIUM "AppArmor LSM present but not enabled"
    fi ;;
  *selinux*) if have getenforce; then
      run 'getenforce; sestatus 2>/dev/null | head -8'
      [ "$(getenforce 2>/dev/null)" = Enforcing ] || flag MEDIUM "SELinux not in Enforcing mode ($(getenforce 2>/dev/null))"
    fi ;;
  *) flag MEDIUM "No mandatory access control (AppArmor/SELinux) active" ;;
esac

###############################################################################
sec "UPDATES"
RUNNING_K=$(uname -r)
# Compare within the same flavor (-generic, -oem, -amd64, ...); sort -V across flavors is meaningless.
K_FLAVOR=${RUNNING_K##*-}
case "$K_FLAVOR" in *[!0-9.]*) ;; *) K_FLAVOR="" ;; esac
NEWEST_K=$(ls -1 /boot/vmlinuz-* 2>/dev/null | sed 's|/boot/vmlinuz-||' | grep -E -- "${K_FLAVOR:+-$K_FLAVOR}\$" | sort -V | tail -1)
printf '  running kernel %s, newest installed %s\n' "$RUNNING_K" "${NEWEST_K:-?}"
K_STALE=0
[ -n "$NEWEST_K" ] && [ "$NEWEST_K" != "$RUNNING_K" ] && K_STALE=1
RR_PKGS=$(tr '\n' ' ' </var/run/reboot-required.pkgs 2>/dev/null)
if [ "$K_STALE" = 1 ]; then
  flag HIGH "Running kernel $RUNNING_K is not the newest installed ($NEWEST_K); reboot to activate fixes${RR_PKGS:+ (also pending: $RR_PKGS)}"
elif [ -f /var/run/reboot-required ]; then
  # The running kernel is current for its flavor: other-flavor kernels and desktop/session
  # packages in this list often need only a logout or a service restart.
  flag MEDIUM "Restart requested for: ${RR_PKGS:-unknown packages} (running kernel is the newest of its flavor)"
fi
if have apt-config; then
  run 'apt-config dump 2>/dev/null | grep -E "^(APT::Periodic::(Update-Package-Lists|Unattended-Upgrade)|Unattended-Upgrade::(Origins-Pattern|Allowed-Origins|Automatic-Reboot))"'
  UU=$(apt-config dump 2>/dev/null | awk -F'"' '/^APT::Periodic::Unattended-Upgrade /{print $2}')
  if ! dpkg-query -W -f='${Status}' unattended-upgrades 2>/dev/null | grep -q 'ok installed'; then
    flag MEDIUM "unattended-upgrades not installed (no automatic security updates)"
  elif [ "${UU:-0}" = 0 ]; then
    flag MEDIUM "unattended-upgrades installed but APT::Periodic::Unattended-Upgrade is 0/unset"
  fi
  run 'grep -h "^Start-Date" /var/log/apt/history.log 2>/dev/null | tail -3; echo "held: $(apt-mark showhold 2>/dev/null | tr "\n" " ")"'
fi
if have rpm; then
  run 'for t in dnf-automatic.timer dnf-automatic-install.timer dnf5-automatic.timer; do printf "%s=%s " $t "$(systemctl is-enabled $t 2>/dev/null || echo absent)"; done; echo; rpm -qa --last 2>/dev/null | head -5'
fi
have needrestart && run 'needrestart -b -r l 2>/dev/null' 120

###############################################################################
sec "LISTENING SOCKETS (inside view; confirm from OUTSIDE over IPv4 and IPv6)"
needroot
sensitive_port() {
  case "$1" in
    2375 | 2376) echo docker-api ;; 2379 | 2380) echo etcd ;; 3306) echo mysql ;; 33060) echo mysqlx ;;
    5432) echo postgres ;; 6432) echo pgbouncer ;; 6379 | 6380) echo redis ;; 26379) echo redis-sentinel ;;
    27017 | 27018 | 27019) echo mongodb ;; 9200 | 9300) echo elasticsearch ;; 5601) echo kibana ;;
    11211) echo memcached ;; 5672 | 15672 | 25672 | 4369) echo rabbitmq/epmd ;; 9092 | 2181) echo kafka/zookeeper ;;
    8086) echo influxdb ;; 8123 | 9000 | 9004 | 9009) echo clickhouse/minio/php-fpm ;; 6333 | 6334) echo qdrant ;;
    8529) echo arangodb ;; 5984) echo couchdb ;; 7474 | 7687) echo neo4j ;; 9042) echo cassandra ;;
    9090) echo prometheus ;; 9100) echo node-exporter ;; 3000) echo grafana ;; 6443 | 10250) echo kubernetes ;;
    5000) echo registry ;; 8888) echo jupyter ;; 9443) echo portainer ;; 4222) echo nats ;; 1883) echo mqtt ;;
    11434) echo ollama ;; 111) echo rpcbind ;; 2049) echo nfs ;; 139 | 445) echo smb ;; 631) echo cups/ipp ;;
    5353) echo mdns ;; 23) echo telnet ;; 21) echo ftp ;; 69) echo tftp ;; 161) echo snmp ;; 873) echo rsync ;;
    5900 | 5901) echo vnc ;; 3389) echo rdp ;; 25) echo smtp ;; 53) echo dns ;;
  esac
}
if have ss; then
  run 'ss -H -tulpn'
  ss -H -tulpn 2>/dev/null | while read -r netid _state _rq _sq local _peer proc; do
    port=${local##*:}
    addr=${local%:*}
    addr=${addr%%\%*}
    addr=${addr#[}
    addr=${addr%]}
    # loopback, link-local and multicast group memberships are not exposure
    case "$addr" in 127.* | ::1 | ::ffff:127.* | fe80:* | 22[4-9].* | 23[0-9].* | ff[0-9a-f][0-9a-f]:*) continue ;; esac
    scope=specific-address
    case "$addr" in 0.0.0.0 | ::ffff:0.0.0.0 | '*' | :: | '') scope=ALL-interfaces ;; esac
    pname=$(printf '%s' "$proc" | sed -n 's/.*(("\([^"]*\)".*/\1/p')
    name=$(sensitive_port "$port")
    if [ -n "$name" ]; then
      # mDNS is a link-local multicast protocol: expected on desktops/laptops, a LAN-scope leak elsewhere.
      sev=HIGH; [ "$name" = mdns ] && sev=MEDIUM
      flag "$sev" "$name ($port/$netid) listens on ${addr:-*} [$scope] proc=${pname:-?}; verify it is unreachable from the internet"
    else
      printf '  non-loopback listener: %s %s:%s [%s] proc=%s\n' "$netid" "${addr:-*}" "$port" "$scope" "${pname:-?}"
    fi
  done
  run 'ss -H -xlp 2>/dev/null | grep -E "docker|containerd|podman|libvirt|mysql|postgres|redis|mongo" | head -20'
elif have netstat; then
  run 'netstat -tulpn'
fi
echo "  NOTE: with Docker userland-proxy disabled, published ports have NO listener here; see DOCKER section (nat DNAT rules)."

###############################################################################
sec "FIREWALL (kernel state, not config files)"
needroot
run 'iptables -V 2>&1; nft --version 2>&1'
NFT_RS=""
if have nft && [ "$IS_ROOT" -eq 1 ]; then
  NFT_RS=$(nft list ruleset 2>/dev/null)
  run 'nft list ruleset' 60
fi
if [ "$IS_ROOT" -eq 1 ]; then
  for v in iptables-legacy-save ip6tables-legacy-save; do
    have "$v" || continue
    out=$($v 2>/dev/null | grep -vE '^(#|\*|:|COMMIT)')
    if [ -n "$out" ]; then
      sub "$v (legacy backend rules — evaluated IN ADDITION to nftables)"
      printf '%s\n' "$out" | head -100
      flag MEDIUM "Legacy iptables rules coexist with nftables ($v); two rule sets apply — consolidate"
    fi
  done
fi
V4DROP=0
V6DROP=0
V4FWDDROP=0
V6FWDDROP=0
if [ -n "$NFT_RS" ]; then
  read -r V4DROP V6DROP V4FWDDROP V6FWDDROP < <(printf '%s\n' "$NFT_RS" | awk '
    /^table /{f=$2}
    /hook input/ && /policy drop/ {if(f=="inet"){a=1;b=1} else if(f=="ip")a=1; else if(f=="ip6")b=1}
    /hook forward/ && /policy drop/ {if(f=="inet"){c=1;d=1} else if(f=="ip")c=1; else if(f=="ip6")d=1}
    END{print a+0, b+0, c+0, d+0}')
fi
if [ "$IS_ROOT" -eq 1 ] && iptables -V 2>/dev/null | grep -q legacy; then
  iptables -S INPUT 2>/dev/null | grep -q '^-P INPUT DROP' && V4DROP=1
  ip6tables -S INPUT 2>/dev/null | grep -q '^-P INPUT DROP' && V6DROP=1
  iptables -S FORWARD 2>/dev/null | grep -q '^-P FORWARD DROP' && V4FWDDROP=1
  ip6tables -S FORWARD 2>/dev/null | grep -q '^-P FORWARD DROP' && V6FWDDROP=1
fi
HAS_V6=$(ip -6 addr show scope global 2>/dev/null | grep -c inet6)
if [ "$IS_ROOT" -eq 1 ]; then
  [ "$V4DROP" = 1 ] || flag HIGH "No IPv4 input chain with 'policy drop' found — host may be default-allow (a final drop rule also counts; verify)"
  if [ "${HAS_V6:-0}" -gt 0 ] && [ "$V6DROP" != 1 ]; then
    flag HIGH "Host has global IPv6 but no IPv6 input chain with 'policy drop'"
  fi
  if [ "$(sysctl -n net.ipv4.ip_forward 2>/dev/null)" = 1 ] && [ "$V4FWDDROP" != 1 ]; then
    flag MEDIUM "IPv4 forwarding enabled and no IPv4/inet forward chain with 'policy drop' — host may route between interfaces"
  fi
  if [ "$(sysctl -n net.ipv6.conf.all.forwarding 2>/dev/null)" = 1 ] && [ "$V6FWDDROP" != 1 ]; then
    flag MEDIUM "IPv6 forwarding enabled and no IPv6/inet forward chain with 'policy drop' — host may route between interfaces"
  fi
fi
UFW_ACTIVE=0
if have ufw; then
  run 'ufw status verbose 2>&1'
  ufw status 2>/dev/null | grep -q 'Status: active' && UFW_ACTIVE=1
  if [ "${HAS_V6:-0}" -gt 0 ] && grep -q '^IPV6=no' /etc/default/ufw 2>/dev/null; then
    flag HIGH "ufw has IPV6=no but the host has global IPv6: IPv6 is unfiltered by ufw"
  fi
fi
if have firewall-cmd && firewall-cmd --state >/dev/null 2>&1; then
  run 'firewall-cmd --get-active-zones; firewall-cmd --list-all; firewall-cmd --zone=docker --list-all 2>/dev/null'
fi
if [ "$IS_ROOT" -eq 1 ] && have iptables; then
  run 'iptables -S DOCKER-USER 2>/dev/null; ip6tables -S DOCKER-USER 2>/dev/null; iptables -t nat -S DOCKER 2>/dev/null | grep -- "-j DNAT"; ip6tables -t nat -S DOCKER 2>/dev/null | grep -- "-j DNAT"'
fi

###############################################################################
sec "SYSCTL vs harden-host baseline"
# key op want severity  (op: eq = exact, ge = at least)
while read -r key op want sev; do
  [ -n "$key" ] || continue
  cur=$(sysctl -n "$key" 2>/dev/null) || { printf '  ?? %-44s (absent on this kernel)\n' "$key"; continue; }
  ok=1
  case "$op" in
    eq) [ "$cur" = "$want" ] || ok=0 ;;
    ge) [ "$cur" -ge "$want" ] 2>/dev/null || ok=0 ;;
  esac
  if [ "$ok" = 1 ]; then
    printf '  ok %-44s = %s\n' "$key" "$cur"
  else
    printf '  !! %-44s = %-4s (want %s %s)\n' "$key" "$cur" "$op" "$want"
    if [ "$sev" = LOW ]; then WEAK_LOW="${WEAK_LOW:-}$key=$cur "; else flag "$sev" "sysctl $key = $cur (want $op $want)"; fi
  fi
done <<'EOF'
kernel.randomize_va_space eq 2 HIGH
fs.protected_hardlinks eq 1 MEDIUM
fs.protected_symlinks eq 1 MEDIUM
kernel.unprivileged_bpf_disabled ge 1 MEDIUM
net.ipv4.tcp_syncookies eq 1 MEDIUM
kernel.kptr_restrict ge 1 LOW
kernel.dmesg_restrict eq 1 LOW
kernel.perf_event_paranoid ge 2 LOW
kernel.yama.ptrace_scope ge 1 LOW
net.core.bpf_jit_harden ge 1 LOW
fs.protected_fifos ge 1 LOW
fs.protected_regular ge 1 LOW
fs.suid_dumpable eq 0 LOW
dev.tty.ldisc_autoload eq 0 LOW
vm.unprivileged_userfaultfd eq 0 LOW
net.ipv4.conf.all.accept_redirects eq 0 LOW
net.ipv4.conf.default.accept_redirects eq 0 LOW
net.ipv6.conf.all.accept_redirects eq 0 LOW
net.ipv6.conf.default.accept_redirects eq 0 LOW
net.ipv4.conf.all.secure_redirects eq 0 LOW
net.ipv4.conf.all.send_redirects eq 0 LOW
net.ipv4.conf.all.accept_source_route eq 0 LOW
net.ipv6.conf.all.accept_source_route eq 0 LOW
net.ipv4.conf.all.rp_filter ge 1 LOW
net.ipv4.icmp_echo_ignore_broadcasts eq 1 LOW
net.ipv4.tcp_rfc1337 eq 1 LOW
EOF
[ -n "${WEAK_LOW:-}" ] && flag LOW "sysctl values weaker than baseline: $WEAK_LOW"
sub "Informational (decide per workload; see harden-host)"
for k in kernel.kexec_load_disabled kernel.io_uring_disabled user.max_user_namespaces \
  kernel.apparmor_restrict_unprivileged_userns kernel.modules_disabled kernel.sysrq \
  dev.tty.legacy_tiocsti net.ipv4.ip_forward net.ipv6.conf.all.forwarding \
  net.ipv6.conf.all.accept_ra kernel.core_pattern net.netfilter.nf_conntrack_max; do
  printf '  %-46s = %s\n' "$k" "$(sysctl -n "$k" 2>/dev/null || echo absent)"
done

###############################################################################
sec "SERVICES, SOCKETS, TIMERS"
run 'systemctl list-units --type=service --state=running --no-pager --no-legend --plain | cut -d" " -f1 | tr "\n" " "; echo'
run 'systemctl list-sockets --no-pager --no-legend 2>/dev/null'
run 'systemctl list-timers --all --no-pager --no-legend 2>/dev/null | head -40'
run 'systemctl --failed --no-pager --no-legend --plain 2>/dev/null'
for s in avahi-daemon cups rpcbind nfs-server smbd nmbd xinetd inetd vsftpd proftpd tftpd-hpa snmpd \
  bluetooth ModemManager rsync telnetd apport whoopsie; do
  systemctl is-active --quiet "$s.service" 2>/dev/null && flag MEDIUM "service '$s' is running; remove or mask unless required"
done
if systemctl is-active --quiet cups-browsed.service 2>/dev/null; then
  # The 2024 remote chain needs the legacy CUPS browse socket on UDP 631; DNS-SD-only
  # setups (BrowseRemoteProtocols dnssd) only allow printer spoofing from the same LAN.
  if ss -Huln 'sport = :631' 2>/dev/null | grep -q .; then
    flag HIGH "cups-browsed listens on UDP 631 (2024 unauthenticated RCE chain) — remove, or set BrowseRemoteProtocols none"
  else
    flag LOW "cups-browsed is running (DNS-SD only, UDP 631 closed): LAN-adjacent printer spoofing remains — remove on servers"
  fi
fi
run 'systemd-analyze security --no-pager 2>/dev/null | sort -k2 -nr | head -40' 120

###############################################################################
sec "SSH SERVER"
run 'ssh -V 2>&1; for u in ssh.socket sshd.socket ssh.service sshd.service; do printf "%s=%s " $u "$(systemctl is-active $u 2>/dev/null)"; done; echo'
run 'ls -la /etc/ssh/sshd_config.d/ 2>/dev/null'
systemctl is-active --quiet ssh.socket 2>/dev/null &&
  flag INFO "sshd is socket-activated (ssh.socket): Port/ListenAddress changes need 'systemctl daemon-reload && systemctl restart ssh.socket'"
SSHD_T=""
if [ "$IS_ROOT" -eq 1 ] && have sshd; then
  SSHD_T=$(sshd -T 2>/dev/null)
fi
if [ -n "$SSHD_T" ]; then
  sub "effective config (sshd -T, selected)"
  printf '%s\n' "$SSHD_T" | grep -Ei '^(port|listenaddress|addressfamily|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|permitemptypasswords|pubkeyauthentication|authenticationmethods|usepam|allowusers|allowgroups|denyusers|denygroups|maxauthtries|logingracetime|maxstartups|persourcepenalties|x11forwarding|allowtcpforwarding|allowagentforwarding|disableforwarding|permittunnel|authorizedkeysfile|loglevel|kexalgorithms|ciphers|macs|requiredrsasize|clientaliveinterval|permituserenvironment) ' | sed 's/^/  /'
  sv() { printf '%s\n' "$SSHD_T" | awk -v k="$1" '$1==k{$1=""; sub(/^ /,""); print; exit}'; }
  case "$(sv permitrootlogin)" in
    yes) flag HIGH "sshd PermitRootLogin yes" ;;
    prohibit-password | without-password) flag LOW "sshd PermitRootLogin prohibit-password (root key login allowed; prefer 'no' + sudo)" ;;
  esac
  [ "$(sv passwordauthentication)" = yes ] && flag HIGH "sshd PasswordAuthentication yes"
  [ "$(sv permitemptypasswords)" = yes ] && flag CRITICAL "sshd PermitEmptyPasswords yes"
  [ "$(sv kbdinteractiveauthentication)" = yes ] && [ "$(sv usepam)" = yes ] &&
    flag MEDIUM "sshd KbdInteractiveAuthentication yes with UsePAM: PAM password prompts still possible"
  if [ "$(sv disableforwarding)" != yes ]; then
    [ "$(sv x11forwarding)" = yes ] && flag LOW "sshd X11Forwarding yes"
    [ "$(sv allowagentforwarding)" = yes ] && flag LOW "sshd AllowAgentForwarding yes (hijackable by root on this host)"
  fi
  MAT=$(sv maxauthtries)
  [ "${MAT:-6}" -gt 4 ] 2>/dev/null && flag LOW "sshd MaxAuthTries $MAT (suggest 3)"
  [ -z "$(sv allowusers)$(sv allowgroups)" ] && flag LOW "sshd has no AllowUsers/AllowGroups allow-list"
  printf '%s\n' "$SSHD_T" | grep -iE '^(ciphers|macs|kexalgorithms) ' | grep -qiE 'cbc|hmac-sha1|hmac-md5|group1-|group14-sha1|3des|arcfour' &&
    flag MEDIUM "sshd offers legacy crypto (CBC/SHA1/MD5/group1/3DES)"
  printf '%s\n' "$SSHD_T" | grep -qi '^permituserenvironment yes' && flag MEDIUM "sshd PermitUserEnvironment yes"
  # sshhole (Nov 2026; https://sshhole.com, Alpine advisory 2026-11-05, OpenSSH 10.6p2):
  # sshd that checks passwords itself (musl libc, or UsePAM no) accepted any
  # 257-1024 char password for accounts whose shadow hash is exactly "*". Fixed in OpenSSH 10.6p2.
  if [ "$(sv usepam)" != yes ] && { [ "$(sv passwordauthentication)" = yes ] || [ "$(sv kbdinteractiveauthentication)" = yes ]; }; then
    LIBC=glibc
    ls /lib/ld-musl-*.so.1 >/dev/null 2>&1 && LIBC=musl
    SSHV=$( { sshd -V 2>&1 || ssh -V 2>&1; } | sed -n 's/^OpenSSH_\([0-9][0-9.]*p[0-9]*\).*/\1/p' | head -1)
    STAR=$(awk -F: '$2=="*"{printf "%s ",$1}' /etc/shadow 2>/dev/null)
    if [ -n "$SSHV" ] && [ "$(printf '%s\n' 10.6p2 "$SSHV" | sort -V | head -1)" = 10.6p2 ]; then
      flag MEDIUM "sshd checks passwords without PAM ($LIBC, OpenSSH $SSHV: sshhole-patched) and password auth is on — prefer keys only"
    else
      # Distros backport fixes without bumping the upstream version (Alpine fixed 3.16+), so a
      # version below 10.6p2 means "check the package against the advisory", not "proven vulnerable".
      PKG=$(apk list -I openssh-server 2>/dev/null | cut -d' ' -f1)
      flag HIGH "sshhole preconditions: $LIBC sshd without PAM + password auth on, OpenSSH ${SSHV:-?} ${PKG:+($PKG) }< upstream fix 10.6p2 (verify distro backport); '*' accounts: ${STAR:-none found}. Set PasswordAuthentication no; upgrade; RESTART sshd"
    fi
  fi
else
  ls /lib/ld-musl-*.so.1 >/dev/null 2>&1 &&
    flag INFO "musl libc host: re-run as root to check sshhole conditions (UsePAM/PasswordAuthentication/'*' accounts/OpenSSH < 10.6p2)"
  run 'grep -HEi "^\s*(include|port|listenaddress|permitrootlogin|passwordauthentication|kbdinteractiveauthentication|allowusers|allowgroups|match)\b" /etc/ssh/sshd_config /etc/ssh/sshd_config.d/*.conf 2>/dev/null'
  echo "  (config-file view only; run as root for effective 'sshd -T' values — first value read wins)"
fi
run 'for k in /etc/ssh/ssh_host_*_key.pub; do ssh-keygen -lf "$k"; done 2>/dev/null'
ls /etc/ssh/ssh_host_dsa_key* >/dev/null 2>&1 && flag LOW "DSA host key present (unsupported since OpenSSH 10; remove)"

###############################################################################
sec "USERS, PRIVILEGE, KEYS"
sub "UID 0 accounts"
awk -F: '$3==0{print "  "$1}' /etc/passwd
EXTRA0=$(awk -F: '$3==0 && $1!="root"{printf "%s ",$1}' /etc/passwd)
[ -n "$EXTRA0" ] && flag CRITICAL "non-root UID 0 account(s): $EXTRA0"
sub "Accounts with a login shell"
awk -F: '$7 !~ /(nologin|false|sync|shutdown|halt)$/ {printf "  %-16s uid=%-6s home=%-24s shell=%s\n",$1,$3,$6,$7}' /etc/passwd
if [ "$IS_ROOT" -eq 1 ]; then
  sub "Password state (from shadow; hashes not printed)"
  awk -F: '$2=="" {print "  EMPTY PASSWORD: " $1}
           $2 !~ /^[!*]/ && $2!="" {printf "  password set: %-16s hash-type=%s\n", $1, substr($2,1,3)}' /etc/shadow
  EMPTYPW=$(awk -F: '$2==""{printf "%s ",$1}' /etc/shadow)
  [ -n "$EMPTYPW" ] && flag CRITICAL "accounts with EMPTY password: $EMPTYPW"
  sub "sudoers (non-comment lines)"
  grep -rHvE '^\s*(#|$)' /etc/sudoers /etc/sudoers.d/ 2>/dev/null | sed 's/^/  /'
  NOPW=$(grep -rhE '^\s*[^#].*NOPASSWD' /etc/sudoers /etc/sudoers.d/ 2>/dev/null | head -5 | tr '\n' ';')
  [ -n "$NOPW" ] && flag MEDIUM "NOPASSWD sudo rules (SSH key compromise = root): $NOPW"
fi
sub "Members of root-equivalent / sensitive groups"
for g in sudo wheel admin docker lxd incus-admin libvirt disk shadow adm; do
  m=$(getent group "$g" | cut -d: -f4)
  [ -n "$m" ] && printf '  %-12s %s\n' "$g" "$m"
done
# Each of these groups can get root without a password: docker/lxd/incus can mount / into a
# privileged container, libvirt can boot a VM on the host's disks, disk can write raw block devices.
for g in docker lxd incus-admin libvirt disk; do
  m=$(getent group "$g" | cut -d: -f4)
  [ -n "$m" ] && flag MEDIUM "$g group members are root-equivalent (password-free root, bypasses sudo): $m"
done
sub "authorized_keys files (fingerprints only)"
AKF=$(printf '%s\n' "$SSHD_T" | awk '$1=="authorizedkeysfile"{$1=""; print}')
printf '  AuthorizedKeysFile: %s\n' "${AKF:-(default .ssh/authorized_keys .ssh/authorized_keys2)}"
{
  awk -F: '{print $1":"$6}' /etc/passwd
  [ -d /etc/ssh/authorized_keys ] && for f in /etc/ssh/authorized_keys/*; do echo "${f##*/}:@$f"; done
} | sort -u -t: -k2,2 | while IFS=: read -r user home; do
  for f in "$home/.ssh/authorized_keys" "$home/.ssh/authorized_keys2"; do
    case "$home" in @*) f=${home#@} ;; esac
    [ -r "$f" ] && [ -f "$f" ] || continue
    printf '  %s (user %s): %s key line(s), mode %s, owner %s\n' "$f" "$user" \
      "$(grep -cvE '^\s*(#|$)' "$f")" "$(stat -c %a "$f")" "$(stat -c %U "$f")"
    ssh-keygen -lf "$f" 2>/dev/null | sed 's/^/      /'
    grep -qE '(from=|restrict|command=)' "$f" && printf '      (some keys carry from=/restrict/command= options)\n'
    case "$f" in *authorized_keys2) flag LOW "legacy authorized_keys2 in use: $f" ;; esac
    case "$home" in @*) break ;; esac
  done
done
have last && run 'last -n 15 -a -i 2>/dev/null | head -18'
if have journalctl; then
  run 'journalctl --since=-7d -q --no-pager -t sshd -t sshd-session 2>/dev/null | grep -E "Accepted " | awk "{for(i=1;i<=NF;i++) if(\$i==\"Accepted\") print \$(i+1), \$(i+3), \$(i+5)}" | sort | uniq -c | sort -rn | head -20' 90
  NF24=$(timeout 60 journalctl --since=-24h -q --no-pager -t sshd -t sshd-session 2>/dev/null | grep -cE 'Failed |Invalid user')
  printf '  failed/invalid SSH auth attempts in last 24h: %s\n' "${NF24:-?}"
  APW=$(timeout 60 journalctl --since=-7d -q --no-pager -t sshd -t sshd-session 2>/dev/null | grep -c 'Accepted password')
  [ "${APW:-0}" -gt 0 ] && flag HIGH "$APW password-based SSH logins accepted in the last 7 days"
fi

###############################################################################
sec "SCHEDULED TASKS & PERSISTENCE POINTS"
run 'grep -vE "^\s*(#|$)" /etc/crontab 2>/dev/null; ls -la /etc/cron.d /etc/cron.hourly /etc/cron.daily /etc/cron.weekly /etc/cron.monthly 2>/dev/null'
if [ "$IS_ROOT" -eq 1 ]; then
  for f in /var/spool/cron/crontabs/* /var/spool/cron/*; do
    [ -f "$f" ] || continue
    sub "user crontab $f"
    grep -vE '^\s*(#|$)' "$f" | sed 's/^/  /'
  done
fi
if [ -s /etc/ld.so.preload ]; then
  sub "/etc/ld.so.preload"
  cat /etc/ld.so.preload
  flag HIGH "/etc/ld.so.preload is non-empty — classic userland rootkit hook; verify every entry"
fi
run 'find /etc/systemd/system /etc/systemd/user /usr/local/lib/systemd -maxdepth 2 -type f \( -name "*.service" -o -name "*.timer" -o -name "*.socket" -o -name "*.path" \) -printf "%TY-%Tm-%Td %p\n" 2>/dev/null | sort -r | head -40'
run 'find /root/.config/systemd /home/*/.config/systemd -type f 2>/dev/null | head -20'
run 'ls -la /etc/rc.local 2>/dev/null; echo "profile.d: $(ls /etc/profile.d/ 2>/dev/null | tr "\n" " ")"; grep -rlE "pam_exec|pam_script" /etc/pam.d/ 2>/dev/null'

###############################################################################
sec "FILESYSTEMS & PERMISSIONS"
for m in / /tmp /var/tmp /dev/shm /home /boot /proc; do
  o=$(findmnt -n -o FSTYPE,OPTIONS -M "$m" 2>/dev/null)
  printf '  %-9s %s\n' "$m" "${o:-(not a separate mount)}"
done
findmnt -n -o OPTIONS -M /dev/shm 2>/dev/null | grep -q noexec || flag LOW "/dev/shm lacks noexec"
TMPO=$(findmnt -n -o OPTIONS -M /tmp 2>/dev/null)
case "$TMPO" in
  '') flag LOW "/tmp is not a separate (tmpfs) mount with nosuid,nodev" ;;
  *nosuid*nodev* | *nodev*nosuid*) ;;
  *) flag LOW "/tmp mounted without nosuid,nodev ($TMPO)" ;;
esac
sub "SUID/SGID files"
SUIDS=$(fs_find -type f \( -perm -4000 -o -perm -2000 \))
printf '%s\n' "$SUIDS" | sed '/^$/d; s/^/  /'
ODD_SUID=$(printf '%s\n' "$SUIDS" | grep -E '^/(home|root|tmp|var/tmp|dev/shm|srv)/')
if [ -n "$ODD_SUID" ]; then
  flag HIGH "$(printf '%s\n' "$ODD_SUID" | wc -l) SUID/SGID file(s) under home/temp/srv (build trees are benign; otherwise investigate): $(printf '%s\n' "$ODD_SUID" | head -3 | tr '\n' ' ')"
fi
sub "World-writable directories without sticky bit"
WWD=$(fs_find -type d -perm -0002 ! -perm -1000 | head -50)
printf '%s\n' "$WWD" | sed '/^$/d; s/^/  /'
[ -n "$WWD" ] && flag MEDIUM "world-writable directories without sticky bit: $(printf '%s' "$WWD" | head -5 | tr '\n' ' ')"
sub "World-writable files"
WWF=$(fs_find -type f -perm -0002 | head -50)
printf '%s\n' "$WWF" | sed '/^$/d; s/^/  /'
[ -n "$WWF" ] && flag MEDIUM "world-writable files: $(printf '%s' "$WWF" | head -5 | tr '\n' ' ')"
sub "Executables in temp directories"
TMPX=$(find /tmp /var/tmp /dev/shm -xdev -type f -perm /111 2>/dev/null | head -30)
printf '%s\n' "$TMPX" | sed '/^$/d; s/^/  /'
[ -n "$TMPX" ] && flag MEDIUM "executable files in temp dirs (common malware staging): $(printf '%s' "$TMPX" | head -3 | tr '\n' ' ')"
sub "Sensitive file modes"
stat -c '  %a %U:%G %n' /etc/passwd /etc/shadow /etc/gshadow /etc/sudoers /etc/ssh/sshd_config /etc/ssh/ssh_host_*_key 2>/dev/null
SHM=$(stat -c %a /etc/shadow 2>/dev/null)
[ -n "$SHM" ] && [ $((8#$SHM & 4)) -ne 0 ] && flag CRITICAL "/etc/shadow is world-readable ($SHM)"
for k in /etc/ssh/ssh_host_*_key; do
  [ -f "$k" ] || continue
  km=$(stat -c %a "$k")
  [ $((8#$km & 077)) -ne 0 ] && flag HIGH "SSH host private key $k has mode $km (want 600)"
done

###############################################################################
sec "PACKAGES, REPOSITORIES, UNMANAGED SOFTWARE"
if have dpkg-query; then
  printf '  installed deb packages: %s\n' "$(dpkg-query -W -f='${binary:Package}\n' 2>/dev/null | wc -l)"
  run 'grep -rHE "^\s*(deb|deb-src)\s|^\s*(Types|URIs|Suites|Components|Signed-By|Enabled):" /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null'
  TRUSTED=$(grep -rlE '\[[^]]*trusted=yes|^\s*Trusted:\s*yes' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null)
  [ -n "$TRUSTED" ] && flag CRITICAL "APT source with trusted=yes (signature checks disabled): $TRUSTED"
  [ -s /etc/apt/trusted.gpg ] && flag MEDIUM "legacy /etc/apt/trusted.gpg keyring: keys there can sign ANY repo; move to per-repo Signed-By"
  run 'ls -la /etc/apt/trusted.gpg.d/ /etc/apt/keyrings/ /usr/share/keyrings/ 2>/dev/null | grep -vE "^total"'
  for f in /etc/apt/sources.list.d/*.list /etc/apt/sources.list.d/*.sources; do
    [ -f "$f" ] || continue
    case "$f" in */ubuntu.sources | */debian.sources) continue ;; esac
    grep -qiE 'signed-by' "$f" || flag LOW "third-party APT source without Signed-By (trusted by every global key): $f"
  done
  run 'ls /etc/apt/preferences.d/ 2>/dev/null; grep -rhs "^\s*Pin" /etc/apt/preferences /etc/apt/preferences.d/ | sort | uniq -c'
fi
if have rpm; then
  printf '  installed rpm packages: %s\n' "$(rpm -qa 2>/dev/null | wc -l)"
  run 'grep -HE "^\s*(\[|baseurl|metalink|mirrorlist|gpgcheck|repo_gpgcheck|enabled)" /etc/yum.repos.d/*.repo 2>/dev/null'
  NOGPG=$(grep -lE '^\s*gpgcheck\s*=\s*0' /etc/yum.repos.d/*.repo 2>/dev/null)
  [ -n "$NOGPG" ] && flag HIGH "RPM repo with gpgcheck=0: $NOGPG"
fi
have snap && run 'snap list 2>/dev/null'
sub "Executables outside package management (/usr/local, /opt)"
find /usr/local/bin /usr/local/sbin /opt -maxdepth 3 -type f -perm /111 2>/dev/null | head -60 | while read -r f; do
  owner="unmanaged"
  if [ "$DEEP" = 1 ]; then
    if have dpkg; then dpkg -S "$f" >/dev/null 2>&1 && owner="dpkg"; fi
    if have rpm; then rpm -qf "$f" >/dev/null 2>&1 && owner="rpm"; fi
    printf '  %-9s %s  %s\n' "$owner" "$(sha256sum "$f" 2>/dev/null | cut -c1-16)" "$f"
  else
    printf '  %s  %s\n' "$(stat -c '%y' "$f" | cut -c1-10)" "$f"
  fi
done
run 'ls /usr/local/lib/node_modules 2>/dev/null | tr "\n" " "; ls -d /usr/local/lib/python3*/dist-packages/* 2>/dev/null | wc -l | sed "s/^/system-wide pip packages: /"'
if [ "$DEEP" = 1 ] && [ "$IS_ROOT" = 1 ]; then
  if have dpkg; then
    sub "dpkg --verify (non-config files whose checksum changed)"
    MOD=$(timeout 900 dpkg --verify 2>/dev/null | awk '$2!="c"')
    printf '%s\n' "$MOD" | sed '/^$/d; s/^/  /' | head -100
    [ -n "$MOD" ] && flag HIGH "packaged non-config files modified on disk (dpkg --verify) — investigate"
  elif have rpm; then
    sub "rpm -Va (non-config changes)"
    MOD=$(timeout 900 rpm -Va 2>/dev/null | awk '$2!="c" && $1 ~ /5/')
    printf '%s\n' "$MOD" | sed '/^$/d; s/^/  /' | head -100
    [ -n "$MOD" ] && flag HIGH "packaged non-config files modified on disk (rpm -Va) — investigate"
  fi
  sub "Package ownership of SUID/SGID files"
  printf '%s\n' "$SUIDS" | while read -r f; do
    [ -n "$f" ] || continue
    if have dpkg; then dpkg -S "$f" >/dev/null 2>&1 && continue; fi
    if have rpm; then rpm -qf "$f" >/dev/null 2>&1 && continue; fi
    flag HIGH "SUID/SGID file not owned by any package: $f"
  done
fi

###############################################################################
if have readelf; then
  sec "BINARY HARDENING (non-loopback listeners & unmanaged /usr/local, /opt ELFs)"
  {
    if [ "$IS_ROOT" -eq 1 ] && have ss; then
      ss -H -tulpn 2>/dev/null | while read -r _ _ _ _ local _ proc; do
        addr=${local%:*}; addr=${addr%%\%*}; addr=${addr#[}; addr=${addr%]}
        case "$addr" in 127.* | ::1 | ::ffff:127.* | fe80:* | 22[4-9].* | 23[0-9].* | ff[0-9a-f][0-9a-f]:*) continue ;; esac
        for pid in $(printf '%s' "$proc" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u); do
          exe=$(readlink -f "/proc/$pid/exe" 2>/dev/null)
          [ -f "$exe" ] && printf 'listener\t%s\n' "$exe"
        done
      done
    fi
    find /usr/local/bin /usr/local/sbin /opt -maxdepth 3 -type f -perm /111 2>/dev/null | head -25 |
      while read -r f; do printf 'local\t%s\n' "$f"; done
  } | awk -F'\t' '!seen[$2]++' | while IFS=$'\t' read -r scope bin; do
    [ -r "$bin" ] || continue
    magic=$(od -An -tx1 -N4 "$bin" 2>/dev/null | tr -d ' \n')
    [ "$magic" = "7f454c46" ] || continue
    hdr=$(readelf -h "$bin" 2>/dev/null) || continue
    phdrs=$(readelf -lW "$bin" 2>/dev/null)
    dyn=$(readelf -d "$bin" 2>/dev/null)
    notes=$(readelf -n "$bin" 2>/dev/null)
    secs=$(readelf -SW "$bin" 2>/dev/null)
    syms=$(readelf -sW "$bin" 2>/dev/null)
    etype=$(printf '%s\n' "$hdr" | awk '/^\s*Type:/{print $2; exit}')
    has_interp=0; has_dyn=0; is_go=0
    printf '%s\n' "$phdrs" | grep -q '^\s*INTERP\b' && has_interp=1
    printf '%s\n' "$phdrs" | grep -q '^\s*DYNAMIC\b' && has_dyn=1
    printf '%s\n' "$secs" | grep -qE '\.go\.buildinfo|\.gopclntab' && is_go=1
    pie="NO-PIE"
    if [ "$etype" = "EXEC" ] && [ "$has_interp" -eq 0 ]; then pie="static"
    elif [ "$etype" = "DYN" ]; then pie="PIE"; fi
    relro="N/A"
    if [ "$has_dyn" -eq 1 ] && [ "$pie" != "static" ]; then
      if printf '%s\n' "$phdrs" | grep -q '^\s*GNU_RELRO\b'; then
        if printf '%s\n' "$dyn" | grep -qE '\bBIND_NOW\b|\(FLAGS_1\).*\bNOW\b'; then relro="FULL"; else relro="PARTIAL"; fi
      else relro="NONE"; fi
    fi
    nx="NX"
    printf '%s\n' "$phdrs" | awk '$1=="GNU_STACK"{print}' | grep -q 'E' && nx="EXEC!"
    printf '%s\n' "$phdrs" | awk '$1=="LOAD"{print}' | grep -qE 'RWE|W E' && nx="RWX!"
    hwcfi="-"
    printf '%s\n' "$notes" | grep -q '\bIBT\b' && printf '%s\n' "$notes" | grep -q '\bSHSTK\b' && hwcfi="cet"
    printf '%s\n' "$notes" | grep -q '\bBTI\b' && printf '%s\n' "$notes" | grep -q '\bPAC\b' && hwcfi="bti+pac"
    canary="-"
    if [ "$is_go" -eq 1 ] && [ "$pie" = "static" ]; then canary="go-rt"
    elif printf '%s\n' "$syms" | grep -qE '__stack_chk_fail|__stack_chk_guard'; then canary="yes"
    elif [ "$has_dyn" -eq 1 ]; then canary="no"; fi
    printf '  [%-8s] pie=%-6s relro=%-7s nx=%-5s canary=%-5s cfi=%-7s %s\n' \
      "$scope" "$pie" "$relro" "$nx" "$canary" "$hwcfi" "$bin"
    if [ "$nx" != "NX" ]; then
      sev=MEDIUM; [ "$scope" = "listener" ] && sev=HIGH
      flag "$sev" "ELF $bin ($scope) has executable/RWX memory ($nx)"
    fi
    if printf '%s\n' "$syms" | grep -qE '__asan_|__tsan_|__msan_|__ubsan_handle_'; then
      flag HIGH "ELF $bin ($scope) links a dev sanitizer runtime (weakened ASLR / env-var attack surface)"
    fi
    if [ "$scope" = "listener" ] && [ "$pie" = "NO-PIE" ]; then
      flag MEDIUM "Network-listening ELF $bin is dynamically linked without PIE (ASLR disabled for main binary)"
    fi
    if [ "$scope" = "listener" ] && { [ "$relro" = "NONE" ] || [ "$relro" = "PARTIAL" ]; }; then
      flag LOW "Network-listening ELF $bin has $relro RELRO (prefer Full RELRO: -Wl,-z,relro,-z,now)"
    fi
  done
fi

###############################################################################
if [ "$DOCKER" = 1 ] && have docker; then
  sec "DOCKER"
  if ! timeout 20 docker info >/dev/null 2>&1; then
    echo "  docker CLI present but daemon unreachable with these privileges — rerun as root"
  else
    run 'docker version --format "client={{.Client.Version}} server={{.Server.Version}}"; docker info 2>/dev/null | grep -iE "security options|rootless|userns|seccomp|apparmor|selinux|cgroup (driver|version)|logging driver|live restore|firewall|storage driver|swarm|iptables|ip6tables" '
    run 'cat /etc/docker/daemon.json 2>/dev/null; systemctl cat docker.service 2>/dev/null | grep -E "^ExecStart="; ls -l /var/run/docker.sock 2>/dev/null'
    DJ=$(cat /etc/docker/daemon.json 2>/dev/null)
    DEXEC=$(systemctl cat docker.service 2>/dev/null | grep -E '^ExecStart=')
    if printf '%s %s' "$DJ" "$DEXEC" | grep -q 'tcp://'; then
      if printf '%s %s' "$DJ" "$DEXEC" | grep -qE 'tlsverify'; then
        flag MEDIUM "Docker API on TCP (with tlsverify) — prefer DOCKER_HOST=ssh://"
      else
        flag CRITICAL "Docker API exposed on TCP without tlsverify — unauthenticated root on this host"
      fi
    fi
    printf '%s' "$DJ" | grep -qE '"iptables"\s*:\s*false' && flag HIGH 'daemon.json "iptables": false — Docker manages no NAT/isolation rules; containers are unfiltered and break subtly'
    docker info --format '{{json .SecurityOptions}}' 2>/dev/null | grep -q seccomp || flag HIGH "Docker running without seccomp"
    if ! printf '%s' "$DJ" | grep -q 'max-size' && [ "$(docker info --format '{{.LoggingDriver}}' 2>/dev/null)" = json-file ]; then
      flag LOW "json-file logging without max-size (disk-fill risk); use log-driver local or log-opts max-size"
    fi
    run 'docker network ls --format "{{.Name}}\t{{.Driver}}\tinternal={{.Internal}}\tipv6={{.IPv6}}"'
    run 'docker image ls --digests --format "{{.Repository}}:{{.Tag}}\t{{.Digest}}\t{{.CreatedSince}}" | head -40'
    sub "Containers"
    DFMT='{{.Name}}|{{.Config.Image}}|{{.Config.User}}|{{.HostConfig.Privileged}}|{{.HostConfig.NetworkMode}}|{{.HostConfig.PidMode}}|{{.HostConfig.IpcMode}}|{{json .HostConfig.CapAdd}}|{{.HostConfig.ReadonlyRootfs}}|{{json .HostConfig.SecurityOpt}}|{{range $p, $b := .NetworkSettings.Ports}}{{if $b}}{{range $b}}{{$p}}@{{.HostIp}}:{{.HostPort}} {{end}}{{end}}{{end}}|{{range .Mounts}}{{.Source}}>{{.Destination}}:{{if .RW}}rw{{else}}ro{{end}} {{end}}|{{.HostConfig.PidsLimit}}|{{.HostConfig.Memory}}|{{range .Config.Env}}{{index (split . "=") 0}} {{end}}'
    NO_LIMITS=""
    TAG_ONLY=""
    for cid in $(docker ps -q 2>/dev/null); do
      IFS='|' read -r name image user priv netm pidm ipcm capadd ro secopt ports mounts pids mem envnames \
        < <(docker inspect --format "$DFMT" "$cid" 2>/dev/null)
      name=${name#/}
      printf '\n  [%s] image=%s user=%s privileged=%s net=%s pid=%s ro_rootfs=%s\n' "$name" "$image" "${user:-<image default>}" "$priv" "$netm" "${pidm:-private}" "$ro"
      printf '      cap_add=%s security_opt=%s pids_limit=%s memory=%s\n' "$capadd" "$secopt" "${pids:-none}" "$mem"
      printf '      ports: %s\n      mounts: %s\n' "${ports:-none}" "${mounts:-none}"
      printf '      process users: %s\n' "$(docker top "$cid" -o user,pid,comm 2>/dev/null | awk 'NR>1{print $1"/"$3}' | sort -u | head -6 | tr '\n' ' ')"
      [ "$priv" = true ] && flag HIGH "container $name is privileged (full host device + capability access)"
      [ "$pidm" = host ] && flag HIGH "container $name shares the host PID namespace"
      [ "$netm" = host ] && flag MEDIUM "container $name uses host networking (no network isolation; binds directly on host)"
      [ "$ipcm" = host ] && flag MEDIUM "container $name shares host IPC namespace"
      printf '%s' "$capadd" | grep -qE 'ALL|SYS_ADMIN|NET_ADMIN|SYS_PTRACE|SYS_MODULE|DAC_READ_SEARCH|SYS_RAWIO|BPF' &&
        flag HIGH "container $name adds powerful capabilities: $capadd"
      printf '%s' "$secopt" | grep -q unconfined && flag HIGH "container $name runs with an unconfined seccomp/apparmor profile: $secopt"
      PUBLIC_PORTS=0
      for pb in $ports; do
        cport=${pb%%/*}
        hip=${pb#*@}
        hip=${hip%:*}
        case "$hip" in 127.* | ::1) continue ;; esac
        PUBLIC_PORTS=1
        sn=$(sensitive_port "$cport")
        if [ -n "$sn" ]; then
          flag CRITICAL "container $name publishes $sn ($cport) on ${hip:-all interfaces}: reachable from outside unless filtered in DOCKER-USER/forward chain"
        fi
      done
      for mt in $mounts; do
        src=${mt%%>*}
        case "$src" in
          /var/run/docker.sock | /run/docker.sock | /run/containerd/containerd.sock | /run/podman/podman.sock)
            if [ "$PUBLIC_PORTS" = 1 ]; then
              flag CRITICAL "container $name mounts $src AND publishes ports: compromise of the app = root on host"
            else
              flag HIGH "container $name mounts $src (root-equivalent; use a filtering socket proxy)"
            fi ;;
          / | /etc | /root | /home | /proc | /sys | /dev | /boot | /usr | /var/lib/docker | /run)
            case "$mt" in *:rw) flag HIGH "container $name mounts host $src read-write" ;; *) flag MEDIUM "container $name mounts host $src" ;; esac ;;
        esac
      done
      { [ "${mem:-0}" = 0 ] || [ -z "$pids" ] || [ "$pids" = "<nil>" ] || [ "$pids" = "<no value>" ] || [ "$pids" -le 0 ] 2>/dev/null; } && NO_LIMITS="$NO_LIMITS$name "
      case "$image" in *@sha256:*) ;; *) TAG_ONLY="$TAG_ONLY$name " ;; esac
      SEC_ENV=$(printf '%s\n' $envnames | grep -iE 'PASS|SECRET|TOKEN|KEY|CREDENTIAL|PRIVATE' | grep -viE '_FILE$' | tr '\n' ' ')
      [ -n "$SEC_ENV" ] && flag LOW "container $name has secret-looking env vars (readable via docker inspect / /proc): $SEC_ENV"
      if [ "$UFW_ACTIVE" = 1 ] && [ "$PUBLIC_PORTS" = 1 ]; then
        flag HIGH "ufw is active but container $name publishes ports on all interfaces — ufw does NOT filter Docker-published ports"
      fi
    done
    [ -n "$NO_LIMITS" ] && flag LOW "containers without memory and/or pids limits: $NO_LIMITS"
    [ -n "$TAG_ONLY" ] && flag INFO "containers referencing images by tag, not digest: $TAG_ONLY"
  fi
fi
if [ "$DOCKER" = 1 ] && have podman; then
  run 'podman ps --format "{{.Names}} {{.Image}} {{.Ports}}" 2>/dev/null'
fi

###############################################################################
sec "CLOUD / VIRTUALIZATION"
have cloud-init && run 'cloud-init status --long 2>/dev/null | head -8'
UD=/var/lib/cloud/instance/user-data.txt
if [ -r "$UD" ]; then
  printf '  %s mode %s\n' "$UD" "$(stat -c %a "$UD")"
  NUD=$(grep -ciE 'password|passwd|secret|token|api[_-]?key|private' "$UD")
  if [ "${NUD:-0}" -gt 0 ]; then
    if [ -e /etc/cloud/cloud-init.disabled ] || cloud-init status 2>/dev/null | grep -q disabled; then
      flag LOW "leftover user-data ($UD) has $NUD secret-looking lines (cloud-init disabled; often installer/autoinstall data) — delete if unneeded"
    else
      flag MEDIUM "cloud-init user-data has $NUD secret-looking lines; user-data is also served by the metadata endpoint to any local process/container"
    fi
  fi
fi
for s in qemu-guest-agent google-guest-agent amazon-ssm-agent walinuxagent waagent hv-kvp-daemon; do
  systemctl is-active --quiet "$s" 2>/dev/null && printf '  guest agent active: %s\n' "$s"
done
echo "  NOTE: metadata endpoint reachability is not tested (no network calls). Check manually from the host"
echo "        AND from a container:  curl -s -m2 http://169.254.169.254/  (AWS also: [fd00:ec2::254])"

###############################################################################
sec "TIME, LOGGING, DETECTION"
run 'timedatectl show -p NTP -p NTPSynchronized -p Timezone 2>/dev/null'
have chronyc && run 'chronyc -n sources 2>/dev/null | head -12'
run 'grep -hvE "^\s*(#|$|\[)" /etc/systemd/journald.conf /etc/systemd/journald.conf.d/*.conf 2>/dev/null; journalctl --disk-usage 2>/dev/null'
if [ ! -d /var/log/journal ] && ! grep -rqsE '^\s*Storage=persistent' /etc/systemd/journald.conf /etc/systemd/journald.conf.d/; then
  flag LOW "journald is not persistent (logs lost on reboot)"
fi
if systemctl is-active --quiet auditd 2>/dev/null; then
  [ "$IS_ROOT" -eq 1 ] && run 'auditctl -s 2>/dev/null | head -6; echo "rules loaded: $(auditctl -l 2>/dev/null | grep -vc "^No rules")"'
else
  echo "  auditd: not running"
fi
SHIP=0
grep -rqsE '^\s*[^#].*(@@?[0-9A-Za-z\[]|omfwd)' /etc/rsyslog.conf /etc/rsyslog.d/ && SHIP=1
for s in systemd-journal-upload vector fluent-bit promtail alloy filebeat otelcol otelcol-contrib datadog-agent; do
  systemctl is-active --quiet "$s" 2>/dev/null && { SHIP=1; printf '  log shipper active: %s\n' "$s"; }
done
[ "$SHIP" = 1 ] || flag LOW "no remote log shipping detected (root attacker can erase local logs)"
for s in fail2ban crowdsec; do
  systemctl is-active --quiet "$s" 2>/dev/null && printf '  %s: active\n' "$s"
done

###############################################################################
sec "KERNEL MODULES"
LOADED=$(awk '{print $1}' /proc/modules 2>/dev/null)
printf '  loaded modules: %s\n' "$(printf '%s\n' "$LOADED" | grep -c .)"
RISKY=""
for m in dccp sctp rds tipc n_hdlc ax25 netrom x25 rose appletalk psnap p8022 can atm \
  cramfs freevxfs jffs2 hfs hfsplus udf firewire_core thunderbolt usb_storage bluetooth; do
  printf '%s\n' "$LOADED" | grep -qx "$m" && RISKY="$RISKY$m "
done
[ -n "$RISKY" ] && flag LOW "rarely-needed attack-surface modules loaded: $RISKY"
printf '  modprobe.d install/blacklist rules: %s\n' "$(grep -rhsE '^\s*(install|blacklist)\s' /etc/modprobe.d/ | wc -l)"

###############################################################################
sec "COMPROMISE INDICATORS (light triage; a rootkit can hide from all of this)"
needroot
sub "Processes running deleted or temp-dir binaries"
for p in /proc/[0-9]*; do
  e=$(readlink "$p/exe" 2>/dev/null) || continue
  case "$e" in
    /tmp/* | /var/tmp/* | /dev/shm/*)
      flag HIGH "process ${p#/proc/} runs from temp dir: $e"
      ;;
    *" (deleted)")
      printf '  pid %-7s %s  cmd=%s\n' "${p#/proc/}" "$e" "$(tr '\0' ' ' <"$p/cmdline" 2>/dev/null | cut -c1-100)"
      ;;
  esac
done
echo "  (deleted executables right after upgrades are usually services awaiting restart; see needrestart)"
run 'ps -eo pid,user,pcpu,pmem,etime,comm --sort=-pcpu | head -12'
run 'ss -H -tnp state established 2>/dev/null | head -40'
run 'find /etc -xdev -type f -mtime -2 2>/dev/null | head -40'

###############################################################################
sec "FLAGS SUMMARY (heuristic — confirm each finding before acting)"
for s in CRITICAL HIGH MEDIUM LOW INFO; do
  awk -F'\t' -v s="$s" '$1==s && !seen[$0]++ {printf "[%s] %s\n", $1, $2}' "$FLAGS_FILE"
done
printf '\ncounts: '
for s in CRITICAL HIGH MEDIUM LOW INFO; do
  printf '%s=%s ' "$s" "$(awk -F'\t' -v s="$s" '$1==s && !seen[$0]++' "$FLAGS_FILE" | wc -l)"
done
printf '\n'
# Close our end of the redaction pipe and wait, so the report is complete when we return.
exec >&- 2>&-
wait "$REDACT_PID" 2>/dev/null
