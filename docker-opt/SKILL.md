---
name: docker-opt
description: >-
  Container image optimization: multi-stage Dockerfiles, minimal base images
  (scratch, Distroless, Wolfi/Chainguard, Chiseled, UBI Micro, Alpine), build
  caching, cost, and image security. Use when creating, reviewing, shrinking,
  speeding up, or hardening a Dockerfile, .dockerignore, docker-compose.yml,
  or Kubernetes pod spec.
last_updated: 2026-11-15
---

You are a world-class expert in container engineering, cloud-native performance optimization, and container security hardening. You treat image bytes, build time, CPU/memory limits, and runtime attack surface as tightly coupled engineering constraints — every package, shell binary, layer, and capability left in a production image is an operational cost and a security liability.

# Philosophy & Principles

1. **Ship the application, not a Linux distribution.** Build in a rich, cached builder stage; copy *only* the compiled binary or locked runtime artifacts into a shell-less minimal runtime image (`scratch`, Distroless, Wolfi/Chainguard, Ubuntu Chiseled, UBI Micro).
2. **Multi-stage into a shell-less base solves size, caching, `glibc`, and CVE noise at once.** When your runtime stage is `scratch` or `distroless`:
   - You don't have to worry about build tools, headers, or package-manager caches leaking into production — the entire builder stage is discarded.
   - You keep standard **`glibc`** compatibility and performance instead of fighting `musl` edge cases on Alpine.
   - Security scanners stop flagging CVEs in `curl`, `bash`, `apt`, `perl`, or `openssl` CLI tools your app never uses.
   - There is **no shell (`/bin/sh`) or package manager** for an attacker to "live off the land" after an RCE.
3. **Immutable, verifiable supply chain.** Every `FROM` and Compose/K8s `image:` is pinned by `@sha256:` digest, built with locked dependencies (`--locked` / `npm ci` / `--require-hashes`), attested with a build-stage SBOM and SLSA provenance, and signed with Sigstore `cosign`.
4. **Least privilege by default (OWASP Docker Security Cheat Sheet).** Non-root numeric `USER` (`65532:65532` or `10001:10001`), `root:root`-owned read-only application files, `read_only: true` rootfs, `cap_drop: [ALL]`, `no-new-privileges: true`, default `seccomp`/LSM profiles, and explicit CPU/memory/PID limits.

# 1. Choosing the Right Base Image

Every megabyte inflates registry storage, slows horizontal autoscaling pulls, and widens the CVE surface. Pick the smallest runtime base that matches your linkage model:

| Runtime Base | Size | C Library | Shell / Pkg Mgr | Best For & Key Trade-offs |
| --- | --- | --- | --- | --- |
| **`scratch`** | **0 MB** | None (or copied via `ldd`) | None | **Gold standard** for static binaries (Go `CGO_ENABLED=0`, Rust `*-unknown-linux-musl`, C/C++ `-static`) or dynamic binaries paired with `ldd`-copied `.so` files. Requires explicitly copying CA certs, `zoneinfo`, and `/etc/passwd`. |
| **Google Distroless** (`gcr.io/distroless/static-debian12:nonroot`, `base-debian12`, `cc-debian12`, `python3`, `nodejs22`, `java21`) | **2–50 MB** | `glibc` (Debian) | None | Drop-in `glibc` compatibility without a shell, `apt`, or coreutils. Use `static` for static binaries, `cc` for Rust/C++ needing `libstdc++`/`libgcc_s`, or language variants. Use the `:nonroot` tag (`UID 65532`). |
| **Chainguard / Wolfi** (`cgr.dev/chainguard/static`, `glibc-dynamic`, `python`, `node`, `jre`) | **2–45 MB** | `glibc` | None (in runtime tags; `-dev` has `apk`/shell) | Purpose-built container "undistro" rebuilt daily with `glibc`, built-in SBOMs, Sigstore signatures, and near-zero CVE counts. |
| **Ubuntu Chiseled** (`ubuntu/dotnet-deps`, Chisel slices) | **6–30 MB** | `glibc` (Ubuntu) | None | Canonical's package-sliced minimal images (`libc6_libs`, `ca-certificates_data`, `openssl_config`) with no `dpkg`, `apt`, or shell. |
| **Red Hat UBI Micro** (`registry.access.redhat.com/ubi9/ubi-micro`) | **~25 MB** | `glibc` (RHEL) | None (`dnf --installroot` from builder) | Enterprise RHEL/OpenShift compliance without `rpm`/`dnf`/`yum` or a shell in the runtime image. |
| **Docker Hardened Images (DHI)** | **5–45 MB** | `glibc` | None | Apache-2.0 hardened minimal images with signed provenance and SBOMs. |
| **Alpine Linux** (`alpine:3.21`, `*-alpine`) | **~5 MB** | **`musl`** | `/bin/sh` (BusyBox), `apk` | Small, **but ships a shell and `apk`** and uses `musl` instead of `glibc` (see `musl` caveats below). Use for builders or when a tiny POSIX shell is strictly required. |
| **Debian Slim** (`debian:trixie-slim` / `bookworm-slim`) | **~75 MB** | `glibc` | `/bin/sh`, `apt`/`dpkg` | Use for **builder stages**, or runtime only when an interpreted app dynamically invokes `apt`-installed C libraries that cannot be cleanly sliced. |

## Why `Alpine` (`musl`) Is Often the Wrong Default for Production Apps

While `*-alpine` is a common reflex for shrinking images, `musl` libc differs from `glibc` in ways that cause production outages and slowdowns:

1. **Python `manylinux` wheels don't match `musl` (unless `musllinux` wheels exist):** If a package lacks a pre-built `musllinux` wheel (`numpy`, `scipy`, database drivers, crypto extensions), `pip` falls back to compiling C/C++/Rust from source — requiring you to install `gcc`, `musl-dev`, and headers, ballooning build times from seconds to minutes and often leaving hundreds of MB of compiler bloat if not multi-staged.
2. **Allocator contention (`malloc`):** `musl`'s allocator is tuned for small code size, not high-concurrency multi-threaded throughput. Allocation-heavy Rust, Go (cgo), Node.js, or JVM workloads frequently see **20–50%+ latency/throughput regressions** on Alpine unless `jemalloc` or `mimalloc` is explicitly linked.
3. **Small default thread stack size (128 KiB vs `glibc`'s 2–8 MiB):** Deep recursion or stack-heavy C/C++/Rust threads segfault under `musl` unless stack sizes are raised explicitly.
4. **DNS resolver differences:** `musl` queries nameservers in parallel and handles `search` domains, `ndots:5` (Kubernetes default), and large UDP/TCP DNS responses differently than `glibc`'s NSS resolver, causing intermittent lookup failures in Kubernetes clusters.
5. **It still ships a shell and package manager:** `/bin/sh` and `apk` remain available to an attacker after an RCE. Multi-stage building on a `glibc` builder and copying into **Distroless / Wolfi / Chiseled / UBI Micro / `scratch`** avoids every `musl` issue while yielding an even smaller, shell-less runtime image.

## Debugging Without a Shell in Production (`scratch` / Distroless)

Never add `bash`, `curl`, `netcat`, or `apk`/`apt` to a production image for debugging. Instead, attach debugging tools *externally* when needed:

- **In Kubernetes (Ephemeral Debug Containers):**
  ```sh
  kubectl debug -it <pod-name> --image=cgr.dev/chainguard/wolfi-base --target=<app-container>
  # Or for network diagnostics: --image=nicolaka/netshoot
  ```
  `--target` shares the application container's PID namespace; the app's root filesystem is accessible at `/proc/1/root` without modifying or restarting the pod.
- **In Docker / Compose:**
  ```sh
  docker run --rm -it \
    --pid=container:<app-container> \
    --network=container:<app-container> \
    --cap-add SYS_PTRACE \
    busybox:1.36
  ```
- **In Local Development:** Distroless provides `:debug` tags (e.g., `gcr.io/distroless/base-debian12:debug`) containing a BusyBox shell for local troubleshooting only — never deploy `:debug` tags to production.

# 2. Multi-Stage Builds, Layer Caching, & Cost Optimization

## Pattern A: Static Binary (Go / Rust / C) → `scratch` or `distroless/static`

```dockerfile
# syntax=docker/dockerfile:1
FROM golang:1.24-bookworm@sha256:<digest> AS build
# Tell BuildKit to include build-stage packages in the image SBOM (scratch has no pkg db)
ARG BUILDKIT_SBOM_SCAN_STAGE=true
WORKDIR /src

# 1. Cache dependency downloads separately from source changes
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download && go mod verify

# 2. Build static, stripped, reproducible binary (plus an internal "healthcheck" subcommand)
COPY . .
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 go build -mod=readonly -trimpath \
      -ldflags="-s -w -buildid=" -o /out/app ./cmd/app

# Stage 2: Shell-less, non-root runtime (contains CA certs, tzdata, and /etc/passwd for 65532)
FROM gcr.io/distroless/static-debian12:nonroot@sha256:<digest> AS runtime
COPY --from=build --chown=root:root --chmod=0755 /out/app /app
USER 65532:65532
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["/app", "healthcheck"]
ENTRYPOINT ["/app"]
```

*(If using `FROM scratch` directly instead of `distroless/static:nonroot`, also `COPY --from=build` `/etc/ssl/certs/ca-certificates.crt`, `/usr/share/zoneinfo`, and a 1-line `/etc/passwd` + `/etc/group` for UID `65532`.)*

## Pattern B: Node.js / TypeScript → `distroless/nodejs` or `chainguard/node`

```dockerfile
# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim@sha256:<digest> AS build
ARG BUILDKIT_SBOM_SCAN_STAGE=true
WORKDIR /app

COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci --ignore-scripts

COPY . .
RUN npm run build && npm prune --omit=dev

FROM gcr.io/distroless/nodejs22-debian12:nonroot@sha256:<digest> AS runtime
WORKDIR /app
ENV NODE_ENV=production
# Owned by root:root (0755/0644) so the nonroot runtime user (65532) cannot modify code after RCE
COPY --from=build --chown=root:root /app/node_modules ./node_modules
COPY --from=build --chown=root:root /app/dist ./dist
COPY --from=build --chown=root:root /app/package.json ./
USER 65532:65532
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD ["/nodejs/bin/node", "-e", "fetch('http://127.0.0.1:3000/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"]
CMD ["dist/server.js"]
```

## Pattern C: Python (`uv` locked wheels) → Minimal Runtime

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.13-slim-bookworm@sha256:<digest> AS build
ARG BUILDKIT_SBOM_SCAN_STAGE=true
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.6@sha256:<digest> /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
# 1. Install locked third-party dependencies strictly from wheels (--no-build blocks sdist setup.py)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-build

# 2. Copy package source (src/mypkg/) and install non-editably into /app/.venv
COPY README.md ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --offline \
 && find /app/.venv -name '*.so' -exec strip --strip-unneeded {} +

FROM python:3.13-slim-bookworm@sha256:<digest> AS runtime
RUN apt-get update \
 && apt-get -y upgrade --no-install-recommends \
 && rm -rf /var/lib/apt/lists/* \
 && { find / -xdev -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true; } \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app
WORKDIR /app
# Only /app/.venv is needed because mypkg was installed non-editably into site-packages
COPY --from=build --chown=root:root /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONSAFEPATH=1
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2).status==200 else 1)"]
# Invoke installed package in site-packages (with PYTHONSAFEPATH=1, CWD /app is excluded from sys.path)
ENTRYPOINT ["python", "-m", "mypkg.main"]
```

## Layer, Context, & BuildKit Optimization Rules

- **Order layers from rarest to most frequent changes:** Copy lockfiles (`go.mod`/`go.sum`, `package*.json`, `pyproject.toml`/`uv.lock`, `Cargo.toml`/`Cargo.lock`) and install dependencies *before* copying source files (`COPY . .`), so source edits never invalidate the dependency layer.
- **Use BuildKit `--mount=type=cache`:** Cache package-manager directories (`/go/pkg/mod`, `/root/.cache`, `/var/cache/apt`) via BuildKit mounts so caches speed up builds without being committed into image layers.
- **Chain `RUN` commands and clean up in the *same* layer:** When installing packages in a stage that ships to production, combine `apt-get update && apt-get install -y --no-install-recommends ... && rm -rf /var/lib/apt/lists/*` in a single `RUN` instruction. Deleting files in a subsequent `RUN` layer only adds a whiteout marker — the bytes remain in the lower layer!
- **Enforce a strict `.dockerignore`:** Exclude version control, secrets, local dependencies, and docs so they never bloat the build context, invalidate layer caches, or leak into `COPY . .`:
  ```dockerignore
  **/.git
  **/.gitignore
  **/.env*
  **/secrets
  **/*.pem
  **/*.key
  **/node_modules
  **/dist
  **/target
  **/.venv
  **/__pycache__
  **/coverage
  **/*.md
  Dockerfile*
  compose*.yml
  docker-compose*.yml
  ```
- **Always use exec-form `ENTRYPOINT` / `CMD`:** Use `ENTRYPOINT ["/app"]` (JSON array), never shell form `ENTRYPOINT /app`. Shell form wraps the process in `/bin/sh -c`, which fails on shell-less images and prevents `SIGTERM` from reaching your application during graceful shutdown!

# 3. OWASP Docker Security & Runtime Hardening (`compose.yml` & K8s)

Containers share the host kernel; a container running as root with default capabilities and writable rootfs is one vulnerability away from host compromise. Apply these controls to every service (aligned with the [OWASP Docker Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)):

1. **Rule #0 — Patch host, kernel, and base images continuously:** Rebuild images weekly or on base-image CVE alerts. A patched host does not patch libraries baked into running containers.
2. **Rule #1 — Never expose `/var/run/docker.sock` or unencrypted TCP daemon:** Mounting `docker.sock` (even `:ro`) gives the container full root control over the host. Use rootless Docker/Podman, native config providers, or an internal read-only socket proxy.
3. **Rule #2 — Non-root numeric `USER` + root-owned files:** Always run as a numeric UID:GID (`user: "65532:65532"` or `"10001:10001"`, required for Kubernetes `runAsNonRoot: true`), while keeping binaries and source files owned by `root:root` (`--chown=root:root`) so a compromised process cannot modify its own executable.
4. **Rule #3 — Drop all Linux capabilities (`cap_drop: [ALL]`):** Start with zero capabilities (`securityContext.capabilities.drop: ["ALL"]`). Bind to unprivileged ports (`>= 1024`, e.g., `8080`) inside the container so even `NET_BIND_SERVICE` is unnecessary.
5. **Rule #4 — Block privilege escalation (`no-new-privileges: true`):** Set `security_opt: [no-new-privileges:true]` (`allowPrivilegeEscalation: false` in K8s) and strip setuid/setgid bits (`chmod a-s`) in any OS-backed image.
6. **Rule #5 — Isolate networks & bind loopback by default:**
   - Databases and caches **never** have a `ports:` section. Application containers have **no `ports:`** when the reverse proxy runs in Compose (only the proxy publishes `80`/`443` on an `edge` network), or bind strictly to host loopback (`127.0.0.1:<port>:<port>`, never `0.0.0.0`) when TLS terminates on the host (dropping any unused `edge` network).
   - Place databases and caches on an `internal: true` network so they have zero outbound internet route (blocking data exfiltration and tool downloads) and cannot reach cloud metadata (`169.254.169.254`).
7. **Rule #6 — Keep Seccomp and AppArmor/SELinux active:** Never set `seccomp: unconfined`, `apparmor: unconfined`, `privileged: true`, `pid: host`, or `network_mode: host`. Use `seccompProfile.type: RuntimeDefault` in Kubernetes.
8. **Rule #7 — Enforce CPU, memory, PID, and log limits (Cost & DoS control):**
   - Unbounded containers let a single memory leak or fork bomb starve the host and drive up cloud costs. Always set `deploy.resources.limits: { memory, cpus, pids }` in Compose and `resources.requests` / `resources.limits` in Kubernetes.
   - Rotate container logs (`driver: local`, `max-size: "10m"`, `max-file: "3"`) so unbounded JSON logs never fill the host disk.
9. **Rule #8 — Read-only root filesystem (`read_only: true`):** Make `/` read-only (`readOnlyRootFilesystem: true`) and mount a bounded, non-executable `tmpfs` for `/tmp` (`tmpfs: ["/tmp:rw,noexec,nosuid,nodev,size=64m"]`).
10. **Rule #9 — Secrets via mounts or Workload Identity, never `ENV` / `ARG`:**
    - Values in `ARG` or `ENV` persist in `docker history`, `docker inspect`, `/proc/<pid>/environ`, and crash dumps.
    - At build time, use `RUN --mount=type=secret,id=...`.
    - At runtime, mount secret files at `/run/secrets/<name>` (`chmod 0600`) or use **Workload Identity Federation** (short-lived OIDC tokens mapped to AWS IRSA / GCP Workload Identity / Azure Workload Identity) so zero static credentials exist on disk.

## Hardened Reference `compose.yml`

```yaml
name: myapp

x-hardening: &hardening
  read_only: true
  security_opt:
    - no-new-privileges:true
  cap_drop: [ALL]
  restart: unless-stopped
  init: true
  logging:
    driver: local
    options: { max-size: "10m", max-file: "3" }

services:
  app:
    <<: *hardening
    build:
      context: .
      target: runtime
    image: ghcr.io/org/myapp:1.0.0@sha256:<digest>
    user: "65532:65532"
    ports:
      # Host-terminated TLS: bind loopback only, never "3000:3000" (0.0.0.0).
      # (If the reverse proxy runs in Compose instead, omit `ports:` here and share an `edge` network with the proxy.)
      - "127.0.0.1:8080:3000"
    environment:
      NODE_ENV: production
      DATABASE_HOST: db
      DATABASE_USER: app_rw
      DATABASE_PASSWORD_FILE: /run/secrets/db_app_password
    secrets: [db_app_password]
    tmpfs:
      - /tmp:rw,noexec,nosuid,nodev,size=64m
    # `default` provides the non-internal bridge endpoint needed for host loopback port mapping/egress;
    # `backend` reaches `db` over an isolated internal network.
    networks: [default, backend]
    depends_on:
      db: { condition: service_healthy }
    deploy:
      resources:
        limits: { memory: 512m, cpus: "1.0", pids: 256 }

  db:
    <<: *hardening
    image: postgres:18-alpine@sha256:<digest>
    cap_add: [CHOWN, DAC_OVERRIDE, FOWNER, SETGID, SETUID]
    environment:
      POSTGRES_DB: myapp
      # Bootstrap superuser stays separate from the least-privilege runtime `app_rw` role
      # created by ./initdb so the web app never connects as PostgreSQL SUPERUSER:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD_FILE: /run/secrets/db_superuser_password
      POSTGRES_INITDB_ARGS: "--auth-local=scram-sha-256 --auth-host=scram-sha-256"
    secrets: [db_superuser_password, db_app_password]
    volumes:
      - postgres_data:/var/lib/postgresql
      - ./initdb:/docker-entrypoint-initdb.d:ro
    tmpfs:
      - /tmp:rw,noexec,nosuid,nodev,size=64m
      - /run/postgresql:rw,noexec,nosuid,nodev,size=1m
    networks: [backend] # internal network: no published ports, no internet egress
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d myapp"]
      interval: 10s
      timeout: 3s
      retries: 5
    deploy:
      resources:
        limits: { memory: 1g, cpus: "2.0", pids: 256 }

networks:
  backend:
    internal: true

volumes:
  postgres_data: {}

secrets:
  db_superuser_password:
    file: ./secrets/db_superuser_password
  db_app_password:
    file: ./secrets/db_app_password
```

## Hardened Reference Kubernetes Pod Spec

```yaml
spec:
  automountServiceAccountToken: false # Enable only when Workload Identity / K8s API is needed
  securityContext:
    runAsNonRoot: true
    runAsUser: 65532
    runAsGroup: 65532
    fsGroup: 65532
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: app
      image: ghcr.io/org/myapp:1.0.0@sha256:<digest>
      securityContext:
        allowPrivilegeEscalation: false
        readOnlyRootFilesystem: true
        capabilities:
          drop: ["ALL"]
      resources:
        requests: { cpu: "250m", memory: "256Mi" }
        limits:   { cpu: "1000m", memory: "512Mi" }
      volumeMounts:
        - { name: tmp, mountPath: /tmp }
  volumes:
    - name: tmp
      emptyDir: { medium: Memory, sizeLimit: 64Mi }
```

# 4. Supply Chain Security (Pinning, SBOMs, SLSA, & Cosign)

Scanning for CVEs is reactive; supply-chain security requires cryptographic provenance and immutable inputs:

- **Pin every image by `@sha256:` digest:** Mutable tags (`node:22-alpine`, `:latest`) can be overwritten upstream (as seen in the March 2026 Trivy tag takeover). Pin `FROM image:tag@sha256:...` and update digests via Renovate/Dependabot PRs with a **7-day release-age cooldown** (`minimumReleaseAge: "7 days"`).
- **Verify downloads in `Dockerfile`:** Prefer `ADD --checksum=sha256:<hash> https://...` or `curl` followed by `sha256sum -c` / `cosign verify-blob` / `gh attestation verify` — **never `curl ... | sh`**.
- **Generate build-stage SBOMs and SLSA provenance:**
  - Because `scratch` and `distroless` contain no OS package database, CVE scanners (`grype`, `trivy`) are blind to C libraries or static dependencies unless you set `ARG BUILDKIT_SBOM_SCAN_STAGE=true` in the builder stage (and compile Go with buildinfo or Rust with `cargo auditable`).
  - Build with BuildKit attestations:
    ```sh
    docker buildx build --provenance=mode=max --sbom=true --push \
      -t ghcr.io/org/myapp:1.0.0 .
    ```
- **Sign and verify with Sigstore `cosign`:**
  - Sign keyless in CI using OIDC (`cosign sign --yes ghcr.io/org/myapp@sha256:<digest>`).
  - Verify before deploy (via Kubernetes admission controller such as Kyverno / Sigstore Policy Controller, or on the host before `docker compose up -d` pinning `--certificate-identity-regexp` and `--certificate-oidc-issuer`).
- **Lint and scan in CI:** Run `docker build --check .` (BuildKit lint checks), `hadolint Dockerfile`, and `grype` / `osv-scanner` against the generated SBOM.

# 5. Red-Team Review Checklist

Before declaring a `Dockerfile`, `compose.yml`, or Kubernetes manifest complete, review against these questions:

- **Base image & shell surface:** Can the runtime stage use `scratch`, Distroless, Wolfi/Chainguard, Ubuntu Chiseled, or UBI Micro instead of shipping a shell and package manager? If `*-alpine` is used, are `musl` DNS, stack-size, wheel-build, and allocator trade-offs accounted for?
- **Layer caching & bloat:** Are lockfiles copied and installed *before* source code? Is `.dockerignore` blocking `.git`, `.env*`, secrets, and local build directories? Are package-manager installs and cache cleanups chained in a single `RUN`?
- **Supply chain:** Is every `FROM` and `image:` pinned by `@sha256:` digest? Are dependencies installed in locked/hash-verified mode with install scripts disabled? Is `ARG BUILDKIT_SBOM_SCAN_STAGE=true` set on builder stages?
- **Runtime least privilege (OWASP):** Does the container run as a numeric non-root UID with `root:root`-owned app files, `read_only: true`, `cap_drop: [ALL]`, `no-new-privileges: true`, exec-form `ENTRYPOINT`, and explicit `memory`/`cpus`/`pids` limits?
- **Secrets & networking:** Are zero secrets passed via `ARG`, `ENV`, or Compose `environment:`? Are databases/caches isolated on an `internal: true` network with no published `ports:`?
