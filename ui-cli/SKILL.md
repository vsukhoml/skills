---
name: ui-cli
description: >-
  CLI UX design in any language: human TTY versus pipe, script, and agent
  output (stdout/stderr, --json, exit codes), command and flag grammar,
  --help, shell completions, --dry-run and undo safety, and terminal color and
  Unicode width. Use when designing, building, or reviewing a command-line
  tool, its flags, output, help text, or error messages.
last_updated: 2026-11-15
---

# First-Principles Command-Line Interface Design (`ui-cli`)

Designs and audits **Command-Line Interfaces (CLIs)** as first-class user
interfaces — optimizing time-to-command, discoverability, mistake-proofing
(Poka-Yoke), composability, and legibility for **both human operators at an
interactive TTY and automated callers (shell pipelines, CI jobs, and AI agents)**.

*(For full-screen alternate-buffer terminal dashboards with panes and widgets,
combine this skill with `ui-layout`, `ui-ergonomics`, and `ui-performance`.)*

Consult [references/cli-patterns-and-contracts.md](references/cli-patterns-and-contracts.md)
for exit-code tables, environment-variable precedence (`NO_COLOR`, `TERM`, `CI`),
`--help` & error templates, and TTY vs. pipe behavior matrices.

---

## 1. The Dual-Audience Contract: Human TTY vs. Pipe, CI & Agents

Every modern CLI serves two interfaces through one binary: an **interactive human
UI** when attached to a terminal (`isatty`) and a **deterministic data/RPC
contract** when piped, scripted, or invoked by an agent.

1. **Strict `stdout` vs. `stderr` separation:**
   * **`stdout` is exclusively for primary command output** (records, generated
     files, query results, `--json` payloads) so `tool list | jq .` or `tool dump
     > out.sql` never corrupts downstream consumers.
   * **`stderr` carries all human conversation:** progress bars, spinners,
     warnings, `[DRY-RUN]` notices, interactive prompts, and error diagnostics.
2. **Automatic `isatty` adaptation (Zero corruption on pipe):**
   * When `stdout` is **not** a TTY, automatically disable ANSI colors, box-drawing
     borders, column truncation (`…` must **never** chop IDs or paths in a pipe!),
     spinners, and automatic `$PAGER` spawning.
   * When `stdin` or `stderr` is **not** a TTY (or `CI=true` / `--no-input` is
     set), **never hang waiting on an interactive prompt** — fail immediately with
     exit code `2` naming the exact `--flag` required to run unattended!
3. **First-class machine-readable output (`--json` / `--plain`):**
   * Provide `--json` (or `--format json|jsonl|tsv|plain`) on every inspection,
     list, status, or diff command, treating field names as a versioned contract.
   * `--plain` / `--tsv` emits headerless, tab-separated lines with `1` record per
     line so standard Unix tools (`awk`, `cut`, `xargs`, `sort`) compose in `0`
     glue code.

---

## 2. Command Grammar, Discoverability & Time-to-Invoke (`ui-ergonomics`)

Minimize keystrokes, memorization, and manual-page round-trips on Critical User
Journeys (CUJs):

1. **Predictable grammar & universal flags:**
   * Choose one consistent grammar: **`tool <resource> <action>`** for multi-domain
     CLIs (e.g., `cluster create`, `cluster list`, `token revoke`) or **`tool
     <action>`** for single-purpose tools, keeping verb vocabulary uniform across
     every resource (`list`, `get`, `create`, `delete` — accepting muscle-memory
     aliases like `ls`/`rm` without duplicating `--help` noise).
   * **Prefer `--long-flags` over positional argument roulette:** Limit positional
     arguments to `1–2` unmistakable targets (`<file>`, `<source> <dest>`). Never
     require memorizing whether the 3rd positional arg is `region` or `profile`!
   * **Honor universal flag conventions:** `-h`/`--help`, `-V`/`--version`,
     `-q`/`--quiet`, `-v`/`--verbose`, `-n`/`--dry-run`, `-y`/`--yes`,
     `-o`/`--output`, `--color=auto|always|never`, and `--` (end-of-flags sentinel
     so arguments starting with `-` work cleanly). Reserve single-letter short
     flags for the top `3–5` daily options.
2. **Example-first `--help` & fuzzy typo suggestions:**
   * Lead every `--help` output with a 1-sentence purpose and **`2–4` copy-pasteable
     examples covering the 80% CUJs** *before* listing flags grouped by role
     (`Common Options`, `Output`, `Safety`, `Global`). Keep default `--help`
     scannable within one terminal screen where possible.
   * On unknown subcommands or mistyped flags (`--dryrun`, `deploi`), compute edit
     distance and print **`Did you mean '--dry-run'?`** + the exact `--help` command
     (exiting `2`, never dumping a 200-line manual that scrolls the error off-screen!).
3. **Fast shell completions (The CLI Command Palette):**
   * Ship built-in completion generation (`tool completions bash|zsh|fish|pwsh`)
     covering subcommands, flags, enum values, and fast dynamic local state —
     eliminating recall friction (`Hick's Law`) right at the `Tab` key.

---

## 3. CLI Poka-Yoke: Make Wrong Commands Hard to Run

A mistyped CLI command can wipe production state in `< 10 ms` with no GUI visual
surround. Apply five structural safeguards:

1. **`--dry-run` (`-n`) & Blast-Radius Diff Previews:**
   * Every mutating, bulk, sync, migration, or deploy command **must** support
     `--dry-run` (or print an explicit change summary before confirmation), showing
     exact counts, target environment/context (`[PRODUCTION: prod-eu-1]`), and
     concrete diffs while exiting `0` with zero side effects.
2. **Print the exact Undo / Rollback command on reversible mutations:**
   * Instead of training blind `y` muscle memory on routine reversible actions,
     execute cleanly and print the copy-pasteable recovery command (`Reverted? Run:
     tool release rollback v1.4.2` or `Undo: tool trash restore 91a4c`).
3. **Graduated friction for irreversible destructive commands:**
   * Never delete unbounded wildcards or entire environments silently.
   * On interactive TTYs, display affected scope and require typing the target
     identifier (or explicit `y/N` defaulting to **`N`** on bare `Enter`!) for
     irreversible deletes; in scripts, require an explicit `--yes` or
     `--confirm=<resource-name>` guard.
4. **Secret & credential hygiene (Ban raw `--password <secret>` argv):**
   * Command-line arguments (`argv`) leak to local process tables (`ps aux`), shell
     history (`~/.zsh_history`), and CI logs! Accept secrets strictly via
     `--token-stdin` / `--password-file <path>`, scoped environment variables /
     credential helpers, or masked TTY prompt — rejecting or loudly warning if a
     secret value is passed inline on `argv`.
5. **`SIGINT` (`Ctrl+C`) cleanliness & atomic writes:**
   * Trap `SIGINT`/`SIGTERM` cleanly: restore terminal cursor/echo state if altered,
     clean up temporary files, write output files atomically (`temp + fsync +
     rename`) so interrupted runs never leave corrupt half-written configs, print
     resumable progress state if multi-step, and exit 130 on SIGINT (143 on SIGTERM, i.e., 128 + signum).

---

## 4. Performance, Color, Accessibility & Unicode (`ui-performance`, `ui-colors`, `ui-accessibility`, `ui-typography`)

* **Sub-`50 ms` startup & instant `--help` / tab-completion:** Defer heavy imports,
  plugin discovery, config network fetches, and SDK initialization until *after*
  argument parsing (`< 20–50 ms` cold start so `Tab` completion and `--help` feel
  instantaneous!).
* **Streaming & anti-flicker progress:** Emit nothing extra for `< 150 ms` commands;
  render `stderr` progress/ETA updates at `4–10 Hz` (with `tabular-nums` / fixed-
  width fields so columns don't jitter!) for long tasks; stream large list/log
  outputs line-by-line (`jsonl` / paged `$PAGER` on TTY) without `O(N)` buffering.
* **Polar-safe terminal colors & `NO_COLOR`:** Respect `NO_COLOR` (non-empty = zero
  ANSI color), `TERM=dumb`, and `--color`. Users run both **dark and light**
  terminal backgrounds — stick to standard ANSI 16 semantic slots or mid-lightness
  OKLCh truecolor values (`L ≈ 0.50–0.68`) legible on *both* polarities, and
  **always** pair color with text/symbol labels (`✓ OK`, `! WARN`, `✗ ERROR`).
* **Screen-reader & Unicode safety:** Avoid unmapped Private Use Area (NerdFont)
  glyphs or `80`-char `──────` ASCII rule spam that screen readers read character-
  by-character; align tabular columns using **`UAX #11` display width** (accounting
  for `2`-cell CJK/emoji and `0`-cell ANSI escapes + combining marks, never raw
  `strlen`!).
* **Three-part errors & semantic exit codes:** Print **`error:` what failed + why +
  exact next command/flag** to `stderr`, and return deterministic exit codes (`0`
  success, `1` runtime failure, `2` CLI usage/flag error, `130` `SIGINT`, `143`
  `SIGTERM`).

---

## Before You Finish (`ui-cli` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| `"Loading..."` banner, spinner, or ANSI escape codes written to `stdout` | Move diagnostics/progress to `stderr`; strip ANSI when `!isatty(stdout)` |
| Table truncates IDs (`abc123…`) even when piped to `grep` / `awk` | Disable truncation & borders when piped, or provide `--plain` / `--json` |
| Interactive `[y/N]` prompt hangs unattended CI pipeline | Detect `!isatty(stdin)` / `CI=true` and fail fast (`exit 2`) naming `--yes` |
| `--token <secret>` required on command line (`ps aux` / shell history leak) | Replace with `--token-stdin`, `--token-file`, keychain, or masked TTY prompt |
| Destructive `delete` mutates production immediately with no preview | Add `--dry-run`, display `[ENV]` + affected count, default `y/N` to `N` |
| `--help` dumps 120 alphabetical flags with zero examples; typos dump full help | Put `2–4` common examples first, group flags, print `"Did you mean ...?"` |
| CLI cold start takes `600 ms` on `--help` or `Tab` completion | Lazy-load heavy modules/network clients after CLI parser dispatches |
| Column alignment breaks on CJK names or colored strings (`len(ansi_str)`) | Strip ANSI escapes + measure width via `UAX #11` grapheme display cells |
