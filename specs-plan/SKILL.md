---
name: specs-plan
description: >-
  Breaks an approved spec, ADR, or design into a dependency-ordered task plan
  for the SPECS suite, with traceability tags, acceptance criteria, and
  verification commands. The plan file is also the execution ledger. Use after
  a spec has passed specs-grill and before implementation starts.
last_updated: 2026-11-15
---

# SPECS Planning

Decomposes an approved spec, ADR, or design into a scannable, dependency-ordered
execution plan at `docs/plans/PLAN-NNNN-<slug>.md`, using a two-pass
Generator–Critic process, the `specs` Document Quality & Reviewability Standard,
and a user approval gate before implementation starts.

**Precondition:** Target specs (`SPEC-NNNN`) must carry `status: approved`
after passing `specs-grill` (zero open blocking questions). If a target spec is
still `draft` or `grilled`, tell the user and offer to run `specs-grill` first —
planning against an unapproved or ambiguous spec produces confidently wrong
tasks.

## Workflow

### 1. Parse Input & Prime

Read `GLOSSARY.md` / `GLOSSARY-MAP.md` (in `docs/` or repo root, if present),
the source artifact(s) (`spec.md` verifying `status: approved`, `design.md`, and
governing ADRs), and inspect the affected code paths. Canonical glossary terms
and ADR boundary/ownership rules govern task titles, proposed type/function
names in `Target`, and acceptance criteria (never introduce `Avoid:` synonyms).
Check `docs/plans/index.md` and `docs/plans/` for an existing plan covering the
same spec — **never create a duplicate plan; update or resume the existing one**
(idempotency).

### 2. Generator Pass

Draft `docs/plans/PLAN-NNNN-<slug>.md` as a **technical document that people
read to make a decision** — applying plain English for international or
non-native readers, any available technical-document writing skill, and the
`specs` Document Quality & Reviewability Standard so a reviewer can verify
requirement coverage, task order, and one-way steps on the first screen:

* **Answer-first summary:** Below `# PLAN-NNNN: <Title>`, write a 3 to 5
  sentence summary stating the governing spec, phase and task count, any one-way
  step (migration, wire format, public API), and the current fixpoint status.
* **Requirement coverage table:** Frame a compact table (italic conclusion caption
  below) mapping every `REQ-NNNN` and
  `INV-NNNN` in the source spec to its satisfying task IDs and test target.
  Every REQ maps to at least one task; no task exists without a governing REQ or
  INV (YAGNI).
* **Atomic, dependency-ordered tasks:** Group tasks under `## Phase N: <Name>`
  (`foundations -> core behavior -> failure/recovery & verification`), with at
  most 3 heading levels. Each task targets one coherent change (`< ~100` changed
  lines) and lists explicit `Blocked by` task IDs.
* **Unambiguous acceptance criteria & commands:**
  * Write each acceptance criterion as a single falsifiable clause with a real
    component/function subject and lowercase `must` or `must not` (never
    `should`, `may`, `could`, `would`, or ALL-CAPS shouting).
  * Do not repeat full spec prose; cite `Name (REQ-YYYY)` and state the concrete
    code-level postcondition.
  * Keep inline commands and fenced `bash` blocks to straight ASCII quotes and
    flags and spaces only (no `\t`), so commands copy cleanly from Markdown and
    Google Docs.

**Plan & task template (every plan file must follow this layout):**

````markdown
---
id: PLAN-NNNN
governing: SPEC-XXXX
status: draft
updated: <YYYY-MM-DD>
---

# PLAN-NNNN: <Short imperative title>

<3 to 5 sentence summary: governing spec, phase and task count, any one-way
migration or wire-format step, and fixpoint status.>

## Requirement coverage

Table 1 maps every normative requirement and invariant in SPEC-XXXX to its
implementation task and verification target.

Requirement                | Tasks      | Verification target
-------------------------- | ---------- | -------------------
Token expiry (REQ-0001)    | T-01, T-02 | `auth/verify_test.go`
Monotonic nonce (INV-0001) | T-03       | `store/nonce_test.go`

*Table 1: All requirements in SPEC-XXXX have a task and a test.*

## Phase 1: Foundations

Each task in Phase 1 establishes types and storage boundaries before feature
handlers run:

### T-01: <Short imperative title without trailing colon>

T-01 implements the <target capability> under these constraints:

- **Governing:** SPEC-XXXX (REQ-0001), ADR-ZZZZ
- **Blocked by:** none
- **Target:** `path/to/file.go` (`Verifier.Verify`)
- **Acceptance criteria:** Each statement below must hold before T-01 closes:
  - `Verifier.Verify` must reject tokens larger than 4 KiB with `ErrOversize`.
  - `Verifier.Verify` must not allocate heap state before checking length.
- **Verification:** `go test -run TestVerifyBounds ./auth/...`
- **Notes:** Reuse `clock.Monotonic` (`pkg/clock`). One-way step: none.
- **Status:** pending
````

### 3. Reviewability Check & Critic Pass

1. **Check the draft before human review:** List and fix any measurable rule
   violations in the plan (running any available technical-document lint script,
   and verifying the opening summary, framed Table 1, and zero ambiguous modals
   `should`/`may`/`could`/`would`).
2. **Spawn a critic subagent** to antagonistically audit the clean plan:
   * Template compliance for every task (`Target` names exact files/symbols —
     never `"various files"`).
   * Valid DAG: no cycles, no missing foundation blockers, one-way steps called
     out before irreversible tasks run.
   * Bidirectional coverage: every `REQ-NNNN` and `INV-NNNN` in `SPEC-XXXX`
     appears in Table 1 and at least one task; no orphan tasks.
   * Domain & boundary alignment: task titles, new symbol names in `Target`, and
     acceptance criteria use canonical `GLOSSARY.md` vocabulary (zero `Avoid:`
     synonyms) and obey ADR bounded-context ownership rules.
   * Testable `must` / `must not` criteria and real project verification
     commands (verified in `Makefile`, `Cargo.toml`, `go.mod`, `package.json`,
     `pyproject.toml`, `build.gradle.kts`, `CMakeLists.txt`, or CI).
   * Zero duplication of work already completed in existing code or prior plans.

Fix critic findings in at most 3 rounds (re-checking reviewability limits after
edits), then surface any remaining trade-off to the user.

### 4. Approval Gate

Create or update `docs/plans/index.md` whenever a plan is added or renamed
(`PLAN-NNNN`, linked title, and one literal sentence stating the scope). Present
a concise overview (phase count, task count, one-way steps, and Table 1)
alongside the plan path, and ask the user to **Approve**, **Modify**, or
**Reject** (using the structured question tool). On modification feedback,
regenerate from Step 2 and re-verify. **Do not start coding before approval.**

### 5. The Plan Is the Ledger

Once approved (`status: approved`), update `docs/plans/index.md` to reflect the
approved plan; the plan file is now the single source of execution truth:

* Update each task's `Status:` (`pending -> in_progress -> done | skipped |
  blocked`) **immediately as each transition occurs**, not in a batch at the
  end, so interrupted work resumes cleanly without duplicate edits.
* Record mid-execution discoveries append-only: add a one-sentence deviation
  note with date (`YYYY-MM-DD`) on the affected task, and append any newly
  discovered task as the next `T-NN` with explicit `Blocked by` wiring and a
  row in Table 1.
* On completion, run the `specs` Solidify drift check, record the fixpoint
  verdict in the opening summary, set `status: done`, and update
  `docs/plans/index.md`.

## Execution Handoff

Before starting implementation on a domain with strict invariants, calculations,
or module boundaries that lack automated checks or specialist review gates in
`docs/agents/gates/`, offer to run **`specs-tools`** so task verification rests
on deterministic guardrails. Then execute the approved `PLAN-NNNN` task graph via
**`specs-implement`** (which dispatches ready-frontier slices, enforces
vertical red-green seam testing, updates `Status:` immediately, and closes out
with `specs` Solidify and cold-diff review). Never start a task whose blockers
are not `done`.
