# High-Leverage Optimization Moves & Microarchitecture Matrix (`perf-engineering`)

Every move below is a **falsifiable hypothesis**, not a blind style rule — verify its
effect on the scoreboard and keep only moves whose measured gain justifies any added
code complexity.

---

## 1. Algorithmic, Boundary & Work-Avoidance Moves (Highest ROI)

1. **Eliminate Super-Linear & Hidden $O(N^2)$ Loops:**
   * Repeated string concatenation without buffer capacity, linear `.contains()` inside
     a loop, re-sorting already-ordered streams, or per-edge graph cycle scans when
     topological/monotonic IDs make cycles impossible.
2. **Amortize Boundary Crossings (Batching):**
   * One SQL `WHERE id = ANY($1)` / `UNNEST` instead of `N` point queries; one batched
     RPC/IPC message; one `writev` / `io_uring` submission batch; one FFI/CGO/PyO3 call
     over a contiguous slice instead of `100,000` per-element FFI crossings!
3. **Fast Path for the Common Case ("Split Simple from General"):**
   * If `97%` of strings are pure ASCII (`(word & 0x8080808080808080ULL) == 0`), numbers
     fit in `int64`, or containers hold `<= 4` items, handle the common case inline in
     5 instructions and outline the general fallback (`#[cold]` / `[[unlikely]]`).
   * **Mandatory safety gate:** Explicitly test *both* the fast path, the slow path, and
     the exact boundary transition between them!
4. **Hoist, Defer & Specialize:**
   * Hoist loop-invariant lookups, regex compilation, timezone loading, and config reads
     out of hot loops.
   * **Defer until read:** Never eagerly format debug strings, stack traces, or unused
     JSON fields on the hot path; compute summary stats lazily or on a `1-in-2^k`
     bitmask sample (`(counter++ & 0x3FF) == 0`).
   * Replace heavy general machinery on hot paths (`regex` for fixed prefix/delimiter
     splits, `sprintf`/`fmt` reflection for formatting a single integer/timestamp).

---

## 2. Memory Representation & Cache-Locality Moves

Most "CPU-bound" code is actually stalled `60–80%` of cycles waiting on L1/L2/DRAM!

1. **Shrink Structs & Eliminate Padding:**
   * Order struct fields largest-alignment-first (`u64`/pointers $\rightarrow$ `u32`
     $\rightarrow$ `u16` $\rightarrow$ `u8`/enums) and verify with `sizeof()` /
     `pahole` / `-Z print-type-sizes` / Go `fieldalignment` / JVM `JOL` (Java Object
     Layout). Halving a 64-byte node to 32 bytes doubles effective L1/L2/LLC capacity
     and memory bandwidth!
2. **Split Hot Fields from Cold Fields:**
   * If a scan touches `id`, `status`, and `timestamp` (`16 B`) on `10^6` records while
     `description`, `error_msg`, and `metadata` (`240 B`) are read on `< 1%` of hits,
     move cold fields behind an index/pointer into a side table so `4` hot records pack
     into every `64 B` cache line instead of `0.25`!
3. **`32-bit` Array Indices Instead of `64-bit` Pointers:**
   * In ASTs, graphs, ECS tables, and caches with `< 4 × 10^9` nodes, `uint32_t`
     indices into a contiguous `Vec`/slab halve link footprint, eliminate per-node
     allocator headers (`16–32 B` each!), improve prefetcher spatial locality, and make
     serialization trivial.
4. **Flat Contiguous Containers & Bitvectors over Node Graphs:**
   * Replace `std::map` / `LinkedList` / boxed-node hash maps with contiguous vectors
     (binary search or linear scan wins up to `N ~ 32–64`!), SwissTable/open-addressed
     hash maps, or **dense arrays / bitvectors** when keys are small integers/enums
     (set intersection becomes a single `u64` bitwise `&` + `popcnt`!).
5. **`SoA` (Structure of Arrays) vs. `AoS` (Array of Structures):**
   * Use `SoA` (`xs[], ys[], flags[]`) when vectorized/columnar kernels stream over 1–2
     fields across thousands of rows; keep `AoS` (or `AoSoA` cache-line blocks of 8/16
     items) when random point lookups read all fields of a single entity together.
6. **Eliminate False Sharing in Concurrent Code:**
   * Never place two independent atomics/counters written by different threads in the
     same `64 B` (`128 B` on Apple Silicon / spatial-prefetch x86) cache line! Prefer
     **thread-local / per-CPU counters aggregated on read**, or `alignas(64)` padding.

---

## 3. Allocation & Lifetime Moves

1. **`reserve()` Known Sizes & Small-Buffer Optimization (`SBO`):**
   * Pre-size vectors/maps/strings whenever length is known or bounded; use stack/inline
     small-vector storage (`SmallVec<[T; 8]>`, SSO strings) when common counts are tiny
     and `sizeof(T)` is small.
2. **Hoist Scratch Buffers Across Loop Iterations (With High-Water Cap!):**
   * `buf.clear()` keeps allocated capacity across requests/iterations (`0 allocs/op`).
   * **Leak guard:** If a rare `50 MB` outlier payload stretches `buf.capacity()`, drop
     and reallocate back to default capacity whenever `buf.capacity() > MAX_RETAINED`!
3. **Arena / Bump Allocation for Phase- or Request-Scoped Objects:**
   * Allocate parse trees, query plans, or frame-temporary structs from a bump pointer
     (`1` pointer add per alloc, `O(1)` bulk reset at request end, `0` individual
     `free()` traversal!). *Never mix short-lived objects into a long-lived arena.*
4. **Zero-Copy Views & Index Sorting:**
   * Pass read-only slices/views (`std::span`, `string_view`, `&[u8]`, Go `[]byte`
     sub-slices, Python `memoryview`, JS/TS `Uint8Array.subarray()` rather than copying
     `.slice()` — cloning tiny extracts retained long-term so they don't pin multi-MB
     backing buffers) instead of allocating substrings; sort an array of
     `(key, uint32_t index)` pairs (`8 B`) instead of swapping `256 B` structs during
     `sort()`.

---

## 4. Top-Down Microarchitectural (`TMAM`) Remediation Matrix

When `perf stat --topdown` / `llvm-mca` / VTune flags a specific CPU stall category on
a proven hot kernel:

| Dominant Stall Category | Hardware Root Cause | Targeted Code Fixes |
| --- | --- | --- |
| **Front-End Bound** | I-cache misses, ITLB thrash, macro-op decode stalls (bloated inlining / huge switch / mega-binary) | Outline cold error/logging branches (`#[cold]`), stop over-inlining giant templates, enable **PGO + BOLT / Propeller** basic-block layout |
| **Bad Speculation** | Unpredictable data-dependent branches (`~15–20` cycle flush per miss) | Sort data if free, replace unpredictable `if` with branchless arithmetic/lookup (`cmov` / `select_unpredictable`), batch filter predicates via bitmasks |
| **Back-End: Memory Bound** | L1/L2/LLC cache misses, TLB misses, DRAM bandwidth saturation | Shrink structs, hot/cold split, flat/SoA layout, cache blocking/tiling to fit L1/L2, hugepages (`2 MB` THP) for multi-GB hash tables |
| **Back-End: Core Bound** | Long loop-carried dependency chains (`acc += x[i]` FP latency `3–4 cyc`), divider stalls, port contention | Break serial dependency chains into `2–4` independent accumulators (`acc0, acc1, acc2, acc3`) so out-of-order/SIMD ports saturate; strength-reduce integer division (`libdivide` / shifts) |
| **High Retiring (Still Slow)** | CPU retires `4+` IPC cleanly — simply executing *too many instructions*! | Algorithmic reduction, SIMD vectorization (`AVX2`/`NEON`/portable SIMD), bit-parallel SWAR operations |

---

## 5. Locking Wins Against Silent Regression in CI

Wall-clock `assert duration < 50ms` checks **always** either flake on shared CI runners
or use such a loose threshold (`< 2000ms`) that a `10x` regression passes unnoticed!
Lock performance invariants with **deterministic physical counters**:

1. **Exact or bounded allocation assertions** in unit/integration tests (e.g., Go
   `testing.AllocsPerRun(...) == 0`, Rust custom counting allocator / `dhat`, C++
   scoped `malloc` hook, Python `tracemalloc` / `memray` allocation limits, JVM
   `ThreadMXBean.getThreadAllocatedBytes` / `JFR`, Android `androidx.benchmark`
   `AllocationMetric`, Node/V8 `v8.getHeapStatistics()`).
2. **Exact query / RPC / syscall count assertions** (`assert db_queries_executed == 2`
   on batch `N=50` vs `N=5` so an accidental `N+1` regression fails deterministically!).
3. **Deterministic instruction / cycle-model gates** (`Cachegrind` `Ir` instruction
   reads with ASLR off, or `llvm-mca` block RThroughput on critical DSP/crypto kernels).
4. **Artifact / symbol / struct size assertions** (`static_assert(sizeof(Node) <= 32)`,
   CI ELF symbol/Flash size budget).
