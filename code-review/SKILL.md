---
name: code-review
description: >-
  Multi-axis code review with parallel cold-diff subagents: correctness and
  security, spec/ADR conformance, standards and module depth, and repo-local
  domain gates. Use when reviewing uncommitted diffs, commits, branches, or
  pull requests, or as a quality gate before merging.
last_updated: 2026-11-15
---

# Multi-Axis Cold-Diff Code Review (`code-review`)

Executes a repeatable, high-signal code review by running deterministic repo
guardrails first and then evaluating the diff across **orthogonal, isolated
subagents** so clean formatting never masks a logic bug, a missed requirement,
or a domain-rule violation.

Consult [references/smell-and-bug-catalog.md](references/smell-and-bug-catalog.md)
for the Correctness/Test-Integrity checklist and the Module-Depth + Fowler Smell
Baseline passed to subagents.

---

## Step 1: Pin the Diff Target Once (Fail Fast)

Resolve what is under review before spawning any subagent:

1. **No arguments (working tree default):**
   * Run `git diff` (unstaged), `git diff --cached` (staged), and
     `git status --short` (untracked net-new files).
2. **Commit SHA:**
   * Verify `git rev-parse --verify <sha>^{commit}` and run `git show <sha>`.
3. **Fixed point / branch / tag (`<base>`):**
   * Verify `git rev-parse --verify <base>` and capture `git diff <base>...HEAD`
     (merge-base three-dot diff) plus `git log <base>..HEAD --oneline`.
4. **Pull / merge request URL or ID:**
   * Fetch PR/MR context and diff using the repo's forge CLI or remote refs
     (e.g., `gh pr view` + `gh pr diff`, `glab mr view` + `glab mr diff`, or
     `git fetch` + three-dot `git diff`).

Extract `CHANGED_FILES` (all modified, added, and untracked target paths). If
the ref does not resolve or the diff is empty, stop immediately and report it.

---

## Step 2: Run Structural Guardrails First (When Reviewing Local Code)

Reviewers must never spend tokens reporting syntax, type, lint, or import-seam
errors that deterministic checks catch in seconds:

* Inspect `AGENTS.md` / `CLAUDE.md` or the project's build/task configuration
  for its deterministic gate command (e.g., `check-gates` running compilation/
  types, linter, module-boundary checks, and golden tests).
* When reviewing a local working tree or branch and the command runs locally
  without external side effects, execute it first and record its exit status and
  any failures under `## Structural Gates`.

---

## Step 3: Discover Context & Matching Domain Specialist Gates

Locate the repository's ground-truth artifacts (do not complain if optional docs
do not exist):

1. **Domain language & architectural decisions:** Check `GLOSSARY.md` /
   `GLOSSARY-MAP.md` (repo root or `docs/`) and `docs/adrs/` or `docs/adr/`.
2. **Originating spec / plan / ticket:** Check in order:
   * A spec/plan/issue path or ID supplied by the user;
   * Commit message or PR references (`SPEC-NNNN`, `PLAN-NNNN`, `#123`, `!45`);
   * Matching spec/plan files under `docs/specs/`, `docs/plans/`, or `specs/`.
3. **Documented coding standards:** Check `CODING_STANDARDS.md`,
   `CONTRIBUTING.md`, `.editorconfig`, and coding sections of `AGENTS.md`.
4. **Dynamic Domain Specialist Gates (`docs/agents/gates/*.md` & `.claude/agents/`):**
   * Scan `docs/agents/gates/*.md` (and any `*reviewer*.md` / `*auditor*.md` in
     `.claude/agents/`, deduplicating by `name` when `.claude/agents/<name>.md`
     wraps `docs/agents/gates/<name>.md`).
   * Match each gate's `triggers` path globs (or documented scope) against
     `CHANGED_FILES`. Every matched gate (for example `cpa-tax-reviewer` when
     `src/tax/**` changed) runs as its own parallel specialist axis!

---

## Step 4: Dispatch Cold-Diff Review Axes in Parallel

> **Fast-path exception:** If the diff is `< 30` changed lines across `1–2`
> files, has no originating spec, and matches zero `docs/agents/gates/` files,
> evaluate Axes 1 and 3 directly in a single pass after reading the full files.

Otherwise, spawn **fresh-context read-only subagents in parallel** so no axis
pollutes another. Pass **lean context pointers** (the exact git diff command,
`CHANGED_FILES`, and relevant doc paths), instructing every subagent to **read
full modified files** because diff hunks in isolation hide broken callers and
surrounding invariants:

### Axis 1: Correctness, Security & Test Integrity (Always Runs)
* **Prompt focus:** Audit `CHANGED_FILES` (reading full files) using the Bug,
  Security & Test-Integrity checklist in
  [references/smell-and-bug-catalog.md](references/smell-and-bug-catalog.md):
  logic/boundary errors, broken invariants, concurrency/partial-failure hazards,
  auth/injection/secret exposure, swallowed errors, unintended behavior changes,
  and **missing or tautological tests** (tests that recompute production
  formulas or mock internal collaborators instead of testing public seams).
* **Budget:** `<= 350` words; classify each finding as `BLOCKING` or `WARNING`.

### Axis 2: Spec, ADR & Glossary Conformance (Runs When Spec/ADR/Ticket Exists)
* **Prompt focus:** Compare the diff cold against the originating spec/ticket,
  governing ADRs, and `GLOSSARY.md`. Report:
  1. Requirements, invariants, or error-table transitions missing or partial;
  2. Unrequested behavior / scope creep not grounded in the spec;
  3. Contradictions with accepted ADRs or `GLOSSARY.md` (`Avoid:` synonyms used
     in new public identifiers);
  4. Missing requirement traceability comments/test tags when the repo uses them.
* Quote the exact spec/ADR requirement per finding. **Budget:** `<= 350` words;
  classify as `BLOCKING` or `WARNING`. (If no spec/ADR/ticket exists, skip this
  subagent and note `Spec axis: skipped (no originating spec/ticket)`.)

### Axis 3: Standards, Module Depth & Design Smells (Always Runs)
* **Prompt focus:** Check the diff against documented repo standards plus the
  **Module Depth & Fowler Smell Baseline** pasted from
  [references/smell-and-bug-catalog.md](references/smell-and-bug-catalog.md).
  * **Repo overrides baseline:** Documented repo conventions always win; skip
    anything linters/formatters already enforce.
  * **Hard rule vs. judgment:** Breaches of explicit repo rules can be `WARNING`
    or `BLOCKING`; baseline smells and shallow-module observations are always
    labeled `JUDGMENT`. **Budget:** `<= 350` words.

### Axis 4..N: Matched Domain Specialist Gate(s) (1 Subagent per Matched Gate)
* **Prompt focus:** Load the full gate file (`docs/agents/gates/<role>.md`), its
  listed `sources`, the diff command, and `CHANGED_FILES`. Execute its domain
  blocking checklist cold and return its `VERDICT: PASS | WARN | BLOCK` report
  in `<= 350` words.

---

## Step 5: High-Certainty Filtering & Orthogonal Report

Before emitting the final review, enforce these quality bars across all axes:

1. **Be certain before calling something a bug:** Review only the changes and
   their direct blast radius (not untouched legacy code). Verify library/API
   behavior in source before flagging. Every `BLOCKING` or `WARNING` item must
   name `[file:line]` and the **concrete input, state, or concurrency scenario**
   that triggers failure. State `"Uncertain: ..."` if unverified rather than
   inventing hypotheticals.
2. **Never merge or cross-rank axes:** Keep headings strictly separate so a
   clean `Standards` pass never hides a `Spec` miss or a `Domain Gate` block:
   * `## Structural Gates` *(when local checks ran)*
   * `## Correctness, Security & Tests`
   * `## Spec & ADR Conformance`
   * `## Standards & Module Depth`
   * `## Domain Gate: <name>` *(one section per matched specialist gate)*
3. **Zero flattery or filler:** Matter-of-fact engineering prose only. Never
   write `"Great job"`, `"Nice clean PR"`, or `"Thanks for..."`.
4. **Closing Gate Verdict:** End with a 2-line verdict block:
   * `VERDICT: PASS | PASS WITH WARNINGS | CHANGES REQUIRED` (`CHANGES REQUIRED`
     whenever any structural check fails or any axis emits a `BLOCKING` / `BLOCK`
     finding).
   * Per-axis count and single highest-severity item within each axis.
