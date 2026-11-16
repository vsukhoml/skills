---
name: refactoring
description: >-
  Safe refactoring and legacy modernization: extracts implicit behaviors and
  invariants, requires characterization and differential tests at each
  boundary before structural edits, then applies small behavior-preserving
  steps (Mikado, Branch by Abstraction, Strangler Fig, codemods) and removes
  dead code. Use when restructuring, modernizing, migrating, or cleaning up
  existing code without changing its behavior.
last_updated: 2026-11-15
---

# Safe Brownfield Refactoring & Legacy Modernization (`refactoring`)

Refactoring changes **internal code structure** while keeping **all externally
observable behavior 100% invariant**. Never rewrite code you have not characterized,
never couple safety-net tests to private internals you are about to delete, and never
mix behavior changes into a structural commit.

* Consult [references/contract-extraction-and-characterization.md](references/contract-extraction-and-characterization.md)
  for the **Behavioral Contract Ledger** template, Hyrum's Law quirk triage, boundary
  characterization / golden-master / differential-oracle harnesses, minimal dependency-
  breaking seams, and the 1-minute sabotage check.
* Consult [references/migration-patterns-and-codemods.md](references/migration-patterns-and-codemods.md)
  for Ousterhout module deepening vs. shallow fragmentation, the **Mikado Method** for
  tangled dependencies, **Branch by Abstraction / Strangler Fig** with live shadow
  diffing, and deterministic **AST codemods** (`ast-grep`, `comby`, `LibCST`, `OpenRewrite`).

*(When proposing formal repository specs/ADRs for undocumented systems or reviewing
readability after restructuring, also activate any available documentation-discovery,
test-driven development, and code review skills.)*

---

## 1. Extract Implicit Requirements, Observable Behaviors & Invariants (Read-Only Gate!)

Before proposing or editing a single structural line, perform **codebase archaeology**
(reading source, callers, tests, schemas, and `git log -S` / `-L` blame) and write a
concise **Behavioral Contract Ledger**:

1. **Extract Implicit Functional Requirements & Chesterton's Fences:**
   * Document *what business/system rules the code currently enforces* — especially ugly
     special-case `if` branches, retry loops, or normalization hacks!
   * **Chesterton's Fence:** Never delete or "simplify" a strange branch until `git
     log -L` / issue history explains what past outage or edge case put it there.
2. **Catalog User-Observable Behaviors (`Hyrum's Law` Surface):**
   * Record every externally visible contract callers or users can observe:
     * **Inputs & coercions:** Parameter ranges, defaults, whitespace/Unicode/case
       normalization, CLI flags, env vars, wire/config schemas.
     * **Outputs & error shapes:** Exact return payloads, sort/tie-break order, numeric
       rounding/precision, HTTP/RPC status codes, CLI stdout/stderr & exit codes.
     * **Side effects & envelopes:** Persisted file/DB mutations, emitted events/IPC
       messages, idempotency behavior, ordering guarantees, and latency/RAM bounds.
   * **Separate Load-Bearing Quirks from Latent Bugs:** If you spot an apparent bug
     during archaeology, **do NOT silently "fix" it inside a refactor!** Record it
     explicitly and get owner alignment to fix it in a separate, dedicated `[fix]`
     commit *before* or *after* the refactor.
3. **Identify Internal Invariants (`INV`):**
   * List data-structure and state-machine truths that must hold across every step
     (conservation laws `sum(parts) == total`, lock acquisition order, ownership/arena
     lifetimes, sortedness, idempotency keys, cache coherence).
4. **Map Every Boundary Interface (`Inbound` & `Outbound` Seams):**
   * Enumerate all public functions/types, API/CLI entrypoints, event consumers
     (*inbound seams*), and all DB/file/network/clock/RNG calls (*outbound seams*)
     bordering the refactor scope.

---

## 2. Lock Boundary Interface Test Coverage *Before* Touching Structure

**Iron Law:** Zero structural refactoring begins until **every boundary interface** in
your map has verified automated test coverage across happy, boundary, ordering, and
error paths!

1. **Audit Existing Tests for "Hollow Coverage":**
   * Line coverage lies when tests mock out the boundary being changed, lack assertions,
     or call **private internal helpers directly** (tests coupled to private internals
     shatter the moment you restructure, blinding your safety net right when you need it!).
   * Shift tests to exercise **public boundary interfaces** with realistic data.
2. **Build Characterization & Differential Harnesses for Uncovered Seams:**
   * **Characterization / Golden-Master Tests:** Feed representative + boundary/error
     inputs into the public seam and assert the exact recorded `(output, persisted
     state, emitted side-effects)` — pinning *what the code actually does today*.
   * **Same-Process Differential Oracle (`legacy(x) == candidate(x)`):** Whenever
     rewriting an algorithm, parser, serializer, or query builder, keep the old routine
     callable in tests and fuzz/property-test `1,000–50,000` generated inputs asserting
     bit-for-bit (or invariant-equivalent) parity!
   * **Minimal Enabling Seams Only:** If hard-wired globals, wall clocks, or live
     sockets block testing, apply *only* zero-logic mechanical dependency injection
     (`Parameterize Constructor/Function`, `Extract Outbound Interface`) first so the
     characterization suite runs fast and deterministically.
3. **Run the 1-Minute Sabotage Check:**
   * Temporarily flip one operator/branch inside the target code, confirm your boundary
     test suite **fails immediately**, and revert the sabotage. If tests stay green when
     code is broken, your safety net has a hole — fix the test before refactoring!

---

## 3. Pick the Right Refactoring Strategy

1. **Small-Step Module Deepening (Single Module / Cohesive Scope):**
   * Execute tiny mechanical moves (*Split Pure Core from I/O Shell*, *Extract Pure
     Function*, *Inline Shallow Pass-Through Wrapper*, *Replace Boolean Soup with Sum
     Type*), running boundary tests after **every** move.
   * **Deepen, don't shatter!** Never chop one readable 200-line algorithm into 15
     shallow 12-line pass-through functions scattered across 5 files — aim for **narrow
     public interfaces hiding deep, pure internal logic**.
2. **The Mikado Method (Tangled / Cascading Compile Dependencies):**
   * Attempt the goal change $\rightarrow$ note every compile/test breakage as child
     nodes in a dependency graph $\rightarrow$ **`git restore .` immediately back to
     green!** $\rightarrow$ solve and commit **leaf prerequisites bottom-up** so the
     codebase compiles and passes tests at *every single commit*.
3. **Branch by Abstraction / Strangler Fig + Shadow Diffing (Large or Live Systems):**
   * Put a clean **Boundary Interface** in front of the legacy component $\rightarrow$
     build the new implementation alongside it $\rightarrow$ dual-run **Shadow Mode**
     (returning `legacy` while comparing `candidate` outputs & latencies asynchronously
     until mismatches == `0`) $\rightarrow$ ramp traffic (`1% -> 10% -> 100%`)
     $\rightarrow$ **delete the legacy code and temporary router completely**.
4. **Deterministic AST Codemods & Batching Proven Mechanics Only:**
   * Across `>= 15` call sites, use syntax-aware AST tools (`ast-grep`, `comby`,
     `LibCST` / `libcst.codemod`, `jscodeshift`, `OpenRewrite`, Kotlin
     `@Deprecated(..., ReplaceWith(...))`, `ast-grep --lang kotlin`, `gofmt -r`,
     `clang-tidy`, `rust-analyzer` SSR) instead of error-prone manual edits or regexes
     that mangle strings and comments.
   * **Never batch exploration:** Verify the transformation rule on one slice first; once
     proven, batch remaining sites with per-step assertions/checks that **halt at the
     first mismatch** so a flawed rule never corrupts the rest of the queue.

---

## 4. Strict Execution Discipline ("Two Hats" & Clean Exit)

1. **Kent Beck's "Two Hats" Rule:** Every commit is **strictly either** `[refactor]`
   (zero behavior change; existing characterization assertions **unmodified**!) **or**
   `[fix]`/`[feat]` (intentional behavior change with explicit test updates).
2. **Never Leave Half-Migrated "Lava Layers":** A refactor that introduces `"NewServiceV2"`
   while leaving `"OldService"` alive on 30% of callers indefinitely **increased**
   system complexity! Finish the cutover and delete the dead path, or track an explicit
   removal task before closing.
3. **Verify Post-Refactor Invariants:** Confirm all boundary characterization +
   differential tests pass, performance/memory/binary size did not regress beyond noise,
   and public surface area / coupling measurably shrank.

---

## Before You Finish (`refactoring` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Editing legacy code before listing observable behaviors & boundary seams | Write the **Behavioral Contract Ledger** (inputs, outputs, side effects, quirks, invariants) first |
| Starting a rewrite with `0` boundary tests (or tests mocking private internals) | Pin **all inbound/outbound boundary seams** with characterization tests + pass a sabotage check |
| AI/engineer "cleans up" an odd `if` branch and silently breaks a downstream client | Obey **Hyrum's Law & Chesterton's Fence**: check `git log -L` and preserve observable quirks |
| Single 1,500-line PR mixes structural reorganization, renames, AND 3 bug fixes | Enforce **Two Hats**: split pure `[refactor]` commits (tests untouched) from `[fix]` commits |
| Working tree stays broken/uncompilable for hours during a big type-signature change | Revert to green and apply the **Mikado Method** bottom-up from leaf prerequisites |
| Chopping 1 cohesive routine into 14 tiny shallow pass-through wrappers | Build **deep modules**: narrow interface + pure functional core, inline pointless wrappers |
| Leaving `LegacyParser` + `NewParser` + `use_v2` shim alive forever ("Lava Layer") | Shadow-verify to `0` mismatches, ramp to `100%`, and **delete** legacy code + shim |
