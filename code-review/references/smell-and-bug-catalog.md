# Bug, Test-Integrity & Module-Smell Reference (`code-review`)

Pass the relevant section below directly into the corresponding subagent prompt
so fresh-context review subagents have self-contained criteria without extra
skill lookups.

---

## 1. Axis 1 Checklist: Correctness, Security & Test Integrity

1. **Logic, Bounds & Invariants (`BLOCKING` when reproducible):**
   * Off-by-one bounds, wrong comparison operators (`<` vs `<=`), integer
     overflow/truncation, float precision loss in exact domains, nil/empty/zero
     inputs, wrong guard polarity, unreachable branches.
   * Language-specific type/value traps: JS/TS truthiness or `||` defaults
     conflating `undefined`/`null` with valid falsy `0`/`""`/`false`, runtime-erased
     `as T` casts on unvalidated external payloads, and Kotlin non-null `!!`
     assertions or unguarded Java platform types (`T!`).
   * Unintended behavioral regressions to existing callers.
2. **Failure Paths, State & Concurrency (`BLOCKING` / `WARNING`):**
   * Partial writes leaving inconsistent state on mid-operation failure, missing
     rollback/cleanup, unclosed handles/goroutines/tasks, lock-order or TOCTOU
     races, non-idempotent retries, unbounded `O(n^2)` loops or `N+1` queries on
     untrusted/unbounded input sizes.
   * Swallowed errors, unawaited floating promises in JS/TS, swallowed coroutine
     `CancellationException` in Kotlin (`catch (Exception)` / `runCatching` around
     `suspend` calls without rethrowing cancellation), broad catch-all handlers
     hiding root causes, or leaked internal stack/PII details across trust
     boundaries.
3. **Security Surface (`BLOCKING`):**
   * Authn/authz bypass, IDOR/tenant-isolation gaps, SQL/command/template/path
     injection, SSRF, hardcoded secrets, missing input size caps.
   * Client/platform hazards: JS/TS prototype pollution (`__proto__` /
     `constructor.prototype` merges), DOM XSS (`innerHTML` /
     `dangerouslySetInnerHTML` / `javascript:` URLs), and Android mutable
     `PendingIntent`s (`FLAG_MUTABLE` without explicit component) or unvalidated
     exported-component `Intent` extras / deep-link `Uri`s.
4. **Test Integrity (`BLOCKING` / `WARNING`):**
   * New non-trivial branches or bug fixes shipped with zero behavioral seam
     test.
   * **Tautological assertions:** test recomputes `expected` with the same
     formula/helper as the implementation instead of asserting independent
     worked literals, golden fixtures, or invariants.
   * **Brittle internal coupling:** test mocks internal collaborators or peeks
     at private state/tables instead of exercising the public module interface.

---

## 2. Axis 3 Baseline: Module Depth & Fowler Code Smells

Two binding rules govern this baseline:
1. **Documented repo conventions always win.** Where a repo standard endorses a
   pattern, suppress any conflicting heuristic below. Skip formatting/lint rules
   already enforced by automated tooling.
2. **Baseline items are always `JUDGMENT`, never `BLOCKING`** (unless an
   explicit repo rule elevates them). Quote the hunk and name the smell + minimal
   remedy:

### Module Depth & Seam Health (Ousterhout)
* **Shallow Pass-Through Module:** Public interface is nearly as complex as its
  body (thin wrapper/manager forwarding parameters unchanged). -> Collapse into
  caller or deepen the module to hide real policy/state.
* **Seam Leakage / Deep Internal Import:** Caller or test imports another
  package's internal subfolder/helper instead of its root entry point, or leaks
  storage/wire types across a domain seam. -> Route through the public entry
  point or narrow adapter.
* **Temporal / Hidden Coupling:** Caller must invoke `init()` -> `prepare()` ->
  `run()` in magic order without type enforcement. -> Combine into one deep
  entry point or encode states in types.

### Classic Code Smells (Fowler, *Refactoring* Ch. 3)
* **Mysterious Name:** Function, variable, or type hides what it represents or
  drifts from `GLOSSARY.md` terms. -> Rename to canonical domain noun/verb.
* **Duplicated Logic Shape:** Same branching/transformation shape repeated
  across hunks. -> Extract shared pure helper if genuinely one concept.
* **Feature Envy:** Function reaches repeatedly into another struct/module's
  fields more than its own. -> Move behavior onto the type owning the data.
* **Data Clumps:** The same 3+ parameters travel together across signatures. ->
  Bundle into a cohesive value struct/type.
* **Primitive Obsession:** Raw `string`, `int`, or `float` stands in for a
  constrained domain concept (money, IDs, units, states). -> Wrap in a domain
  type/newtype.
* **Repeated Switches:** Parallel `switch`/`if-else` cascades over the same
  discriminant in multiple places. -> Consolidate into one dispatch table or
  exhaustive match.
* **Shotgun Surgery / Divergent Change:** One small rule change scatters edits
  across many modules, or one file changes for unrelated reasons. -> Colocate
  what changes together; split orthogonal responsibilities.
* **Speculative Generality:** Hooks, generic type params, or flags added for
  hypothetical future needs outside the current task. -> Delete and inline.
