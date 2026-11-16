---
name: specs-implement
description: >-
  Executes an approved SPECS plan (PLAN-NNNN) or spec (SPEC-NNNN) as a
  dependency-ordered task graph, with implementer subagents in isolated
  worktrees, red-green seam tests, structural guardrails, and cold-diff
  review. Use when ready to implement an approved spec or plan.
last_updated: 2026-11-15
---

# SPECS Graph Execution & Guardrailed Implementation (`specs-implement`)

Turns an approved `PLAN-NNNN` (and governing `SPEC-NNNN`) into verified,
traceable production code on an integration branch — maximizing concurrency
across independent DAG slices while enforcing deterministic structural brakes
and cold-diff specialist review before completion.

---

## Preconditions & Brake Check (Stop Before Slop)

Verify all three preconditions before dispatching implementation work:

1. **Approved spec & plan:**
   * Every target `SPEC-NNNN` must carry `status: approved` after passing
     `specs-grill` (zero unresolved blocking questions). If a target spec is
     still `draft`, `grilled`, or ambiguous, stop and route to `specs-grill`.
   * If work spans more than one small (`< ~100`-line) slice and no approved
     `docs/plans/PLAN-NNNN-*.md` exists, stop and route to `specs-plan`.
2. **Two-speed deterministic brakes wired:**
   * Locate the repo's **fast single-slice command** (`< 5 s` single test +
     incremental compile/typecheck) and **full structural gate command**
     (`check-gates`: compile/types, lint, module-boundary check, golden suite)
     in `AGENTS.md` / `CLAUDE.md` or the project's build/task configuration.
3. **Domain gate check:**
   * Inspect `docs/agents/gates/`. If the spec introduces high-blast-radius
     domain rules (financial/tax math, double-entry state, regulated PII/PHI,
     auth/crypto, or wire protocols) and neither `tests/golden/` nor
     `docs/agents/gates/` has been configured yet, offer to run **`specs-tools`**
     first so brakes exist before code accelerates.

---

## Execution Modes (Right-Sized for Token Efficiency)

Choose the lightest mode that matches the plan graph:

* **Serial In-Place Mode (`1–2` sequential tasks, or user requests current branch):**
  Execute one task at a time directly on the active feature branch using the
  Task Execution Contract below, updating `PLAN-NNNN` after every state change.
* **Frontier Subagent Mode (`3+` tasks or parallel DAG waves):**
  Treat `PLAN-NNNN` as a directed acyclic graph over a single **integration
  branch** (`feat/<spec-slug>` or current non-main branch):
  * Compute the **ready frontier**: tasks with `Status: pending` whose
    `Blocked by` dependencies are all `done` **and whose `Target` file paths are
    disjoint** (if two ready tasks edit the same file, serialize them in two
    waves rather than paying merge-conflict tax).
  * Spawn **one fresh-context implementer subagent per frontier task**, each in
    an isolated git worktree (`Workspace: "branch"` or `git worktree add
    <worktree-path> -b <slice-branch> <integration-sha>`) so concurrent resets,
    staging, and commits never share `.git/index` or `HEAD`.

---

## Sparse Context-Pointer Protocol (Never Dump Transcripts)

Subagents suffer when fed bloated conversation history. Communicate strictly
through **file paths, line ranges, and git refs** (`<= 25` lines per brief):

1. **(Optional) Shared upfront exploration:** If multiple tasks touch an
   unfamiliar legacy subsystem, run **one** read-only exploration subagent first
   and have it write concise navigation notes (`<= 200` lines) to a scratch file
   outside the repo, then pass that file path to implementer subagents so none
   repeats codebase discovery.
2. **Implementer Subagent Brief (exact pointer fields):**
   * **Base ref & slice branch:** Integration branch name + expected base `HEAD`
     SHA + dedicated slice branch (`feat/<spec-slug>-T-NN`) in its isolated
     worktree.
   * **Task pointer:** Path and line range of `T-NN` in `docs/plans/PLAN-NNNN-*.md`.
   * **Contract pointers:** `GLOSSARY.md`, `SPEC-NNNN` (`REQ-*`, `INV-*` IDs for
     this task), `design.md`, and governing `ADR-NNNN` paths.
   * **Verification commands:** Fast inner-loop command (`< 5 s`), task-specific
     `Verification:` command from `T-NN`, and repo `check-gates` command.
   * **Task Execution Contract** (below) + required return payload: commit SHA,
     touched files, command exit codes, and any 1-sentence spec/plan deviation.

---

## Task Execution Contract (Every Slice Must Obey)

Each task (`T-NN`) executes this exact loop:

1. **Test-first vertical slices at public seams:** Build the task using
   **test-driven development with a vertical-slice red-green loop at public
   module seams** (activating any available test-driven development skill):
   * Test only through public module entry points (never internal subfolders or
     private helpers; mock only external system boundaries like clock, RNG, or
     network).
   * Use **independent expected-value oracles** (worked spec literals,
     `tests/golden/` tables, or `INV-NNNN` properties) — **never** tautological
     tests that recompute production formulas.
   * Run the `< 5 s` single-test command on every `RED -> GREEN` cycle.
2. **Traceability & readability:**
   * Add governing comments (`// Governing: SPEC-XXXX, REQ-YYYY`) on implementing
     functions/blocks and cite `REQ-YYYY` / `INV-YYYY` in test names or comments
     so `grep REQ-YYYY` locates spec, implementation, and test.
   * Follow `specs-readability` (intent-focused comments, structural public API
     docstrings, canonical `GLOSSARY.md` identifiers, zero `Avoid:` synonyms,
     atomic `< ~100`-line scope).
3. **Deterministic verification before reporting done:**
   * Run `T-NN`'s exact `Verification:` command **and** the repo's structural
     gate (`check-gates`).
   * In Frontier Subagent Mode, rebase/merge the latest integration branch tip
     into the slice branch, re-run `T-NN` verification, commit cleanly, and
     report back.
4. **3-strike circuit breaker:** If a task fails verification or hits an
   architectural contradiction more than **3 times**, **stop immediately** — do
   not loop blindly. Report the exact contradiction so the coordinator marks the
   task `blocked` and surfaces the decision (or routes to `specs-adr`).

---

## Coordinator Ledger & Wave Loop

Maintain `PLAN-NNNN` as the live execution ledger throughout:

1. Mark dispatched tasks `Status: in_progress` **immediately** before launching.
2. As each slice completes:
   * Verify its reported test and `check-gates` commands exited `0`.
   * Merge/fast-forward the slice commit onto the integration branch.
   * Immediately update `T-NN` in `PLAN-NNNN` to `Status: done` (recording any
     append-only `YYYY-MM-DD` deviation note or newly discovered `T-MM` task in
     Table 1 + phase list).
3. Recompute the ready frontier and dispatch the next wave until every task in
   `PLAN-NNNN` is `done` (or explicitly `skipped`/`blocked` with user sign-off).

---

## Integration Closeout Gate (`Solidify`)

Once all tasks land on the integration branch, run the closeout sequence before
declaring the spec implemented:

1. **Full deterministic & golden gate:** Run `check-gates` and the full test
   suite across the integration branch (`0` warnings/errors suppressed).
2. **Cold-diff multi-axis + domain review:** Run a **parallel multi-axis
   cold-diff code review** across `<base>...HEAD` covering *(a) Correctness,
   Security & Test Integrity*, *(b) Spec, ADR & Glossary Conformance*, *(c) Repo
   Standards & Module Depth*, and *(d) every matching specialist gate in
   `docs/agents/gates/`* (activating any available multi-perspective code review
   skill).
   * If any axis or domain specialist gate returns `BLOCKING` / `BLOCK`
     (`CHANGES REQUIRED`), run a fresh targeted fix slice (red regression test ->
     minimal fix -> `check-gates`), then re-verify the failed review axis.
3. **Readability & bidirectional fixpoint check (`specs` Solidify):**
   * Run `specs-readability` over modified source files.
   * Verify bidirectional traceability: every `REQ-NNNN` and `INV-NNNN` in
     `SPEC-NNNN` maps to a governing comment and passing test, and every
     governing comment matches current spec prose.
4. **Finalize ledger & cleanup:**
   * Record `"fixpoint reached — no action required"` in `PLAN-NNNN`, set
     `PLAN-NNNN` `status: done`, set `SPEC-NNNN` `status: implemented`, and
     update `docs/plans/index.md` + `docs/specs/index.md`.
   * Remove temporary subagent worktrees and report the integration branch,
     commit range, gate results, and review verdict to the user.
