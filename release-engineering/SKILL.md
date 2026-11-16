---
name: release-engineering
description: >-
  Release engineering and CI/CD architecture for containers, native binaries,
  desktop and mobile apps, libraries, cloud services, and firmware OTA:
  deployment model selection, reproducible builds, artifact size minimization,
  build-once promotion, canary and ring rollout, and fast rollback. Use when
  designing or reviewing a build, release, or deploy pipeline, packaging or
  versioning an artifact, or planning a rollout or rollback.
last_updated: 2026-11-15
---

# Hermetic Builds, Minimal Artifacts & First-Principles CI/CD (`release-engineering`)

Bridges committed source code to running production systems with **deterministic
bytes, minimal runtime footprint, right-sized CI/CD trust boundaries, progressive
blast-radius control, and instant rollback** — across cloud containers, standalone
CLI/server binaries, mobile/desktop bundles, libraries, WebAssembly, and embedded
firmware OTA images.

* Consult [references/reproducibility-and-footprint.md](references/reproducibility-and-footprint.md)
  for the 7-point reproducibility checklist, cross-language compiler/linker
  footprint recipes, detached `.debug` symbol workflows, and CI size-budget gates.
* Consult [references/cicd-topologies-and-actuation.md](references/cicd-topologies-and-actuation.md)
  for first-principles CI/CD topology selection (Manual vs. Push vs. Host-Timer Pull
  vs. Cluster GitOps / TUF Fleet Pull), closing the "GitOps auto-commit illusion",
  outcome-based expectations, release blocks, and AI-agent CI/CD schemas.
* Consult [references/progressive-delivery-and-rollback.md](references/progressive-delivery-and-rollback.md)
  for build-once digest promotion, canary/ring rollout schedules, feature-flag
  lifecycles, `SIGTERM` zero-drop drain, and brick-proof firmware `A/B` OTA handshakes.

*(When authoring container `Dockerfile`s or locking down compiler exploit mitigations
and CI runner permissions, also activate any available container-image optimization,
binary build-hardening, and software supply-chain security skills.)*

---

## 1. Hermetic & Bit-for-Bit Reproducible Builds

**"Same git commit + lockfile => identical `SHA-256` output bytes on any machine."**
Reproducibility proves no build runner tampered with outputs, maximizes build-cache
hit rates, and makes delta updates tiny:

1. **Two-Phase Hermeticity (`Fetch` -> `Offline Build`):**
   * **Phase 1 (Fetch):** Resolve and verify cryptographic hashes of all locked
     dependencies and pinned toolchains (`--locked` / `--frozen-lockfile` /
     `-mod=readonly`) into a local cache.
   * **Phase 2 (Compile & Package — Network Off):** Execute compilation, codegen,
     and packaging with **zero network access** (`--offline`, container
     `--network=none`, or hermetic sandbox), isolated from ambient host `/usr/local`,
     `$HOME` rc files, and unpinned system compilers.
2. **Eliminate All 7 Build-Entropy Sources:**
   * **Clocks:** Set `SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)` and `TZ=UTC`;
     ban `__DATE__`, `__TIME__`, and wall-clock build timestamps; clamp archive/
     wheel/OCI layer mtimes to `@$SOURCE_DATE_EPOCH`.
   * **Build paths:** Remap absolute workspace paths (`-ffile-prefix-map=$PWD=.` in
     C/C++, `go build -trimpath`, Rust `--remap-path-prefix`, relative Python/JS
     paths) so `/home/dev/app` and `/ci/job-92/app` emit identical instructions and
     DWARF metadata.
   * **Filesystem & locale order:** Force `LC_ALL=C.UTF-8` and sort every directory
     walk or glob (`tar --sort=name`, deterministic `ar D`, sorted codegen maps) —
     never inherit `ext4` vs. `APFS` `readdir()` order!
   * **Owner/permission metadata:** Normalize archive UID/GID and umask (`tar
     --owner=0 --group=0 --numeric-owner --mode='u+rwX,go+rX,go-w'`, explicit
     `0755`/`0644` modes).
   * **Deterministic Build-IDs (Keep debuggability without random UUIDs!):** Use
     content-hashed build IDs (`-Wl,--build-id=sha1` on ELF) rather than random
     `--build-id=uuid` or stripping build IDs blindly — giving crash dumps and
     tokenized traces an immutable key while staying 100% reproducible!
   * **Target CPU baseline:** Never pass `-march=native` / `target-cpu=native` in
     distributed releases (causes runner-dependent output drift and `SIGILL` crashes
     on older CPUs; target explicit baselines like `x86-64-v2`/`v3` or runtime SIMD
     dispatch).
3. **Verify, don't assume:** Run a CI reproducibility check building twice under
   distinct paths/umasks and asserting identical `SHA-256` (using `diffoscope` to
   pinpoint any stray timestamp or unsorted symbol table).

---

## 2. Minimize Release Artifact & Image Footprint

Every unnecessary megabyte in a release artifact **slows cold starts and autoscaling
pulls, inflates OTA/CDN bandwidth and flash wear, and ships extra attack surface
("living-off-the-land" shells, unused C parsers, and unreferenced dependencies)**:

1. **Ship Only the Runtime Closure (Discard the Builder):**
   * **Containers:** Compile in a cached builder stage and copy **only** the minimal
     executable closure into a shell-less runtime base (`scratch` for static or
     `ldd`-sliced binaries; Distroless, Wolfi/Chainguard, Ubuntu Chiseled, or UBI
     Micro when `glibc`/CA-certs/tzdata are needed — `0` shell, `0` package manager,
     `0` build toolchain).
   * **Standalone binaries & packages:** Link against a minimal baseline (`static`
     when pure, or an old `glibc` sysroot such as Zig `cc` / Debian oldstable so one
     small binary runs everywhere without bundling a 500 MB runtime).
   * **Mobile / Desktop / Web:** Emit per-ABI split bundles (never ship `x86_64` +
     `arm64` `.so` copies inside one mobile download!), prune dev dependencies,
     subset fonts, data-slice locale tables, and pre-compress static assets
     (`zstd` / `brotli -q 11`).
2. **Strip Runtime Payloads — Archive Detached Debug Symbols Separately:**
   * Never choose between *"bloated 180 MB unstripped production binary"* and *"blind
     unsymbolicated hex stack traces"*!
   * Extract full DWARF/PDB/dSYM/source-map/firmware-token tables into a **separate
     symbol artifact** keyed by deterministic `Build-ID` (`objcopy --only-keep-debug`
     + `strip --strip-unneeded`, Rust `debug = true` (or `debug = "line-tables-only"`)
     + `split-debuginfo = "packed"` + `strip = "symbols"`), upload symbols to your
     crash/trace store, and ship **only** the lean stripped binary (`5–10x` smaller!).
3. **Dead-Code Elimination & Size-Budget Gates:**
   * Enable function/data section GC + LTO (`-ffunction-sections -fdata-sections
     -Wl,--gc-sections -flto`, Rust `lto = "thin"`/`"fat"`), disable default
     dependency features (`default-features = false`), and optimize Wasm with
     `wasm-opt`.
   * **Gate PRs on size regressions:** Measure compressed image/binary/Flash-ROM/RAM
     delta in CI (e.g., `bloaty`, `cargo-bloat`, `twiggy`, ELF `size`) and fail
     builds that breach Flash limits or jump unexpectedly (`> 5–10%`).

---

## 3. First-Principles CI/CD Topology & Actuation Ladder

Separate **three distinct trust planes** instead of treating "CI/CD" as one privileged
monolith:
1. **Plane 1 — CI (`Pure Function, Zero Prod Credentials`):** `(Commit + Lockfile) ->
   Signed Artifact@sha256 + Symbols + Provenance`. CI parses untrusted PRs/deps and
   must **never** hold standing production keys — even when deployment is manual,
   **builds/tests stay automated and deterministic** (never compile releases from a
   dirty developer working tree!).
2. **Plane 2 — Release Authorization (`Policy Gate`):** Cryptographic human sign-off
   (`FIDO2`/GPG tag or PR — *Continuous Delivery*) or automated canary/branch policy
   attestation (*Continuous Deployment*).
   * **Beware the "GitOps Auto-Commit Illusion":** Moving from Push to Pull gives
     **zero** security gain if CI can directly `git push` unreviewed image digests to
     the GitOps `main` branch and the cluster blindly syncs it! By transitivity, a
     compromised CI runner still owns production unless target actuation verifies an
     independent policy/signature boundary.
3. **Plane 3 — CD Actuation (`Pick the Lightest Rung That Fits Target Physics`):**
   Derive actuation from **fleet size ($N$), deploy cadence ($f$), inbound network
   reachability/NAT, blast radius, and daemon tax** — earning every moving part:
   * **Rung 0 — Scripted `FIDO2` Manual Actuation (`N = 1–3` hosts, low $f$, small
     team):** Developer triggers **one idempotent script** (`./scripts/deploy.sh prod
     v1.4.2 <sha256>`) over hardware-key SSH (`ed25519-sk`). Target verifies `minisign`
     / `cosign`, swaps symlink/container atomically, checks `/readyz`, and auto-reverts
     on failure. **Cost: `0` CD daemons, `0` prod credentials stored in CI!**
   * **Rung 1 — Host-Local Timer Pull (`N = 1–50` VMs / NAT'd appliances, no K8s):**
     An OS-native `systemd.timer` (`60 s` + jitter, **`0` inbound ports**) polls a
     tiny signed `prod.json` manifest over HTTPS (`ETag`), verifies signature +
     monotonic timestamp freshness + `@sha256`, cutovers atomically, and reverts on
     failed `/readyz` — giving **100% of Pull's zero-inbound-port & NAT safety with
     zero Kubernetes/controller bloat**.
   * **Rung 2 — Ephemeral OIDC Scoped Push (`N = 1–10` cloud PaaS / serverless / CDN /
     IaC targets):** When target APIs are cloud-managed and synchronous fail-fast job
     feedback matters, run deploy in an isolated **Protected Environment** job with
     `concurrency` serialization and a **short-lived (`5–15 min`) OIDC token** scoped
     strictly to updating that single service's digest (never static keys or broad
     cloud admin!).
   * **Rung 3 — Declarative Cluster GitOps / TUF Fleet Pull (`5–500` K8s clusters or
     `10^2–10^7` client/firmware devices):** Use scoped in-cluster reconcilers
     (`Flux`/`Argo CD` with signed-commit verification and separate app vs. state
     repos) or **TUF/Uptane** client OTA pollers with offline root keys, short-lived
     timestamp anti-freeze metadata, and deterministic cohort bucketing.

---

## 4. Candidate Qualification, Config Pushes & Release Controls

1. **Three-Stage Test Funnel & "Qualified Candidate" Selection:**
   * Run **`Local Fast Checks (< 10 s)` -> `Presubmit PR Checks` -> `Postsubmit
     Integration Qualification`**. Under high commit or agent throughput, two green
     PRs can break `main` when combined (*semantic merge skew*) — use a merge queue or
     cut release candidates strictly from the **newest postsubmit-green,
     non-quarantined commit**, snapshotting the release pipeline config with the
     candidate so in-flight rollouts never mutate mid-flight.
2. **Never Rebuild Per Environment ("Build Once, Promote Digest"):**
   * Build **one environment-agnostic artifact** once, sign its `SHA-256` digest, and
     promote that exact digest (`autopush/dev -> staging -> canary -> prod`).
3. **Separate Fast Data-Config Pushes from Binary Pushes — Keep Canary Physics:**
   * Package pure-data configs separately from binaries so urgent tuning/kill-switches
     build in seconds rather than hours, and **serialize concurrent config pushes**.
   * **Never skip canarying a config!** Configs activate untested code paths and cause
     outages: validate config schemas/invariants in CI and stage config rollouts
     through **`1 cell / 10% -> short soak (e.g., 5 min) -> automated control-vs-canary
     SLI comparison -> rest of fleet`**.
4. **Enforce `N-1` / `N-2` Wire & Schema Compatibility:**
   * Rolling server deploys require **`N-1` compatibility** (`Expand -> Backfill ->
     Contract`); lagging mobile/CLI/firmware clients require explicit
     **`min_supported_client_version`** windows + CI wire-compatibility gates.
5. **Commit Lineage, Release Blocks & "Rollback + Quarantine":**
   * Maintain an instant **commit-to-environment status query** (`status <commit>`):
     if a bad commit is caught *before* `prod`, **quarantine the commit/candidate and
     place a reason-linked Release Block**; if it already reached `preprod`/`prod`,
     **roll back the digest AND atomically quarantine/block the bad candidate** so
     automated promoters or pull reconcilers cannot immediately re-deploy it!

---

## 5. Progressive Delivery, Feature Flags & Sub-Minute Rollback

Treat deployment (placing bytes) as distinct from release (exposing traffic):

1. **Ringed / Canary Blast-Radius Progression:**
   * Roll out across isolated failure domains (`Dogfood/Internal -> 1% Canary ->
     10% Single-AZ/Cell -> 50% -> 100%`) with mandatory bake windows — **never** push
     a global config change, binary, or firmware OTA to `100%` of regions/units at once!
2. **Automated SLI Guardrails & Sub-Minute Rollback:**
   * Compare canary vs. baseline control on core SLIs (error rate, `p99` latency,
     crash-free sessions, saturation); auto-halt and revert to the **previous pinned
     digest** in `< 60 s` on breach. Never "roll forward with a rushed hotfix" while
     production is burning if a clean digest revert is available!
3. **Short-Lived Feature Flags (Prevent Flag Debt):**
   * Every release flag carries an owner, default-off safe state, and **removal
     ticket/expiry date**; delete flag branches promptly once `100%` baked.
4. **Zero-Drop `SIGTERM` Drain & Brick-Proof Firmware `A/B` OTA:**
   * **Services:** On `SIGTERM`, flip readiness to `draining` immediately, wait LB
     propagation delay (`2–5 s`), finish in-flight work within deadline, and exit `0`.
   * **Firmware / Appliances:** Use dual **`A/B` partitions + Bootloader Trial
     Confirmation** under hardware watchdog timer; confirm `Slot B` *only* after
     self-test and healthy communication succeed, else auto-revert to `Slot A`.

---

## 6. Outcome Expectations & AI-Agent-Ready CI/CD

1. **Model Declarative Outcome Expectations (Not Just Open-Loop DAGs):**
   * Traditional pipelines are *open-loop ("least-effort")*: a 03:00 AM transient test
     flake stalls promotion for hours, while "99% workflow pass rate" hides a 4-day-old
     stale staging environment.
   * Define **`<= 5` sparse, time-bound, verifiable Outcome Expectations** over
     observable environment state (e.g., *"Staging runs a qualified build with
     commit-lag `< 4 h`"*, *"Prod promotes within window `W` when `open_p0_blockers ==
     0`"*):
     * Measure **outcome SLIs** (`commit_lag`, qualified-candidate availability) over
       internal pipeline step counts.
     * Use **closed-loop bounded reconciliation** (`OBSERVE` | `ALERT` |
       `AUTO_RECONCILE`): auto-retry transient infra flakes (`<= 2`), fall back to
       promoting the newest *already-qualified* candidate `N-1` when candidate `N`
       fails qualification (preventing head-of-line blocking), and auto-resume the
       moment blocking issues close instead of polling manually.
     * **Avoid DSL bloat:** Keep expectation predicates sparse and non-conflicting;
       auto-generate defaults from stage definitions.
2. **Optimize CI/CD Ergonomics & Safety for AI Coding Agents:**
   * **Local Hermetic Fast Loop (`< 10–30 s`):** Expose one local command running
     affected-target lint/type/unit/contract checks identically to CI so agents never
     burn `15 min` push-and-wait loops on trivial errors.
   * **Token-Thrifty Structured Diagnostics (`--json` / JSONL):** Emit compact failure
     records (`error_kind`: `compile` | `assertion` | `contract` | `size_budget` |
     `flaky` | `infra_transient` | `release_blocked`, `file:line`, minimal diff, and
     an exact **1-line `repro_cmd` including deterministic PRNG `--seed`**) rather than
     dumping `50,000` lines of raw ANSI logs into agent context.
   * **Strict `< 24 h` Flake Quarantine:** Auto-quarantine flaky tests out of blocking
     presubmit so intermittent failures neither send agents on false bug hunts nor
     train them to blindly re-run broken builds.
   * **Capability-Scoped Agent Verbs (Poka-Yoke):** Feed agents explicit expectation
     context (`broken_expectation`, `deadline`, `canary_confidence`, `active_blocks`
     with linked issue IDs) and restrict autonomous agent mutations to safe, auditable
     verbs (`rerun_transient`, `bisect_culprit`, `promote_previous_qualified`,
     `quarantine_candidate`, `place_block`, `rollback_and_block`) — **forbidding**
     `bypass_block`, `disable_canary_sli`, or raw prod shell commands without human
     `FIDO2` approval.

---

## Before You Finish (`release-engineering` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Two builds of the same commit produce different `SHA-256` hashes | Pin `SOURCE_DATE_EPOCH`, remap build paths, sort file globs (`LC_ALL=C`), disable network in build |
| `-march=native` in CI release flags causes `SIGILL` on customer CPUs | Pin explicit portable ISA baseline (`x86-64-v2`/`v3`) or runtime feature dispatch |
| Production container ships `bash`, `apt`, `gcc`, or `300 MB` unstripped debug info | Multi-stage into shell-less base (`scratch`/Distroless/Wolfi) + split `.debug` symbols |
| Staging tests one build, then CI runs `build --prod` from scratch for production | Build **once**, sign `@sha256:` digest, and promote the identical artifact across stages |
| Long-lived SSH root key in CI for a 1-VPS app, or 1 GiB GitOps operator for 2 VMs | Match Rung `0–3`: `FIDO2` scripted manual (`Rung 0`) or `systemd.timer` signed pull (`Rung 1`) |
| GitOps CI job auto-pushes unverified digests straight to prod `main` ("Pull illusion") | Gate state repo via signed PRs / separate policy verifier + verify signatures on target |
| Config push bypasses canary ("it's just data") or overlaps another config push | Serialize config pushes, validate schema in CI, and canary `1 cell/10% -> soak -> SLI check -> all` |
| Digest rollback succeeds, then automation immediately re-promotes the broken build | Atomically pair every **rollback** with a **candidate quarantine / release block** |
| AI agent burns tokens parsing `50 MB` CI logs or chasing flaky tests | Emit compact JSON failure + 1-line `repro_cmd` (`--seed`), run `< 30 s` local affected checks, quarantine flakes |
| Rolling deploy drops `0.5%` of active HTTP/RPC requests with `502` | Fail readiness probe on `SIGTERM`, sleep `2–5 s` LB drain window, then finish in-flight requests |
| Firmware OTA overwrites single flash partition in place (power cut bricks unit!) | Use signed dual `A/B` slots (or recovery loader) + watchdog trial-boot confirmation |
