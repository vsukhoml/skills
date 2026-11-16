---
name: ui-performance
description: >-
  UI responsiveness and large-data rendering (10^4 to 10^8 records) at 60/120
  Hz for web, desktop, mobile, GPU, and TUI: virtualization, off-thread sort,
  filter, and search, stream conflation, chart level of detail, and
  rendering-tier selection. Use when a UI janks, freezes, or scrolls slowly,
  or when building a large table, list, chart, or live-updating view.
last_updated: 2026-11-15
---

# UI Performance, Frame Budgets & Large-Dataset Engineering (`ui-performance`)

Designs and audits user interfaces so **every interaction feels instantaneous** and
**frame times hold steady even over $10^4\text{–}10^8$ rows, log lines, or data
points** — across desktop toolkits, mobile frameworks, browser runtimes, GPU/
immediate-mode canvases, and terminal UIs (TUIs).

Consult [references/large-data-and-rendering.md](references/large-data-and-rendering.md)
for virtualization index math, off-thread snapshot pipelines, stream-conflation
architectures, LTTB / min-max envelope chart decimation, and platform profiling
checklists.

---

## 1. Hardware & Human Perceptual Latency Budgets

Every UI thread shares one iron constraint: **input handling + state update +
layout + paint/submit must finish inside a single `vsync` interval** or frames
drop visibly.

| Budget Tier | Threshold | User Perception & Engineering Rule |
| --- | --- | --- |
| **120 Hz ProMotion / High-Refresh Frame** | **`<= 8.33 ms`** (`~5–6 ms` app work + OS/compositor headroom) | Scroll, drag, pan/zoom, and cursor tracking must complete inside this window with **zero** blocking I/O, large allocations, or $O(N)$ walks. |
| **60 Hz Standard Frame** | **`<= 16.67 ms`** (`~10–12 ms` app work) | Hard ceiling for standard animations, table scrolling, and resize reflow. |
| **Direct Input Acknowledgement** | **`<= 50 ms`** | Keypresses, clicks, toggles, and selection highlights must paint visual confirmation within `1–3` frames even if background work continues. |
| **Instant-Feel Operation** | **`<= 100 ms`** | Filter/command-palette keystrokes feel instantaneous below `100 ms`; do **not** flash loading spinners for operations finishing `< 150 ms` (causes flicker). |
| **Async Progress & Skeleton Window** | **`150 ms – 1 s+`** | Keep existing view interactive or render geometry-matched skeletons (`0` layout shift when data arrives); show determinate progress + cancel control above `~2 s`. |

---

## 2. Choose the Right Rendering Tier Before Writing Widgets

Retained widget/DOM trees carry heavy per-node memory, style, accessibility, and
constraint-solver overhead. Match the rendering tier to **live visible primitive
count** and **mutation rate**:

| Rendering Tier | Safe Live Primitive Budget | Best Fit & Representative Examples |
| --- | --- | --- |
| **1. Retained Widget / DOM Tree** | **`<= 500 – 1,500` live nodes** (`O(visible)` via virtualization) | Forms, dialogs, navigation chrome, and **virtualized** lists/tables/trees (e.g., native list/table views in SwiftUI/UIKit, Compose `LazyColumn`, Qt `QAbstractItemModel` views, Flutter `SliverList`, virtualized DOM grids). |
| **2. 2D Immediate / Retained Canvas** | **`1,000 – 100,000` primitives** per frame | Dense custom timelines, flamegraphs, order books, sparkline matrices, node wires, and multi-series 2D charts (e.g., Skia, Direct2D, CoreGraphics, Cairo, `QPainter`, HTML `<canvas>`, custom `egui`/`iced` painter). |
| **3. GPU Instanced / Shader Pipeline** | **`100,000 – 10,000,000+` points/glyphs** | Scatterplots, maps, LiDAR/CAD viewports, waveform oscilloscopes, and massive heatmaps using instanced quads/SDFs and vertex/compute buffers (e.g., Vulkan, Metal, Direct3D, `wgpu`, WebGPU/WebGL). |
| **4. Terminal Cell Diff Buffer (TUI)** | **Viewport `cols × rows` (`~3k–15k` cells)** | Terminal dashboards, log pagers, and process monitors emitting minimal ANSI escape diffs per tick with synchronized output (e.g., `ratatui`, `bubbletea`, `textual`, `notcurses`). |

* **Hybrid rule:** When moving a dense grid or canvas to Tier 2 or Tier 3, expose a
  lightweight **virtualized accessibility proxy / active-descendant node** for the
  focused/hovered region so `ui-accessibility` keyboard and screen-reader walks
  stay 100% functional without instantiating `100,000` widget nodes!

---

## 3. 1D & 2D Viewport Virtualization (Never Instantiate $O(N)$ Nodes)

Any collection that can exceed **`~100–200` items** (tables, logs, traces, dropdown
pickers, file trees, Kanban lanes) **must** virtualize so live UI nodes scale as
**$O(\text{visible\_viewport} + \text{overscan})$**, never $O(N)$:

1. **Uniform-stride rows/cells ($O(1)$ index math — preferred for dense data):**
   * Fix row height $H$ (aligned to semantic type scale in `ui-typography` so `200%`
     scaling simply doubles $H$ cleanly):
     $$\text{first} = \max\!\left(0,\ \lfloor \text{scrollOffset} / H \rfloor - \text{overscan}\right), \qquad \text{count} = \lceil \text{viewportHeight} / H \rceil + 2 \cdot \text{overscan}$$
   * Even $10^7$ log lines scroll at `120 Hz` in `O(1)` time and `O(1)` UI memory!
2. **Variable-height rows ($O(\log N)$ prefix-sum / Fenwick tree):**
   * Seed unmeasured items with a realistic estimated height, measure actual height
     once on mount into a Fenwick tree (binary indexed tree) or segmented prefix
     array, and binary-search scroll offset in $O(\log N)$. **Anchor scroll
     position** against the top visible item when above-viewport items resize so
     content never jumps under the user's eyes.
3. **2D Virtualization for wide grids & spreadsheets:**
   * Virtualize **columns** as well as rows whenever column count exceeds `~25–30`,
     pinning frozen key columns (`ID`, `Name`) in a synchronized header/column
     layer driven by the same scroll state.
4. **Node recycling & stable identity:**
   * Key pooled/recycled item views by **stable record ID** (never mutable array
     index when rows insert/delete/reorder) and keep overscan small (`3–8` rows, or
     velocity-adaptive) so fast flicks don't flash blank gutters while idle memory
     stays minimal.

---

## 4. Off-UI-Thread Data Pipelines & Contiguous Memory

Sorting, filtering, regex/fuzzy searching, JSON/CSV/Arrow decoding, or aggregating
`> 5,000` records on the UI thread guarantees dropped frames (`16 ms` blows out to
`80–800 ms`).

1. **Worker / background-task pipeline:**
   * Own the authoritative dataset (`10^5–10^8` rows) on a background worker thread,
     process, or async task pool (e.g., OS worker thread, Rust/C++ thread pool,
     Go goroutine, Kotlin `Dispatchers.Default`, Web Worker + `SharedArrayBuffer` /
     Wasm).
   * Store hot sortable/filterable fields in **contiguous / columnar arrays
     (Struct-of-Arrays)** rather than pointer-chasing boxed object graphs — linear
     scans over `1,000,000` `f64`/`i64` values take `< 2 ms` in CPU cache vs.
     `> 60 ms` across heap-fragmented objects!
2. **Immutable View-Slice / Index-Vector Handoff:**
   * Rather than copying filtered records, compute an immutable **index vector**
     (`Vec<u32>` / `Int32Array` of matching row IDs) or **viewport page slice**
     (`rows[first..last]`) off-thread and swap the reference atomically on the UI
     thread.
3. **Cancelable, generation-tagged queries:**
   * Tag every filter/search/sort request with a monotonic `generation_id`. As the
     user types `e -> er -> err -> erro -> error`, immediately update the text box
     (`< 8 ms`) and abort or discard stale worker generations so an expensive old
     query never overwrites a newer result!

---

## 5. High-Rate Streaming Conflation & Human-Readable Cadence

Live telemetry, market feeds, build logs, and traces often arrive at **$10^3\text{–}
10^5$ events/second** while the display refreshes at `60–120 Hz` and human eyes can
only read changing digits at **`4–10 Hz`**:

1. **Decouple ingestion from rendering (Conflation Buffer):**
   * Ingest network/IPC events on a background thread into a lock-free ring buffer
     or per-key latest-value map (`conflation`). **Never** trigger a UI state/model
     notification per incoming packet!
2. **Flush at `vsync` for graphics, throttle at `4–10 Hz` for text digits:**
   * Coalesce spatial/chart/canvas state and commit **at most once per animation
     frame** (`60/120 Hz`).
   * Downsample rapidly ticking **numeric text readouts** (`CPU %`, `Price`,
     `Throughput`) to `100–250 ms` (`4–10 Hz`) with `tabular-nums` (`ui-typography`)
     so numbers remain legible instead of an unreadable blur, and provide a 1-click
     / `Space` **Pause / Resume stream** toggle (`ui-ergonomics`) — auto-pausing
     tail-follow the instant the user scrolls up to inspect history!

---

## 6. Chart & Spatial Level-of-Detail (LOD) Decimation

Never submit `500,000` polyline vertices or scatter markers into a `1,200 px`-wide
chart — `> 400` points map to the same horizontal pixel column, wasting GPU/CPU
time and hiding spikes in overdraw:

* **Time-series polylines:** Downsample dynamically to **`1–2` samples per device
  pixel column** (`~1,200–2,400` points) using **per-pixel `[min, max, first,
  last]` bucket envelopes** (guarantees zero missed outlier spikes!) or
  **Largest-Triangle-Three-Buckets (LTTB)** for smooth perceptual shape, recomputing
  from a multiscale pyramid as the user zooms in.
* **2D scatter, maps & node graphs:** Cull off-viewport items via an **R-tree,
  quadtree, or uniform spatial hash** before draw submission; aggregate dense zoom-
  out regions into binned hex/grid density heatmaps (colored in OKLab via
  `ui-colors`) and progressively reveal individual nodes + text labels only past
  legible zoom thresholds.

---

## 7. Eliminate Layout Thrashing, Allocation Churn & Janky Transitions

* **Never interleave geometry reads and mutations** (`read bounds -> set size ->
  read bounds` inside a loop forces $O(N)$ synchronous full-tree relayouts). Batch
  all measurements first, then batch all mutations once.
* **Bound invalidation blast radius:** Isolate frequently updating leaf widgets
  (clocks, sparklines, progress bars, cursor readouts) behind layout/repaint
  boundaries (e.g., fixed box dimensions, CSS `contain: strict` / `content-visibility`,
  Flutter `RepaintBoundary`, Compose state-read scoping, Qt dirty rects) so a
  ticking badge never relayouts the entire dashboard.
* **Zero per-frame allocations & text-shaping churn on hot paths:** Reuse scratch
  buffers in immediate-mode/canvas render loops; cache shaped glyph runs (`HarfBuzz`
  / `CoreText` / `DirectWrite` / Canvas text atlas) rather than re-shaping unchanged
  strings every `8.3 ms`.
* **Animate only compositor-cheap properties:** Restrict continuous transitions to
  **transform** (translate/scale/rotate) and **opacity** (`<= 150–200 ms` on UI
  feedback; `0 ms` instant on keyboard focus/selection traversal, honoring reduced
  motion per `ui-accessibility`). Never animate `width`, `height`, `top`/`left`,
  margins, or blur radii over dense views.

---

## Before You Finish (`ui-performance` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Rendering all `N` rows/options/logs into widget/DOM nodes (`N > 200`) | Add 1D/2D viewport virtualization (`O(visible + overscan)`) |
| Picker/combobox freezes opening `10,000` options | Virtualize dropdown list + debounce/worker-offload fuzzy filter |
| Sorting, filtering, or parsing large payload on the UI thread | Move to worker/background thread; swap immutable index slice |
| WebSocket / IPC handler mutates UI state on every incoming message | Conflate into ring/map buffer; flush `<= 1x/frame` (`4–10 Hz` for digits) |
| Live log viewer yanks scroll position to bottom while user reads above | Disengage auto-follow on upward scroll; show `"Resume live tail (N new)"` pill |
| Chart draws `100k+` SVG/DOM nodes or raw un-decimated points | Switch to Canvas/GPU + per-pixel `[min, max]` envelope or LTTB LOD |
| Interleaved layout measure + mutate inside a loop, or animating `height`/`width` | Batch reads before writes; animate only `transform` & `opacity` |
| Proportional digits or unconstrained badge width causes `60 Hz` table jitter | Enable `tabular-nums` (`ui-typography`) + fixed/contained cell geometry |
