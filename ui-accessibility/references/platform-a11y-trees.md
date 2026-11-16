# Cross-Platform Accessibility Trees & Composite Keyboard Contracts (`ui-accessibility`)

Reference mapping universal accessibility concepts onto native desktop, mobile,
GPU/immediate-mode, terminal TUI, and web toolkits, followed by standard keyboard
contracts for composite widgets.

---

## 1. Cross-Platform Accessibility Tree Mapping

Every UI stack maps the same five semantic concepts (`Role`, `Name`, `Value/State`,
`Relationships`, `Live Announcement`) to the host OS accessibility bus:

| Universal Concept | Web (HTML / WAI-ARIA) | Apple (`SwiftUI` / `AppKit` / `UIKit`) | Android (`Compose` / `Views`) | Windows (`WinUI` / `WPF`) & Cross-Platform (`Qt` / `GTK` / `Flutter` / `AccessKit`) | Terminal TUI (`ratatui`, `bubbletea`, `textual`) |
| --- | --- | --- | --- | --- | --- |
| **Role** | Native element (`<button>`, `<dialog>`) or `role="..."` | Native view or `.accessibilityAddTraits(...)` / `NSAccessibility.Role` | `Modifier.semantics { role = Role.Button }` | `AutomationProperties` / `QAccessible::Role` / `GtkAccessibleRole` / `Semantics(button: true)` / `accesskit::Role` | Place real terminal cursor on active cell; provide `--plain` / accessible line mode for screen-reader streams |
| **Accessible Name** | Visible `<label>`, text content, `aria-labelledby`, `aria-label` | `.accessibilityLabel("...")` | `contentDescription` / `semantics(mergeDescendants = true)` | `AutomationProperties.Name` / `QWidget::accessibleName` / `accesskit::Node::set_label` | Visible ASCII/UTF-8 label adjacent to cursor; avoid unlabeled PUA NerdFont icons |
| **Value & State** | `checked`, `aria-expanded`, `aria-selected`, `aria-invalid`, `aria-valuetext` | `.accessibilityValue("250 ms")`, `.isSelected` | `stateDescription = "Expanded"`, ` toggleableState` | `TogglePattern`, `ExpandCollapsePattern`, `RangeValuePattern`, `accesskit::Toggled` | Explicit text marker (`[x]` vs `[ ]`, `▸` vs `▾`, `ACTIVE`) — never color-only ANSI! |
| **Helper / Error Link** | `aria-describedby` / `aria-errormessage` | `.accessibilityHint("...")` or combined value/error label | `semantics { error("...") }` | `AutomationProperties.HelpText` / `DescribedBy` / `QAccessible::Description` | Inline status/error row rendered immediately adjacent + status-bar summary |
| **Decorative Hide** | `alt=""` or `aria-hidden="true"` | `.accessibilityHidden(true)` | `contentDescription = null` (unmerged decorative) | `AutomationView="Raw"` / ignore in `AccessKit` / `ExcludeSemantics` | Avoid decorative box-drawing spam inside readable data cells (`──` repeated 80x reads aloud!) |
| **Polite Live Update** | `aria-live="polite"` / `role="status"` | `AccessibilityNotification.Announcement(msg)` | `liveRegion = LiveRegionMode.Polite` | `AutomationPeer.RaiseNotificationEvent` / `GtkAccessible::announce` / `SemanticsService.announce` | Dedicated quiet status line + optional terminal title/BEL on completion |
| **Reduced Motion Query** | `@media (prefers-reduced-motion: reduce)` | `@Environment(\.accessibilityReduceMotion)` / `NSWorkspace.accessibilityDisplayShouldReduceMotion` | `Settings.Global.ANIMATION_DURATION_SCALE == 0f` | `SystemParametersInfo(SPI_GETCLIENTAREAANIMATION)` / `GtkSettings:gtk-enable-animations` | Disable ASCII spinner frames (`⠋⠙⠹`) -> static `[..]` / `[OK]` so braille displays don't thrash! |

---

## 2. Terminal / TUI Accessibility Specifics

Terminal screen readers (`orca`, `NVDA`, `VoiceOver` in Terminal/iTerm2, `TDSR`,
`fenrir`) track the **hardware terminal cursor** and diff character cells:

1. **Park the real terminal cursor on the focused control/row:** Even if you hide
   the blinking cursor visually via ANSI `DECTCEM` and draw an OKLCh highlight bar,
   consider moving the actual `(row, col)` cursor position to the focused cell edge
   before flushing each frame — screen magnifiers and braille displays track cursor
   coordinates!
2. **Never use Private Use Area (PUA) NerdFont glyphs alone:** Screen readers read
   unmapped PUA codepoints as `"unknown character"` or hex gibberish. Pair icons
   with text labels or provide an ASCII/Unicode-clean icon fallback.
3. **Kill `60 Hz` braille/speech thrash:** Animated Braille spinners (`⠋⠙⠹⠸`) or
   ticking elapsed-millisecond counters redraw the screen buffer `10–60x/s`, causing
   terminal screen readers to re-announce endlessly. Respect `NO_COLOR`, `TERM=dumb`,
   and `--no-anim` / reduced-motion flags.

---

## 3. Standard Keyboard Contracts for Composite Widgets

Users carry muscle memory across apps. Do not invent bespoke navigation keys when
standard composite contracts apply:

| Composite Widget | `Tab` Behavior | Internal Navigation Keys | Activation / Dismissal |
| --- | --- | --- | --- |
| **Tabs (`TabList`)** | `1` `Tab` stop on active tab (`Tab` moves into panel content) | `Left`/`Right` (or `Up`/`Down` on vertical tabs), `Home`/`End` | Automatic activation if panel switches `< 50 ms`; `Enter`/`Space` if panel triggers network load |
| **Menu / Context Menu / Command Palette** | Focus trapped until closed | `Up`/`Down`, `Home`/`End`, `Right` opens submenu, `Left` closes submenu, character typeahead | `Enter` (or `Space` on menu items) invokes & closes; `Esc` closes & restores trigger focus |
| **Combobox / Filterable Picker** | `1` `Tab` stop on input | `Down`/`Up` moves active option highlight while text cursor stays in input! | `Enter` selects highlighted option; `Esc` closes popup (second `Esc` clears filter if desired) |
| **Data Grid / Table (`ui-performance`)** | `1` `Tab` stop enters grid at last-focused cell/row (`Cmd/Ctrl+Home`/`End` jumps bounds) | `Up`/`Down`/`Left`/`Right`, `PageUp`/`PageDown`, `Space` toggles row selection (`Shift+Up/Down` range-selects) | `Enter` / `F2` enters cell edit or opens row detail; `Esc` cancels edit back to grid navigation |
| **Tree View** | `1` `Tab` stop on active node | `Up`/`Down` visible nodes; `Right` expands closed node (or moves to first child if open); `Left` collapses open node (or moves to parent) | `Enter` opens/activates node; `Space` toggles selection checkbox if multi-select |
| **Toolbar / Segmented Control** | `1` `Tab` stop on active/first button | `Left`/`Right`, `Home`/`End` (wrapping optional) | `Space` / `Enter` activates focused button |
| **Modal Dialog / Alert Dialog** | Cycles strictly among controls *inside* dialog | Standard `Tab` / `Shift+Tab` | `Enter` triggers default safe button (never auto-default an irreversible delete!); `Esc` cancels & restores trigger focus |

---

## 4. Virtualized & Canvas Accessibility Without $O(N)$ Overhead

When `ui-performance` virtualizes `1,000,000` rows or draws a `2D Canvas`/`GPU`
grid:

* **Expose total set size & 1-based position:** Populate `setSize = 1_000_000` and
  `posInSet = i + 1` (`aria-rowcount` / `aria-rowindex`, `AccessibilityNodeInfo.CollectionInfo`,
  `NSAccessibilityIndexAttribute`) on the `~40` currently mounted rows so screen
  readers announce *"Row 4,812 of 1,000,000"* instead of *"Row 12 of 40"*.
* **Programmatic scroll-on-focus:** Handling `PageDown`, `Home`, `End`, or screen-
  reader `ScrollIntoView` updates the virtual scroll offset *first*, mounts the
  target slice synchronously within the frame, and places focus on the materialized
  cell.
