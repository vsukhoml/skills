---
name: tdd
description: >-
  Test-driven development with a vertical-slice red-green loop, behavioral
  tests at public seams, and anti-tautological assertions. Use when building a
  feature or fixing a bug test-first, running a red-green-refactor cycle,
  writing integration or golden-oracle tests, or implementing plan tasks slice
  by slice.
last_updated: 2026-11-15
---

# Test-Driven Development (`tdd`)

Builds features and fixes bugs through a **tight, repeatable vertical-slice
`RED -> GREEN` feedback loop** anchored at public module seams and backed by
independent expected-value oracles.

Consult [references/patterns-and-seams.md](references/patterns-and-seams.md) for
concrete multi-language examples of seam tests, independent golden/property
oracles, and system-boundary fakes vs. banned internal mocks.

---

## Step 0: Prime Vocabulary & Fast Runner (`< 5 s` Inner Loop)

Before writing the first test:

1. **Align with repo vocabulary & decisions:** Read `GLOSSARY.md` /
   `GLOSSARY-MAP.md` (in `docs/` or repo root, if present) and any governing
   ADRs or spec sections touching the module. Test names, fixture builders, and
   public interfaces must use canonical domain terms (never `Avoid:` synonyms)
   and cite requirement/invariant IDs (`REQ-NNNN`, `INV-NNNN`) when the repo
   tracks them.
2. **Pin the fast single-slice command:** Check `AGENTS.md` or the project's
   build/test configuration for its single-file / single-case test filter
   command (e.g., `go test -run`, `cargo test`, `pytest -k`, `ctest -R`, `gradle
   --tests`, `dotnet test --filter`, `vitest run`).
   * **Speed rule:** The inner red-green command must run in seconds. Never run
     a slow full-repo suite on every slice; reserve the full structural & golden
     gate for slice/task completion.

---

## Step 1: Lock Public Seams Before Writing Any Test

A **seam** is the public module entry point where callers observe behavior
without reaching inside private submodules, internal folders, or backing tables.

1. **Test only through public entry points:** Tests must import the exact public
   interface external callers import — never internal subfolders (`internal/`,
   `lib/`, `_private`), private helpers, or raw storage tables behind an
   interface's back. Code internals can be rewritten completely; behavioral seam
   tests must survive unchanged.
2. **Confirm seams upfront:** Unless the user or an approved task definition
   already fixed the exact target seam, list the **1–3 public seams** you plan
   to test with a one-line note on *(a) what failure modes each catches* and
   *(b) what it intentionally leaves out*, and confirm with the user before
   writing tests.

---

## Step 2: Three Non-Negotiable Guardrails (Hard Bans)

Every cycle must obey all three rules:

1. **Ban Tautological Oracles (Never Recompute the Formula):**
   * **Forbidden:** Computing `expected` in the test using the same formula,
     rate expression, helper, or constant as production code
     (`expect(calcTax(x)).toBe(Math.round(x * RATE))`), or snapshotting
     unverified output from the code just written. Such tests pass by
     construction even when the formula is wrong.
   * **Required:** Derive expected values from an **independent oracle**:
     worked literal examples from the spec/statute/RFC, immutable fixture tables
     in `tests/golden/` / `testdata/golden/`, algebraic invariants
     (conservation, round-trip, idempotency, monotonicity), or a separate
     reference implementation.
2. **Ban Horizontal Bulk Slicing:**
   * **Forbidden:** Writing 10 failing tests upfront and then implementing all
     production code in one batch. Bulk upfront tests lock in *imagined* call
     shapes before real implementation constraints surface.
   * **Required:** Work in **vertical tracer-bullet slices**: **one** failing
     behavioral test -> **minimal** production code to pass -> fast check ->
     next slice informed by what just ran.
3. **Ban Internal Collaborator Mocks & Side-Channel Assertions:**
   * **Forbidden:** Mocking your own internal classes/modules/functions,
     asserting internal call counts or call order (`toHaveBeenCalledTimes`), or
     querying raw DB rows to verify a write when the module's public read API
     can observe the behavior.
   * **Required:** Isolate **only true system boundaries** (external network
     APIs, wall-clock time, RNG, hardware/OS I/O) via narrow injected interfaces
     or realistic in-memory/local test adapters.

---

## Step 3: The Repeatable Vertical Loop

Execute this exact sequence for each behavioral slice:

1. **RED — Write one failing behavioral test at the seam:**
   * Express *what* capability or rejection rule holds (`"rejects expired token
     with ErrExpired"`, `"phases out credit above $200,000 MAGI"`), never *how*
     internals execute.
   * Run the fast single-test command and **verify it fails for the expected
     behavioral reason**. A test that passes immediately or fails on syntax/type
     errors does not count as RED — fix the setup until the assertion itself
     fails cleanly.
2. **GREEN — Write the minimal production code to pass:**
   * Implement only what the red test demands; do not add speculative branches,
     config flags, or abstractions for unscheduled slices.
   * Run the fast single-test command + incremental typecheck until GREEN.
3. **LOCAL TIGHTEN — Keep slice debt near zero:**
   * Clean up dead locals or obvious duplication *inside the lines just touched*
     while keeping tests green. Defer cross-module structural refactoring to a
     dedicated refactoring pass or post-implementation code review.
4. **REPEAT — Next vertical slice:**
   * Cover happy path -> boundary/cliff edges -> explicit failure/error-table
     cases -> invariants (`INV-NNNN`), one tracer bullet at a time.
5. **STRUCTURAL GATE — Close out the task:**
   * Once all vertical slices for the task pass, run the repository's full
     deterministic gate command (`check-gates`: full typecheck, linter,
     module-boundary rules, and `tests/golden/` + unit/integration suite). Do
     not declare work complete while any structural check is red.
