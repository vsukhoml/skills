# Migration Topologies, Module Deepening & AST Codemods (`refactoring`)

---

## 1. Deepen Modules — Do Not Fragment Into Pass-Through Soup!

A classic refactoring mistake (common in both human and LLM edits) is splitting a
300-line function into twelve 25-line helpers that pass the same 8 arguments to each
other ("classitis" / shallow wrappers). Follow Ousterhout's **Module Depth** principle:

$$\text{Module Value} = \frac{\text{Complexity Hidden Inside}}{\text{Width \& Cognitive Cost of Public Interface}}$$

* **Good structural moves:**
  * **Hoist I/O out to an Imperative Shell ("Sandwich Pattern"):**
    1. Shell reads inputs/state via I/O $\rightarrow$
    2. **Pure Core** computes `(Input, CurrentState) -> (Decision, StateDelta, Commands)`
       with zero mocks needed $\rightarrow$
    3. Shell commits `StateDelta` and executes `Commands`.
  * **Inline shallow pass-through wrappers** that add zero abstraction and merely rename
    parameters across layers.
  * **Consolidate scattered state mutations** into one type owning its own invariants
    (shrinking `pub` fields to module-private).

---

## 2. The Mikado Method (Refactoring Tangled Code Without Breaking `main`)

Whenever attempting a structural change triggers a cascade of compiler/test errors across
dozens of files, **stop digging in a red working tree** and run the Mikado loop:

```text
[Goal: Split BillingContext from GlobalAppState]  (Attempted -> 19 compile errors -> REVERT!)
   ├──► [Prereq A: Pass TaxRates explicitly to InvoiceCalc] (Attempted -> 2 errors -> REVERT!)
   │       └──► [Leaf A1: Load TaxRates once in StartupConfig]  <-- 0 errors! COMMIT #1 (GREEN!)
   └──► [Leaf B: Replace GlobalAppState.clock() with Clock param] <-- 0 errors! COMMIT #2 (GREEN!)
```

1. **Set the Mikado Goal** and try the naive edit (`5–10 min` timebox).
2. **Record every compiler/test failure** as child prerequisite nodes on your scratch
   graph.
3. **`git restore .` immediately!** Never debug inside a half-broken cascade.
4. **Execute Leaf Nodes first:** Each leaf compiles cleanly, passes 100% of boundary
   characterization tests, and lands as a tiny, reviewable `[refactor]` commit.
5. Repeat up the tree until the root goal lands in a 20-line green diff!

---

## 3. Branch by Abstraction, Strangler Fig & Live Shadow Diffing

For high-risk production components (storage backends, auth/permission engines, pricing
calculators, protocol routers) where offline tests alone cannot cover 100% of live
traffic diversity:

```text
Caller ──► [Boundary Interface / Router]
                ├──► 1. Legacy Impl (Authoritative response returned to caller)
                └──► 2. Candidate Impl (Async/bounded shadow run, isolated side-effects!)
                            │
                            ▼
                     [Diff Comparator] ──► Emits mismatch counter + sampled redacted diff
```

1. **Step 1 — Introduce the Boundary Interface:** Route all callers through a single
   interface backed 100% by `LegacyImpl` (`[refactor]` commit #1).
2. **Step 2 — Build `CandidateImpl` Behind the Seam:** Verify offline with unit +
   differential fuzz/property tests against `LegacyImpl`.
3. **Step 3 — Shadow / Dual-Read Verification (`Scientist` Pattern):**
   * Run `CandidateImpl` on sampled (`1% -> 100%`) live read/compute requests **under a
     strict timeout + panic recovery guard** so a bug or latency spike in `CandidateImpl`
     can *never* break or slow down the caller!
   * Ensure `CandidateImpl` in shadow mode **never double-writes external side effects**
     (compare intended write commands in memory rather than firing duplicate emails/charges!).
   * Fix discrepancies until live mismatch rate hits **`0.000%`** over full business
     cycles.
4. **Step 4 — Progressive Cutover & Complete Deletion:**
   * Flip authoritative return to `CandidateImpl` across rings (`1% -> 10% -> 100%`)
     with an instant runtime kill-switch back to `LegacyImpl`.
   * Once baked, **delete `LegacyImpl`, the shadow comparator, and the toggle** in a
     final cleanup commit so zero lava-layer debt remains!

---

## 4. Syntax-Aware AST Codemods (Scale Without Typos)

When changing function signatures, error wrappers, import paths, or struct layouts across
dozens or hundreds of files, **write a deterministic AST transformation**:

| Ecosystem | Structural / AST Codemod Tools |
| --- | --- |
| **Polyglot (20+ langs)** | `ast-grep` (`sg run -p '$OBJ.old($A, $B)' -r '$OBJ.new($B, $A)'`), `comby` |
| **Rust** | `cargo fix`, `rust-analyzer` Structural Search Replace (`SSR`), `syn`/`quote` |
| **Go** | `gofmt -r 'old(a, b) -> new(b, a)' -w .`, `gopls` rename, `golang.org/x/tools/go/analysis` |
| **Python** | `LibCST` & `libcst.codemod` (preserves comments & formatting!), `ruff --fix` |
| **Kotlin / JVM** | `OpenRewrite` recipes, Kotlin `@Deprecated(..., ReplaceWith(...))` + compiler/IDE migration, `ast-grep --lang kotlin` |
| **C / C++** | `clang-tidy` / Clang `LibTooling` (`ASTMatchers` + `Transformer`), `coccinelle` (`spatch` for C/kernel!) |
| **TypeScript / JS** | `jscodeshift`, `ts-morph`, `ast-grep` |

* **Codemod workflow:** Run the AST tool on a clean worktree $\rightarrow$ inspect a
  sample `git diff` to verify comments/formatting survived $\rightarrow$ run full build +
  boundary characterization tests $\rightarrow$ land the mechanical codemod in its **own
  isolated commit** (never hand-edit 3 files inside a 90-file mechanical codemod commit!).
