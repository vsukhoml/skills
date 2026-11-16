# UI Screen & Change-Diff Audit Reference (`ui`)

## 1. Resolving Change-Diff Scope (Read-Only)

When reviewing uncommitted work, a branch, a commit, or a PR/MR:

1. **Never mutate the working tree:** `git fetch` is allowed; `git checkout`,
   `git switch`, `git stash`, and `gh pr checkout` are forbidden. Read non-HEAD
   refs via `git show <ref>:path` or an isolated temporary `git worktree`.
2. **Default target order** (when user gave no explicit ref):
   * Branch ahead of `git merge-base origin/<default-branch> HEAD` (+ any dirty
     files, reporting both counts);
   * Dirty working tree (`git diff` + `git diff --cached`);
   * Otherwise stop and ask whether to review an open PR/MR, `HEAD~1..HEAD`, or a
     whole-surface audit — never guess silently.
3. **Exclude non-UI noise:** Skip lockfiles, generated code, vendored assets, and
   binary snapshots, naming what was excluded.

---

## 2. Checking Removed (`-`) Diff Lines for Silent UI Regressions

Regressions often hide on the deleted side of a diff. Scan removed lines across
changed UI files and check whether an equivalent replacement exists in the same
change before flagging `Regression`:

| Removed Signal (Any UI Stack) | Owning Skill | Regression Check |
| --- | --- | --- |
| Accessible label/role/description (`aria-*`, `accessibilityLabel`, `contentDescription`, Qt/GTK accessible name) | `ui-accessibility` | Did an icon control, input, or custom widget lose its programmatic name or state announcement? |
| Focus ring, tab-stop, keybinding, or shortcut handler (`focus-visible`, `onKeyDown`, `QShortcut`, Compose `onKeyEvent`, TUI keymap) | `ui-accessibility` / `ui-ergonomics` | Did a control drop out of keyboard reach, lose visible focus, or lose a fast keyboard accelerator? |
| Undo handler, confirmation guard, unit suffix, or input validator/constraint | `ui-ergonomics` | Did a destructive or error-prone action become easy to trigger by mistake? |
| Virtualized list/table/canvas windowing (`LazyColumn`, `ListView.builder`, `QAbstractItemModel`, virtualizer, LOD decimation) swapped for `.map()` / full loop | `ui-performance` | Will large datasets now instantiate $O(N)$ widgets or block the UI thread? |
| Reduced-motion or high-contrast branch (`prefers-reduced-motion`, `accessibilityReduceMotion`, `highContrast`) | `ui-accessibility` / `ui-colors` | Does motion or low-contrast chrome now ignore OS user preferences? |
| Tabular numerals (`tabular-nums`, `monospacedDigit`, `tnum`), Unicode grapheme/`wcwidth`/NFC handling, BiDi isolation, or truncation expand/tooltip | `ui-typography` / `ui-layout` | Do live numbers now jitter horizontally, CJK/emoji/RTL strings misalign or corrupt on slice, or truncated fields hide values permanently? |
| Logical leading/trailing layout properties swapped for hardcoded `left`/`right`, or IME composition guard (`isComposing` / preedit) removed | `ui-layout` / `ui-ergonomics` | Did RTL mirroring break, or does `Enter`/shortcut handling now corrupt active CJK/IME input? |
| URL/workspace filter synchronization or background-refresh focus/input preservation removed | `ui-ergonomics` | Do Back/Forward, refresh, or live polling updates now wipe user filters or clobber active typing? |
| CLI `--dry-run`, `--json`/`--plain`, `isatty` check, `NO_COLOR`, `stderr` separation, or `--yes` non-TTY guard removed | `ui-cli` | Do shell pipelines, CI jobs, or operators lose preview safety, clean `stdout` data, or unattended scriptability? |

---

## 3. Consolidated Output Format

### A. Scope & Domain Coverage

State the resolved target, UI toolkit/stack, token/convention docs found, and any
excluded paths or unexpanded consumers. Then show domain coverage:

| Domain | Evidence Inspected | Result |
| --- | --- | --- |
| Ergonomics & Poka-Yoke | CUJs, views, flows, keymaps, destructive guards | `<N> findings` or `Clear` |
| CLI Ergonomics & Streams | Flags, `--help`, `stdout`/`stderr`, `isatty`, `--json`, exit codes | `<N> findings`, `Clear`, or `Not applicable` |
| Performance & Scale | Lists, tables, streams, render loops, CLI cold-start | `<N> findings` or `Clear` |
| Accessibility | Keyboard walk, AT roles/names, focus, hit targets | `<N> findings` or `Clear` |
| Layout & Adaptivity | Grouping, resize/scale bounds, RTL, i18n growth | `<N> findings` or `Clear` |
| Typography | Scale, `tnum` data columns, measure, truncation | `<N> findings` or `Clear` |
| Color & Contrast | OKLCh tokens, light/dark pairs, non-color cues | `<N> findings` or `Clear` |

*(Mark any domain with zero relevant files in a diff as `Not applicable in diff`,
or `Not reviewed (<reason>)` if skipped — never `Clear` without inspection.)*

### B. Ranked Findings Table (`<= 15` rows, one root cause per row)

Order by `Severity` (`HIGH` -> `MEDIUM` -> `LOW`), then by systemic reach (shared
token/widget before single leaf). Include `Status` (`Introduced` | `Regression` on
diff reviews; `Active` on whole-surface audits):

| Severity | Status | Domain | Location | Before | After | Why (Principle & User Impact) |
| --- | --- | --- | --- | --- | --- | --- |

*(For diff reviews, list at most `3` `Pre-existing` items in a separate courtesy
note below; they never affect the verdict.)*

### C. Verification & Verdict

- List commands, contrast/palette scripts, or interactive walks actually run vs.
  items marked `Not verified`.
- End with **`Verdict: Block`** (one or more `HIGH` findings remain in scope) or
  **`Verdict: Approve`** (zero `HIGH` findings in inspected scope).
