# Guardrail & Domain Gate Templates (`specs-tools`)

Adapt these templates to the repository's language, package manager, and directory
conventions. Keep every file concise and deterministic.

---

## 1. Canonical Cold-Diff Domain Gate (`docs/agents/gates/<role>.md`)

Store domain-specialist review gates in `docs/agents/gates/<role>.md`. Code
review workflows discover this directory automatically, match `triggers` globs
against changed files, and spawn one fresh-context read-only subagent per
matched gate.

```markdown
---
name: cpa-tax-reviewer
role: Senior CPA & Statutory Tax Calculation Reviewer
triggers:
  - "src/tax/**"
  - "internal/tax/**"
  - "tests/golden/tax/**"
  - "docs/specs/*tax*/**"
sources:
  - "docs/GLOSSARY.md"
  - "docs/specs/tax-engine/spec.md"
  - "docs/adrs/ADR-0003-fixed-point-cents.md"
---

# Domain Gate: CPA & Statutory Tax Calculation Review

You are a cold-diff domain reviewer auditing changes that touch tax calculation
logic, rate tables, or statutory worksheets. General code style and generic bugs
are reviewed elsewhere; stay strictly inside statutory and numerical correctness.

## Read First

1. Read the listed `sources` above (`GLOSSARY.md`, governing spec, and ADRs).
2. Inspect the full modified files (not diff hunks in isolation) plus any
   touched files under `tests/golden/tax/`.

## Blocking Checks (`BLOCKING` if violated)

1. **Statutory & spec fidelity:** Every bracket threshold, deduction cap, credit
   phase-out rate, and filing-status branch matches `SPEC-NNNN` and its cited
   statutory table for the explicit `TaxYear` (no cross-year constants mixed).
2. **Rounding & exact arithmetic:** All intermediate and final currency/rate
   operations obey the documented rounding rule (e.g., IRS whole-dollar
   half-up vs exact cent fixed-point) at the exact step specified; zero binary
   floating-point (`float`/`f64`/`number` float math) on monetary values.
3. **Cliff, zero, and negative boundaries:** Phase-out entry/exit cliffs, zero
   income, net-loss carryovers (floor at `0` vs refundable), and married-filing-
   separately special caps are handled explicitly rather than falling through.
4. **Anti-tautological golden coverage:** Every new or changed tax rule is
   verified by an independent worked example in `tests/golden/tax/` (with
   source citation), never by a test that recomputes the implementation formula.
5. **Immutable golden provenance:** Existing expected values in
   `tests/golden/tax/` were not altered without an accompanying spec/statute
   amendment explaining why prior figures changed.

## Output Contract (`<= 350` words, zero filler)

- Verdict first: `VERDICT: PASS` | `VERDICT: WARN` | `VERDICT: BLOCK`
- Group findings under `BLOCKING` then `WARNING`.
- Each finding states: `[file:line]` — concrete input/filing-status scenario that
  produces the wrong result, expected vs actual outcome, and cited `REQ-NNNN` /
  domain rule.
```

### Optional Native Claude Code Subagent Wrapper (`.claude/agents/<role>.md`)

When `.claude/` is used in the repo, write a thin wrapper so interactive
`@cpa-tax-reviewer` invocations and automated review runs share one definition:

```markdown
---
name: cpa-tax-reviewer
description: Cold-diff CPA & statutory tax reviewer for changes touching tax calculations, rate tables, or golden tax fixtures.
tools: Read, Grep, Glob, Bash(git diff:*, git show:*)
---

Read and execute the domain gate specification in `docs/agents/gates/cpa-tax-reviewer.md`
against the target diff. Report `VERDICT: PASS | WARN | BLOCK` with `file:line`
citations in at most 350 words.
```

---

## 2. Structural & Domain Guardrail Mechanisms (Tier 2 — Purpose & Examples)

Define the check by **purpose** first; prefer native compiler/visibility rules
or a small zero-dependency repo script before adding external tools:

| Guardrail Purpose | Native Compiler / Build Mechanism (Preferred) | Illustrative Ecosystem Tool Examples (`e.g.`) |
| --- | --- | --- |
| **Module-Seam / Deep-Import Boundary** *(callers & tests import only public module entry points)* | Go `internal/`; Rust private submodules + narrow root `pub`; Swift/Kotlin `internal` visibility; C# `InternalsVisibleTo` off; C/C++ public `include/` vs private `src/` header path split | Python: `tach`, `import-linter`; TS/JS: `dependency-cruiser`; JVM: `ArchUnit`; Go: `depguard`; any stack: small import-graph check script |
| **Banned Domain Constructs** *(e.g., binary float in money/tax, direct wall-clock in pure core, unscoped tenant DB queries, raw PII in logs)* | Distinct wrapper/newtypes hiding raw constructors; restricted module prelude | Multi-language AST matchers (`ast-grep`, `semgrep`), native linters (`clippy` `disallowed-types`, `ruff` `TID251`, `golangci-lint` `forbidigo`, Kotlin `detekt` `ForbiddenMethodCall`/`ForbiddenImport`, `clang-tidy`, `eslint`, Roslyn analyzers), or repo check script |

### Illustrative Multi-Language AST Rule Example (`ast-grep`)

*(Shown for Python; the same purpose applies in any language via its native
linter, compiler diagnostics, `ast-grep`/`semgrep` grammar, or a repo script.)*

```yaml
id: no-float-in-money
language: python
severity: error
files:
  - "src/tax/**/*.py"
  - "src/ledger/**/*.py"
message: "Binary float is forbidden in monetary/tax paths (INV-0002); use fixed-point Cents/Decimal."
rule:
  any:
    - pattern: float($$$)
    - kind: float
```

---

## 3. Two-Speed Gate Runner (Purpose & Example)

Every repository needs **two** predictable verification entry points in its
existing build/task system (or a portable `scripts/check-gates.sh` invoked by
both local developers/agents and CI):
1. **Fast inner loop (`check-fast`, `< 5 s`):** incremental compile/typecheck +
   single targeted test file/filter for each red-green slice.
2. **Full structural & golden gate (`check-gates`):** full compile/typecheck +
   linter + module-boundary/banned-construct/license checks + golden/invariant
   suite before completing a task or merging.

```sh
#!/bin/sh
# Example portable wrapper: scripts/check-gates.sh (adapt commands to repo stack)
set -eu
# 1. Static types / compile check
# 2. Lint + module-boundary + banned-construct + license/manifest checks
# 3. Golden-oracle vectors + unit/integration test suite
```

---

## 4. Lean Context Pointer Block (`AGENTS.md` / `CLAUDE.md`)

Keep always-loaded steering files compact (`<= 12` lines for verification &
gates). Point to files on disk rather than inlining checklists:

```markdown
## Verification & gates

- **Domain language & decisions:** Read `docs/GLOSSARY.md` and `docs/adrs/index.md` before naming types, seams, or tests; never use `Avoid:` synonyms.
- **Fast inner loop (`< 5 s`):** `<single-file typecheck + test command>` (run on every red-green slice; never write tautological tests that recompute formulas).
- **Full structural gate:** `<check-gates command>` (enforces module seams, banned domain constructs, and `tests/golden/` vectors; must pass before task completion).
- **Specialist cold-diff gates:** `docs/agents/gates/` — run any gate whose `triggers` match touched paths during code review before merging.
```


---

## 5. GTM, Licensing, Migration & Marketplace Structural Checks (Tier 2)

Wire only the checks relevant to the project's distribution and compliance
profile into `check-gates`, defining the **verification purpose** first and
picking a tool or lightweight script that fits the stack:

| Verification Purpose | What It Must Enforce | Illustrative Tool / Script Examples (`e.g.`) |
| --- | --- | --- |
| **Inbound OSS, Font & ML-Weight License Gate** | Fail build if any direct/transitive dependency or bundled asset/model carries a denied or unknown SPDX license for the chosen distribution mode | SBOM/license scanners (`syft` + policy script, `ort`, `licensee`, `cargo-deny`, `pip-licenses`, `go-licenses`, `license-checker`, Gradle/Maven license plugins) |
| **Non-Blocking Schema Migration Gate (High-SLO)** | Reject lock-taking DDL, non-nullable column additions without safe defaults, or single-step destructive drops that break N-1 rolling deploys | Migration analyzers (`squawk`, `atlas migrate lint`, `sqlfluff` custom rules) or a repo DDL regex/AST check script |
| **Native Binary & Store Manifest Conformance** | Verify required binary alignment, signing/entitlements, and privacy-manifest schema before store upload | ELF program-header check (`readelf -l` / `llvm-readobj` verifying `>= 16 KB` `PT_LOAD` alignment on Android `.so` files), `plutil -lint` on Apple `PrivacyInfo.xcprivacy`, manifest schema validator |
| **Store Listing Caps & Required URL Check** | Verify every localized field in `store/listing/*` fits exact store character/byte limits and required Privacy / Support / Web-Deletion URLs resolve | Zero-dependency repo script (`scripts/check-store-metadata.*`) validating lengths and required files across locales |

---

## 6. Cold-Diff GTM & Marketplace Specialist Gate Templates (`docs/agents/gates/`)

*(Adapt the `triggers` globs below to the repository's actual source, manifest,
and lockfile paths.)*

### A. `privacy-compliance-reviewer.md` (GDPR / HIPAA / SOC 2 / AI Data Governance)

```markdown
---
name: privacy-compliance-reviewer
role: Privacy, Data Governance & Sub-Processor Compliance Reviewer
triggers:
  - "**/migrations/**"
  - "**/schema*"
  - "**/models/**"
  - "**/telemetry/**"
  - "**/analytics/**"
  - "**/ai/**"
  - "*lock*"
  - "**/PrivacyInfo.xcprivacy"
  - "docs/gtm/**"
sources:
  - "docs/specs/gtm-constraints/spec.md"
  - "docs/gtm/data-inventory-and-subprocessors.md"
---

# Domain Gate: Privacy, Residency & Data-Use Compliance

Audit the diff cold for privacy, retention, residency, AI data-use, and
sub-processor drift against `docs/specs/gtm-constraints/spec.md`.

## Blocking Checks (`BLOCKING` if violated)

1. **Unmapped PII/PHI & retention:** New persisted personal/customer fields lack
   classification, TTL/retention enforcement, or coverage in the account/tenant
   hard-deletion or crypto-shredding path (soft `is_deleted` flags alone fail).
2. **Immutable-sink & log leakage:** Raw PII, tokens, secrets, or regulated
   payloads written to structured logs, crash breadcrumbs, analytics events, or
   unencrypted append-only event streams.
3. **Unapproved sub-processor / non-ZDR AI egress:** New third-party SDKs,
   analytics endpoints, or LLM/API calls transmit customer data outside approved
   sub-processors, regional residency cells, or zero-data-retention (ZDR) tiers.
4. **Policy-to-code drift:** Code behavior diverges from `docs/gtm/` disclosures
   or mobile privacy manifests without updating those artifacts in the same PR.

## Output Contract (`<= 350` words)

`VERDICT: PASS | WARN | BLOCK`, grouping `BLOCKING` then `WARNING` with
`[file:line]`, concrete data-exposure scenario, and cited `REQ-NNNN`.
```

### B. `slo-operability-reviewer.md` (SLAs, Blast Radius & Audited Supportability)

```markdown
---
name: slo-operability-reviewer
role: Principal SRE, Multi-Tenant Resiliency & Supportability Reviewer
triggers:
  - "**/migrations/**"
  - "**/api/**"
  - "**/handlers/**"
  - "**/jobs/**"
  - "**/workers/**"
  - "docs/gtm/slo-and-support-playbook.md"
sources:
  - "docs/specs/gtm-constraints/spec.md"
  - "docs/gtm/slo-and-support-playbook.md"
---

# Domain Gate: SLO Resiliency & Support Operability

Audit the diff cold for SLA/error-budget hazards, noisy-neighbor blast radius,
zero-downtime deploy safety, and 3 AM support diagnosability.

## Blocking Checks (`BLOCKING` if violated)

1. **Deploy & migration safety:** Schema or wire-protocol changes break N-1
   rolling compatibility or acquire long table locks during live traffic.
2. **Unbounded work & missing timeouts:** Outbound RPC/HTTP/DB calls lack
   explicit deadlines, pagination/payload bounds, idempotency keys on retries, or
   per-tenant rate/concurrency isolation.
3. **Silent or un-supportable failures:** Customer-impacting background or API
   failures lack correlation IDs, SLI error classification (`4xx` vs `5xx`), or a
   redacted support diagnostic / replay path (requiring raw prod DB access).
4. **Un-audited privileged actions:** Admin or support impersonation/break-glass
   paths mutate or view tenant data without mandatory reason logging and audit
   event emission.

## Output Contract (`<= 350` words)

`VERDICT: PASS | WARN | BLOCK` with `[file:line]`, failure/load scenario, blast
radius, and cited `REQ-NNNN`.
```

### C. `store-readiness-reviewer.md` (App Store / Play Store / Marketplace Gate)

```markdown
---
name: store-readiness-reviewer
role: Mobile & Marketplace Submission Review Specialist
triggers:
  - "ios/**"
  - "android/**"
  - "**/Info.plist"
  - "**/PrivacyInfo.xcprivacy"
  - "**/AndroidManifest.xml"
  - "**/manifest.json"
  - "**/auth/**"
  - "**/account/**"
  - "**/billing/**"
  - "store/**"
  - "fastlane/**"
sources:
  - "docs/specs/gtm-constraints/spec.md"
  - "store/review-notes.md"
  - "store/screenshots-plan.md"
---

# Domain Gate: App Store, Google Play & Marketplace Readiness

Audit the diff cold for platform review rejection triggers across binaries,
manifests, auth/deletion, billing, permissions, and store metadata.

## Blocking Checks (`BLOCKING` if violated)

1. **Account creation vs. deletion & sign-in parity:** Adding/changing account
   or social-login flows breaks in-app full account deletion (Apple `5.1.1(v)`),
   Play Store dual-path web deletion URL parity, or Sign in with Apple (`4.8`)
   including token revocation.
2. **Permission & disclosure drift:** New OS/browser permissions, tracking SDKs,
   or Required-Reason APIs added without matching `NS*UsageDescription`,
   `PrivacyInfo.xcprivacy`, Play Data Safety / Nutrition Label updates, and
   least-privilege reviewer justifications.
3. **Billing & external-link compliance:** Digital feature unlocks bypass the
   platform's mandated in-app billing seam (e.g., StoreKit / Play Billing)
   without a documented reader/multi-platform exemption, or omit purchase
   restoration.
4. **Reviewer sandbox & screenshot seed breakage:** Auth/MFA/onboarding edits
   break the non-expiring reviewer demo login or break deterministic routes used
   by `store/screenshots-plan.md`.

## Output Contract (`<= 350` words)

`VERDICT: PASS | WARN | BLOCK` with `[file:line]`, exact store guideline /
rejection trigger, and required fix.
```
