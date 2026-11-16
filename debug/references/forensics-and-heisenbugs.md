# Forensics, Bisection & Heisenbug Playbook (`debug`)

---

## 1. Automated Binary Search in Git (`git bisect run`)

Whenever a behavior worked at *any* known past commit `GOOD` and fails at `BAD`, **never
read commit logs guessing** — `git bisect` isolates 1 culprit in `1,000` commits in `10`
automated runs:

```bash
git bisect start BAD_REF GOOD_REF
git bisect run bash -c '
  # Exit 125 tells git bisect to SKIP commits that fail to compile for unrelated reasons!
  cargo build --quiet --test repro_test || exit 125
  # Exit 0 = good, Exit 1..124 = bad (bug reproduced!)
  cargo test --quiet --test repro_test exact_case_name
'
git bisect reset
```

* **Flaky reproducer in bisect?** Wrap the test in a loop (`for i in {1..20}; do
  ./repro && continue || exit 1; done; exit 0`) so a `25%` race fails with probability
  $1 - 0.75^{20} = 99.7\%$ on bad commits while passing `20/20` on good commits!

---

## 2. Tracing Backward from Corruption to Origin (Time-Travel & Watchpoints)

A segfault or panic tells you **who tripped over the tripwire**, not **who planted it**:

1. **Linux Time-Travel Debugging (`rr`) — Turns Heisenbugs into Deterministic Tape:**
   ```bash
   # Record with randomized scheduler quantum (--chaos exposes thread races 10x faster!):
   rr record --chaos ./my_test_binary
   rr replay
   # Inside gdb under rr:
   (gdb) continue                 # Run forward until crash / assertion failure!
   (gdb) print &corrupted_struct->state
   (gdb) watch -l corrupted_struct->state   # Set hardware write watchpoint on exact address
   (gdb) reverse-continue         # Run TIME BACKWARD to the exact instruction that wrote the bad bytes!
   ```
2. **Standard `gdb` / `lldb` Post-Mortem Coredump Triage:**
   ```bash
   coredumpctl info               # Locate recent crash + Build-ID
   coredumpctl debug              # Or: gdb ./binary /var/lib/systemd/coredump/core...
   (gdb) thread apply all bt full # Full locals across ALL threads (essential for deadlocks/races!)
   ```

---

## 3. Taming Specific "Impossible" Bug Classes (Heisenbugs)

| Symptom Class | Why Printf Debugging Fails | Definitive Instrument & Trap |
| --- | --- | --- |
| **Data Race / Torn State** | `printf` adds a lock + syscall barrier, making the race vanish! | Compile with **`TSan`** (`-fsanitize=thread`), Go **`-race`**, JVM **`jcstress`** / Kotlin **`-Dkotlinx.coroutines.debug`**, or permutation model-checker (`Loom` / `shuttle`); record under `rr record --chaos`; on single-threaded Node/V8, audit shared mutable state mutated across `await` suspension points |
| **Use-After-Free / Buffer Overrun / UB** | Corrupts unrelated heap neighbor `50 ms` later | Compile with **`ASan + UBSan`** (`-fsanitize=address,undefined -fno-omit-frame-pointer`), `Valgrind`, or page-guard allocator (`efence` / GWP-ASan) |
| **Silent `NaN` / `Inf` Poisoning** | `NaN` propagates silently through 10,000 math ops and compares `false` everywhere! | On glibc/x86, `#define _GNU_SOURCE` + `feenableexcept(FE_INVALID \| FE_DIVBYZERO \| FE_OVERFLOW)` (or `_MM_SET_EXCEPTION_MASK`) fires `SIGFPE` on the exact instruction creating `NaN`; **on ARM64, hardware FP trap-enable bits are typically `RAZ/WI`** — use `-fsanitize=float-divide-by-zero` or explicit `isnan()` assertions in `check_rep()`! |
| **Deadlock / Hung Process** | Process sits at `0%` CPU forever | Send `SIGQUIT` (Go), `jcmd <pid> Thread.print` (JVM/Kotlin; Android `/data/anr/` traces on `> 5 s` main-thread stalls), `node --report-on-signal` / `--inspect` (Node/V8), or `gdb -batch -ex "thread apply all bt" -p <pid>`; look for cycles in lock/await order |
| **Memory Leak / Unbounded Growth** | RSS climbs over 48 hours until OOM-killer strikes | Diff heap snapshots across time: `pprof --base=t0.pb t1.pb`, `heaptrack`, `memray`, `jeprof`, JVM `jcmd <pid> GC.heap_dump` in Eclipse `MAT` / Android `LeakCanary`, or Node/V8 `v8.writeHeapSnapshot()` **3-snapshot diff** (objects allocated between `S1` and `S2` that survive in `S3`) |
| **Compiler Optimization Bug? (99.9% = UB!)** | *"Works at `-O0`, breaks at `-O2`!"* | Almost always **Undefined Behavior** in your code (uninitialized local, signed overflow, strict-aliasing violation, missing `volatile` on MMIO, data race). Check `-Wall -Wextra -Werror` + `ASan + UBSan` + `-fno-strict-aliasing` *before* suspecting the compiler! |
| **ARM Cortex-M HardFault / BusFault** | MCU resets or spins in `HardFault_Handler` | Inspect stacked exception frame (`R0..R3, R12, LR, PC, xPSR` via `MSP`/`PSP`) + **`SCB->CFSR`** (`UFSR` div-by-zero/unaligned, `BFSR` + **`SCB->BFAR`** exact faulting bus address, `MMFSR` + `MMFAR`), then run `addr2line -f -i -e firmware.elf <PC>` |

---

## 4. Blameless 5-Whys $\to$ Structural Prevention Template

Never stop at *"fixed line 142"* or *"human error"*. Close every high-severity bug or
incident with three permanent artifacts:

1. **Minimal Automated Regression Test:** Proves the exact failure mode is permanently
   extinct (and verified to **fail** when the fix is stashed).
2. **Sibling-Bug Sweep:** Grep / AST query across the entire repo for every parallel
   occurrence of the same mistake (e.g., all other callers forgetting timezone `UTC`,
   unchecked integer cast, or missing `idempotency_key`).
3. **5-Whys Structural Upgrade (Pick `>= 1`):**
   * *Why did the bug happen?* $\rightarrow$ Direct mechanical root cause.
   * *Why did it compile?* $\rightarrow$ Can a sum type, newtype, or `#[must_use]` make
     it uncompilable?
   * *Why did unit/integration tests miss it?* $\rightarrow$ Add property/fuzz/DST seed
     coverage or `check_rep()` invariant.
   * *Why did rollout reach users?* $\rightarrow$ Tighten canary SLI, schema check, or
     atomic rollback-and-quarantine gate.
