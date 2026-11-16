---
name: harden-docker
description: >-
  Docker and Podman host and container hardening: daemon.json, the Docker
  socket and docker group, rootless versus userns-remap, runtime flags
  (non-root, read-only rootfs, cap_drop, seccomp), compose networks, secrets,
  and minimal images. Use when the user shares a Dockerfile,
  docker-compose.yml, daemon.json, or `docker run` command, mounts
  docker.sock, runs databases in Docker, or asks whether containers or a
  container host are secure.
last_updated: 2026-11-15
---

# Docker / Container Hardening

Three facts frame everything here:

1. **Control of the Docker daemon is root on the host.** That covers the
   `docker` group, `/var/run/docker.sock`, and a TCP API.
2. **Containers share the host kernel.** Isolation is namespaces, seccomp,
   capabilities and LSMs, so every flag that weakens one of these
   (`--privileged`, `--pid=host`, `cap_add: SYS_ADMIN`) removes real
   isolation.
3. **Docker networking routes around host firewalls.** Published ports are
   DNAT'ed into FORWARD. The full treatment is in `harden-firewall` §4.

**Reference files:**

- `references/daemon.json` → `/etc/docker/daemon.json`. Validated with
  `dockerd --validate --config-file`.
- `references/compose-hardened.yml`: proxy + app + PostgreSQL + Redis.
  Validated with `docker compose config`.
- `references/Dockerfile.hardened`: (A) static binary on `scratch`, (B) a
  dynamically linked binary on `scratch` with exactly its libraries, (C)
  Python on a slim base, plus `.dockerignore`. (A) and (B) were built and run
  with hardened runtime flags.

## 1. Audit what runs now

`harden-audit`'s DOCKER section does this. Manual equivalents:

```sh
docker info | grep -iE 'security options|rootless|userns|logging driver|live restore|firewall'
cat /etc/docker/daemon.json; systemctl cat docker | grep ExecStart      # any -H tcp:// ?
getent group docker                                                      # every member = root
docker ps --format '{{.Names}}' | xargs -r docker inspect --format \
 '{{.Name}} priv={{.HostConfig.Privileged}} net={{.HostConfig.NetworkMode}} pid={{.HostConfig.PidMode}} user={{.Config.User}} caps={{.HostConfig.CapAdd}} ro={{.HostConfig.ReadonlyRootfs}} ports={{.NetworkSettings.Ports}} mounts={{range .Mounts}}{{.Source}}:{{.Destination}} {{end}}'
iptables -t nat -S DOCKER | grep DNAT      # what is published, from the kernel's view
```

As a second opinion, run the CIS Docker Benchmark script `docker-bench-security`.
Pin it and read it first: it runs as root with host access.

## 2. Daemon configuration (`daemon.json`)

JSON has no comments, so each key is explained here:

| Key | Why | Cost / caveat |
| --- | --- | --- |
| `"ip": "127.0.0.1"` | Default host IPv4 address for `-p`/`ports:` entries that give none. `-p 5432:5432` now binds **IPv4 loopback**, not the world. The best single safety net against accidental exposure. | Sets only the default **IPv4** bind address: publish `"[::1]:port:port"` explicitly if IPv6 loopback is needed, and keep `docker_guard.nft` (`harden-firewall`) for IPv6 forward parity. Public services must be explicit: `0.0.0.0:443:443` and `[::]:443:443`. Existing compose files that relied on the default stop being public, so check before rolling out. |
| `"no-new-privileges": true` | Blocks setuid/file-capability escalation inside every container | Images that need `sudo`/setuid inside break. Entrypoints that start as root and drop via gosu/su-exec still work. |
| `"icc": false` | No traffic between containers on the **default** `docker0` bridge | Has no effect on user-defined networks. Isolate those by network design (§4). |
| `"userland-proxy": false` | No `docker-proxy` process per published port; NAT only. Saves RAM, removes a userspace hop. | Published ports no longer appear in `ss -tlnp`; audit via the nat table. Test loopback access to published ports after enabling. |
| `"live-restore": true` | Containers survive daemon restarts and upgrades | Not compatible with Swarm |
| `"log-driver": "local"` + `max-size`/`max-file` | Compressed, rotated logs. Unbounded `json-file` logs are the classic full-disk VPS outage. | `docker logs` still works. Use a shipper for central logs. |
| `"default-ulimits"` | Sane fd limits instead of inherited huge values | Raise per container if a DB needs it |
| `"ip6tables": true` | Default since 27.0. Keep it, so Docker's IPv6 isolation rules exist. | — |

Never:

- `"hosts": ["tcp://0.0.0.0:2375"]` or `-H tcp://` without mutual TLS. That is
  unauthenticated root for the internet. For remote management use
  `DOCKER_HOST=ssh://admin@host` (rides on hardened SSH), or a Docker context
  over SSH.
- `"iptables": false` (see `harden-firewall`).
- `"seccomp-profile": "unconfined"`, or
  `--security-opt seccomp=unconfined` / `apparmor=unconfined` on containers.

Optional:

- `"userns-remap": "default"` maps container root to an unprivileged host
  UID range.
- `"firewall-backend": "nftables"` (29.x, experimental; see `harden-firewall`).

Apply with `dockerd --validate --config-file /etc/docker/daemon.json` and
then `systemctl restart docker`. With live-restore on, containers keep
running.

## 3. Rootful vs rootless vs userns-remap

| Mode | Container root is | Pros | Cons |
| --- | --- | --- | --- |
| Rootful (default) | Host root (namespaced) | Everything works; fastest networking | A container escape is host root. Daemon is root. |
| `userns-remap` | Unprivileged host UID range | Escapes land as nobody-ish. Same daemon UX. | Per-daemon (not per-container). Bind-mount ownership pain. Some features (`--userns=host` needs) clash. |
| **Rootless Docker** / **rootless Podman** | The invoking user | Daemon and containers run unprivileged. Published ports hit host INPUT, so the normal firewall applies. | Needs unprivileged user namespaces (on Ubuntu ≥ 23.10, an AppArmor profile for rootlesskit). Ports <1024 need `net.ipv4.ip_unprivileged_port_start`. Default port driver hides client IPs (use `pasta`/`slirp4netns`). Some network modes and perf differ. |

- **Recommendation:** rootless (Docker or Podman) for single-tenant app hosts
  whose stacks don't need privileged features.
- Rootful + `userns-remap` when tooling assumes rootful Docker.
- Plain rootful only with the full flag discipline below.
- **Podman + Quadlet** (`.container` units) runs containers as systemd
  services. It is daemonless and rootless-friendly, and integrates with
  `harden-host` §6 sandboxing and journald.

## 4. Network design (compose)

- **Only the edge publishes.** One reverse proxy publishes 80/443. Every other
  service has **no `ports:`**.
- **DBs and caches go on an `internal: true` network.** Such a network has no
  route outside and can't publish ports. A compromised DB container can't
  download tools or exfiltrate directly.
- Apps that need egress attach to a normal network as well. The reference
  compose shows `edge` + `backend`.
- **Need DB access from your laptop?** Use `ssh -L` to the container IP, or
  publish temporarily to `127.0.0.1`. Never `0.0.0.0`.
- **Separate networks per trust zone.** Containers on the same user-defined
  network can reach each other on all ports. `icc` does not apply there.
- **Never `network_mode: host`** for internet-facing services unless you
  intend host-level binding. All network isolation disappears.
- **Metadata endpoint.** Containers reach `169.254.169.254` by default. Block
  it in the forward path (`docker_guard.nft` / `docker-user-fw.sh`), and on
  AWS set IMDSv2 hop limit 1.
- **IPv6.** If containers get IPv6, apply the same rules to the IPv6 forward
  path. The reference nft table is `inet` for this reason.

## 5. Runtime flags (every container)

See the `x-hardening` anchor in `compose-hardened.yml`.

| Flag | Blocks | Notes |
| --- | --- | --- |
| `user: "10001:10001"` (and `USER` in the image) | Root inside = more kernel attack surface, file-ownership abuse on mounts | Use a numeric UID (Kubernetes `runAsNonRoot` needs it). Official DB images drop privileges in their entrypoint, so verify with `docker top <c> -o user,pid,comm`. |
| `read_only: true` + `tmpfs: /tmp:noexec,nosuid,nodev` | Dropping tools and persistence into the container FS | Writable paths become explicit volumes or tmpfs |
| `cap_drop: [ALL]` + minimal `cap_add` | Raw sockets, chown games, mount, etc. | Typical add-backs: `NET_BIND_SERVICE` (bind <1024; better to listen on 8080), and `CHOWN`/`SETUID`/`SETGID`/`DAC_OVERRIDE`/`FOWNER` for root-start entrypoints that drop privileges |
| `security_opt: [no-new-privileges:true]` | setuid escalation | Also daemon-wide (§2) |
| Default seccomp + AppArmor/SELinux | ~44 dangerous syscalls; LSM confinement | Never set `unconfined`. Custom profiles only if measured. |
| `deploy.resources.limits` `{memory, cpus, pids}` | Fork bombs and memory exhaustion taking down the host | Efficiency too: predictable packing on small VPSes. Don't also set `pids_limit`; compose rejects the conflict. |
| `init: true` | Zombie accumulation; signal handling | Tiny tini as PID 1 |
| No `privileged`, no `pid/ipc: host`, no `devices` unless required | Full device access, host process visibility | `privileged` = root on host for practical purposes |
| No host mounts of `/`, `/etc`, `/root`, `/home`, `/proc`, `/sys`, `/var/lib/docker` | Host takeover via the filesystem | Bind mounts: `:ro` unless writes are needed |

### docker.sock: the most common real-world escalation

Traefik, Portainer, Watchtower, Dozzle, CI runners and "auto-update" tools ask
for `/var/run/docker.sock`. Whoever can talk to it can start a privileged
container mounting `/`, which means **root on the host**. A `:ro` mount does
*not* help: read-only applies to the socket file, not to the API. Options:

1. Don't. Traefik can use the file provider instead of the Docker provider.
2. Put a **filtering socket proxy** in between, on an internal network. Allow
   only `GET /containers`, `/events` and the like, and nothing that creates,
   execs or pulls. Pin and review the proxy image.
3. Run the tool in rootless Docker or a separate VM.

Any container holding the socket **and** facing the internet is Critical.

## 6. Secrets

- Never put secrets in `ENV`/`ARG`, image layers, or compose `environment:`.
  They are visible via `docker inspect`, `/proc/<pid>/environ`, image history,
  registry copies, crash reports and child processes.
- Use compose `secrets:` with `file:`. They are mounted read-only at
  `/run/secrets/<name>`. Official images (postgres, mysql, mariadb, mongo,
  redis via config) support `*_FILE` variables.
- For build-time secrets, use
  `RUN --mount=type=secret,id=...`, built with
  `docker buildx build --secret id=...,src=...`.
- Keep secret files at `chmod 600`, outside VCS. Encrypt them in git with
  sops + age if they must be versioned (`harden-supply-chain`).

## 7. Images

- **Default to `FROM scratch`: ship the binary, not an operating system.**
  - **What goes in.** The runtime image contains only what the process
    actually opens:
    - the executable (plus, if dynamically linked, exactly its libraries and
      ELF loader)
    - the CA bundle, if it dials TLS
    - zoneinfo, if it uses time zones
    - one-line `/etc/passwd` and `/etc/group` entries for its numeric user
  - **What you gain.** With no shell, package manager, coreutils, curl or
    setuid binaries:
    - an RCE has nothing to live off
    - scanners report no CVEs for packages the app never uses
    - images are a few MB: faster pulls, faster starts, less registry and disk
  - **Measured with `references/Dockerfile.hardened`:**
    - A Go service on scratch is **7 MB**. It ran healthy with `--read-only
      --cap-drop ALL` as uid 65532, and HTTPS worked.
    - curl with only its 34 linked libraries is **23 MB**, versus **118 MB**
      for the same curl on `debian:trixie-slim`.

  | What you ship | Runtime base | Pattern in `Dockerfile.hardened` |
  | --- | --- | --- |
  | Static binary: Go `CGO_ENABLED=0`, Rust `*-unknown-linux-musl`, C/C++ `-static` | `scratch` | (A) |
  | Dynamically linked binary: C/C++, Rust-gnu, a distro-packaged tool | `scratch` + `ldd`-collected libs | (B) |
  | Same, when (B) gets fiddly (heavy `dlopen()`, NSS, OpenSSL providers, gconv) | distroless `cc`/`base`, Ubuntu chiselled images, Red Hat UBI Micro, Chainguard/Wolfi, Docker Hardened Images (free, Apache-2.0 since Dec 2025) | (C) |
  | Interpreted: Python, Node, Ruby, Java | distroless language images, DHI, Chainguard/Wolfi, Ubuntu chiselled, UBI Micro, `-slim` | (C) |
  | Alpine | Only if a package manager is needed at runtime (rare) | musl ≠ glibc: DNS (`ndots`), 128 KiB thread stack, wheel compilation, malloc contention, and auth code paths differ (sshhole) |

- **Scratch trade-offs.** Handle these on purpose; don't use them as a reason
  to ship an OS:
  - **Debugging without a shell.** Attach a throwaway toolbox to the
    container's namespaces instead of baking tools in:
    `docker run --rm -it --cap-add SYS_PTRACE --pid=container:app --network=container:app busybox:musl`
    (or in Kubernetes, an ephemeral debug container: `kubectl debug -it <pod> --image=cgr.dev/chainguard/wolfi-base --target=app`).
    The app's filesystem is at `/proc/1/root`. Reading it needs `SYS_PTRACE`,
    and only the debug container gets it. Alternatively, run `nsenter -t <pid> -n`
    from the host.
  - **Healthchecks.** There is no `curl`/`wget`, so build a `healthcheck`
    subcommand into the binary (pattern A), or probe from the proxy or another
    container.
  - **Scanners go blind.** There is no package database, so Trivy and Grype
    only see binaries with embedded metadata: Go buildinfo, Rust
    `cargo auditable`, jars. Put `ARG BUILDKIT_SBOM_SCAN_STAGE=true` in the
    build stages so `--sbom=true` records what went in, then scan *that* SBOM.
    A "0 CVEs" result on a scratch image proves nothing by itself.
  - **Missing files fail at runtime, not at build:**

    | Missing | Symptom | Fix |
    | --- | --- | --- |
    | CA bundle | x509 errors | Copy `ca-certificates.crt` |
    | `/etc/passwd` | "unknown userid" | Add the one-line passwd/group |
    | zoneinfo | "unknown time zone" | Copy zoneinfo, or embed it (Go `time/tzdata`) |
    | `/tmp` | Write errors | `--tmpfs /tmp` |
    | A `dlopen()`ed library | Fails only on the code path that loads it | Add it to pattern (B), or switch to (C) |

    In CI, run the image with production flags (`--read-only --cap-drop ALL
    --user 65532`) and exercise the real code paths.
  - **Static linking moves the libc choice into your build.** Go's pure
    resolver skips NSS plugins. musl-static binaries inherit musl's DNS,
    `crypt()` and locale behavior. Allocation-heavy Rust on musl wants
    mimalloc or jemalloc.
- **Pin by digest:** `FROM image:tag@sha256:...`, and `image: ...@sha256:`
  in compose. Tags are mutable, and a re-pushed tag is the supply-chain attack.
  Let Renovate or Dependabot bump digests via reviewed PRs.
- **Multi-stage builds + compiler hardening (`harden-build`).** Compilers,
  package managers and build secrets stay in the build stage, while the binary
  copied into `scratch`/`distroless` carries full production exploit
  mitigations:
  - **C/C++:** `-O2 -D_FORTIFY_SOURCE=3 -fPIE -pie -fstack-protector-strong
    -fstack-clash-protection -ftrivial-auto-var-init=zero -fcf-protection=full`
    (`-mbranch-protection=standard` on `aarch64`), Clang LTO `-fsanitize=cfi
    -fsanitize-trap=cfi`, `-D_GLIBCXX_ASSERTIONS`, and
    `-Wl,-z,relro,-z,now,-z,noexecstack`.
  - **Rust:** `overflow-checks = true`, `panic = "abort"`, `-C relro-level=full`,
    and `cargo auditable build --release` (embeds `.dep-v0` SBOM data into the
    ELF).
  - **Go:** `CGO_ENABLED=0 -trimpath -ldflags="-s -w -buildid="` (strips symbol
    tables while preserving `.go.buildinfo` for vulnerability scanners).
  - Gate the builder stage with `harden-build/scripts/check-elf.sh --strict`
    before the runtime `COPY --from=build` step, including `/venv` `.so` wheels
    for Python/Node images.
- **Non-root numeric `USER`.** App code is owned by root and not writable by
  the runtime user. Strip setuid bits.
- **`.dockerignore`** for `.git`, `.env*`, keys and `node_modules`. The build
  context ends up in layers otherwise.
- `HEALTHCHECK`. No `ADD <url>` without `--checksum=sha256:`. No
  `curl | sh` in RUN.
- **No sshd inside containers.** Use `docker exec` and host SSH. Alpine-based
  images running sshd were directly hit by sshhole (Nov 2026: a musl/no-PAM
  password bypass for `*` accounts). Before that, CVE-2019-5021 shipped
  Alpine images with an empty root password.
- **Scan and sign** with an SBOM: `--sbom=true --provenance=mode=max`, grype
  or trivy, and cosign. Pin and verify the scanners themselves too; the Trivy
  GitHub Actions and binary were compromised in March 2026. See
  `harden-supply-chain`.
- Lint with `docker build --check .` (BuildKit build checks) and hadolint.

## 8. Updates and lifecycle

- **Rebuild images at least weekly or on base-image CVE alerts.** A patched
  host does not patch containers.
- Prefer **digest bumps via PR + CI rebuild + deploy** over in-place
  auto-updaters that `pull :latest` into production (Watchtower-style). An
  auto-updater is an unreviewed supply-chain channel straight into prod, and
  it usually needs the Docker socket.
- `docker system df` plus a weekly prune timer
  (`docker image prune -af --filter until=168h`) keeps disks healthy.
- **Upgrading Docker itself:** read the release notes for firewall changes.
  28.x changed raw-table and FORWARD behavior; 29.x added the nftables
  backend and made the containerd image store the default. Then re-run the
  firewall canary (`harden-firewall` §4).

## Verification checklist

- `docker info`: seccomp and apparmor/selinux are present in Security Options;
  logging driver is `local` (or rotated); no TCP API.
- No container is privileged, uses host pid/network, mounts `docker.sock`
  (or uses a filtering proxy), or adds `SYS_ADMIN`/`NET_ADMIN`.
- `iptables -t nat -S DOCKER` (or nft `docker-bridges`) shows DNAT only for
  intended public ports. The outside scan agrees. The canary is filtered.
- `docker exec <c> id` is non-root, or `docker top` shows the dropped user.
  `touch /x` fails on read-only containers.
- `docker run --rm --network <app-net> curlimages/curl -m2 http://169.254.169.254/`
  fails.
- `docker inspect` shows no secret values in `Config.Env`.
