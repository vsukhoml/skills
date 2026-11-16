---
name: specs-discover
description: >-
  Documentation gap analysis for the SPECS suite: compares an existing
  codebase with its specs and ADRs and proposes a prioritized, evidence-based
  list of missing or stale documentation. Use to bootstrap SPECS artifacts on
  an undocumented project or to find coverage gaps on a documented one.
  Proposes only; it drafts nothing.
last_updated: 2026-11-15
---

# SPECS Discovery

Inspects a repository, compares code reality against `docs/`, and presents a
high-signal, decision-ready proposal table of missing or stale ADRs, specs, and
domain glossaries.

**CRITICAL RULE — propose, do not draft.** This skill only identifies *what*
needs documentation and *why*. It never creates or edits `GLOSSARY.md`,
`ADR-NNNN.md`, or `spec.md` files. Drafting happens after user approval, one
artifact at a time, via `specs-adr` and the `specs` Establish phase.

## Workflow

### 1. Prime Context

Read existing documentation first: `GLOSSARY.md` / `GLOSSARY-MAP.md` (in `docs/`
or repo root), `docs/adrs/index.md`, `docs/specs/index.md`, `docs/plans/`,
`README.md`, `CLAUDE.md` / `AGENTS.md`, and existing specs/ADRs. Record current
coverage, staleness, and the link graph — you are diffing code reality against
this baseline. If no `docs/` root exists, the baseline is empty and `ADR-0001`
(Foundational Blueprint) is automatically the first proposal.

### 2. Inventory the System

Inspect the codebase (delegate broad scanning to a research subagent on large
repositories) to identify load-bearing boundaries:

* **Entry points:** binaries, CLIs, daemons, exported libraries, worker jobs.
* **Trust & interface boundaries:** public HTTP/RPC schemas, auth gates, IPC
  protocols, wire or file formats.
* **Domain vocabulary & bounded contexts:** overloaded nouns (`account`, `user`,
  `transaction`) carrying different meanings across packages/services, or
  distinct bounded contexts communicating via domain events or shared IDs.
* **Expensive-to-reverse or non-obvious choices:** languages, data stores,
  auth/crypto models, cross-context integration patterns, boundary `"no"` rules,
  and deliberate deviations from standard repo patterns (such as manual SQL
  bypassing the repo ORM on a hot path).
* **Behavioral density:** modules with nontrivial state machines, invariants,
  failure recovery, or large test suites (`verified in source`).

### 3. Diff Against Existing Docs

Classify each load-bearing area as:

* **Documented & current:** Existing ADR/spec matches the code and has testable
  contracts. Skip it.
* **Documented but stale:** Code has diverged from the specification, design
  document, or ADR, or listing rule violations in the technical document
  surfaces unresolved `TBD` / `[Open: ...]` placeholders, ambiguous modals
  (`should`/`may`), or missing contracts (run any available technical-document
  lint script when triaging existing docs). Propose a targeted revision.
* **Undocumented:** No governing ADR or spec exists.

### 4. Shape a High-Signal Proposal Table

Keep the proposal list concise and proportional to reversal cost:

* **No low-signal stubs:** Do not propose specs for thin glue code, generated
  files, or trivial CRUD wrappers. Group tightly coupled sub-packages into one
  coherent component spec rather than splitting one boundary across 4 tiny files.
* **`ADR-0001` first:** Mandatory `P0` if absent (tech stack, languages, build,
  and repository conventions embodied in code).
* **Offer ADRs sparingly (3-Gate Filter):** Propose additional ADRs **only**
  when a choice embodied in code is **(1) hard to reverse**, **(2) surprising
  without context** (including boundary/ownership `"no"` rules, deliberate
  deviations from the obvious path, or invisible external constraints), and
  **(3) the result of a real trade-off**. Skip obvious or easily reversed
  library choices.
* **Domain glossary when terms drift:** Propose `docs/GLOSSARY.md` (or
  `docs/GLOSSARY-MAP.md` plus per-context glossaries when bounded contexts give
  the same noun different meanings) if core domain nouns are overloaded or
  inconsistent across modules.
* **Specs for stateful or boundary-critical components:** Modules with external
  contracts, invariants, failure modes, or substantial test suites lacking
  `docs/specs/<feature>/spec.md`.

Present the report with an **answer-first summary** followed by a **framed
table** (italic conclusion caption below):

```markdown
## Documentation gap analysis

<2 to 4 sentences: baseline doc count vs code modules inspected (verified in
source), count of P0/P1/P2 proposals, and the first step with the fact that puts it
first.>

Table 1 lists the proposed ADRs and specifications ordered by priority and
reversal risk.

Artifact  | Proposed title         | Priority | Evidence (verified in source)
--------- | ---------------------- | -------- | -------------------------------
ADR-0001  | Go service stack       | P0       | 4 binaries in `cmd/`, no ADR.
ADR-0002  | PostgreSQL ledger      | P0       | `pgx` transactions (`ledger/`).
SPEC-0001 | Token issue and revoke | P1       | `auth/` has 38 tests, no spec.
SPEC-0002 | Webhook retry worker   | P2       | Spec omits `retry.go` cap.

*Table 1: Two P0 architecture records block downstream component specs.*
```

Priority definitions:

* **P0 (Foundational / blocking):** Missing `ADR-0001`, undocumented trust or
  storage boundary, or stale spec actively contradicting production code.
* **P1 (Core contract):** Stateful or externally facing component with invariants
  and failure paths not yet specified.
* **P2 (Optional):** Isolated internal module with low reversal cost.

### 5. Approval Gate

Present the report and ask the user to choose via the structured question tool:
**Approve all**, **Select / modify items**, or **Cancel**. Do not write files
before approval.

### 6. Hand Off

Draft approved items lazily and one at a time in priority order:

1. `GLOSSARY.md` / `GLOSSARY-MAP.md` (when approved: pure domain definitions +
   `Avoid:` synonyms, zero implementation details; see `specs`).
2. `specs-adr` for ADRs (starting with `ADR-0001`; Compact ADR or Full MADR by
   reversal cost).
3. `specs` Establish phase for specs (followed by `specs-grill` before marking
   `approved`).
4. Verify every drafted artifact against the `specs` Document Quality &
   Reviewability Standard and update its directory `index.md`.
