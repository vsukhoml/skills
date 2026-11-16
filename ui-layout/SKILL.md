---
name: ui-layout
description: >-
  Spatial UI layout for desktop, mobile, TUI, and web: proximity and grouping,
  alignment axes, reading order, split panes, responsive reflow, safe areas,
  RTL mirroring, and translation string growth. Use when laying out or
  reviewing a screen, panel, form, or responsive breakpoint, or when fixing
  spacing, alignment, or overflow.
last_updated: 2026-11-15
---

# First-Principles Spatial Layout, Reflow & Localization Geometry (`ui-layout`)

Structures visual hierarchy, alignment, adaptive reflow, and localization geometry
from **perceptual Gestalt laws and constraint-solving first principles** — across
desktop windowing toolkits, mobile frameworks, immediate-mode canvases, terminal
character grids (TUI), and web layout engines.

Consult [references/spatial-and-platform-mapping.md](references/spatial-and-platform-mapping.md)
for cross-platform layout primitives, master-detail/split-pane patterns, RTL
mirroring invariants, and translation expansion budgets.

---

## 1. Gestalt Proximity & Low-Noise Grouping

Human vision parses spatial clusters **before** reading borders or labels:

1. **The `>= 2x` Proximity Invariant:**
   * Keep spacing *between* distinct groups at least **`2x` larger** than spacing
     *within* a group (`gap_outer >= 2 * gap_inner`), drawn from a discrete token
     scale (e.g., `4, 8, 12, 16, 24, 32, 48` logical px/dp/pt, or `0, 1, 2` blank
     cells in TUI).
   * Label-to-control gap (`4–6 px`) must always be markedly tighter than control-
     to-next-label gap (`16–24 px`) so nobody ever misreads which field a label or
     error belongs to!
2. **Containment Escalation Ladder (Stop as Early as Possible):**
   Separate groups using the lightest mechanism that makes structure unambiguous:
   1. **Whitespace & proximity** (zero visual clutter — try first!).
   2. **Shared alignment axis** (clean vertical/horizontal rail).
   3. **Subtle OKLCh surface step** (`bg_surface` vs `bg_canvas` per `ui-colors`).
   4. **1 px hairline divider or border** (only when dense rows/panes sit tight or
      under OS high-contrast mode).
   * **Ban "Box-in-Box-in-Box" nesting:** Never wrap a bordered table inside a
     bordered card inside a bordered pane with three competing paddings and shadows.
3. **Interactive vs. Static Visual Clarity:**
   * Controls (buttons, editable cells, clickable cards, comboboxes) must share a
     consistent affordance vocabulary distinct from read-only status pills and
     section headers; borderless/ghost buttons need **`>= 8–12 px` clearance** so
     adjacent targets never blur together (`ui-ergonomics`).

---

## 2. Shared Alignment Rails & Visual-Logical Parity

1. **Minimize alignment axes (`<= 3–4` X-rails per view):**
   * Every element that looks *nearly* aligned (`2–6 px` off an adjacent edge) reads
     as a defect. Snap headings, form labels, inputs, card edges, and table columns
     onto shared layout rails.
   * **Header-to-data rail lock:** Table column headers **must** share the exact
     alignment of their cells (`start`-aligned for text/IDs/statuses; `end`- or
     decimal-aligned for quantities, prices, latencies, and percentages per
     `ui-typography`).
   * **Optical vs. geometric centering:** Icons with asymmetric mass (play triangle
     `▶`, back chevron `‹`, external-link arrow `↗`) or mixed icon+text buttons
     need slight optical padding balance so they *look* centered inside hit boxes.
2. **Visual Order == Logical Order (`ui-accessibility`):**
   * Reading order (top-to-bottom, `start`-to-`end`) **must** match the underlying
     widget/DOM tree and keyboard `Tab`/arrow traversal order. Never fix a visual
     placement bug by detaching visual coordinates (`order`, reverse-direction,
     arbitrary canvas XY) from focus order.

---

## 3. Adaptive Reflow, Split Panes & Viewport Discipline

Desktop windows resize arbitrarily (`1/3`-screen tiled vertical split to `3840 px`
ultrawide), mobile devices rotate and fold, TUIs run inside `80×24` to `240×70`
tmux panes, and users zoom to `200%`:

1. **Content-driven reflow, never device-name guessing:**
   * Switch column counts and pane layouts based on **available container width**
     and minimum legible content measure (e.g., CSS Container Queries / `minmax()`,
     SwiftUI `ViewThatFits` / `GeometryReader`, Compose `BoxWithConstraints`, Qt/GTK
     size policies, TUI column thresholds) — never hardcoded `"phone vs desktop"`
     user-agent checks.
2. **Master-Detail & User-Resizable Split Panes (`ui-ergonomics`):**
   * For high-frequency triage/inspection workflows (logs, mail, issues, traces,
     file trees, DB browsers), prefer a **side-by-side Master-Detail / Inspector
     split** on wide containers (`>= 900–1,000 px` or `>= 120` TUI cols) so clicking
     or arrowing down items previews details in `0 ms` with zero back-button
     ping-pong, collapsing cleanly to a single-pane push/drawer view on narrow
     containers.
   * Give splitters a generous grab halo (`>= 8–12 px`), a keyboard/double-click
     reset, sensible `min/max` pane clamps, and persisted user width.
3. **One primary scroll axis per pane & honest overflow cues:**
   * Avoid nested same-axis scroll containers (`vertical table scroll` trapped
     inside `vertical page scroll` steals wheel events!). Pin shell toolbars/filters
     cleanly and let the primary data viewport own scrolling.
   * Whenever horizontal tabs, chips, or wide columns can overflow, show an explicit
     affordance (clipped half-item peek, scroll buttons, column-count badge, or
     subtle edge mask) so off-screen controls are never invisible.
4. **Safe areas, window chrome & sticky scroll padding:**
   * Inset interactive controls away from OS notches, rounded display corners,
     gesture home bars, macOS/Windows custom titlebar traffic lights, soft-keyboard
     (IME) occlusion, and TUI bottom status bars.
   * Set scroll-into-view padding equal to sticky header/footer height so keyboard-
     focused rows or search matches never land hidden underneath sticky chrome!

---

## 4. Translation Expansion & Logical RTL Mirroring

Interfaces break silently outside English unless geometry flexes by construction:

1. **Survive `+35–50%` horizontal expansion & taller vertical scripts:**
   * German, Russian, French, Finnish, and Greek routinely expand UI strings by
     **`+35–50%`** (and **`+80–100%`** on short `4–8 char` English words like
     `"Save"`, `"View"`, `"Edit"`, `"New"`!), while CJK compacts horizontally and
     Arabic, Thai, Vietnamese, and Devanagari require **taller line boxes** without
     clipping ascenders/diacritics.
   * **Never** lock text-bearing buttons, tabs, badges, or form rows to fixed widths
     or fixed pixel heights: use `min-height` + intrinsic content sizing, allow
     horizontal button bars to wrap or collapse into overflow when labels grow, and
     prefer **top-aligned form labels** over narrow fixed-width left label columns
     whenever localization is in scope.
   * When truncation is unavoidable inside dense cells/trees, always provide a
     keyboard- and pointer-reachable full-value path (`ui-typography`,
     `ui-accessibility`).
2. **Author in Logical Coordinates (`Start` / `End`, `Inline` / `Block`):**
   * Use toolkit-native logical flow directions (`start`/`end`, `leading`/`trailing`,
     `inline-start`/`inline-end` — never raw `left`/`right` for layout padding,
     borders, alignment, or drawer anchoring) so Right-to-Left (`ar`, `he`, `fa`,
     `ur`) locales mirror automatically!
   * **Mirroring rules — know what flips and what NEVER flips:**
     * **Flip in RTL:** Page/sidebar/master-detail order, `start` text alignment,
       form icon placement, directional progress/breadcrumbs/back-forward arrows
       (`←` / `→`), horizontal swipe/arrow navigation semantics.
     * **Keep unmirrored in RTL:** Clocks and circular progress (`clockwise`), media
       playback timelines and transport controls (`Play ▶` / `Rewind` / scrub bar
       represents physical tape/time media convention), phone/calculator digit pads,
       code snippets/file paths/URLs/math formulas, and asymmetric physical-object
       icons (e.g., magnifying glass handle, checkmark `✓` in most platform HIGs).

---

## Before You Finish (`ui-layout` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Inner card gap (`16 px`) equals or exceeds gap between neighboring cards (`12 px`) | Enforce `gap_between >= 2 * gap_within` on discrete spacing tokens |
| Triple-nested bordered containers (`Pane -> Card -> Bordered Table`) | Strip redundant borders/shadows; separate with whitespace or subtle surface tint |
| Numeric table header is `start`-aligned while cells below are `end`-aligned | Lock header alignment rail to cell data alignment (`end` for numbers) |
| Visual CSS/coordinate reorder makes `Tab` jump backwards across screen | Reorder source/widget tree so visual and focus order match |
| Master list opens full-page detail on `2,560 px` desktop monitor | Use responsive Master-Detail split pane (`>= 900 px`), single-pane on narrow |
| Sticky header covers focused input or `#anchor` / search jump target | Add scroll-margin / viewport inset matching sticky chrome height |
| Fixed `width: 80px; height: 28px` button clips German label or `200%` font scale | Use `min-width`/`min-height` + intrinsic padding and wrap/overflow fallback |
| Hardcoded `margin-left` / `Left` constraint breaks Arabic/Hebrew RTL layout | Replace with logical `inline-start` / `leading` primitives |
