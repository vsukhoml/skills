---
name: specs-tools
description: >-
  Turns stable specs, ADRs, and glossaries into repeatable guardrails for the
  SPECS suite: module-boundary, AST, license, and migration checks,
  golden-oracle harnesses, cold-diff specialist review gates, and lean
  AGENTS.md or CLAUDE.md pointers. Use when moving from specs to active
  development, or when hardening the feedback loop of a repo.
last_updated: 2026-11-15
---

# SPECS Development Guardrails & Domain Gates (`specs-tools`)

Bridges **approved specifications and architecture** (`GLOSSARY.md`, `SPEC-NNNN`,
`ADR-NNNN`) into a **repeatable, fast-feedback development harness** before code
generation accelerates.

> **Core engineering principle:** Accelerators without brakes produce a slop
> cannon. Implementation agents run at **maximum context pressure** (exploring,
> editing, debugging), so prose reminders in `AGENTS.md` decay rapidly. Push
> mechanical rules down into **zero-token deterministic checks** (`< 5 s`), push
> domain-formula verification into **independent golden fixture tables**, and push
> non-mechanical domain judgment into **cold-diff specialist review gates**
> (`docs/agents/gates/<role>.md`) that inspect diffs with fresh context and low
> context pressure.
>
> **Purpose-first, language-neutral rule:** Define every guardrail by **what
> invariant it enforces, its exit-code contract, and its runtime budget** — never
> assume a single language or third-party tool. Prefer native compiler/visibility
> features or a small zero-dependency repo script when they suffice; treat named
> tools (`e.g., ...`) strictly as optional ecosystem examples.

Consult [references/gate-templates.md](references/gate-templates.md) for
ready-to-adapt gate definitions, multi-ecosystem check examples, two-speed
runners, and `AGENTS.md` pointer blocks.

---

## The 5-Tier Guardrail Pyramid (Classify Bottom-Up)

Never write a prose rule for an LLM reviewer when a lower tier can enforce the
invariant deterministically:

| Tier | Mechanism (Purpose First) | Cost per Turn | What Belongs Here |
| --- | --- | --- | --- |
| **1. Type, Compiler & Visibility** | Distinct domain/unit types, fixed-point types, exhaustive sum types, unused-result/nullability errors, native package/symbol visibility | `0` tokens (`< 2 s`) | Preventing invalid states or private access from compiling (`Cents` vs binary float, `TaxYear` vs raw integer, `VerifiedToken` vs raw string). |
| **2. Structural, License & Manifest Checks** | Deterministic checks for module-import boundaries, banned AST/API patterns, inbound SPDX/asset licenses, lock-free schema migrations, and platform binary/manifest caps *(via native build checks, small repo scripts, or stack linters — e.g., `ast-grep`, `depguard`, `cargo-deny`, `squawk`)* | `0` tokens (`< 3 s`) | Enforcing `ADR-NNNN` module seams, banning mechanical domain hazards (floats in money/tax, unscoped tenant queries, raw PII logging), blocking copyleft/NC license contamination, catching lock-taking DDL, and validating store manifests & listing caps. |
| **3. Independent Golden, Property & Seed Oracles** | Immutable external test-vector tables (`tests/golden/` or `testdata/golden/`), `INV-NNNN` property generators, and deterministic `DEMO_SEED=store` UI smoke harnesses | `0` tokens (`< 5 s`) | Worked statutory worksheets, RFC wire frames, spec boundary tables, conservation/monotonicity/idempotency properties, and reproducible non-PII store screenshot states. |
| **4. Cold-Diff Domain Specialist Gates** | Path-triggered specialist reviewer personas in `docs/agents/gates/<role>.md` (plus `.claude/agents/<role>.md` when applicable) | Paid **only** on matching diffs | High-EV judgment no linter can encode: **CPA statutory tax review**, **double-entry ledger audit**, **privacy/GDPR/HIPAA & sub-processor drift**, **SLO/support operability**, **App Store / Play Store rejection review**. |
| **5. Lean Context Pointers** | `<= 12`-line `## Verification & gates` section in `AGENTS.md` / `CLAUDE.md` | Minimal always-loaded cost | Exact `check-fast` and `check-gates` commands plus 1-line pointers to `GLOSSARY.md`, `docs/*/index.md`, and `docs/agents/gates/`. |

---

## Workflow

### 1. Inspect Repo & Spec Surface (Read-Only First)

Read what exists without assuming language or layout:

1. **Domain & spec artifacts:** `GLOSSARY.md` / `GLOSSARY-MAP.md`,
   `docs/adrs/index.md` + governing ADRs, and target `SPEC-NNNN` (`REQ-*`,
   `INV-*`, lifecycle/failure tables, worked examples) + `design.md`.
2. **Existing build & guardrail wiring:** The project's build manifests, task
   runners, pre-commit hooks, and CI workflows (whatever language or build tool
   the repo uses). Note any check that already exists but sits unwired or slow.
3. **Existing agent steering & gates:** `AGENTS.md`, `CLAUDE.md`,
   `docs/agents/gates/`, `.claude/agents/`, and `.agents/`. **Idempotency rule:**
   update or sharpen existing gates and scripts rather than creating duplicates.

### 2. Map Domain Failure Modes to Structural Brakes

Extract the project's **catastrophic or subtle domain failure modes** from the
specs and ADRs, then assign each to the lowest tier in the Guardrail Pyramid
by **purpose first** (selecting a native language feature, small repo script, or
stack-matched tool):

* **Module seam drift:** Enforce `ADR-NNNN` / `design.md` boundaries so callers
  and tests import only public module entry points, never internal subfolders
  (via native visibility like Go `internal/`, Rust/Swift/Kotlin/C# module
  visibility, C/C++ public-header checks, or import-graph linters, e.g., `tach`,
  `dependency-cruiser`, ArchUnit).
* **Mechanical domain & GTM footguns:** Enforce deterministic checks in
  `check-gates` for constructs, dependencies, or binary traits that are *always
  wrong* for this project:
  * *Banned domain & telemetry constructs:* Forbid unsafe representations or
    calls in guarded paths — such as binary floating-point in `tax/` or
    `ledger/`, direct wall-clock calls in pure engines, unscoped DB queries
    missing `TenantContext`, unstructured `print`/string-interpolated logs, raw
    `PII`/`Request` dumps bypassing `Secret<T>`/`Redacted<T>`, or dynamic strings
    in metric labels (`specs-telemetry`) — via compiler/type rules, multi-language
    AST matchers (`e.g., ast-grep, semgrep`), or a small repo check.
  * *Commercial & SLO brakes (from `specs-gtm` / ADRs):* Enforce an **inbound
    SPDX & ML-weight license allowlist** matching the distribution model,
    **non-blocking schema-migration validation** (e.g., SQL lock/compatibility
    analyzers such as `squawk` or a DDL check script), and outbound I/O timeout
    checks.
  * *Marketplace, localization & app-store brakes:* Enforce **native binary
    page-alignment / entitlement checks** (e.g., verifying `>= 16 KB` ELF segment
    alignment on Android `.so` artifacts), **platform privacy-manifest validation**
    (e.g., iOS `PrivacyInfo.xcprivacy`), **store-listing character-cap &
    required-URL validation** over `store/`, and — when multi-locale (`Tier 1+`)
    i18n is in scope — zero-token checks for **catalog key/placeholder parity,
    banned string concatenation in localized paths, and pseudo-localized
    (`[Ŝàvé ····]`) overflow smoke tests**.
* **Tautological-test & UI-drift risk:** Propose immutable `tests/golden/` (or
  `testdata/golden/`) tables seeded from independent worked examples plus
  `INV-NNNN` property checks — and, for marketplace apps, a deterministic
  `DEMO_SEED=store` smoke/screenshot runner verifying every frame in
  `store/screenshots-plan.md` renders cleanly without PII.
* **Cold-diff domain review gates (`1–3` max, high EV only):** Propose a
  specialist gate **only** where domain or regulatory judgment materially
  reduces escaped defects. Examples:
  * *Tax / payroll calculation* -> `cpa-tax-reviewer` (IRC/IRS pub citations,
    filing-status & phase-out cliff boundaries, rounding rules, tax-year table
    isolation, non-tautological worksheet vectors).
  * *Trading / payments / billing* -> `ledger-auditor` (conservation of value,
    double-entry balance on partial failure/reversal, idempotency keys,
    settlement/cut-off calendar semantics).
  * *Privacy / regulated data / AI governance* -> `privacy-compliance-reviewer`
    (PII/PHI redaction, retention TTL & crypto-shredding/erasure parity, ZDR AI
    boundaries, unapproved sub-processor/SDK additions, policy-to-code drift).
  * *High-SLO SaaS & enterprise support* -> `slo-operability-reviewer`
    (expand-contract migration safety, bounded retries/deadlines, noisy-neighbor
    bulkheads, correlation IDs, audited support break-glass diagnosability).
  * *App Store / Play Store / Marketplace apps* -> `store-readiness-reviewer`
    (in-app + web account deletion parity, Sign in with Apple / IAP rules,
    permission-justification & Nutrition Label / Data Safety parity, reviewer
    sandbox login viability).
  * *Parsers / distributed protocols* -> `protocol-state-reviewer` (RFC framing
    bounds, illegal state transitions, replay/out-of-order idempotency).
  * **Anti-bloat rule:** Never invent generic filler personas (`"clean-code-bot"`,
    `"general-qa"`). General correctness, spec conformance, and coding standards
    are already handled by standard multi-axis code review.

### 3. Present the Gate Plan & Confirm

Present a compact proposal table stating the **invariant/purpose** first and the
concrete mechanism for this repo second, before installing tools or writing files:

```text
Risk / Invariant               | Tier | Guardrail Purpose & Mechanism                  | Trigger / Speed
------------------------------ | ---- | ---------------------------------------------- | ---------------
Deep imports across pkg seams  | T2   | Module-boundary check (e.g., native / linter)  | check-gates <2s
Binary float in tax paths      | T2   | Banned-type AST check (e.g., ast-grep / lint)  | check-gates <1s
Tautological bracket tests     | T3   | Golden oracle (tests/golden/worksheets.json)   | check-fast  <2s
Phase-out & rounding semantics | T4   | docs/agents/gates/cpa-tax-reviewer.md          | tax/** diff
```

Ask the user to **Approve** or **Adjust** the proposed checks, any new dev-tool
installs, and the specialist reviewer roster.

### 4. Scaffold & Prove Every Brake Bites

Execute the approved items cleanly:

1. **Wire two-speed verification commands** (using the repo's native build/task
   runner or a portable `scripts/check-gates.*` invoked both locally and in CI):
   * **Inner-loop fast check (`check-fast` pattern):** runs incremental
     typecheck/compile + a single targeted test file/filter in `< 5 s`.
   * **Full deterministic gate (`check-gates`):** runs typecheck + linter +
     module-boundary/AST rules + golden/invariant test suite cleanly, exiting
     non-zero on any failure.
2. **Prove structural checks bite (mandatory):**
   * Run `check-gates` on the clean tree -> must exit `0`.
   * Introduce a temporary synthetic violation in memory/working tree (e.g., a
     forbidden cross-module internal import or banned `float` in the guarded
     path), run the check -> **verify it exits non-zero with a clear message**,
     then immediately revert the synthetic probe and re-verify exit `0`. Never
     leave an untested linter rule in place.
3. **Seed independent golden fixtures (`tests/golden/` or `testdata/golden/`):**
   * Populate initial vectors from worked examples in `SPEC-NNNN` or cited
     authoritative references, recording the source citation on every case so
     future agents cannot silently overwrite expected values to make a broken
     implementation pass.
4. **Write Cold-Diff Domain Gate(s) (`docs/agents/gates/<role>.md`):**
   * Follow the frontmatter and checklist contract in
     [references/gate-templates.md](references/gate-templates.md): explicit path
     `triggers`, authoritative `sources`, concrete `BLOCKING` failure checks
     (including verifying that new domain branches add independent golden cases),
     and a strict `<= 350`-word output budget.
   * If the repo uses `.claude/` (or the user wants native Claude Code
     subagents), also generate the matching thin `.claude/agents/<role>.md`
     wrapper pointing at `docs/agents/gates/<role>.md` so one source of truth
     governs every harness.
5. **Write Lean Context Pointers in `AGENTS.md` (and `CLAUDE.md` if separate):**
   * Keep the added/updated `## Verification & gates` section to `<= 12` lines
     (see template in [references/gate-templates.md](references/gate-templates.md)).
   * Prune or move verbose prose coding checklists out of `AGENTS.md` into
     `CODING_STANDARDS.md` or `docs/agents/gates/` so always-loaded context
     stays tiny.

### 5. Handoff

Report the verified commands (`check-fast` example + `check-gates` command), the
seeded golden fixture path(s), and the active `docs/agents/gates/*.md` roster.

* If no approved execution plan exists yet -> route to **`specs-plan`** (so task
  `Verification:` lines use the new fast commands and golden targets).
* If `PLAN-NNNN` is already approved -> route to **`specs-implement`**.
