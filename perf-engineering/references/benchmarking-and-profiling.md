# Benchmarking, Profiling & Scalability Reference (`perf-engineering`)

---

## 1. Physical Unit-Cost Ratios & Analytical Bounds

Use order-of-magnitude hardware ratios to build a **Speed-of-Light Model** before
writing code (exact nanoseconds vary per CPU generation; the **ratios** govern design):

| Operation | Typical Latency / Throughput | Ratio vs. L1 Hit |
| --- | --- | --- |
| 1 CPU cycle (`3–4 GHz`, `4–6` wide superscalar) | `~0.25–0.33 ns` | `0.5x` |
| L1 data cache hit (`32–64 KB`) | `~0.5–1 ns` | `1x` |
| L2 cache hit (`512 KB–2 MB`) | `~3–4 ns` | `~6x` |
| Branch misprediction pipeline flush | `~5 ns` (`15–20` cycles) | `~10x` |
| L3 / LLC hit (`16–128 MB`, shared) | `~10–15 ns` | `~25x` |
| Uncontended CAS / mutex lock + unlock | `~15 ns` | `~30x` |
| Cross-core contended cache line (`perf c2c` HITM) | `~40–80 ns` | `~100x` |
| Main DRAM random access (pointer chase / LLC miss) | `~50–90 ns` | `~120x` |
| Linux syscall (`getpid` / minimal `read` boundary) | `~60–150 ns` | `~200x` |
| Sequential `1 MB` read from DRAM (`~25–80 GB/s`/core) | `~15–60 µs` | `~50,000x` |
| NVMe SSD `4 KB` random read (`io_uring` vs sync) | `~15–60 µs` | `~60,000x` |
| Same-AZ datacenter TCP/RPC round trip | `~50–250 µs` | `~250,000x` |
| Cross-continent WAN round trip | `~80–150 ms` | `~200,000,000x` |

### Analytical Laws Worth Checking First

1. **Amdahl's Ceiling:** Speeding up fraction $p$ of execution by factor $S$ bounds
   overall speedup to:
   $$S_{\text{total}} = \frac{1}{(1 - p) + \frac{p}{S}} \le \frac{1}{1 - p}$$
2. **Little's Law (Concurrency Sizing):** $L = \lambda \cdot W$ (mean in-flight items
   $L$ = arrival rate $\lambda \times$ mean latency $W$). If a DB call takes $W = 10\text{ ms}$
   and you need $\lambda = 5,000\text{ req/s}$, a connection pool of size $L < 50$ is
   **mathematically guaranteed to queue** regardless of CPU speed!
3. **Roofline Arithmetic Intensity:** $I = \frac{\text{Operations}}{\text{DRAM Bytes Transferred}}$.
   If $I < I_{\text{ridge}}$ (typically `4–12 FLOPs/byte`), the kernel is **memory-bandwidth
   bound**: adding SIMD instructions without shrinking bytes read/written (`SoA`, loop
   fusion, cache tiling, narrower types) yields **zero** speedup!
4. **Gunther's Universal Scalability Law (USL):**
   $$C(N) = \frac{N}{1 + \alpha(N - 1) + \beta N(N - 1)}$$
   Fit $(N, C(N))$ at $N = 1, 2, 4, 8, 16, 32$ threads: $\alpha$ quantifies lock/queue
   serialization; any $\beta > 0$ reveals **coherency thrash / false sharing** that makes
   throughput peak at $N_{\max} = \lfloor\sqrt{(1 - \alpha)/\beta}\rfloor$ and degrade above it!

---

## 2. Anti-Gaming & Bias-Resistant Benchmark Harness Design

### A. Defeating Layout Bias (`ABBA` Paired Interleaving)

Binary link order and even `char **environ` byte size shift stack/instruction cache-line
alignment by `5–10%` (Mytkowicz et al., *"Producing Wrong Data Without Doing Anything
Obviously Wrong"*).

1. **Paired same-machine `ABBA` interleaving:** Keep baseline (`worktree-base`) and
   candidate (`worktree-cand`) built with **identical compiler + flags** (especially FP
   flags!). Alternate execution `A, B, B, A, A, B, B, A ...` (`>= 10–30` pairs) so
   thermal drift and background jitter affect both arms symmetrically, and evaluate the
   paired ratio / Mann-Whitney U (`benchstat`).
2. **Suspect layout luck?** Vary function alignment (`-falign-functions=64`, Rust
   `-Z randomize-layout` / linker order) or inspect `objdump -d` + `perf stat -e
   cycles,instructions,branches,branch-misses,L1-dcache-load-misses,LLC-load-misses`. If
   instruction count and cache misses did *not* drop while wall time dropped `4%`, you
   measured code-alignment luck, not an algorithmic improvement!

### B. Six Non-Negotiable Anti-Gaming Evaluator Rules

When running human or AI-driven optimization loops:
1. **Assert a non-trivial checksum / domain invariant on every timed run** (outside the
   inner timed region if expensive, or accumulate a cheap XOR/hash into `black_box`).
2. **Lock benchmark inputs, harness scripts, and tolerance checks read-only** — an
   automated optimizer allowed to edit its own test suite or widen an `epsilon` clamp
   will "optimize" by shrinking the suite or loosening accuracy!
3. **Emit per-case vectors alongside suite aggregates** so a `3x` regression on skewed
   or adversarial inputs cannot hide inside a `+10%` geometric mean.
4. **Separate `inputs/` (tuning) from `holdout/` (final verification)** — verify the
   winning commit once on `holdout/` to catch overfitting to fixed benchmark sizes.
5. **Distinguish `infra_failed` from candidate failure:** If an external OOM or noisy
   host killed a run, mark it `untested` and re-run rather than recording a valid idea
   as a refuted dead end.
6. **Fresh process per candidate** whenever language runtimes cache imported modules,
   JIT tiers, or allocator arenas across runs.

---

## 3. Per-Substrate Profiling, Benchmarking & Assembly Matrix

| Substrate | Microbenchmark & Stats | On-CPU / Off-CPU / Memory Profilers | Disassembly / Microarch / Safety Gates |
| --- | --- | --- | --- |
| **C / C++** | Google Benchmark (`DoNotOptimize`, `ClobberMemory`) + `ministat` / `hyperfine` | `perf stat --topdown`, `perf record -g` (frame pointers `-fno-omit-frame-pointer` or `--call-graph dwarf`), `offcputime-bpfcc`, `heaptrack`, `perf c2c` | `objdump -d -M intel -S`, `llvm-mca`, `ASan + UBSan` + `TSan` |
| **Rust** | `criterion` / `divan` (`std::hint::black_box`) | `samply`, `cargo flamegraph`, `dhat-rs` (exact heap alloc counts!), `perf stat` | `cargo asm --rust`, `llvm-mca`, `cargo test` + `miri` (on `unsafe` winners) |
| **Go** | `go test -bench=. -benchmem -count=15` $\rightarrow$ **`benchstat old.txt new.txt`** | `pprof` (`cpu`, `alloc_space`, `inuse_space`, `mutex`, `block`, `trace` via `go tool trace`) | `go build -gcflags="-m=2"` (escape/inline), `go tool objdump -s`, `go test -race` |
| **Python** | `pytest-benchmark` / `pyperf` (`python -m pyperf system tune`) | `py-spy record --gil --subprocesses`, `scalene` (CPU + GPU + RAM + copy volume), `memray` | `dis.dis()`, watch C-extension vs pure-Python boundary crossings & import-time work |
| **JVM / Kotlin** | **JMH** (`Blackhole.consume`, `@Fork(3)`, `@State`) — *never hand-roll `System.nanoTime()` loops on JVM!* | `async-profiler` (`-e cpu`, `-e alloc`, `-e lock`, `-e wall`), JDK Flight Recorder (`JFR`) | `-XX:+PrintCompilation`, `-XX:+PrintInlining`, JMH `-prof gc` / `-prof perfasm` |
| **Android / ART** | `androidx.benchmark` (`BenchmarkRule` / `MacrobenchmarkRule` on R8-minified physical hardware, never debuggable!) | **Perfetto** system trace (CPU scheduling, Binder, Compose/RenderThread frames) + NDK `simpleperf` (`stat`/`record`) | R8 full-mode + **Baseline Profiles** (`dex2oat` AOT verification), `oatdump` disassembly |
| **JS / TS (Node/V8)** | `mitata` / `tinybench` (with explicit warmup & blackhole sink) | `node --prof` / `0x` / Chrome DevTools CPU & Heap Allocation Timeline | `--trace-opt --trace-deopt` (catch polymorphic hidden-class megamorphic deopts!) |
| **SQL / Storage** | Parameterized workload replay (`pgbench`, realistic data cardinality & skew!) | `EXPLAIN (ANALYZE, BUFFERS, WAL)`, `pg_stat_statements`, `iostat -xz 1`, `biolatency-bpfcc` | Verify `shared hit` vs `read` blocks, sort/hash `temp written` spills, lock waits |
| **MCU / Firmware** | Cycle-accurate hardware counter: ARM Cortex-M `DWT->CYCCNT` (`0`-jitter cycle delta!) + GPIO logic-analyzer pulse | PC-sampling via SWO/ETM trace (`orbuculum`), linker map (`-Wl,-Map=out.map`), stack high-water painting | `arm-none-eabi-objdump -d -S`, `size -A` / `bloaty` (Flash `.text`/`.rodata` vs SRAM `.bss`/`.data`), XIP flash wait-state stalls |

### ARM Cortex-M Cycle-Exact Microbenchmark Snippet (`0` OS Jitter)

```c
// Enable once at bench init:
CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
DWT->CYCCNT = 0;
DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;

// Measure exact clock cycles of critical ISR/DSP kernel (with interrupts masked ONLY during isolated micro-kernel test):
uint32_t irq_state = __get_PRIMASK();
__disable_irq();
uint32_t start = DWT->CYCCNT;
uint32_t acc = run_filter_kernel(input_buf, len);
uint32_t cycles = DWT->CYCCNT - start;
__set_PRIMASK(irq_state);
sink_volatile = acc; // Prevent DCE + assert expected output checksum!
```

---

## 4. Load Testing Services Without "Coordinated Omission"

* **The Coordinated Omission Bug:** Suppose a `60 s` run hits a service that freezes in a
  `1.0 s` lock/GC stall for `1 s` (and drains post-freeze backlog at `1,000 req/s`).
  * A **closed-loop** generator (`10` worker threads with a `20 ms` normal round-trip
    cycle = `500 req/s` by Little's Law) completes `29,500` fast `20 ms` requests over
    `59 s` and **only `10` stalled requests** during the `1.0 s` freeze (all `10` threads
    sit blocked!). Since `10 / 29,510 = 0.034%`, **`p99` is still reported as `20 ms`**
    — completely hiding a full 1-second outage!
  * An **open-loop** generator firing on an independent `500 req/s` arrival clock
    (`30,000` requests over `60 s`) queues `500` arrivals during the `1.0 s` freeze plus
    `500` more during the `1.0 s` `1,000 req/s` post-freeze backlog drain — `1,000`
    delayed requests experiencing a `~1,000 -> 2 ms` wait ramp — accurately reporting
    **`p99 ~ 700 ms`** (`300th` slowest of `30,000`)!
* **Load-test checklist:**
  1. Drive arrivals via **open-loop arrival rate** (`k6` `constant-arrival-rate` /
     `ramping-arrival-rate`, `vegeta`, `wrk2 -R <rate>`).
  2. Record **un-averaged latency distributions** (HDR Histogram: `p50`, `p95`, `p99`,
     `p99.9`, `max`) **never averaging percentiles across shards!**
  3. Find the **saturation knee** via step-load ramp (`25% -> 50% -> 75% -> 90% ->
     105%`) and verify bounded overload behavior (`429`/`503` load shedding rather than
     unbounded memory OOM or retry storms).
