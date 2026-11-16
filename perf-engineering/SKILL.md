---
name: perf-engineering
description: >-
  Systems performance engineering: profiling (CPU, off-CPU, allocation, lock,
  and PMU flamegraphs), statistically rigorous benchmarks and load tests, and
  ordered optimization from algorithm to memory layout to SIMD, across native
  code, managed runtimes, databases, distributed services, and firmware. Use
  when code is slow, a latency or throughput target is missed, a benchmark or
  load test is needed, or an optimization or performance claim needs proof.
last_updated: 2026-11-15
---

# Systems Performance, Profiling & Rigorous Benchmarking (`perf-engineering`)

Never guess where time goes, never trust a single timing sample, and never trade
away correctness, numerical accuracy, or maintainability for an unmeasured speedup.

* Consult [references/benchmarking-and-profiling.md](references/benchmarking-and-profiling.md)
  for physical latency ratios, Roofline & Universal Scalability Law equations,
  paired `ABBA` anti-bias harnesses, open-loop load testing (avoiding Coordinated
  Omission), and per-language profiler/assembly commands (through MCU `DWT->CYCCNT`).
* Consult [references/optimization-moves.md](references/optimization-moves.md)
  for concrete data-layout, allocation, fast-path, concurrency, flat-profile, and
  Top-Down microarchitectural (`TMAM`) optimization patterns plus CI counter gates.

*(For frame-budget UI virtualization and `60/120 Hz` rendering pipelines, also
activate any available UI responsiveness and large-data rendering skill; for SQL
indexing and storage engines, activate any available data modeling skill.)*

---

## 1. Frame the Problem & Compute Speed-of-Light Bounds First

Before writing a benchmark or touching code, answer five questions in 10 minutes:

1. **Challenge the Premise & Check the Null Alternative:**
   * *"Make X faster"* is a proposed solution, not a problem. State **one measurable
     user/system outcome** with units, input distribution (`cold` vs. `warm`, typical
     vs. adversarial tail), and target hardware.
   * Compare against cheaper **null alternatives**: *do nothing*, *change the caller*
     (batch, cache, move off critical path), *adopt an existing library/index*, or
     *right-size hardware*.
2. **Amdahl's Ceiling & Speed-of-Light Arithmetic:**
   * If target $X$ is `18%` of end-to-end time, even an infinite speedup caps total
     gain at $\frac{1}{1 - 0.18} = 1.22\times$! Measure end-to-end share *before*
     optimizing a leaf.
   * **Back-of-the-envelope bound:** Count irreducible operations $\times$ physical
     unit costs (`L1 ~0.5 ns`, `L2 ~3 ns`, `branch mispredict ~5 ns`, `uncontended
     mutex ~15 ns`, `DRAM ~50 ns`, `1 MB seq RAM ~15–60 µs`, `4 KB NVMe ~20 µs`,
     `datacenter RTT ~50–200 µs`). This immediately names the dominant term (e.g.,
     memory bandwidth vs. branch mispredicts vs. syscall/RPC round-trips).
3. **Pre-Register Equivalence Policy & Guardrails:**
   * **Numeric equivalence:** Explicitly lock **Bit-identical** (financial math,
     crypto, deterministic state — forbids `-ffast-math`, FMA changes, and reordered
     FP reductions), **Tight tolerance band** (checked at full scale on ill-conditioned,
     denormal, and near-cancellation inputs), or **Valid-by-invariant** (exact checker).
   * **Guardrails:** Zero correctness regressions (run with `ASan+UBSan` / `TSan` /
     `-race` — *a data race is fast until it crashes!*); no scenario regresses beyond
     its noise floor (`<= 3%`); cap peak-RAM and binary-size growth (`<= 5%`).

---

## 2. Profile the Right Dimension (Never Just On-CPU Time!)

High latency with low CPU utilization is invisible in an on-CPU flame graph. Match the
instrument to the physical bottleneck:

1. **System Saturation & Scalability (`USE` + Universal Scalability Law):**
   * Check **Utilization, Saturation (run-queue / wait-queue depth), and Errors** for
     CPU, RAM, storage, and network.
   * When throughput plateaus or *drops* as threads/workers $N$ grow, model Gunther's
     **Universal Scalability Law** $C(N) = \frac{N}{1 + \alpha(N-1) + \beta N(N-1)}$:
     $\alpha$ is contention/serialization (lock wait); $\beta > 0$ is **coherency
     crosstalk** (cache-line ping-pong / false sharing / lock convoying) causing
     retrograde collapse!
2. **Select Complementary Profilers:**
   * **On-CPU Flame Graphs** (`perf`, `samply`, `pprof`, `py-spy`, `async-profiler`)
     $\rightarrow$ horizontal frame width = CPU share (not call order!).
   * **Off-CPU / Lock / Block Profiles** (`offcputime`, `pprof` `mutex`/`block`,
     scheduler/futex eBPF traces) $\rightarrow$ reveals I/O waits, lock contention,
     connection-pool starvation, and sleep stalls.
   * **Allocation & Cache/Coherency Profiles** (`heaptrack`, `memray`, `pprof
     -alloc_space`, `perf c2c`) $\rightarrow$ exposes allocator churn, GC pressure,
     LLC misses, and false sharing.
   * **Disassembly + Static/Hardware Microarchitecture** (`objdump -d` / `cargo asm`,
     `llvm-mca` / `uiCA`, `perf stat --topdown`) $\rightarrow$ classifies hot loops
     into **Retiring vs. Bad Speculation vs. Front-End Bound vs. Back-End (Memory vs.
     Core) Bound** in minutes instead of guessing across dozens of blind edits.
   * **Causal Profiling** (`coz` / virtual-speedup experiments) $\rightarrow$ in
     async/pipelined systems, confirms speeding up stage $A$ actually moves end-to-end
     throughput rather than merely increasing stage $A$'s idle wait on stage $B$.
3. **When the Profile Is Flat ("No Single Hotspot"):**
   * **Blame the application caller, not shared leaves** (`memcpy`, `malloc`, `hash`):
     re-attribute leaf cost 2–3 frames up the call stack where redundant copies or
     missing `reserve()` calls originate; profile **allocations and LLC misses**; and
     tighten harness variance so compounding `1–2%` wins resolve cleanly.

---

## 3. Build Statistically Rigorous, Anti-Gaming Benchmarks

Code layout shifts from environment-variable byte length or link order alone can swing
loop timings by `5–10%` — enough to reverse `-O3` vs. `-O2`! Build harnesses that
cannot fool you or be gamed by an automated edit:

1. **Defeat Compiler & Runtime Illusions:**
   * **Consume outputs & assert correctness inside the harness:** Feed outputs to
     `DoNotOptimize` / `black_box` **and assert a non-trivial checksum or domain
     invariant** so an edit that silently drops work never registers as a `100x` win!
   * **Separate warm-up from measurement**, declare `cold` vs. `warm` explicitly, use
     **fresh processes** across candidates when module/allocator caches persist, and
     **never edit the benchmark, test inputs, or tolerance guards** alongside the code!
2. **Crush Variance via Paired Interleaved `ABBA` Runs:**
   * Time baseline `A` and candidate `B` back-to-back in randomized/alternating `ABBA`
     order across two clean worktrees on a quiet machine (`performance` CPU governor,
     pinned core, **zero concurrent builds or subagent test runs during timing!**).
   * Report **medians + spread (`IQR`/`MAD`, `p95`, `p99`)** over `>= 10–30` repeats
     and require statistical significance (`benchstat`, Mann-Whitney U, bootstrap CI)
     exceeding the measured **unchanged-code noise floor**.
3. **Suite Vectors + Held-Out Inputs (Prevent Benchmark Overfitting):**
   * Emit **per-case scores** alongside any suite aggregate (`+8%` mean that is `3x`
     slower on adversarial inputs is a regression!), and re-verify winners once on an
     untouched **holdout input set**.
4. **Open-Loop Load Testing (Defeat Coordinated Omission!):**
   * Closed-loop load generators that wait for response $i$ before sending request
     $i+1$ politely pause whenever the server stalls, hiding `10x` tail-latency spikes!
     Always test services with **open-loop constant-arrival-rate** schedules (`k6`
     `constant-arrival-rate`, `vegeta`, HDR Histogram) up to `70–85%` capacity knee.

---

## 4. Where the Wins Live (Attack strictly in this order!)

1. **Algorithmic Class & Boundary Batching:** $O(N^2) \to O(N \log N) \to O(N) \to O(1)$;
   replace $N+1$ queries/RPCs/syscalls with 1 bulk pass; precompute invariants at
   ingestion boundaries.
2. **Memory Representation & Locality:** Shrink structs (reorder fields to eliminate
   padding, narrow integer/enum widths, `32-bit` array indices over `64-bit` pointers);
   split `hot` fields from `cold` fields; replace pointer-chasing trees/maps/sets with
   contiguous vectors, open-addressed tables, or **bitvectors**; choose `SoA` over
   `AoS` for streaming scans; pad contended cross-thread counters to cache lines (`64 B`
   / `128 B`) to stop false sharing.
3. **Allocation Elimination:** `reserve()` known capacities; hoist and reuse scratch
   buffers across iterations (with a high-water reset cap); use bump/arena allocators
   for request-scoped lifetimes; pass `span`/`string_view`/slices instead of cloning.
4. **Work Avoidance:** **Fast path for the dominant simple case** (e.g., ASCII fast
   path before full UTF-8/regex fallback — testing *both* paths!); defer lazy metrics/
   formatting behind reads; keep disabled log formatting off hot loops.
5. **Compiler & Microarchitectural Mechanics (Last — Disassembly Open!):** Outline
   cold error paths (`[[unlikely]]` / `#[cold]`) so hot functions inline frame-free;
   copy aliased struct fields to locals before tight loops; replace unpredictable
   data-dependent branches (`~5 ns`/miss) with branchless masks/tables; apply SIMD
   verified across build flags and CPU baselines.

---

## 5. Disciplined Hypothesis Loop & Regression Locking

1. **One Hypothesis = One Commit + Scoreboard Row:** State expected effect and
   falsifier before editing; record timing distribution **plus secondary physical
   counters** (instructions, `allocs/op`, LLC/branch misses, binary bytes).
2. **Revert & Log Losers:** Revert any change that stays inside noise, regresses a
   guard metric, or buys `< 2%` at steep readability cost — **and log rejected ideas
   with measured evidence** so nobody re-tries the same dead end.
3. **Re-Verify on Final Branch Commit & Lock with Deterministic Counters:** Later
   commits can undo earlier inlining/layout wins; re-run all headline scenarios on the
   final commit and add **non-flaky deterministic regression gates** (`allocs/op == 0`,
   SQL query count `<= K`, instruction/cycle count via `Cachegrind` / `llvm-mca`, or
   ELF symbol size) — never brittle `assert elapsed < 10ms` sleeps in shared CI!

---

## Before You Finish (`perf-engineering` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Optimizing a function before checking its end-to-end Amdahl share | Profile end-to-end first; compute ceiling $\frac{1}{1 - p}$ and speed-of-light bound |
| Claiming `"12% faster"` from two single runs while builds ran in background | Quiet machine, run paired `ABBA` (`>= 10–30` repeats), verify significance via `benchstat`/U-test |
| Benchmark returns in `0.3 ns` because compiler DCE'd the unused loop | Pass result to `black_box`/`DoNotOptimize` **and** assert a non-trivial checksum |
| Endpoint has `800 ms p99` at `8%` CPU, yet engineer stares at on-CPU flame graph | Capture **off-CPU / lock / block / tracing** profiles to see I/O, mutex, or pool waits |
| Closed-loop `wrk` load test reports `12 ms p99` during `2 s` GC freezes | Switch to **open-loop constant-arrival-rate** load generation to avoid Coordinated Omission |
| CI test `assert time.time() - t0 < 0.05` flakes every day on noisy runners | Gate CI on deterministic proxies (`allocs == 0`, query count, instruction count) + dedicated perf bench |
