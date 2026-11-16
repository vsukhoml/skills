---
name: ui-accessibility
description: >-
  UI accessibility for desktop, mobile, TUI, and web (WCAG 2.2 AA):
  accessibility trees (name, role, state, actions), full keyboard navigation
  and focus, hit targets, live announcements, reduced motion, forced colors,
  and 200% scaling. Use when building or auditing a screen, component, form,
  dialog, or keyboard flow for accessibility or screen-reader support.
last_updated: 2026-11-15
---

# Universal Accessibility Trees, Keyboard & Sensory Ergonomics (`ui-accessibility`)

Builds and audits interfaces so every workflow works reliably via **keyboard alone,
assistive technology (screen readers, voice control, switch devices, braille
displays), coarse/tremor pointers, high zoom (`200%+`), high contrast, and reduced
motion** — across native desktop, mobile, immediate-mode/GPU canvases, terminal UIs
(TUIs), and web browsers.

Consult [references/platform-a11y-trees.md](references/platform-a11y-trees.md) for
the cross-platform accessibility-tree mapping table (`UI Automation`,
`NSAccessibility`/`UIAccessibility`, `AT-SPI2`, `AccessKit`, `AccessibilityNodeInfo`,
WAI-ARIA, and TUI cursor tracking) and composite-widget keyboard contracts.

---

## 1. Universal Accessibility Tree Contract

Every operating system exposes UI state to assistive technologies through a
structured **Accessibility Tree** (even when pixels are painted via Skia, Metal,
Vulkan, or DOM). Every interactive or status-bearing element **must** expose five
accurate properties:

1. **Role:** What kind of control or landmark it is (`Button`, `CheckBox`, `Switch`,
   `TextField`, `ComboBox`, `Slider`, `Tab`, `Row`/`Cell`, `Dialog`, `Alert`,
   `Navigation`).
   * **Native primitives first:** Always use the toolkit's built-in control before
     attaching manual accessibility metadata to a generic box/canvas region —
     native widgets supply role, keyboard activation, OS high-contrast rendering,
     and platform action hooks together.
   * **Custom / GPU / Canvas surfaces:** Expose a synchronized accessibility subtree
     (e.g., via `AccessKit` in Rust/C++ immediate-mode UIs, `SemanticsNode` in
     Flutter/Compose, `QAccessibleInterface` in Qt, `UIAccessibilityElement` on
     Apple platforms, or virtualized DOM/ARIA nodes on Web).
2. **Accessible Name:** What specific action or field this instance represents.
   * Every control has a non-empty programmatic name (`"Revoke production key"`,
     `"Filter logs"`, `"Close panel"` — never `"button"`, `"icon"`, or a raw file/
     enum identifier).
   * **Label-in-name parity (Voice Control rule):** When visible text is shown on a
     control, its programmatic accessible name **must begin with that exact visible
     text** so speech-input users saying *"Click Export"* match reliably.
   * **Decorative graphics stay silent:** Hide purely decorative icons, dividers,
     and sparkline embellishments from the accessibility tree so screen readers do
     not chatter through noise.
3. **Value & State:** Current state (`checked` / `mixed`, `expanded` / `collapsed`,
   `selected`, `disabled`, `busy`, `invalid`, numeric `value` + `min`/`max` +
   human-readable unit string `"65%"` or `"250 ms"`). Never communicate state by
   visual styling alone!
4. **Actions & Relationships:** Programmatic `Invoke`/`Press`, `Increment`/
   `Decrement`, `Expand`, `ScrollIntoView`, plus explicit links to helper units,
   inline validation errors, and controlled panels.
5. **Screen-Space Bounds:** Accurate hit/highlight rectangle updated on scroll and
   resize so screen magnifiers, VoiceOver/TalkBack cursors, and switch scanners
   frame the right target.

---

## 2. Two Mandatory Verification Walks

Static inspection misses broken focus order and silent state updates. Walk every
created or modified view twice:

### Walk A — 100% Keyboard-Only Walk (Unplug the Pointer)

1. **Complete reachability, zero dead traps:** Every interactive action reachable by
   mouse/touch must be operable by keyboard (`Enter`/`Space` to activate, `Esc` to
   dismiss popovers/modals without trapping `Tab`). Hidden, collapsed, or background
   views behind a modal **must** be inert/unreachable by `Tab`.
2. **Composite-widget roving focus (`Tab` moves between groups, Arrows move inside):**
   * Never force `Tab` through `50` toolbar buttons, `8` tabs, or `1,000` table
     cells! Make each composite widget (`TabList`, `Toolbar`, `Menu`, `TreeView`,
     `DataGrid`, `RadioGroup`) a **single `Tab` stop** and navigate items inside it
     with **Arrow keys**, `Home`/`End`, `PageUp`/`PageDown`, and typeahead
     (`ui-ergonomics`).
3. **Predictable focus restoration & deletion survival:**
   * Opening a modal/dialog/drawer moves focus inside it (to the primary search/
     input or first control, or the safe `Cancel` button on destructive confirms);
     closing restores focus to the **exact invoking trigger**.
   * Deleting or archiving item `i` in a list moves focus deterministically to item
     `i + 1` (or `i - 1`, or the list's empty-state primary CTA) — never dropping
     focus back to the window root!
4. **Unmistakable, unobscured focus indicator:**
   * Keyboard focus renders a dedicated ring/outline with **`>= 3:1` contrast**
     against adjacent surfaces (`ui-colors`) and clear separation from selection or
     hover state.
   * **Sticky-chrome clearance:** Focused elements scrolled into view must never
     hide behind sticky headers, toolbars, or floating action bars (`ui-layout`).
5. **Fast region bypass:** Provide landmarks, pane-cycle shortcuts (`F6` /
   `Cmd/Ctrl+K`), or a visible-on-focus `"Skip to main content"` jump so keyboard
   users bypass repetitive chrome in `1` keystroke.

### Walk B — Accessibility-Tree / Screen-Reader Walk

1. **Heading & landmark outline:** Headings/section titles form a clean logical
   hierarchy (`Level 1 -> Level 2 -> Level 3` without skipping levels for visual
   sizing; style size independently via `ui-typography`).
2. **Polite vs. assertive live announcements:**
   * Async state changes that do not move focus (search result counts `"14 matches"`,
     background save `"Saved"`, Undo toasts, form summary errors) announce via a
     **polite** live notification (`NSAccessibilityAnnouncementRequested`,
     `AccessibilityLiveRegion.Polite`, `aria-live="polite"`, or terminal bell/status
     line).
   * Reserve **assertive/interrupting** alerts strictly for urgent, action-blocking
     failures (session expiry, hardware disconnect, critical production fault).
   * Throttle streaming announcements (`ui-performance`) — never flood a screen
     reader with `50` live-region mutations per second!

---

## 3. Pointer, Touch & Motor Ergonomics

1. **Hit-target geometry (`ui-ergonomics`):**
   * **Hard AA floor:** Every standalone pointer target occupies at least **`24 × 24`
     logical px (`dp`/`pt`/`CSS px`)** — either via box size or non-overlapping
     invisible padding/hit-slop spacing.
   * **Touch & high-frequency target:** **44–48 logical px** (44 × 44 pt iOS,
     48 × 48 dp Android; >= 40 px compact desktop toolbar) on touch surfaces and
     primary toolbar/row controls.
   * Zero dead unclickable gap between a control (`Checkbox`/`Radio`/`Switch`) and
     its text label.
2. **Up-event activation (Cancellation safety):**
   * Trigger actions on **pointer release (`click` / `pointerup` / `TouchUpInside`)**
     — never on raw `pointerdown` (except Piano/game keys or menu popups that don't
     mutate state) so users who mis-press can slide off the control to cancel.
3. **Single-pointer & non-path alternatives:**
   * Every drag-and-drop reorder, splitter resize, canvas pan, or multipoint pinch-
     zoom **must** also offer a single-click/tap or keyboard equivalent (e.g.,
     `Move up/down` or `Alt+Up/Down`, preset/stepped zoom `+`/`-`, numeric input).

---

## 4. Accessible Forms & Mistake Recovery

* **Persistent visible labels:** Placeholders vanish the instant typing starts and
  fail contrast; every input needs a persistent visible label (plus explicit unit/
  format hint linked programmatically, e.g., `Timeout (ms)`).
* **Inline, linked error messages:** Set programmatic `invalid` state on the field,
  link the error text to the input so AT reads it on focus, move focus to the first
  invalid field (or an anchored error summary) on submit, and **never** rely on
  disabling the submit button as the sole validation signal (`ui-ergonomics`).
* **Authentication & pasting:** Never block `Paste` or password managers/autofill on
  credentials, tokens, OTP codes, or account numbers.

---

## 5. Sensory, Contrast, Motion & Scaling Adaptation

* **Never rely on color alone (`ui-colors`):** Pair status/diff/chart colors with
  icons, text badges, `+/-` prefixes, or stroke dash patterns.
* **Honor OS `reduced-motion`:** When OS reduced-motion is active (`prefers-reduced-motion`,
  `UIAccessibility.isReduceMotionEnabled`, `ANIMATION_DURATION_SCALE == 0`, GTK
  `gtk-enable-animations`), disable parallax, auto-playing motion, spatial sliding/
  bouncing, and spinning loaders in favor of instant state changes or subtle opacity
  cross-fades (`<= 120 ms`).
* **Honor OS `high-contrast` / `forced-colors`:** Preserve real borders (`1 px`
  transparent/semantic borders that become visible under forced colors) rather than
  relying solely on drop shadows or `2%` background tints to separate cards/buttons.
* **Survive `200%` text & DPI scaling (`ui-layout`, `ui-typography`):** Scaling text
  or display DPI to `200%` (and narrowing viewports to `320` logical px) must
  reflow cleanly without clipping labels, overlapping neighbor controls, or forcing
  two-axis horizontal+vertical scrolling to read prose.

---

## Before You Finish (`ui-accessibility` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Custom box/canvas/icon handles click with no Role, Name, or `Enter`/`Space` handler | Switch to native Button/Control or wire full AT node + keyboard activation |
| Icon-only button has empty name or reads `"trash-svg"` / `"ellipsis"` | Set action-oriented accessible name (`"Delete rule"`, `"More actions for row X"`) |
| Focus outline stripped (`outline: none` / unfocused custom draw) with no `>= 3:1` replacement | Restore high-contrast focus ring cleanly separated from selection/hover |
| Modal opens while background remains `Tab`-reachable, or `Esc` loses focus to root | Trap focus in modal, bind `Esc`, restore focus to invoking trigger on close |
| `Tab` steps through every cell of a 200-row table or 12-button toolbar | Single `Tab` stop on composite widget + Arrow-key roving focus |
| Drag-only kanban/list reorder or pinch-only chart zoom | Add keyboard reorder (`Alt+Up/Down` / menu) and `+`/`-`/reset zoom buttons |
| Error shown only via red border or ephemeral self-dismissing toast | Set invalid state, link persistent inline recovery text, announce politely |
| Fixed pixel container height clips text at `200%` OS font scale | Replace fixed height with min-height + content growth / responsive wrap |
