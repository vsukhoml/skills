# CUJ Friction Logs, Interaction-Cost Math & Poka-Yoke Patterns (`ui-ergonomics`)

## 0. Critical User Journey (CUJ) Identification & Friction Log

Before designing or reviewing individual widgets, map the `3–5` **Critical User
Journeys** end-to-end and walk each through a structured **Friction Log**:

1. **How to extract CUJs from an unfamiliar codebase or spec:**
   * Inspect top-level routes/screens/CLI subcommands, primary write mutations,
     and error/alert handlers.
   * Express each CUJ as **Actor + Trigger + Goal + Done Signal** (e.g., *"On-call
     engineer receives latency alert -> isolates offending deployment -> rolls back
     safely in `<= 45 s`"*).
2. **Walk every CUJ across all 6 view states:**
   `1. First-run Empty` · `2. Loading / Pending` · `3. Populated (p95 scale)` ·
   `4. Filtered-Empty (0 matches)` · `5. Stale / Offline` · `6. Validation or Server Error`.
3. **Friction Log Matrix (record one row per friction point):**

| CUJ & Step | Observed Friction (Motor / Cognitive / Latency) | Cost (`K/H/P/M` or `ms`) | Root-Cause Fix |
| --- | --- | --- | --- |
| *Triage -> Filter by service* | Filter resets to default on Back navigation | `+3 clicks`, lost context | Sync filter/sort/tab state to URL / workspace state |
| *Create -> Enter CJK name* | Pressing `Enter` to confirm IME candidate submits half-typed form! | Broken input / error | Guard `Enter` submit behind `!event.isComposing` / IME preedit check |
| *Save -> Click Submit* | Button shrinks from `"Save rule"` to `24 px` spinner, shifting `Cancel` under cursor | Accidental cancel slip | Keep button width + label intact while busy (`aria-busy` / inline spinner) |

---

## 1. Estimating Interaction Cost (KLM-GOMS Quick Reference)

Use Card, Moran & Newell's Keystroke-Level Model to compare two candidate UI
designs objectively on a repeated workflow:

| Operator | Typical Time | Design Implication |
| --- | --- | --- |
| **`K` — Keystroke / Shortcut** | `0.12–0.28 s` | Fastest possible human input (`1` chord or mnemonic key). |
| **`H` — Homing hands** (`Keyboard <-> Mouse/Trackpad`) | `0.40 s` | Every unnecessary device switch costs `~0.8 s` round-trip. |
| **`P` — Pointing with mouse** (Fitts's Law) | `0.80–1.50 s` | Grows with $\log_2(1 + D/W)$; tiny distant targets cost `> 1.5 s`. |
| **`B` — Mouse button click** | `0.10 s` | Cheap once pointed; double-click or drag-and-drop costs much more and fails more often. |
| **`M` — Mental preparation / visual search** | `1.20 s` | Incurred whenever labels are vague, layout shifts, or >5 ungrouped choices compete. |

### Worked Comparison: Triaging 20 Items in an Operational Queue

- **High-friction UI** (click row -> move across screen -> click `"Approve"` ->
  modal `"Are you sure?"` -> click `"OK"`):
  Per item $\approx P(1.1) + B(0.1) + P(1.3) + B(0.1) + M(0.8) + P(0.9) + B(0.1) = \mathbf{4.4\text{ s}}$
  ($88\text{ s}$ for 20 items, `60` clicks, high slip risk on modal!).
- **Low-friction Poka-Yoke UI** (`j/k` or Down arrow + `a` to approve with
  inline Undo toast, plus colocated inline `"Approve"` button for mouse users):
  Per item (keyboard) $= K(0.2) + K(0.2) = \mathbf{0.4\text{ s}}$ ($8\text{ s}$
  for 20 items — **`11x` faster**, zero modal fatigue, reversible via `z` /
  `Cmd+Z`!).

---

## 2. Dashboard Archetypes & Control Surfaces

Match the layout to how operators use the view:

1. **Operational Triage Dashboard (NOC, Trading, CI/CD, Support Queue):**
   * **Top strip:** Exception counters (`3 Critical`, `12 Degraded`) acting as
     instant toggle filters; `0` state dims quietly into neutral background so
     non-zero anomalies command 100% of chroma!
   * **Center workspace:** High-density virtualized table/timeline sorted by
     urgency/impact, tabular numerals (`tnum`), inline sparklines/bars, and
     keyboard + single-click row actions.
   * **Right/bottom inspector pane (Master-Detail):** Opens details inline
     without losing place in the queue or triggering full-page navigation.
2. **Analytical / Executive Overview:**
   * **Pinned filter & comparison bar:** Time window, comparison baseline (`vs
     prior period` / `vs target`), and segment scope always visible at top.
   * **Small multiples on shared axes:** Prefer aligned small-multiple bar/line
     charts sharing one scale over multi-axis spaghetti charts or pie/donut
     charts with `> 3` slices.

---

## 3. Poka-Yoke Checklist for High-Risk Controls

1. **Environment & Tenant Guardrails:**
   * Visually differentiate high-risk contexts (e.g., distinct top chrome band +
     explicit `[PROD]` pill inside commit/action buttons when attached to
     production vs. local/staging).
2. **Paste & Format Forgiveness:**
   * Accept human-formatted inputs (`+1 (415) 555-0199`, `1,250.00`, trailing
     spaces on API tokens/OTP codes) and normalize silently rather than rejecting
     valid data on formatting trivia; never block paste in any field.
3. **Unsaved-Work Protection:**
   * Auto-save drafts locally where possible; if closing/navigating away would
     discard user input, guard navigation with a specific choice:
     `[Save changes]` / `[Discard changes]` / `[Keep editing]`.
4. **Idempotent Submission:**
   * Immediately transition an active action button into a busy/in-flight state
     on first press (keeping keyboard focus stable!) so a double-click or network
     hiccup never submits duplicate orders, transfers, or jobs.
