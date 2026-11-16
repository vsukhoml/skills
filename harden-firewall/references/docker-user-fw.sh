#!/bin/sh
# /usr/local/sbin/docker-user-fw.sh — restrict Docker-published ports via DOCKER-USER
# (iptables firewall backend; harden-firewall). Prefer docker_guard.nft, which works with both
# backends. Use this when the host's tooling is iptables-centric.
#
# Docker DNATs published ports in PREROUTING, so the packets traverse FORWARD (never INPUT,
# which is why ufw/firewalld input rules don't apply). DOCKER-USER is evaluated first in FORWARD.
# After DNAT `--dport` is the CONTAINER port; match the host port the client used with
# `-m conntrack --ctorigdstport` (Docker docs recommend conntrack for this).
#
# FAIL-CLOSED: no dependency on the external interface name. Traffic from container bridges
# returns to Docker's rules; traffic toward container bridges from anywhere else must match an
# allow rule below.
#
# Run by docker-user-fw.service after every Docker start. Docker keeps DOCKER-USER contents
# across daemon restarts but not across reboots. Do NOT save Docker's dynamic rules with
# iptables-persistent/netfilter-persistent: restoring them at boot conflicts with Docker.
set -eu

# Host ports that are public for everyone (comma-separated):
PUBLIC_TCP="${PUBLIC_TCP:-80,443}"
PUBLIC_UDP="${PUBLIC_UDP:-}"           # e.g. "443" for HTTP/3 (QUIC)
# "port:source" pairs for restricted published ports, IPv4 and IPv6 separately (space-separated):
RESTRICTED_V4="${RESTRICTED_V4:-}"     # e.g. "5432:192.0.2.10/32 6379:192.0.2.10/32"
RESTRICTED_V6="${RESTRICTED_V6:-}"     # e.g. "5432:2001:db8::10/128"
# Interfaces whose traffic may reach every published port (e.g. the admin VPN), space-separated:
TRUSTED_IF="${TRUSTED_IF:-}"           # e.g. "wg0"

apply() {
	ipt=$1
	meta=$2
	pairs=$3
	"$ipt" -n -L DOCKER-USER >/dev/null 2>&1 || "$ipt" -N DOCKER-USER
	# Build all rules in a staging chain (DOCKER-USER-NEW) ending with the DROP rules, then point
	# DOCKER-USER exclusively at DOCKER-USER-NEW so an error under `set -eu` never leaves
	# DOCKER-USER empty/fail-open. If DOCKER-USER already jumps to DOCKER-USER-NEW from an earlier
	# run, park the live chain at DOCKER-USER-OLD first (moving references atomically via -E).
	if "$ipt" -C DOCKER-USER -j DOCKER-USER-NEW 2>/dev/null; then
		"$ipt" -F DOCKER-USER-OLD 2>/dev/null || true
		"$ipt" -X DOCKER-USER-OLD 2>/dev/null || true
		"$ipt" -E DOCKER-USER-NEW DOCKER-USER-OLD
	else
		"$ipt" -F DOCKER-USER-NEW 2>/dev/null || true
		"$ipt" -X DOCKER-USER-NEW 2>/dev/null || true
	fi
	"$ipt" -N DOCKER-USER-NEW
	# Containers must never reach the cloud metadata HTTP service (SSRF -> instance credentials).
	# Port 80 only: on GCE/OCI the same address also serves DNS/NTP.
	"$ipt" -A DOCKER-USER-NEW -d "$meta" -p tcp --dport 80 -j DROP
	"$ipt" -A DOCKER-USER-NEW -m conntrack --ctstate RELATED,ESTABLISHED -j RETURN
	# Container egress / inter-container traffic: Docker's own rules decide.
	"$ipt" -A DOCKER-USER-NEW -i docker0 -j RETURN
	"$ipt" -A DOCKER-USER-NEW -i br-+ -j RETURN
	for i in $TRUSTED_IF; do
		"$ipt" -A DOCKER-USER-NEW -i "$i" -j RETURN
	done
	for p in $(printf '%s' "$PUBLIC_TCP" | tr ',' ' '); do
		"$ipt" -A DOCKER-USER-NEW -p tcp -m conntrack --ctstate NEW --ctorigdstport "$p" -j RETURN
	done
	for p in $(printf '%s' "$PUBLIC_UDP" | tr ',' ' '); do
		"$ipt" -A DOCKER-USER-NEW -p udp -m conntrack --ctstate NEW --ctorigdstport "$p" -j RETURN
	done
	for pair in $pairs; do
		port=${pair%%:*}
		src=${pair#*:}
		proto=tcp
		case "$port" in
			*/udp) proto=udp; port=${port%/udp} ;;
			*/tcp) port=${port%/tcp} ;;
		esac
		"$ipt" -A DOCKER-USER-NEW -p "$proto" -s "$src" -m conntrack --ctstate NEW --ctorigdstport "$port" -j RETURN
	done
	for br in docker0 br-+; do
		"$ipt" -A DOCKER-USER-NEW -o "$br" -m limit --limit 6/min --limit-burst 10 -j LOG --log-prefix "docker-user drop: " 2>/dev/null || true
		"$ipt" -A DOCKER-USER-NEW -o "$br" -j DROP
	done
	# Atomically swap rule 1 of DOCKER-USER to jump to DOCKER-USER-NEW, trim any older rules,
	# and delete the previous staging chain.
	"$ipt" -R DOCKER-USER 1 -j DOCKER-USER-NEW 2>/dev/null || "$ipt" -I DOCKER-USER 1 -j DOCKER-USER-NEW
	while "$ipt" -D DOCKER-USER 2 2>/dev/null; do :; done
	"$ipt" -F DOCKER-USER-OLD 2>/dev/null || true
	"$ipt" -X DOCKER-USER-OLD 2>/dev/null || true
}

apply iptables 169.254.169.254 "$RESTRICTED_V4"
# Docker >= 27 manages ip6tables by default; skip if this host has no IPv6 netfilter at all.
if ip6tables -n -L FORWARD >/dev/null 2>&1; then
	apply ip6tables fd00:ec2::254 "$RESTRICTED_V6"
fi
