---
name: ui
description: >-
  Router for the ui-* suite: UI architecture, design, and audit for CLI,
  terminal TUI, desktop, mobile, and web. Use when designing, building,
  optimizing, or reviewing a UI, CLI, dashboard, or UI diff.
last_updated: 2026-11-15
---

# First-Principles User Interface Engineering & Review (`ui`)

Designs, builds, and audits user interfaces from **human-factors, perceptual, and
frame-budget first principles** — independent of whether the target is a
**Command-Line Interface (CLI)**, terminal cell dashboard (**TUI**), native
desktop toolkit, mobile framework, GPU/immediate-mode canvas, or browser DOM/CSS.

---

## Core Engineering Philosophy

1. **Optimize Critical User Journeys (CUJs) & low interaction cost:** Map the
   3–5 end-to-end CUJs first; set explicit step and latency budgets, minimize
   pointer travel, hand-homing (`Keyboard <-> Mouse`), choice overload, and scan
   time, and keep view state addressable/shareable.
2. **Make wrong actions hard (Poka-Yoke):** Constrain inputs so invalid states
   cannot be entered, surface units and blast-radius previews at the locus of
   attention, provide instant **Undo** for routine work, and reserve deliberate
   friction for irreversible actions.
3. **Perceptual math & full Unicode correctness:** Compute color ramps and
   contrast in **OKLab / OKLCh** (compiling down to sRGB/P3/ANSI when needed),
   size spacing by Gestalt ratios, enforce tabular numerals on data, and handle
   **Unicode** cleanly (`UTF-8`, `NFC`, `UAX #29` graphemes, `UAX #11` wide/emoji
   cell widths, `UAX #9` BiDi isolation, and IME preedit composition).
4. **Respect hardware frame budgets at scale:** Hold `16.6 ms` (`60 Hz`) /
   `8.3 ms` (`120 Hz`) frame times even over $10^5\text{–}10^7$ records via
   virtualization, off-thread transforms, stream conflation, and LOD decimation.
5. **Write in the project's native idiom:** Never prescribe CSS/HTML fixes in a
   Qt, SwiftUI, Compose, Flutter, ImGui, or `ratatui` codebase — map universal
   principles to the project's actual widget/layout/token primitives.

---

## The `ui-*` Suite Router

Load the owning domain skill(s) in this order so workflow usability, responsiveness,
and accessibility are never masked by superficial visual polish:

| Priority & Skill | What It Owns |
| --- | --- |
| 1. `ui-ergonomics` | Critical User Journey (CUJ) identification & friction logs, common-view & dashboard architecture, Fitts's Law & KLM-GOMS time-to-action budgets, keyboard/IME-safe shortcuts, addressable state, Poka-Yoke error-proofing, Undo, and microcopy. |
| 2. `ui-cli` | Command-Line Interface (CLI) UX for humans, pipes, CI & agents: `stdout` data vs `stderr` diagnostics, `isatty` auto-degradation, `--json`/`--plain`, flag/subcommand grammar, example-first `--help` & shell completions, `--dry-run`, secret-safe inputs, `NO_COLOR`, and semantic exit codes. |
| 3. `ui-performance` | `60/120 Hz` frame & `< 50 ms` CLI startup budgets, 1D/2D viewport virtualization, off-thread sorting/filtering, high-rate stream conflation, chart/canvas LOD decimation, anti-flicker loading hysteresis, and rendering-tier selection. |
| 4. `ui-accessibility` | Platform accessibility trees (`Name`, `Role`, `State/Value`, `Actions`), 100% keyboard-complete flows, focus indicators & containment, hit-target geometry, reduced-motion, and `200%` text/DPI scaling. |
| 5. `ui-layout` | Gestalt proximity grouping, shared alignment edges, visual-vs-logical reading order, content-driven responsive/split-pane reflow, safe areas/sticky chrome clearance, logical RTL mirroring, and translation expansion. |
| 6. `ui-typography` | Semantic type scales, optical legibility floors, tabular figures (`tnum`) & numeric alignment, **Unicode correctness** (`NFC`, `UAX #29` graphemes, `UAX #11` CJK/emoji `2`-cell width, `UAX #9` BiDi isolation, `UAX #14` wrapping), and recoverable middle-truncation. |
| 7. `ui-colors` | OKLab/OKLCh perceptual ramps, primitive-to-semantic token seams, dark/high-contrast tuning, data-viz scales, measured WCAG 2.2 + APCA $L_c$ contrast, and compile-time translation to sRGB/P3/RGBA/ANSI. |

---

## Designing or Building a New Interface (Sequence)

When creating a screen, dashboard, CLI/TUI, or desktop/mobile workflow:

1. **Map Critical User Journeys, views & CLI contracts (`ui-ergonomics`, `ui-cli`):**
   Identify the `3–5` core end-to-end CUJs (`Daily 80% Loop`, `Onboarding`,
   `Incident/Error Triage`, `High-Stakes Commit`) and set step + latency budgets.
   Assign `1` primary action per view, colocate sequential controls, wire IME-safe
   keyboard accelerators, keep filter/selection state addressable, and design
   Poka-Yoke constraints + Undo; for CLIs (`ui-cli`), enforce `stdout` data vs
   `stderr` diagnostics, `isatty` auto-degradation, `--json`/`--plain`,
   `--dry-run`, and `< 50 ms` startup.
2. **Size for data volume (`ui-performance`):** Pin expected and worst-case row/
   point counts and update rates (`events/s`). Choose virtualization, worker
   offloading, conflation, and rendering tier *before* committing to $O(N)$
   widget trees.
3. **Establish spatial, Unicode & visual tokens (`ui-layout`, `ui-typography`, `ui-colors`):**
   Define spacing steps, logical `start`/`end` alignment axes, semantic type
   roles (with `tabular-nums`, grapheme/display-width safety, and BiDi isolation
   for dynamic strings), and OKLCh semantic color tokens (matching visual density
   and tone to the domain rather than generic marketing card templates).
4. **Walk all 6 states + keyboard/AT (`ui-accessibility`):** Verify `Empty`,
   `Filtered-Empty`, `Loading`, `Populated`, `Stale/Offline`, and `Error` states
   plus narrow/`200%`-scaled, RTL/wide-glyph, reduced-motion, and keyboard-only
   walks before declaring completion.

---

## Auditing an Existing Screen or Git Change

Consult [references/review-and-audit.md](references/review-and-audit.md) for
diff-scope resolution, removed-signal regression checks, and the consolidated
output table. Follow four rules on every review:

1. **Resolve scope & recon first (never mutate the tree):**
   * For a **screen/flow audit**, state the exact views and states inspected
     (including empty, loading, error, and resized states).
   * For a **diff/PR review**, resolve `<base>...<head>`, expand `1` hop to
     affected parent surfaces (`2` hops for shared tokens/primitives, up to `5`
     representative consumers), inspect deleted (`-`) lines for stripped labels,
     focus rings, shortcuts, undo paths, or virtualization, and classify each
     finding as `Introduced`, `Regression`, or `Pre-existing` (`<= 3` courtesy
     notes; never block on pre-existing debt).
   * Identify the project's UI toolkit, token files, and documented conventions
     first; write every fix in that exact toolkit.
2. **Evidence & Escalation Triggers (`HIGH` on sight):**
   Every finding cites `path/to/file:line` and concrete evidence. Any confirmed
   instance of these universal failures is **`HIGH`** regardless of surface size:
   * Interactive control missing a programmatic accessible name/role or keyboard
     activation path, or keyboard focus lacking a visible `>= 3:1` indicator.
   * High-frequency workflow trapped behind multi-hop pointer travel/menus with
     no keyboard or colocated path, or mode trap with no locus-of-attention cue.
   * Irreversible destructive action lacking spatial separation, specific verb
     label, `--dry-run`/impact preview, or confirmation/undo safeguard.
   * CLI command polluting piped `stdout` with logs/spinners/ANSI/truncated `…`
     values, hanging non-TTY `stdin` on an interactive prompt, returning `0` on
     failure, or requiring secrets via raw `--password` `argv`.
   * Unbounded/large list, table, log, or chart rendered $O(N)$ without
     virtualization/decimation or blocking the UI thread (`> 50 ms` freeze).
   * Body/control text or active UI boundary failing required contrast, or state/
     meaning conveyed by color alone or motion alone.
   * Control or value clipped/overlapped on supported resize/`200%` scale, or
     truncated data with no keyboard- and pointer-reachable way to view full text.
   * User-facing error that states no actionable recovery path.
3. **Prefer the cheapest fix:**
   1. **Delete** (redundant lines/chrome, confirmation popups on reversible
      actions, animations on high-frequency keys/clicks, unused tokens).
   2. **Use native toolkit primitives** (standard button/dialog/table/focus
      behavior over custom div/canvas rebuilds).
   3. **Reuse existing project tokens & components.**
   4. **Tune the parameter** (OKLCh lightness $L$, spacing multiple, target size,
      shortcut binding).
   5. **Add new structure** only when steps 1–4 cannot solve the root cause.
4. **Consolidate one root cause per row:** Merge duplicate leaf symptoms against
   the shared token or component (`<= 15` ranked findings, `Block` if any `HIGH`
   remains on inspected scope, `Approve` otherwise; mark unrun runtime checks
   `Not verified`).
