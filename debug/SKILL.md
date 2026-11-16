---
name: debug
description: >-
  Hypothesis-driven debugging, crash and heisenbug forensics, incident triage,
  and defect prevention by design across native, managed, distributed, and
  firmware systems. Use when a bug, crash, hang, flaky test, memory
  corruption, or production incident needs a root cause, a minimal reproducer,
  a git bisect, or a fix that also prevents sibling bugs.
last_updated: 2026-11-15
---

# Defect Prevention, Debuggable Design & Scientific Debugging (`debug`)

The fastest bug to fix is the one **made structurally impossible to write**; the
second-fastest is caught **at the exact moment state corrupts via an assertion**; the
third-fastest is **deterministically reproduced and bisected** rather than guessed at.

* Consult [references/prevention-and-debuggable-design.md](references/prevention-and-debuggable-design.md)
  for type-level state machines, parse-don't-validate boundary types, paired
  assertions & `check_rep()` verifiers, deterministic simulation (`Clock`/`Rng`
  injection), and ring-buffer flight recorders.
* Consult [references/forensics-and-heisenbugs.md](references/forensics-and-heisenbugs.md)
  for `git bisect run`, time-travel watchpoints (`rr` / `gdb`), race & memory
  heisenbugs (`ASan`/`TSan`/`Loom`), `NaN` hardware traps, MCU `CFSR` HardFault
  decoding, and 5-Whys postmortems.

*(When designing telemetry schemas or test-first slices, also activate any available
telemetry/observability and test-driven development skills.)*

---

## 1. Prevent Bugs by Construction (First Line of Defense)

Eliminate entire bug classes before runtime:

1. **Make Illegal States Unrepresentable:**
   * Replace loose tuples of booleans and nullable fields (`{is_loading, data, error}`
     has $2^3 = 8$ combinations, 5 invalid!) with **closed sum types / tagged unions /
     explicit state-machine enums** so invalid state combinations fail to compile.
   * Use **distinct domain newtypes / units** (`UserId` vs. `OrderId`, `Milliseconds`
     vs. `Microseconds`, `Cents` vs. `BasisPoints`) so argument-swap and unit-mismatch
     bugs become type errors.
2. **Parse, Don't Validate at Trust Boundaries:**
   * Validate untrusted inputs (JSON, CLI flags, env vars, wire frames, flash records)
     **once at the outer edge** and return a narrowed, immutable proof type
     (`NonEmptyUtf8Nfc`, `BoundedBatch<T, 100>`). Downstream core logic consumes the
     parsed type without redundant defensive checks or forgotten edge cases.
3. **Functional Core, Imperative Shell & Explicit Bounds (Power of 10 / TigerStyle):**
   * Express business rules, protocol state machines, and math as **pure functions**
     `(State, Event, Now) -> (NewState, Effects)` free of hidden I/O, globals, or
     ambient wall clocks.
   * **Bound everything explicitly:** Every loop, queue, cache, retry, recursion depth,
     and timeout carries an explicit upper bound; ban silent integer overflow.
4. **High-Density Paired Assertions & "Negative-Space" Invariants:**
   * Assert **both** expected preconditions/postconditions *and* states assumed
     impossible — ideally **paired across boundaries** (assert invariant before
     serializing/writing *and* assert again when reading back!).
   * **Never confuse invariants with operational errors:**
     * *Broken internal invariant* (corrupted tree/index, `debits != credits`, out-of-
       bounds state) $\rightarrow$ **Fail fast immediately** before persisting corrupt
       data! Never mask internal corruption with `if (ptr == NULL) return OK;`.
     * *Expected external fault* (bad user input, network timeout, full disk)
       $\rightarrow$ **Explicit typed error return** (never `assert()` on raw user data!).

---

## 2. Design Code So Debugging Is Effortless

When a bug *does* slip through, code structure determines whether root-causing takes
**3 minutes** or **3 days**:

1. **Inject All Nondeterminism (`Clock`, `Rng`, `IO`, `Scheduler`):**
   * Never call `SystemTime::now()`, `rand()`, or raw network sockets inside core logic.
     Pass explicit interfaces and **log the 64-bit PRNG `--seed`** on every test/fuzz/
     simulation run so multi-step async or distributed bugs replay **100%
     deterministically on one thread in milliseconds**!
2. **Write `check_rep()` Verifiers & Side-Effect-Free State Dumpers:**
   * Give non-trivial data structures, caches, and state machines a `check_rep(&self)`
     method asserting internal invariants (sorted order, parent/child symmetry, balance
     conservation) enabled in test/debug runs after every mutation.
   * Make internal state cleanly inspectable (`Debug` / `dump_state()` / `SIGUSR1`
     snapshot) with **zero mutating side effects inside getters or `toString()`**!
3. **Zero Silent Failure & Causal Error Wrapping:**
   * Ban empty `catch {}`, ignored `_ = err`, and sentinel magic returns (`-1`/`null`
     silently coerced to `0`). Wrap errors at each boundary with **what operation
     failed + key identifiers** (redacting secrets!).
4. **Linear, `grep`-able Control Flow & Flight Recorders:**
   * Prefer explicit dispatch over hidden import-time side effects, reflection magic,
     monkey-patching, or deep callback chains.
   * Keep a bounded in-memory **ring-buffer flight recorder** (or `.noinit` SRAM crash
     log on firmware) + **deterministic `Build-ID` detached debug symbols** so crashes
     always preserve the exact trailing sequence of events.

---

## 3. Live Production Incident? Mitigate First, Diagnose Second!

If users or hardware are actively impacted right now, **do not debug live on a burning
system**:

1. **Preserve Ephemeral Forensics (`< 60 s`):** Before killing the last wedged process,
   grab **one** non-destructive snapshot (coredump / goroutine-thread stack dump / heap
   profile / flight-recorder ring) so evidence isn't wiped.
2. **Stop the Bleeding (`< 5 min`):** Roll back to the last known-good `@sha256` digest
   (**paired with a release block/quarantine!**), flip the feature kill-switch, drain a
   poisoned shard/AZ, or shed overload.
3. **Root-Cause Offline:** Reproduce and fix calmly against captured inputs once SLIs
   recover.

---

## 4. The Scientific Debugging Loop (No Fixes Without Root Cause!)

**Iron Law:** Symptom patches (*"add a null check at the crash line"*, *"sleep 50ms"*,
*"bump retry count"*) are **bugs wearing a disguise**.

> **3-Strike Stop-the-Line Rule:** If **3 consecutive fix hypotheses** fail or spawn new
> failures, **STOP editing code immediately!** Your mental model of the system is wrong.
> Revert working-tree guesses, list every unverified assumption, and instrument ground
> truth from scratch.

1. **Reproduce Reliably (Lock the Oracle):**
   * Capture a deterministic 1-command reproducer (unit test, replay fixture, seeded
     fuzz input, or `rr record --chaos` trace for races). *If you haven't watched the
     reproducer fail reliably, you cannot prove any edit fixed it.*
2. **Minimize the Input (`Delta Debugging`):**
   * Binary-search away irrelevant input fields, config flags, threads, and steps until
     removing *any* remaining piece makes the bug vanish. Minimal inputs often expose
     the root cause on sight.
3. **Bisect in Time & Space (`O(log N)` Localization):**
   * **In Git history:** If it ever worked before, run `git bisect run ./repro.sh` —
     never eyeball `500` commits manually!
   * **Backward from Symptom -> Infection Origin:** A crash at frame `F` is merely
     where corrupt state was *read*. Place hardware watchpoints (`watch -l`), reverse-
     execute (`rr reverse-continue`), enable `FE_INVALID` traps (for `NaN`s!), or check
     midpoint assertions (`wolf-fence`) to pinpoint the exact line where state
     transitioned from **valid $\to$ infected**.
4. **Test One Falsifiable Hypothesis at a Time (`Predict -> Probe -> Compare -> Note`):**
   * **Predict sharply before every probe:** Write down *"I predict variable `X == V` (or counter `C` drops to `0`) at boundary `B` because..."* — never run an unpredicted *"let's see what changes"* probe. A specific miss (`✗`) refutes a bad mental model in one step.
   * **Keep a one-page crash-recovery ledger (`Verified [cite cmd/trace]`, `Assumed / Open`, `Next probe`):** Update the ledger *immediately* after any refuted prediction before running the next command so context loss never repeats dead ends. When crossing environments (local $\to$ prod, unminified $\to$ release, workload A $\to$ B), **demote earlier `Verified` claims to `Assumed`** until one test re-verifies them on the new target.
   * **Escalate to an executable reference model when prose resists:** After repeated misses on a subtle state machine, protocol, or concurrency interleaving, write a small plain reference script (`model.py`) encoding *only* verified transitions (marking unverified edges explicitly as `Unknown("why")`) and replay it against the full recorded event/trace history so gaps surface honestly instead of guessing another patch.
5. **Fix the Root, Sweep Siblings & Upgrade Structural Prevention:**
   * Turn the minimal reproducer into an automated failing test **first**, then fix the
     root cause at the **infection origin** (not the downstream crash site!).
   * **Sweep for sibling bugs:** Search the codebase (`grep` / AST) for the exact same
     flawed pattern in parallel handlers, parsers, or callers!
   * **Upgrade Horizon 1:** Ask *"How do we make this entire bug class uncompilable or
     instantly caught next time?"* (tighter type, boundary parser, `check_rep()`
     assertion, sanitizer gate, or linter check).

---

## Before You Finish (`debug` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Adding `if (x == null) return` at crash line without knowing why `x` became `null` | Trace backward to where `x` was constructed/mutated; fix the infection source |
| 4th speculative "maybe this fixes it" edit in a row | **Stop-the-Line (3-Strike Rule):** revert guesses, verify raw state, bisect |
| Boolean soup (`isPending && !isCancelled && retryCount > 0`) has impossible states | Replace with a single explicit `State` enum / tagged union |
| `NaN` or memory corruption discovered 10,000 iterations after it happened | Trap at origin (`feenableexcept(FE_INVALID)`, `ASan`/`UBSan`, `check_rep()`, watchpoint) |
| Intermittent race "fixed" by adding `sleep(100ms)` | Reproduce under `TSan` / `-race` / `rr --chaos` / deterministic scheduler seed; fix synchronization |
| Fixing one bug instance without checking neighboring files | Grep/AST-scan for sibling occurrences + add regression test & structural guardrail |
