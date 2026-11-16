---
name: ui-colors
description: >-
  Perceptual UI color systems in OKLCh and OKLab for web, desktop, mobile, GPU
  shaders, and TUI: constant-hue ramps, semantic tokens, data-visualization
  scales, WCAG 2.2 and APCA contrast checks, and a palette script with codegen
  for sRGB, P3, and ANSI. Use when choosing or generating a palette, theme,
  light and dark modes, or chart colors, or when checking contrast.
last_updated: 2026-11-15
---

# Perceptual Color Systems in OKLCh & OKLab (`ui-colors`)

Designs, generates, and audits interface and dashboard color systems from
**perceptual color science first principles** — authoring every ramp, semantic
token, contrast adjustment, and gradient in **OKLCh ($L, C, h$) / OKLab ($L, a,
b$)** and compiling down to whatever representation the target GUI API consumes
(`oklch()`, packed `0xRRGGBBAA` integers, normalized `[f32; 4]` GPU linear floats,
`QColor`/`Color32`/`ImU32`, or 24-bit TUI ANSI sequences).

* **Never eyeball hex ramps or guess contrast:** Run the bundled zero-dependency
  CLI [`scripts/oklch_palette.py`](scripts/oklch_palette.py) to generate
  gamut-clamped OKLCh ramps, audit WCAG 2.2 + APCA $L_c$ contrast pairs, and emit
  compile-time constants in Rust, C++, Go, CSS, or JSON.
* Consult [references/oklch-compile-time.md](references/oklch-compile-time.md)
  for closed-form OKLCh -> sRGB/P3 math, `const fn` / `constexpr` compile-time
  helpers, dark-mode tuning, and dashboard data-visualization scales.

---

## 1. Why OKLCh / OKLab First (And How Non-Web GUIs Use It)

RGB and HSL distort human perception: in HSL, `hsl(60, 100%, 50%)` (yellow,
OKLCh $L \approx 0.97$) and `hsl(240, 100%, 50%)` (blue, OKLCh $L \approx 0.45$)
claim identical `"50% lightness"` while differing by more than `2x` in perceived
luminance, and interpolating sRGB muddies midpoints and shifts hue.

* **Author in OKLCh ($L \in [0, 1]$, $C \ge 0$, $h \in [0^\circ, 360^\circ)$):**
  * **$L$ (Perceived Lightness):** Orthogonal brightness control — changing $L$
    predictably changes contrast without warping hue.
  * **$C$ (Chroma):** Vividness — clamping $C$ via binary search while holding
    $(L, h)$ fixed maps out-of-gamut colors cleanly onto sRGB or Display P3
    without hue shift!
  * **$h$ (Hue angle):** Constant perceptual hue across an entire ramp.
* **Interpolate & blend in OKLab:** Linear `lerp` in Cartesian $(L, a, b)$
  produces smooth, mud-free gradients, hover blends, and chart heatmaps (use
  OKLCh cylindrical `lerp` only when deliberately traversing around the hue
  wheel).
* **Compile-time translation for non-OKLCh GUI APIs:** When the target toolkit
  accepts only sRGB `u8`/`u32` or linear floats (C/C++, Rust `egui`/`iced`/
  `Slint`/`ratatui`, Go, Qt, ImGui, SwiftUI/Compose/Flutter, GPU shaders), keep
  **OKLCh `(L, C, h)` as the source of truth** in compile-time constructors
  (`constexpr oklch(...)` / `const fn oklch(...)`) or codegen via
  `scripts/oklch_palette.py` — zero runtime cost, full perceptual control!
  *(When editing a legacy project that already standardizes on hex tokens and no
  migration was requested, compute in OKLCh via the script and emit the project's
  existing token notation cleanly.)*

---

## 2. Build Role-Driven Ramps, Not Decorative Swatches

1. **Minimal ramp inventory:**
   * **1 Neutral ramp** (achromatic $C = 0$, or subtly tinted $C \in [0.004,
     0.012]$ locked to the brand hue $h$ for cohesive surfaces).
   * **1 Primary Accent ramp** (plus a second accent *only* when two peer
     categories must separate at a glance).
   * **Semantic Status ramps** (`success` $\approx 145^\circ$, `warning`
     $\approx 75^\circ$, `danger` $\approx 25^\circ$, `info` $\approx 250^\circ$)
     — keep every semantic hue at least `>= 15°` apart from the accent hue so
     primary actions never resemble danger or warning states!
2. **Perceptual ramp geometry (`11` or `12` steps):**
   * **Constant $h$** end to end.
   * **Bell-shaped chroma $C(L)$:** Peak vividness in mid-lightness ($L \approx
     0.55\text{–}0.65$), tapering smoothly near white and near black so pale
     surface tints (`step 50/100`) don't glow neon and deep darks (`step 950`)
     don't look muddy. Scale chroma as a *fraction of that hue's sRGB gamut cusp*
     so yellow/cyan ramps match blue/red ramps in perceived weight.
   * **Finer $L$ steps at surface extremes:** Space light surface steps tightly
     ($\Delta L \approx 0.035\text{–}0.05$ for `page -> subtle card -> hover ->
     border`) and mid-ramp steps wider ($\Delta L \approx 0.07\text{–}0.10$).
     Stop short of pure `0.0` black and `1.0` white on ramp endpoints.

---

## 3. Two-Tier Token Seam: Primitives vs. Semantic Roles

Components **never** reference raw hex/RGB literals or hue-named primitives
(`blue_600`):

* **Tier 1 — Primitive Ramp (`private` to theme layer):** Named by hue + step
  (`neutral_100`, `blue_600`).
* **Tier 2 — Semantic Role Tokens (`public` to UI widgets):** Named strictly by
  job (`bg_canvas`, `bg_surface`, `bg_elevated`, `bg_interactive_hover`,
  `border_subtle`, `border_strong`, `text_primary`, `text_secondary`,
  `text_muted`, `accent_solid`, `accent_text`, `danger_solid`, `focus_ring`).
  * **Strict role discipline:** Never pass a `border_*` token to text color or a
    `text_*` token to a background fill; when themes adjust border subtlety,
    borrowed text breaks silently.
  * **One filled primary action per view:** Reserve `accent_solid` background fill
    for the view's single primary action (`ui-ergonomics`); peer secondary
    controls stay neutral/outlined, and calm `0`-exception dashboard states stay
    neutral so real anomalies command 100% of chroma!

---

## 4. Dark Mode, High Contrast & Dashboard Data-Viz Scales

1. **Dark mode is re-tuned, never inverted:**
   * Swap semantic mappings, then **(a) reduce accent/status chroma by `~15–25%`**
     (full light-mode chroma halates on dark backgrounds), **(b) widen $\Delta L$
     between dark elevation layers** (`bg_canvas` $L \approx 0.14$, `bg_surface`
     $L \approx 0.18$, `bg_elevated` $L \approx 0.22$ — dark steps need *lighter*
     elevations to convey depth since drop shadows disappear on dark surfaces),
     and **(c) re-measure every contrast pair** because perceptual polarity is
     asymmetric!
2. **Increased-contrast / Forced-colors mode:** Provide sharpened border and
   text tokens (`border_subtle` stepped up to $\ge 3:1$, `text_secondary` stepped
   toward `text_primary`) when OS high-contrast / `prefers-contrast: more` is
   active.
3. **Dashboard & chart palettes (Large-data clarity):**
   * **Sequential numerical data:** Monotonic $L$ ramp in OKLab/OKLCh (`L: 0.92 ->
     0.30`) so grayscale and color-vision-deficient (CVD) users still read order
     accurately.
   * **Diverging data (e.g., PnL / latency delta around `0`):** Two CVD-safe hues
     (e.g., Blue $255^\circ$ <-> Neutral $L=0.95$ or $0.20$ <-> Amber/Vermilion
     $45^\circ$) matched at identical $L$ per step on both arms!
   * **Categorical series (`<= 6–8` max):** Distinct OKLCh hues separated by CVD-
     safe lightness offsets (avoiding isoluminant red $25^\circ$ vs green
     $140^\circ$ at identical $L$; pair series with line dash/marker shapes or
     direct end-of-line labels).

---

## 5. Measure Contrast on Composited Surfaces (Never Estimate)

Always compute contrast against the **actual composited background** (accounting
for alpha blending or worst-case translucent backdrop):

| Element Role | WCAG 2.2 AA Floor | APCA $\|L_c\|$ Target |
| --- | --- | --- |
| Body & table data text | `>= 4.5 : 1` (`7:1` AAA) | `>= 75` (`90` preferred for dense `12–14px` data) |
| Large text (`>= 24px` or `>= 18.67px` bold) / headlines | `>= 3.0 : 1` | `>= 60` (`>= 45` above `36px`) |
| Interactive control boundaries, focus rings, icons, chart series | `>= 3.0 : 1` | `>= 30–45` |

* **Fixing a failing pair:** Adjust **OKLCh Lightness $L$** while holding $(C, h)$
  fixed (clamping $C$ if $L$ nears `0` or `1`), then re-run
  `scripts/oklch_palette.py check` to prove the rendered sRGB bytes pass.
* **Redundant cue rule (`ui-accessibility`):** Never encode status, diff polarity,
  or validation failure by color alone — pair with an icon, +/- sign, badge
  label, or pattern.

---

## Before You Finish (`ui-colors` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Raw `#hex` / `rgb()` / `Color::from_rgb(...)` literal inside a widget | Reference a semantic role token backed by the OKLCh palette |
| Ramp built by stepping HSL lightness or naive sRGB lerp | Regenerate in OKLCh/OKLab via `scripts/oklch_palette.py ramp` or compile-time helper |
| Naive RGB channel clamp `[0..255]` on vivid OKLCh values | Clamp **chroma $C$** via binary search at fixed $(L, h)$ so hue never shifts |
| White text on mid-lightness accent (`L > 0.63`, e.g. `#3b82f6` = `3.68:1`) | Darken solid button fill (`L ≈ 0.53–0.56`) or switch to dark text and measure |
| Dark mode created by reversing ramp indices `50 <-> 950` | Re-tune dark surface $L$ steps (`0.14 / 0.18 / 0.22`), drop accent chroma, remeasure APCA |
| Dashboard paints every row/badge in saturated red/green/blue | Keep normal state neutral; reserve high chroma for exceptions and single primary action |
