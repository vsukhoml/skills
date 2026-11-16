# Semantic Type Scales, OpenType Features & Cross-Platform Mapping (`ui-typography`)

Reference for defining scalable semantic type tokens, enabling tabular numerals and
glyph disambiguation across GUI toolkits, and handling bidirectional text safely.

---

## 1. Reference Semantic Type Scale (Modular & Role-Named)

Define `~8–10` composite tokens rather than raw sizes. All sizes below represent
`1x` default user preference (`1 rem = 16 px` / `16 sp` / `16 pt`) and scale
linearly or nonlinearly with OS font-size accessibility settings:

| Semantic Token | Size (`rem` / `sp` / `pt`) | Line-Height (Unitless) | Weight | Tracking | Required OpenType / Font Features |
| --- | --- | --- | --- | --- | --- |
| `display_lg` | `2.00` (`32`) | `1.15` | `650–700` | `-0.02em` | `kern`, `liga` |
| `heading_lg` | `1.50` (`24`) | `1.20` | `600` | `-0.015em` | `kern`, `liga` |
| `heading_md` | `1.125` (`18`) | `1.28` | `600` | `-0.01em` | `kern` |
| `heading_sm` | `0.9375` (`15`) | `1.33` | `600` | `0` | `kern` |
| `body_md` | `0.9375–1.0` (`15–16`) | `1.50` | `400` | `0` | `kern`, `liga` |
| `body_sm` | `0.8125–0.875` (`13–14`) | `1.45` | `400` | `+0.005em` | `kern` |
| `label_ui` | `0.8125–0.875` (`13–14`) | `1.25` | `500` | `+0.005em` | `kern` |
| `caption_eyebrow` | `0.75` (`12`) | `1.30` | `500–600` | `+0.05em` (if caps) | `kern` |
| `metric_kpi` | `1.75` (`28`) | `1.15` | `600` | `-0.015em` | **`tnum`, `lnum`** |
| `table_numeric` | `0.8125–0.875` (`13–14`) | `1.30` | `400–500` | `0` | **`tnum`, `lnum`, `zero`** |
| `code_mono` | `0.8125` (`13`) | `1.45` | `400` | `0` | Monospace + **`zero`**, **`calt` off** if ligatures obscure syntax |

---

## 2. Enabling Tabular Numerals (`tnum`) & Slashed Zero (`zero`) Across Toolkits

Never resort to switching the entire UI font to Courier just to stop numbers from
jumping — almost every modern UI proportional font (`SF Pro`, `Inter`, `Segoe UI`,
`Roboto`, `IBM Plex Sans`, `Noto Sans`) ships native OpenType **`tnum`** glyphs!

| Target Stack | How to Enable Tabular Figures (`tnum`) & Disambiguated Zero (`zero`) |
| --- | --- |
| **Web (CSS)** | `font-variant-numeric: tabular-nums lining-nums slashed-zero;` (or `font-feature-settings: "tnum" 1, "zero" 1;`) |
| **Apple (`SwiftUI` / `AppKit` / `UIKit`)** | `Text(val).monospacedDigit()` in SwiftUI; `UIFont.monospacedDigitSystemFont(ofSize:weight:)` or `kNumberSpacingType: kMonospacedNumbersSelector` in CoreText |
| **Android (`Jetpack Compose` / `Views`)** | `TextStyle(fontFeatureSettings = "tnum, zero")` |
| **Flutter** | `TextStyle(fontFeatures: [FontFeature.tabularFigures(), FontFeature.slashedZero()])` |
| **Qt (`QFont` — Qt 6.7+)** | `font.setFeature(QFont::Tag("tnum"), 1); font.setFeature(QFont::Tag("zero"), 1);` |
| **GTK / Pango (`Linux`)** | Pango attribute `font-features="tnum=1, zero=1"` (`pango_attr_font_features_new("tnum=1")`) |
| **Windows (`WinUI` / `WPF` / `DirectWrite`)** | `Typography.NumeralAlignment="Tabular" Typography.SlashedZero="True"` / `DWRITE_FONT_FEATURE_TAG_TABULAR_FIGURES` |
| **Native GPU / C / C++ / Rust (`HarfBuzz` / `cosmic-text` / `parley`)** | Pass `hb_feature_from_string("tnum", -1, &feat)` during glyph shaping; cache shaped glyph runs (`ui-performance`) |
| **Immediate-Mode (`Dear ImGui` / `egui` / `Slint`)** | Bake `tnum` into font rasterizer config (`freetype` / `fontdue` / `swash`) or bind the semantic `mono` family for numeric/metric columns |
| **Terminal TUI** | Inherently `1-cell` tabular for ASCII `[0-9.+-]`! Beware wide East Asian / emoji codepoints (`wcwidth == 2` vs `1`): always measure column width via **Unicode `wcwidth` / `unicode-width`**, never `str.len()` byte count or UTF-16 code units! |

---

## 3. Middle-Ellipsis Helper Logic (Preserving Prefix + Suffix)

Standard end-truncation (`text-overflow: ellipsis`) destroys usability on paths,
cloud ARNs, Kubernetes pod names (`payment-worker-7c9f8d6b4-x92kq`), and UUIDs.
Compute middle truncation deterministically when slot character capacity $M$ is
known (or binary-search shaped width):

```text
function middleEllipsize(s, maxGraphemes, tailKeep = ceil(maxGraphemes * 0.4)):
    if maxGraphemes <= 0:
        return ""
    clusters = graphemeClusters(s)   // NEVER slice raw UTF-8 bytes or UTF-16 surrogates!
    n = len(clusters)
    if n <= maxGraphemes:
        return s
    if maxGraphemes == 1:
        return "…"
    if maxGraphemes == 2:
        return clusters[0] + "…"
    tailKeep = max(0, min(tailKeep, maxGraphemes - 2))
    headKeep = maxGraphemes - tailKeep - 1
    return join(clusters[0 : headKeep]) + "…" + join(clusters[n - tailKeep : n])
```

* **Grapheme-cluster safety:** Always slice on **extended grapheme clusters** (`UAX #29`),
  never raw UTF-8 byte offsets (panics/corrupts multi-byte chars) or UTF-16 code
  units (splits surrogate pairs, flag emojis, or Devanagari/Arabic combining marks).

---

## 4. Unicode Width, Normalization, BiDi & IME Engineering Cheatsheet

### 4.1 Display Width (`UAX #11`), Emoji Presentation & Terminal Mode `2027`

Monospace grids, terminal UIs, and canvas editors break borders whenever byte
length (`len`), UTF-16 code units, or outdated libc `wcwidth()` are used to place
cells:

| Unicode Construct | UTF-8 Bytes | Scalar Code Points | Grapheme Clusters (`UAX #29`) | Terminal / Monospace Cells (`UAX #11`) |
| --- | --- | --- | --- | --- |
| ASCII `"A"` | `1` | `1` | `1` | **`1`** |
| Decomposed `"e\u{0301}"` (`NFD` `"é"`) | `3` | `2` | `1` | **`1`** (`0` for combining mark) |
| CJK ideograph `"漢"` / Fullwidth `"Ａ"` | `3` | `1` | `1` | **`2`** (pad odd trailing border cell!) |
| Text-presentation warning `"⚠\u{FE0E}"` (`VS15`) | `6` | `2` | `1` | **`1`** (explicit monochrome symbol) |
| Emoji-presentation warning `"⚠\u{FE0F}"` (`VS16`) | `6` | `2` | `1` | **`2`** (color emoji glyph) |
| ZWJ family emoji `"👨‍👩‍👧"` | `18` | `5` | `1` | **`2`** (requires grapheme-aware width / DEC `2027`) |

* **Lightweight library choices (zero full-ICU bloat):** Use compact generated
  Unicode tables (`libgrapheme` in C, `unicode-segmentation` + `unicode-width` or
  modular `ICU4X` in Rust/C++/Wasm, `uniseg` in Go, `Intl.Segmenter` in JS).
* **Terminal DEC Mode `2027`:** Query `CSI ? 2027 $ p` on startup and enable `CSI ?
  2027 h` when supported so the terminal emulator and TUI agree on `UAX #29`
  multi-codepoint grapheme cluster widths.
* **NFC normalization at input seams:** Normalize user-entered strings and file-
  picker paths (`macOS APFS` emits `NFD`) via `NFC` before indexing or comparing so
  `"café"` (`U+00E9`) always matches `"cafe\u{0301}"`.
* **IME Preedit geometry:** Subscribe to platform text-input composition events
  (`NSTextInputClient`, `WM_IME_*`/`ITfContext`, Wayland `zwp_text_input_v3`, Qt
  `inputMethodEvent`, DOM `compositionupdate`), draw the uncommitted preedit string
  underlined with accurate `2`-cell CJK advancement, and return the cursor's
  screen-space rectangle so the OS candidate window pops up directly below the
  insertion point.

### 4.2 Bidirectional (`UAX #9`) Isolation

Without isolation, inserting an LTR path `/etc/ssh/sshd_config` or negative number
`-42` next to RTL text (or an RTL Arabic customer name into an English breadcrumb
`Workspace > مشروع-١ > Settings`) lets the Unicode Bidirectional Algorithm (`UAX #9`)
reorder adjacent punctuation and delimiters:

* **Universal string-level fix (works in Qt, GTK, WinUI, SwiftUI, Compose, TUI, and
  plain text):** Wrap every interpolated untrusted/dynamic value in
  **`\u{2068}` (`FIRST STRONG ISOLATE`) ... `\u{2069}` (`POP DIRECTIONAL ISOLATE`)**:
  ```text
  format("Deleted \u{2068}{}\u{2069} ({} items)", resource_name, count)
  ```
* **HTML / DOM equivalent:** `<bdi>{resourceName}</bdi>` (and `dir="ltr"` on code,
  paths, URLs, emails, phone numbers, and mathematical/metric expressions so `−14.2%`
  never flips its minus sign to the wrong side in RTL locales).
