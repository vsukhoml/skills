---
name: ui-typography
description: >-
  UI typography and Unicode text engineering for desktop, mobile, TUI, and
  web: type scales, legibility floors, tabular numerals, grapheme clusters,
  CJK and emoji width, BiDi, line wrapping, IME, and truncation. Use when
  choosing fonts or type sizes, rendering or measuring text, aligning numbers
  in tables, or fixing Unicode, emoji, RTL, or truncation bugs.
last_updated: 2026-11-15
---

# First-Principles Typography, Data Legibility & Text Rendering (`ui-typography`)

Designs and audits how text and numbers render across **native desktop toolkits,
mobile Dynamic Type systems, GPU/Canvas glyph atlases, terminal monospace grids
(TUI), and web browsers** — optimizing reading speed, glanceable numeric comparison,
and resilience across scripts and zoom levels.

Consult [references/type-and-platform-mapping.md](references/type-and-platform-mapping.md)
for semantic type-scale tokens, OpenType feature codes (`tnum`, `zero`, `cv*`),
cross-platform API mappings, and Unicode bidi-isolation patterns.

---

## 1. Semantic Type Roles & Restraint

Components **never** hardcode ad-hoc point sizes (`11px`, `13px`, `15px`, `19px`).
Bundle `(family, size, line_height, weight, tracking, font_features)` into a compact
set of **semantic role tokens**:

1. **Minimal family & weight inventory:**
   * **`<= 2` font families** (`1` proportional UI sans for prose/controls + `1`
     monospace with clear `0/O` and `1/l/I` differentiation for code, hashes, logs,
     keys, and paths). Native system UI stacks (`SF Pro`, `Segoe UI Variable`,
     `Roboto`, `Inter`/`Cantarell`) cost `0 B` of network/bundle overhead and carry
     deep multi-script fallback!
   * **`<= 3` weights** (`400` Regular for body/data, `500` Medium for UI controls/
     headers, `600–700` Semibold/Bold for primary headings and KPIs).
   * **Ban synthetic faux-bold / faux-italic** (sheared or double-struck glyphs
     blur stems on HiDPI and low-DPI alike) and **never use weight `< 400`** at
     `<= 16` logical px or light-on-dark polarity where stem irradiation erodes
     strokes (`ui-colors`).
2. **User-scalable units & optical floors (`ui-accessibility`):**
   * Express sizes in **OS-scalable units** (`rem`, Android `sp`, Apple `Dynamic
     Type` styles, Qt/GTK logical point scale) so `200%` user font scaling works
     everywhere.
   * **Desktop / Mobile sustained reading:** `14–16` logical px (`13–14` compact
     desktop dense tables; `15–17` mobile/prose).
   * **Hard legibility floor:** Never drop below **`12` logical px** (`11 px` only
     for non-essential secondary metadata with weight `>= 500` and high APCA
     contrast `|Lc| >= 75`). Scale up proportionally for 10-foot wallboards!
3. **Role-driven leading (line-height) & tracking (letter-spacing):**
   * **Display & large headings (`>= 24 px`):** Tight unitless leading (`1.10–1.25`)
     and slightly tightened tracking (`-0.01em` to `-0.025em`) so multi-line titles
     hold together visually.
   * **Multi-line body & error prose:** Open unitless leading (**`1.45–1.60`**; bump
     to `1.60–1.75` for scripts with tall stacked diacritics like Arabic, Thai, or
     Vietnamese).
   * **ALL-CAPS restraint:** Never set full sentences in uppercase (`10–15%` slower
     word-shape recognition). Limit uppercase to short `1–3` word micro-labels/
     badges with **`+0.04em` to `+0.08em`** tracking.

---

## 2. Dashboard, Table & Live-Data Numeric Discipline

Operational UIs succeed or fail on how fast an operator compares numbers without
misreading an order of magnitude:

1. **Mandatory Tabular Numerals (`tnum`) on Comparable & Changing Numbers:**
   * Enable OpenType **`tnum` (`tabular-nums`)** — or use the monospace token — on
     **every** table numeric column, live KPI counter, timer, progress percentage,
     price, latency, IP/port, and chart axis readout!
   * Proportional digits (`1` narrower than `8`) make vertical columns ragged and
     cause `60 Hz` horizontal layout jitter (`ui-performance`) whenever a live value
     ticks from `11.1%` to `88.8%`.
2. **Align Numbers on Magnitude & Put Units in the Header (`ui-layout`, `ui-ergonomics`):**
   * **`End`-align (right-align) numeric columns** formatted to **consistent decimal
     places** (`1,240.00`, `   18.50`, `    0.05`) so decimal points form a razor-
     straight vertical rail and `1,240` visually outweighs `18` at a `100 ms` glance!
   * Place the **unit, currency, or scale once in the column header** (`Latency
     (ms)`, `Size (MiB)`, `Delta (%)`) — avoid mixing `420 ms` and `1.4 s` in the
     same sortable column unless highlighted as an anomaly badge.
   * Use explicit **`+` / `−` (`U+2212` true minus, matching `+` width!)** on
     deltas, and use **`—` (em-dash) or `N/A`** in muted text for missing/null data
     so `null` is never confused with `0`!
3. **Disambiguate Identifiers (`zero` + Monospace):**
   * Render API keys, UUIDs, commit SHAs, serial numbers, hostnames, and log lines
     in the monospace role with **slashed/dotted zero (`zero`)** so `0` vs `O` and
     `1` vs `l` vs `I` are unmistakable.

---

## 3. Measure, Wrapping, Truncation & Copyability

1. **Cap reading measure at `60–75 ch` (`45–80 ch` max):**
   * Eyes lose track returning to the next line start when prose stretches beyond
     `~80` characters (`ui-layout`). Constrain documentation, settings descriptions,
     empty-state explanations, and modal body copy even inside wide panes.
   * **Never full-justify UI text** (`text-align: justify` creates uneven "rivers"
     of whitespace, especially in narrow cards or at `200%` zoom).
2. **Intentional wrapping & long-token safety:**
   * Balance short multi-line headings (`text-wrap: balance` or natural width caps)
     and break long unspaced URLs, file paths, or stack-trace symbols cleanly inside
     their container (`overflow-wrap: anywhere` / `WrapMode::WordOrChar`) so a single
     `180-char` token never blows out viewport width.
3. **Smart, Recoverable Truncation (`…`):**
   * Never truncate form labels, warning banners, or error messages — wrap them!
   * In bounded list/tree/table slots, use **middle-ellipsis (`prod-us-east-…-db-09`
     or `/var/log/…/auth.log`)** whenever items share a common prefix (`aws-arn-...`,
     file paths, container names) and differ at the suffix!
   * Every truncated value **must** remain reachable via keyboard focus and pointer
     (detail inspector, row expand, or focusable tooltip per `ui-accessibility`).
4. **Keep Data Selectable & Copyable (`ui-ergonomics`):**
   * Disable text selection (`user-select: none`) *only* on chrome controls (buttons,
     tabs, drag handles, splitters). **Never** make error messages, IDs, IP
     addresses, metrics, or table cells unselectable on desktop/web/mobile — forcing
     an operator to re-type a `36-char` request ID from a screenshot is a severe
     ergonomic defect! Provide a 1-click `Copy` action beside long tokens/commands.

---

## 4. Full Unicode Discipline: Graphemes, Wide Characters, BiDi, NFC & IME

Never equate `"1 character"` with `1 byte`, `1 UTF-16 code unit`, `1 scalar code
point`, or `1 monospace column`:

1. **UTF-8 End-to-End & `NFC` Boundary Normalization:**
   * Keep internal UI strings in valid **UTF-8** and normalize external inputs,
     search queries, clipboard pastes, and OS filenames (e.g., macOS `NFD`
     decomposed `e + U+0301` vs. Linux/Windows/Web `NFC` `U+00E9`) to **`NFC`**
     before equality checks, filtering, or cursor editing.
2. **Extended Grapheme Clusters (`UAX #29`) for Editing & Slicing:**
   * Step cursor movement (`Left`/`Right`), `Backspace`/`Delete`, character-limit
     counters, and truncation strictly on **UAX #29 Extended Grapheme Clusters**
     (e.g., via lightweight table-driven segmenters such as `libgrapheme`,
     `unicode-segmentation`, `ICU4X`, or platform segmenters) so ZWJ emojis
     (`👨‍👩‍👧`), regional flags, and Indic/Arabic combining marks are never torn in
     half!
3. **Wide Characters & Emoji Cell Geometry (`UAX #11` / TUI / Fixed Grids):**
   * In Terminal UIs, code editors, and fixed-cell layouts, compute display width
     per grapheme cluster: combining marks = `0` cells, ASCII/Latin = `1` cell,
     **CJK ideographs, Hangul, fullwidth forms, and Emoji (`VS16 U+FE0F`) = `2`
     cells** (using current Unicode width tables rather than stale libc `wcwidth`;
     enable **DEC Mode `2027`** grapheme-width negotiation on modern terminals).
   * When a `2`-cell character hits the last `1` column of a TUI box, wrap it and
     pad the trailing cell with a space so right borders never tear; append
     **`U+FE0E` (`VS15` text presentation)** on monochrome UI symbols (`⚠︎`, `✓︎`,
     `⚙︎`) when `1`-cell monochrome rendering is intended.
   * **IME Preedit & Space-less Wrapping (`UAX #14`):** Render active CJK/IME
     preedit text inline at its true `2`-cell/shaped width while reporting exact
     cursor screen bounds so the OS candidate popup anchors accurately, and break
     lines per **`UAX #14`** so space-less scripts (Chinese, Japanese, Thai, Lao,
     Khmer) wrap cleanly without ASCII spaces.
4. **Bidirectional (`UAX #9`) Isolation & Typographic Punctuation:**
   * Wrap every dynamic interpolated string (`username`, `filename`, `path`,
     `branch`, `metric`) in **Unicode First-Strong Isolate `U+2068` (`FSI`) ..
     `U+2069` (`PDI`)** (or HTML `<bdi>`), and force `LTR` isolation on paths,
     URLs, code, and signed numbers (`−14.2%`) so RTL/LTR punctuation never
     scrambles across boundaries!
   * Use real ellipsis `…` (`U+2026`), en-dash `–` (`U+2013`) for ranges, and true
     minus `−` (`U+2212`) in prose/tables — while strictly preserving **straight
     ASCII (`"`, `'`, `-`, `--`)** inside code blocks, CLI flags, and copyable
     configs.

---

## Before You Finish (`ui-typography` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| Live metric counter, timer, or numeric table column jitters width or misaligns | Enable `tabular-nums` (`tnum`) + `end`-align fixed-precision decimals |
| Mixed units (`850 ms`, `1.2 s`, `0`) scattered down one numeric column | Normalize unit into column header (`Latency (ms)`) + format `null` as `—` |
| Identical prefixes truncated at end (`arn:aws:iam::123456:role/prod-…` × 20 rows) | Use **middle-ellipsis** (`arn:…:prod-billing-reader`) preserving unique suffix |
| String sliced/truncated by `s[..20]` bytes/UTF-16 units or measured by `s.len()` in TUI | Segment by **`UAX #29` grapheme clusters** + measure columns via **`UAX #11` display width** |
| Search/filter misses macOS `NFD` accented filename or CJK `2`-wide preedit shifts borders | Normalize inputs to **`NFC`**; account for `2`-cell preedit width + cursor IME anchor |
| Error dialog or dashboard cell blocks text selection (`user-select: none` / raw label) | Enable text selection + add 1-click `Copy` button on IDs/errors/snippets |
| Body or help text stretches `1,600 px` (`210 ch`) across wide window | Constrain prose container to `<= 65–75 ch` |
| Hardcoded `px` font sizes ignore OS Dynamic Type / `200%` text zoom | Migrate to semantic role tokens in scalable units (`rem` / `sp` / Dynamic Type) |
| Weight `300` light grey text at `12 px` on dark background | Use weight `>= 400/500` and verify APCA `\|Lc\| >= 75` (`ui-colors`) |
| Dynamic filename/username scrambles punctuation in RTL/LTR mixed label | Wrap interpolated token in `U+2068`..`U+2069` (`FSI`..`PDI`) or `<bdi>` |
