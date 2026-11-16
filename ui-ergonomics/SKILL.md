---
name: ui-ergonomics
description: >-
  UI task ergonomics: critical user journeys and friction logs, dashboard and
  common-view design, interaction cost (Fitts, KLM-GOMS, Hick), keyboard
  shortcuts, mistake-proofing (constraints, previews, undo), and microcopy.
  Use when designing or reviewing a workflow, form, dashboard, navigation,
  shortcut set, or confirmation and error text.
last_updated: 2026-11-15
---

# UI Task Ergonomics, Dashboards & Poka-Yoke (`ui-ergonomics`)

Designs control surfaces, dashboards, and workflows so **common tasks take minimal
physical and cognitive effort** and **mistakes are structurally hard to commit** —
across desktop GUIs, web apps, mobile apps, and terminal UIs (TUIs).

Consult [references/dashboards-and-poka-yoke.md](references/dashboards-and-poka-yoke.md)
for KLM-GOMS operator budgets, dashboard information-architecture patterns, and
the Poka-Yoke mistake-proofing catalog.

---

## 1. Identify Critical User Journeys (CUJs) & Common Views First

Never lay out navigation or controls democratically. Before placing widgets (or
when auditing an existing app), extract its **`3–5` Critical User Journeys (CUJs)**
— the end-to-end goals where user failure means product failure:

1. **Discover CUJs systematically across four archetypes** (inspecting routes/
   commands, specs, support tickets, or telemetry when available):
   * **Daily 80% Core Loop:** What users repeat dozens of times per session
     (`Filter/Locate -> Inspect -> Act -> Next Item`).
   * **Urgent Triage / Error Recovery:** Diagnosing and mitigating a fault under
     time pressure (*"3 failing jobs — isolate root cause and retry/rollback"*).
   * **High-Stakes Commitment:** Money movement, production deploy, permission/key
     revocation, bulk mutation, or checkout.
   * **First-Run / Onboarding to First Value:** Zero-data state to first completed
     outcome without reading external docs.
2. **Assign each CUJ an Interaction & Latency Budget + Friction Log:**
   * Score on **Frequency × Criticality**, promote the daily 80% views to `0–1`
     click/keystroke from launch, and budget **step count, hand-homings (`H = 0`
     target), pointer distance, and latency** (`<= 100 ms` instant step, `<= 1 s`
     navigation/query flow; see CUJ Friction Log template in
     [references/dashboards-and-poka-yoke.md](references/dashboards-and-poka-yoke.md)).
   * Match visual density and atmosphere to the domain (`Compact` calm-neutral
     workbenches for ops/dev/trading tools vs. spacious editorial hierarchy for
     consumer reading — never generic 3-card marketing templates on work tools).

---

## 2. Minimize Time-to-Action (Fitts, Steering, Hick & KLM-GOMS)

Measure control efficiency as **physical + cognitive time per task**, not merely
"fewer screens":

1. **Fitts's Law ($T = a + b \log_2(1 + D/W)$) — Shrink $D$, Grow $W$:**
   * **Colocate sequential controls:** Keep `Search/Filter -> Table Row -> Row/
     Selection Action` spatially proximate. Never force the user to select an
     item at bottom-left and travel `1,800 px` to top-right to act on it; provide
     inline row actions, a selection-anchored action bar, or a context menu/
     shortcut right at the cursor/focus.
   * **Generous hit geometry:** Make frequent interactive targets wide and padded
     (never tiny unpadded glyph targets; zero dead gap between a label and its
     checkbox/radio/switch). On full-screen desktop apps, leverage screen edges
     and corners where pointer overshoot stops naturally (`W -> infinity`).
   * **Ban Steering-Law tunnels ($T = a + b \int ds / W(s)$):** Replace cascading
     hover submenus and 2 px splitter/scrollbar hunting with click-pinned menus,
     command palettes, or wide grab zones (`>= 8–12 px` invisible hit halo).
2. **KLM-GOMS — Eliminate Hand-Homing (`H ≈ 0.4 s` each way) via Keyboard Paths:**
   * Switching hands `Keyboard -> Mouse -> Keyboard` + pointing (`P ≈ 1.1 s`)
     adds `~2 s` per field! High-frequency workflows must support **zero-homing
     keyboard execution**:
     * Auto-focus the primary search/input when opening a dialog, picker, or
       filterable view (`Enter` submits, `Esc` cancels/closes).
     * Provide **discoverable, IME-safe keyboard shortcuts** for common views and
       actions (e.g., command palette `Cmd/Ctrl+K`, `/` to focus filter, arrow or
       `j/k` list traversal, single-key/chord actions on selected items),
       displaying keycap hints in tooltips/menus/TUI footers — and **suppressing
       `Enter`, `Esc`, and single-key shortcuts whenever an Input Method Editor
       (`isComposing` / CJK or dead-key preedit) is actively composing**!
     * Support **inline cell/field editing** and **multi-select batch actions**
       instead of forcing `Open modal -> Edit -> Save -> Close` N times.
3. **Hick–Hyman Law ($T = b \log_2(n + 1)$) — Compress Choice & Pre-Fill Defaults:**
   * **One primary action per view** (`ui-colors` gives only that one solid
     accent fill). Cap visible peer secondary actions at `3–4`; move rare actions
     into an overflow menu or command palette.
   * **Smart defaults:** Pre-select the safe 80% option, remember recent filter/
     sort/column state per view, and pre-fill computable fields rather than
     interrogating the user on blank forms.

---

## 3. Common Views & Dashboard Architecture (3-Second Glance Rule)

Dashboards and operational views exist to drive decisions, not decorate screens:

1. **Shneiderman's Hierarchy (*Overview -> Zoom & Filter -> Details on Demand*):**
   * **Top summary band (`<= 5` primary signals):** Answers *"Is the system
     healthy, and what needs my attention right now?"* within **3 seconds**.
   * **Always show context with numbers:** A raw metric (`412 ms` or `$18,400`)
     is uninterpretable alone. Pair every headline KPI with its **target/SLO
     threshold, delta (`+14% vs 7d`), or compact sparkline**.
   * **High data-ink ratio:** Cut decorative gauges, 3D charts, heavy gridlines,
     and redundant legends (`ui-layout` groups with whitespace first). Use
     pre-attentive channels (position, bar length, OKLCh lightness/semantic
     status cue + icon) so anomalies pop out before conscious reading.
2. **Every Anomaly Is a Control:**
   * Never build dead-end charts or status cards. Clicking or pressing `Enter` on
     `"7 Failing Jobs"` or a latency spike must immediately filter or drill into
     those exact 7 records with the remediation action ready.
3. **Consistent Spatial Anchors:**
   * Keep global navigation, tenant/environment indicators, search/command entry,
     and primary view actions in identical screen zones across every view so
     spatial muscle memory transfers everywhere.

---

## 4. Poka-Yoke: Design So Wrong Actions Are Hard to Make

Treat "user error" as an interface design bug. Apply five defensive layers in
order of strength:

| Poka-Yoke Layer | Principle | Concrete Pattern |
| --- | --- | --- |
| **1. Eliminate the hazard** | Make illegal values unrepresentable | Use constrained pickers, segmented controls, date-range bounds, or entity comboboxes instead of raw free-text IDs/dates; auto-trim whitespace on pasted keys/codes. |
| **2. Expose units, modes & state at the locus of attention** | Users read what they are clicking/typing, never distant status bars | Label explicit units/scales/timezones right on the field (`Timeout (ms)`, `Price (USD)`, `Schedule (UTC)`). Show active environment/mode badges (*`PRODUCTION`*, *`Read-Only`*, *`Regex`*) directly on the header/input border. |
| **3. Preview blast radius before execution** | Replace abstract actions with concrete consequences | Before applying bulk edits, filters, queries, or deletions, display live affected scope (*"Matches 248 active users in EU-West; 0 running jobs interrupted"*). |
| **4. Prefer instant Undo over reflexive confirmation popups** | Routine popups train blind muscle-memory `"OK"` clicking | For reversible operations (archive, move, assign, edit, filter reset), execute **immediately** and provide `Cmd/Ctrl+Z` + an actionable **Undo** toast (`>= 6 s`, paused on hover/focus). |
| **5. Graduated friction for true one-way doors** | Match physical/cognitive friction to irreversibility | Separate destructive controls spatially from `Save`/`Submit`; use danger semantics + specific verb-count copy (*"Delete 3 databases"*, never *"Yes"*/*"OK"*); require two-step arming or typing the target identifier when blast radius is catastrophic. |

---

## 5. State Continuity, Async Hygiene & Clear Microcopy

* **Addressable, shareable view state:** Sync active filters, search query, sort
  column, selected tab, time window, and inspected record ID into addressable
  state (URL query params on Web, copyable deep-link / CLI args / persisted
  workspace state on Desktop/TUI, state restoration on Mobile) so Back/Forward,
  refresh/relaunch, and sharing a link with a teammate preserve exact context.
* **Preserve user input & focus across async updates:** Background polling,
  streaming refreshes, or UI hydration **must never** steal focus, reset cursor/
  scroll offset, or overwrite in-progress user typing! Keep pending buttons at
  their **exact original width with their text label intact** alongside the busy
  indicator, and apply **anti-flicker hysteresis** (`~150 ms` delay before
  showing a spinner/skeleton; `~300 ms` minimum hold once shown).
* **Locale-aware numeric & paste Poka-Yoke:** Never silently misparse `1.234` vs
  `1,234` across locales — accept canonical pasted formats, trim stray whitespace,
  and echo the parsed magnitude/currency clearly before commitment.
* **Verb + Object control labels:** Write *"Export 42 rows (CSV)"*, *"Discard
  draft"*, or *"Revoke API key"* — never ambiguous dialog pairs like *"Cancel /
  OK"* or *"Yes / No"* on a question like *"Cancel unsaved changes?"*.
* **Three-part error messages:** Every validation or runtime error states **(1)
  what failed**, **(2) why / which constraint tripped**, and **(3) the exact action
  to fix or retry** — preserving everything the user already typed!
* **Actionable empty states:** Distinguish *"Zero items exist yet"* (explain what
  belongs here + offer the primary `Create / Import` button) from *"Zero items
  match current filters"* (show active filters + offer a 1-click `Clear filters`
  control).

---

## Before You Finish (`ui-ergonomics` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Frequent 2-step action requires pointer travel across opposite screen corners | Colocate inline action, selection bar, context menu, or keyboard shortcut |
| High-frequency table/form workflow requires `Mouse -> Keyboard -> Mouse` per item | Add keyboard navigation, auto-focus, `Enter`/`Esc`, and shortcut hints |
| Cascading hover-only submenu or `< 6 px` resize/action target | Use click-opened menu / command palette and >= 24 px pointer floor (>= 44–48 dp/pt touch) |
| `"Are you sure?"` modal on a routine reversible action | Delete modal; execute immediately and add **Undo** (`Cmd/Ctrl+Z` + toast) |
| Destructive button sits adjacent to `Save` or says `"OK"` / `"Confirm"` | Separate spatially, apply danger token, name exact verb + target count |
| Numeric input or table column omits unit, currency, or timezone | Add explicit unit suffix/adornment (`ms`, `GiB`, `USD`, `UTC`) |
| Disabled submit button with zero explanation of what is missing | Keep enabled and validate inline on submit, or surface missing prerequisite beside control |
| Dashboard shows raw totals with no baseline, threshold, or drill-down link | Add target/delta/sparkline and make anomalies clickable filters |
