# First-Principles CI/CD Topologies & Actuation Reference (`release-engineering`)

---

## 1. Decomposing "CI/CD" into Three Independent Trust Planes

Most CI/CD security breaches and over-engineered platforms happen because teams
conflate **building**, **authorizing**, and **actuating** into a single privileged
pipeline:

```text
Plane 1: CI (Pure Transform)       Plane 2: Release Policy         Plane 3: CD Actuation
────────────────────────────       ───────────────────────         ─────────────────────
(Commit + Lockfile)                Human FIDO2 / GPG tag           Transitions Target State:
  │  Untrusted inputs (PRs,          OR Automated Canary/            S_actual ──► S_desired
  ▼  deps, test runners)             Branch Policy Gate              via Rung 0 / 1 / 2 / 3
Artifact@sha256 + Provenance  ──►  Signed Release Manifest    ──►  (Verifies signature +
(ZERO prod credentials!)           (env -> @sha256 + config)        health-checks + reverts)
```

### The "Pull / GitOps Security Illusion" (Critical Trap)

Teams often migrate from Push to Pull claiming *"CI no longer holds cluster admin
credentials, so compromising CI cannot touch production"* — and then grant their CI
runner write access to `git push` new image digests directly onto the `main` branch
of the GitOps manifest repo that production auto-syncs!

* **First-principles reality (Transitivity of Authority):** If `CI -> writes GitOps
  main -> Pull Agent applies blindly`, **CI still owns production** (merely with a
  30-second polling delay)!
* **Real isolation requires breaking unverified transitivity:**
  1. Either require **out-of-band authorization** on the state change (human FIDO2/GPG
     signed PR/tag, or a separate isolated promotion verifier service checking independent
     attestations), **and**
  2. Have the target/reconciler **cryptographically verify** both the state manifest
     signature and the artifact provenance (`cosign verify` / `minisign` / TUF
     timestamp + snapshot metadata) *before* executing any update.

---

## 2. Quantitative Decision Matrix (Selecting the Optimal Rung)

Derive the actuation model from **5 physical variables** — never cargo-cult a cluster
controller onto a 2-VPS app or store SSH root keys in CI for a 1-person project:

| Requirement Variable | Rung 0: Scripted Manual (`FIDO2` CLI) | Rung 1: Host-Local Timer Pull (`systemd.timer`) | Rung 2: Ephemeral OIDC Push | Rung 3: Cluster GitOps / TUF Fleet Pull |
| --- | --- | --- | --- | --- |
| **Target Fleet ($N$)** | `1–3` hosts / App Store | `1–50` VMs, VPSes, NAT'd edge | `1–10` cloud envs / PaaS / IaC | `5–500` K8s clusters or `10^2–10^7` devices |
| **Deploy Cadence ($f$)** | Monthly to a few/week | Hourly to daily | Multiple/day | Continuous + self-healing drift |
| **Network Topology** | Admin VPN / Bastion / SSH | **0 inbound ports** (works behind NAT!) | Target API reachable from CI | **0 inbound ports** (outbound HTTPS only) |
| **Persistent Daemon Tax** | **`0` daemons** | **Near-zero** (OS `systemd.timer`) | **`0` target daemons** | **High** on server (controller/Redis); tiny on MCU |
| **CI Compromise Blast Radius** | **Zero** (no prod keys/path in CI; needs physical FIDO2 tap) | **Bounded** if target verifies offline/reviewer signature | **Medium** (mitigated via Protected Env + scoped OIDC) | **Bounded** if GitOps repo enforces signed PRs / TUF |
| **Best Fit** | Early products, single VPS, bench hardware, store releases | Non-K8s production hosts, appliances, homelabs, branch-office edge | Managed cloud (Cloud Run/Lambda/ECS), CDN workers, Terraform | Multi-team Kubernetes, IoT/firmware OTA, desktop/CLI auto-update |

---

## 3. Reference Patterns by Rung

### Rung 0: Automated CI + Idempotent Hardware-Key Manual Actuation

**"Manual" applies ONLY to who triggers the command — never to typing ad-hoc shell
commands!**

* **Rules:**
  1. CI still runs automatically on every commit/tag to build, test, and publish an
     immutable signed artifact (`app@sha256:...` or `app-v1.4.2.tar.zst` + `.minisig`).
  2. No cloud tokens or SSH private keys are stored in the CI provider at all.
  3. An operator with a hardware-backed SSH key (`ssh-keygen -t ed25519-sk`) runs one
     deterministic, idempotent script `./scripts/deploy.sh prod v1.4.2 <expected_sha256>`:

```bash
#!/usr/bin/env bash
# Rung 0: Idempotent atomic deploy with signature verification & auto-rollback
set -euo pipefail
HOST="${1:?usage: deploy.sh <host> <version> <expected_sha256>}"
VER="${2:?}"
DIGEST="${3:?}"

ssh "deploy@${HOST}" bash -s -- "${VER}" "${DIGEST}" <<'REMOTE'
set -euo pipefail
VER="$1"; DIGEST="$2"
REL_DIR="/opt/app/releases/${VER}"
CUR_LINK="/opt/app/current"
PREV_TARGET="$(readlink -e "${CUR_LINK}" || true)"

# 1. Fetch & verify cryptographic hash + offline signature before touching live state
mkdir -p "${REL_DIR}"
curl -fsSL "https://releases.example.com/app-${VER}.tar.zst" -o "${REL_DIR}/pkg.tar.zst"
echo "${DIGEST}  ${REL_DIR}/pkg.tar.zst" | sha256sum -c -
minisign -Vm "${REL_DIR}/pkg.tar.zst" -P RWQf6LRCGA9i53mlYecO4IzT51TGPpvWucNSCh1CBM0QTaLn73Y7GFO3

tar --zstd -xf "${REL_DIR}/pkg.tar.zst" -C "${REL_DIR}"
ln -sfn "${REL_DIR}" "${CUR_LINK}.next"
mv -Tf "${CUR_LINK}.next" "${CUR_LINK}"   # Atomic rename(2) symlink cutover!
sudo systemctl restart app.service

# 2. Bounded readiness gate + automatic rollback on failure
if ! timeout 15 bash -c 'until curl -fsS http://127.0.0.1:8080/readyz >/dev/null; do sleep 0.5; done'; then
  echo "ERROR: ${VER} failed readiness; reverting to ${PREV_TARGET}" >&2
  if [[ -n "${PREV_TARGET}" && "${PREV_TARGET}" != "${REL_DIR}" ]]; then
    ln -sfn "${PREV_TARGET}" "${CUR_LINK}.rollback"
    mv -Tf "${CUR_LINK}.rollback" "${CUR_LINK}"
    sudo systemctl restart app.service
  fi
  exit 1
fi
logger -t deploy "promoted version=${VER} sha256=${DIGEST} prev=${PREV_TARGET}"
REMOTE
```

---

### Rung 1: Lightweight Host-Local Pull Reconciler (`systemd.timer` — Zero K8s Bloat)

When you want **unattended pull deployments + zero inbound firewall holes** on `1–50`
Linux VMs or NAT'd appliances *without* running Kubernetes or a 1 GiB GitOps operator:

1. Store a tiny signed desired-state pointer (`prod.json` + `prod.json.minisig`) in
   static HTTPS object storage or a read-only Git raw endpoint:
   ```json
   {"version": "1.4.2", "image": "ghcr.io/org/app@sha256:9f86d08...", "updated_at": "2026-11-15T20:00:00Z"}
   ```
2. Run an unprivileged/scoped `app-reconcile.timer` (`OnUnitActiveSec=60s`,
   `RandomizedDelaySec=15s` to prevent thundering-herd pulls across hosts):
   * Fetches `prod.json` + `prod.json.minisig` (`If-None-Match` `ETag` -> `304 Not
     Modified` costs `< 1 KB`).
   * Verifies `minisign` / `cosign` signature **and** checks `updated_at` monotonic
     freshness (prevents replay/rollback attacks if the CDN cache is poisoned!).
   * Compares desired `@sha256` against currently running `/opt/app/current-digest`.
   * If different, verifies image/binary attestation, performs atomic cutover, checks
     `/readyz`, and reverts on failure.

---

### Rung 2: Ephemeral OIDC Scoped Push Pipeline

When deploying to cloud APIs (Serverless, Managed Containers, CDN Workers, Terraform):

* **Split CI Build from CD Actuation into separate jobs with distinct identities:**
  * `build` job: `permissions: { contents: read, id-token: write }` (signs image
    provenance only; **zero** cloud IAM access). Passes immutable `image_digest`
    output.
  * `deploy-prod` job:
    * Runs in a **Protected Environment** (`environment: production`) with branch
      restriction (`refs/heads/main` or signed tags only).
    * Enforces serialization (`concurrency: { group: deploy-prod, cancel-in-progress: false }`)
      so concurrent merges never race or leave half-applied state.
    * Exchanges OIDC JWT for a **10-minute deploy-only IAM token** scoped strictly to
      updating that single service's image digest (never broad `AdministratorAccess`!),
      with the cloud IAM OIDC trust policy explicitly pinning the `sub` claim to
      `repo:<org>/<repo>:environment:production` (never wildcard `repo:<org>/<repo>:*`,
      which would let PR or feature-branch workflows assume the production deploy role!).
    * Runs post-deploy smoke/SLI check and reverts to the prior digest automatically on
      failure.

---

### Rung 3: Cluster Reconcilers (GitOps) & Client/Firmware Fleet Pull (TUF / Uptane)

1. **Cluster GitOps (`Flux`, `Argo CD`):**
   * Separate **Application Source Repo** from **Environment Desired-State Repo** (so
     application CI never needs write credentials to the source repo, and state-repo
     history is a clean linear ledger of reversible promotions).
   * Scope each reconciler's RBAC to its target namespace/resources (avoid a single
     `cluster-admin` reconciler shared across untrusted multi-tenant teams).
   * Require explicit **break-glass sync suspension** with audit logging before any
     emergency live hotfix, and backport the fix to Git immediately so reconciliation
     does not revert the mitigation!
2. **Client / Edge / Firmware Fleet Pull (TUF / Uptane Principles):**
   * Separate signing roles (**Root** offline key, **Targets** release key,
     **Snapshot** consistency key, **Timestamp** short-expiry online key) so a
     compromised CDN/mirror cannot serve stale vulnerable firmware (**freeze attack**)
     or mismatched metadata (**mix-and-match attack**).
   * Enforce deterministic **cohort bucketing** (`hash(device_id || release_id) % 1000
     < permille_ring`) + `Retry-After` jitter so `100,000` devices wake up smoothly
     across `0.1% -> 1% -> 10% -> 100%` rings without DDoSing your artifact origin!

---

## 4. Outcome Expectations, Release Blocks & AI-Agent-Ready CI/CD

### A. Why Open-Loop DAGs Break (and How Sparse Outcome Expectations Fix Them)

Traditional CI/CD pipelines model **imperative step execution** (*"Did job #482 exit
0?"*). That creates two systemic blind spots:
1. **Pipeline SLIs lie about user reality:** *"Nightly staging job succeeded 99% of the
   time"* looks healthy even when `staging` has been stuck on a 5-day-old binary due to
   an unresumed release block!
2. **Same failure, opposite right action:** A failing integration test during
   *postsubmit candidate cutting* means *"promote the previous qualified candidate so
   staging stays fresh while bisecting commit `X`"*, whereas the exact same test failing
   during *prod promotion* means *"halt prod promotion immediately"*.

Instead of building a complex microservice maze, represent **Candidate Lineage +
Quarantine/Blocks + `<= 5` Outcome Expectations** in a single declarative state schema
(plain JSON/YAML file or lightweight release CLI):

```json
{
  "pipeline_config_commit": "7c91e4a",
  "active_blocks": [
    {
      "id": "BLK-2026-114",
      "scope": "prod",
      "reason": "DB migration lock contention under investigation",
      "issue_url": "https://tracker.example.com/issues/412",
      "created_by": "oncall@example.com",
      "expires_at": "2026-11-16T04:00:00Z"
    }
  ],
  "quarantined_commits": [
    {
      "commit": "b3f09d2",
      "reason": "Regression in batch refund idempotency",
      "issue_url": "https://tracker.example.com/issues/419"
    }
  ],
  "expectations": [
    {
      "id": "staging_freshness",
      "target_env": "staging",
      "predicate": "qualified == true && commit_lag_seconds <= 14400",
      "status": "AT_RISK",
      "mode": "AUTO_RECONCILE",
      "allowed_reconciliations": [
        "rerun_transient_check:max=2",
        "promote_latest_qualified_non_quarantined_candidate"
      ]
    },
    {
      "id": "prod_weekly_rollout",
      "target_env": "prod",
      "window_utc": "Tue 16:00..19:00",
      "predicate": "canary_verdict == 'PASS' && active_blocks_count == 0 && open_p0_issues == 0",
      "status": "BLOCKED",
      "mode": "AUTO_RECONCILE",
      "allowed_reconciliations": [
        "auto_resume_when_blockers_clear",
        "rollback_and_quarantine_on_strong_canary_regression"
      ]
    }
  ]
}
```

* **Guardrail against over-engineering:** Limit each service to **`<= 5` non-overlapping
  outcome expectations** auto-derived from its stage topology. Never allow circular
  cross-service expectation chains or Turing-complete custom rule scripts!

---

### B. Designing CI/CD Specifically for AI Coding Agents

AI coding agents fail on traditional CI/CD for predictable, mechanical reasons: slow
`15 min` remote push-and-wait loops, `50 MB` unstructured ANSI log dumps that overflow
context windows, unquarantined flaky tests, and missing operational context.

| Agent Friction Point | First-Principles CI/CD Optimization |
| --- | --- |
| **Slow `15 min` push-and-pray loop** | Provide a hermetic local presubmit runner (`make check-affected` / `./ci/presubmit --fast`) executing lint + types + affected unit/contract tests in **`< 10–30 s`** |
| **Token blowout on `50,000`-line logs** | Emit compact structured failure JSONL (`--format=json`) containing *only* failed targets, `error_kind`, `file:line`, minimal diff, and an exact **1-line `repro_cmd` (including `--seed`)** |
| **Semantic merge skew at `10x` PR rate** | Enforce either a **rebase/batch merge queue** or **postsubmit candidate qualification** so two individually green agent PRs cannot silently break `main` -> `prod` |
| **Flaky tests poisoning agent reasoning** | Track per-test flake rate; auto-quarantine any flaky test out of blocking presubmit within `24 h` so agents neither chase phantom bugs nor learn to blindly retry red builds |
| **Opaque pipeline blocks / config lag** | Expose `releasectl status <commit> --json` returning commit stage lineage, snapshotted `pipeline_config_commit`, active `ReleaseBlock` reasons/links, and broken `Expectation` state |
| **Unsafe autonomous agent actions** | Constrain agent CD tools to **capability-scoped Poka-Yoke verbs** (`rerun_transient`, `bisect_culprit`, `quarantine_commit`, `place_block`, `rollback_and_block`, `open_revert_pr`); **require human `FIDO2` approval** to `bypass_block`, `widen_permissions`, or `disable_canary_sli` |

#### Compact Agent-Consumable CI Failure Record (`stdout` / `artifacts/failures.jsonl`)

```json
{
  "step": "unit_tests",
  "target": "//payments:refund_test",
  "error_kind": "deterministic_assertion",
  "flaky_history_7d": 0.0,
  "location": "src/payments/refund.rs:142:9",
  "summary": "expected HTTP 409 on duplicate idempotency_key with mismatched amount, got 200",
  "repro_cmd": "cargo test -p payments refund::tests::duplicate_key_mismatch -- --exact --nocapture",
  "broken_expectation": "presubmit_qualification"
}
```
