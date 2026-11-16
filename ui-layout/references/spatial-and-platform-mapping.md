# Cross-Platform Spatial Primitives, Adaptive Patterns & I18n Geometry (`ui-layout`)

Reference mapping first-principles spatial geometry onto native desktop, mobile,
GPU/immediate-mode, terminal TUI, and web layout systems.

---

## 1. Cross-Platform Layout Primitive Mapping

Every modern UI toolkit expresses the same four layout primitives — **1D Stack**,
**2D Grid**, **Constraint / Flex-Grow Split**, and **Container-Size Query**:

| Spatial Concept | Web (CSS) | Apple (`SwiftUI` / `Auto Layout`) | Android (`Compose`) & `Flutter` | Desktop (`Qt` / `GTK` / `WinUI` / `Slint` / `egui`) | Terminal TUI (`ratatui` / `lipgloss` / `textual`) |
| --- | --- | --- | --- | --- | --- |
| **1D Stack + Uniform Gap** | `display: flex; gap: var(--space-3)` | `HStack(spacing:)` / `VStack(spacing:)` / `UIStackView` | `Row` / `Column(Arrangement.spacedBy(...))` | `QHBoxLayout` / `GtkBox` / `StackPanel` / `VerticalLayout` / `ui.horizontal` | `Layout::horizontal` / `Layout::vertical` with spacing |
| **2D Aligned Grid** | `display: grid; grid-template-columns: ...` | `Grid` / `LazyVGrid(GridItem(.adaptive(...)))` | `LazyVerticalGrid(GridCells.Adaptive(minSize))` | `QGridLayout` / `GtkGrid` / `GridLayout` / `egui::Grid` | Nested `Constraint::{Length, Min, Percentage, Fill}` |
| **Master-Detail Split** | Grid `minmax(260px, 320px) 1fr` + draggable splitter | `NavigationSplitView` / `NSSplitViewController` | `ListDetailPaneScaffold` (Material 3 Adaptive) | `QSplitter` / `AdwNavigationSplitView` / `GtkPaned` | `Layout::horizontal([Constraint::Length(36), Constraint::Fill(1)])` |
| **Container-Driven Reflow** | `@container (min-width: 48rem)` / `repeat(auto-fit, minmax(18rem, 1fr))` | `ViewThatFits` / `@Environment(\.horizontalSizeClass)` / `GeometryReader` | `BoxWithConstraints` / `WindowWidthSizeClass` / `LayoutBuilder` | `resizeEvent` width thresholds / `AdwBreakpoint` | Match on `frame.area().width` (`< 80`, `80..120`, `> 120` cols) |
| **Logical Start / End** | `margin-inline-start`, `padding-inline`, `text-align: start`, `inset-inline-end` | `.leading` / `.trailing` (automatic in SwiftUI & Auto Layout!) | `Alignment.Start` / `PaddingValues(start = ...)` / `EdgeInsetsDirectional` | `Qt::LayoutDirectionAuto` / GTK logical start-end / `FlowDirection` | Track locale direction when aligning cell strings |
| **Safe Area / IME Inset** | `env(safe-area-inset-*)`, `scroll-padding-top`, VisualViewport | `.safeAreaInset(edge:)` / `keyboardLayoutGuide` | `WindowInsets.safeDrawing` / `imePadding()` / `SafeArea` | Window client-area margins + custom titlebar inset | Reserve `1–2` bottom rows for keybind legend + status/command bar |

---

## 2. Spacing Scale & Gestalt Ratio Reference

Pick **one** base unit (`4 px` on GUI displays; `1 cell` horizontally / `1 row`
vertically on TUI) and restrict layout spacing to named steps so arbitrary magic
numbers (`7px`, `13px`, `19px`) never enter widget code:

| Token | Logical px (`dp`/`pt`) | Typical Structural Role |
| --- | --- | --- |
| `space-1` | `4` | Tight inline icon-to-label gap; label-to-helper-text vertical gap |
| `space-2` | `8` | Compact button/cell internal padding; gap between tightly coupled toolbar buttons |
| `space-3` | `12` | Standard input padding; internal gap inside a compact card or form field stack |
| `space-4` | `16` | Standard peer-element gap; default mobile/pane edge padding |
| `space-6` | `24` | Separation **between** distinct form sections or dashboard cards (`>= 2x` inner `8–12` gap!) |
| `space-8` | `32` | Major view region separation; wide desktop pane gutters |
| `space-12` | `48` | Top-level page section break |

* **Density modes (`Compact` vs. `Comfortable`):** Operational dashboards, IDEs,
  trading terminals, and log viewers benefit hugely from a `Compact` token profile
  (e.g., `28–32 px` row height, `space-2` cell padding) while touch/field-ops views
  need a `Comfortable` profile (`44–48 px` rows) — swap the spacing token table
  cleanly rather than hardcoding two separate UIs!

---

## 3. Common Dashboard & Application Shell Archetypes

Avoid inventing fragile custom geometries when proven structural shells fit:

1. **Command-First Workbench (`Nav Rail + Resizable List + Detail/Canvas + Bottom/Top Status`):**
   * Ideal for engineering tools, observability consoles, data explorers, and TUI
     dashboards.
   * Collapse order as container narrows: `1. Hide right secondary inspector into
     tab/drawer -> 2. Collapse left nav labels to icons or Cmd+K drawer -> 3. Fold
     list + detail into single-pane push navigation`.
2. **KPI + Faceted Filter + Virtualized Data Grid:**
   * Top summary strip (`<= 5` clickable anomaly/KPI cards, fixed compact height so
     it never pushes the primary table below the fold!) -> Sticky filter/search +
     selection-action bar -> Full-height virtualized table (`ui-performance`).
3. **Focused Single-Column Task / Settings View:**
   * Constrain form/prose column width (`<= 640–720 px` / `65–75 ch` per
     `ui-typography`) inside wide monitors rather than stretching text inputs `2,200 px`
     wide from screen edge to screen edge!

---

## 4. Translation Expansion & Pseudo-Localization Test

Before shipping any layout intended for multiple locales (or user-authored dynamic
names):

| English Source Length | Expected Expansion Allowance (`DE` / `RU` / `FR` / `FI` / `EL`) |
| --- | --- |
| `1 – 10` characters (`"New"`, `"Save"`, `"Run"`, `"Logs"`) | **`+80%` to `+150%`** (e.g., `"Views"` -> `"Представления"`, `"Edit"` -> `"Bearbeiten"`) |
| `11 – 20` characters (`"Reset password"`) | **`+50%` to `+70%`** |
| `21 – 50` characters (headings, tooltips, banners) | **`+30%` to `+40%`** |
| `> 50` characters (body paragraphs) | **`+20%` to `+30%`** |

* **Automated pseudo-localization smoke test:** Transform every string at build/dev
  time (`"Save" -> "[Ŝàvé ·····]"` adding `+40%` width, accented ascenders/
  descenders, and outer brackets `[` `]`). Any layout where the closing `]` is
  clipped or overlaps a sibling control is a deterministic layout bug!
