# Large-Dataset & Frame-Budget Reference (`ui-performance`)

Deep-dive patterns, algorithms, and profiling diagnostics for keeping UIs inside
`8.33 ms` (`120 Hz`) / `16.67 ms` (`60 Hz`) over large or high-velocity datasets.

---

## 1. Virtualization Math & Scroll-Anchor Invariants

### 1.1 Uniform Row/Cell Virtualization ($O(1)$)

Prefer fixed row heights ($H$) on operational tables, logs, traces, and command
palettes — users scan uniform grids faster (`ui-layout`), and layout math is $O(1)$:

```text
totalContentHeight = N * H
firstVisible       = floor(scrollTop / H)
visibleCount       = ceil(viewportHeight / H)
renderStart        = max(0, firstVisible - overscan)
renderEnd          = min(N, firstVisible + visibleCount + overscan)
offsetY(i)         = i * H
```

* **Coordinate-precision trap at $N \ge 10^6$:** Many toolkits and browsers cap
  scroll container pixel heights (`~16M–33M px` in 24-bit/float32 layout engines;
  at `H = 32 px`, `1,000,000` rows = `32,000,000 px`!). When `N * H` exceeds
  `~8,000,000 px`, map scrollbar thumb `[0.0 .. 1.0]` through a **virtual page
  coordinate** (`virtualScrollTop = ratio * (N * H - viewportHeight)`) and position
  rendered rows relative to the viewport (`y = (i - firstVisible) * H -
  subRowRemainder`) so even `10^8` rows render with sub-pixel accuracy!

### 1.2 Variable-Height Virtualization via Fenwick Tree ($O(\log N)$)

When rows legitimately vary in height (chat threads, multi-line diff hunks, nested
cards):

1. Initialize a Fenwick tree (Binary Indexed Tree) `bit[1..N]` with `estimatedHeight`
   in $O(N)$ (`< 1 ms` for `N = 500,000` `f32` values).
2. `prefixSum(i)` returns exact `offsetY(i)` in $O(\log N)$; binary-lifting on
   `bit` finds `firstVisible` for `scrollTop` in $O(\log N)$ with a single array
   traversal.
3. When row `i` mounts and reports `measuredHeight != currentHeight[i]`:
   * Update `bit.add(i, delta)` in $O(\log N)$.
   * **Scroll anchoring:** If `i < firstVisible`, add `delta` to `scrollTop` in the
     same frame before paint so the user's currently read line stays pixel-locked.

---

## 2. Off-Thread Data Pipeline & Zero-Copy Snapshot Architecture

```text
[Network / Disk / IPC]
        │  (raw chunks / Arrow / columnar buffers)
        ▼
[Background Worker / Task Pool]
  • Columnar store (SoA: timestamps[], severities[], status_codes[], msg_offsets[])
  • Incremental index / trigram or roaring-bitmap filter
  • Cancellation check every ~4,096 rows against atomic latest_generation_id
        │
        │  Immutable ViewSnapshot { generation_id, total_matched, window_rows[] }
        ▼
[UI Thread (<= 2 ms per vsync)]
  • Diffs visible window_rows[0..60] by stable row_id
  • Updates recycled widget slots / Canvas / TUI cell buffer
```

* **Why send only `window_rows` (or shared `Int32Array` indices)?** Serializing
  `200,000` JSON objects across a thread/IPC boundary costs `50–300 ms` — worse
  than the sort itself! Keep the full dataset inside worker memory (or shared
  read-only memory) and materialize **only the `~50–100` currently visible row
  records** plus summary aggregates (`total_matched`, facet counts, histogram bins)
  for the UI thread.
* **Progressive / streaming first paint:** Render the first viewport (`rows 0..50`)
  as soon as the first chunk arrives (`< 50 ms`) rather than blocking first paint on
  downloading or indexing all `1,000,000` rows.

---

## 3. Time-Series & Chart Decimation Algorithms

Given a viewport width of $P$ device pixels (e.g., `P = 1,200` on a `1x` display or
`2,400` on `2x` HiDPI) and $N \gg P$ samples in `[t_start, t_end]`:

### 3.1 Per-Pixel `[first, min, max, last]` Envelope (`O(N)` single pass or `O(P)` via mipmap)

Best for **operational metrics, financial candlesticks/ticks, latency spikes, and
audio waveforms** where dropping a 1-sample spike would mislead an operator:

1. Partition `[t_start, t_end]` into $P$ time buckets (1 per pixel column).
2. In each non-empty bucket, record `(t_first, y_first)`, `(t_min, y_min)`,
   `(t_max, y_max)`, `(t_last, y_last)` — emitting at most `4` vertices per pixel
   column in chronological order (`<= 4P` vertices total).
3. Pre-aggregate **power-of-two mipmap levels** (`1x, 16x, 256x, 4096x` min/max
   summaries) on the worker as data appends in $O(1)$ amortized time so zooming out
   across `100,000,000` points queries `<= 2,400` pre-computed buckets in `< 0.2 ms`!

### 3.2 Largest-Triangle-Three-Buckets — LTTB (`O(N)`)

Best for **smooth trend sparklines** where preserving visual slope and inflection
shape matters alongside an explicit max/min badge:

* Divide data into `K` buckets (`K ≈ P`), keep endpoints exact, and in each bucket
  pick the point maximizing triangle area with the previously selected point and the
  next bucket's centroid.

---

## 4. High-Rate Conflation & Backpressure Pattern

When a stream produces bursts (`tail -f` build output, order-book ticks, distributed
trace spans):

1. **Bounded memory:** Cap client-side rolling history via a ring buffer (e.g.,
   latest `100,000` lines in memory + spill/virtualized cursor to disk/server) so
   leaving a dashboard tab or desktop monitor open overnight never leaks gigabytes
   of RAM.
2. **Two-cadence flush:**
   * **Every `vsync` (`8.3 / 16.6 ms`):** Drain conflated spatial state (chart
     ring append, progress bar fill, virtualized log tail count).
   * **Every `150–250 ms` (`4–6.6 Hz`):** Latch formatted scalar text strings for
     headline KPI cards and table summary cells so human eyes can read discrete
     values calmly.
3. **Scroll-lock Poka-Yoke:** If `userScrolledUp == true`, keep appending to the
   background buffer and incrementing a `"Paused — 1,420 new events (Jump to live)"`
   badge without shifting `scrollTop`.

---

## 5. Cross-Platform Profiling & Verification Matrix

Never guess where `16 ms` went — record a frame trace over realistic data scale
(`10x` normal p95 row count) with CPU throttling (`4x` slowdown or target low-tier
device):

| Target Stack | Primary Frame & Memory Profiler | Key Signals to Check |
| --- | --- | --- |
| **Native Desktop / C++ / Rust / Go** | Tracy Profiler, Linux `perf` + FlameGraph, macOS Instruments (`Time Profiler` / `Core Animation`), Windows PIX / WPA | Frame-time histogram (`p99 <= 8.3/16.6 ms`), per-frame heap allocs (`0` on steady state), glyph/shaping time, GPU draw-call count. |
| **Qt / GTK / Slint / egui / ImGui** | Toolkit frame-time overlay + RenderDoc / Instruments / Tracy | Widget relayout cascades, overdraw regions, texture-atlas rebuilds, `QAbstractItemModel` `data()` call count per frame (`<= visible cells`). |
| **iOS / macOS (SwiftUI / UIKit / AppKit)** | Xcode Instruments (`SwiftUI`, `Core Animation Commits`, `Hitches`) | Hitch ratio (`ms/s`), offscreen-rendered passes, redundant `body` evaluations, main-thread Hang diagnostics (`> 250 ms`). |
| **Android (Compose / Views) & Flutter** | Android Studio System Trace / Perfetto + Macrobenchmark, Flutter DevTools (`Frame Chart`) | UI vs. RenderThread / Raster thread split, unnecessary recompositions, shader compilation jank, `RecyclerView`/`LazyColumn` bind time. |
| **Web (DOM / Canvas / WebGPU)** | Browser DevTools Performance panel (`Long Animation Frames`, Layout Shift, GPU, Memory heap snapshots) | Tasks `> 50 ms`, Forced Reflow / Recalculate Style cost, DOM node count (`<= 1,500`), INP (`<= 200 ms`, target `< 50 ms`), CLS (`0.00`). |
| **Terminal TUI** | Frame-tick timer + byte-counter on PTY stdout | Bytes written per tick (diff-only + DEC mode `2026` synchronized output to eliminate tearing), zero blocking syscalls on input loop. |
