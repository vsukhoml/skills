# CLI Contracts, Exit Codes, Environment Precedence & Templates (`ui-cli`)

Reference tables and copy-ready patterns for building predictable, script-safe, and
human-friendly Command-Line Interfaces in any language.

---

## 1. Standard Exit-Code Contract

Automation, shell `&&` chains, CI gates, and AI agents branch on process exit status.
Never return `0` on failure or `1` on invalid CLI syntax:

| Exit Code | Meaning | Typical Trigger |
| --- | --- | --- |
| **`0`** | **Success** | Command completed (including `--help`, `--version`, and clean `--dry-run`). |
| **`1`** | **Runtime / Operational Error** | Network failure, file not found, remote API error, check/lint gate found violations. |
| **`2`** | **Usage / Validation Error** | Unknown flag/subcommand, invalid flag value, missing required argument, interactive prompt needed on non-TTY. |
| **`64–78`** *(optional `sysexits.h`)* | **Structured System Error** | `65` data format error, `69` service unavailable, `75` temp failure (retryable), `77` permission denied, `78` config error — document in `--help` if used! |
| **`124`** *(convention)* | **Timeout Exceeded** | Command exceeded `--timeout` deadline. |
| **`130` / `143`** | **Interrupted (`SIGINT` / `SIGTERM`)** | Cleanly aborted by signal (`128 + signum`: `130` on `SIGINT`, `143` on `SIGTERM`). |

---

## 2. Configuration & Environment Variable Precedence

Resolve settings in strict highest-to-lowest specificity so explicit CLI flags
always win deterministically:

```text
1. Explicit CLI flags          (--region eu-west-1, --color=never)
2. Scoped env variables        (MYTOOL_REGION=eu-west-1, NO_COLOR=1)
3. Project-local config        (./.mytool.toml or git-root config)
4. User config ($XDG_CONFIG_HOME/mytool/config.toml | %APPDATA% | ~/Library/Application Support)
5. System config & safe built-in defaults
```

### Standard Environment Variables Every CLI Should Respect

| Variable | Contract |
| --- | --- |
| **`NO_COLOR`** | When set and non-empty (`NO_COLOR=1`), disable all ANSI color escapes on `stdout`/`stderr` (unless overridden by explicit `--color=always`). |
| **`CLICOLOR_FORCE` / `FORCE_COLOR`** | Force ANSI color even when `!isatty` (useful inside CI log collectors that render ANSI). |
| **`TERM=dumb`** | Disable ANSI colors, cursor movement, spinners, and alternate-screen TUI features; fall back to plain line output. |
| **`CI`** (`CI=true` / `1`) | Disable interactive prompts and high-frequency progress redraws (`10 Hz` spinners spam 5,000 log lines in CI; print periodic milestone lines instead). |
| **`PAGER`** | Use `$PAGER` (defaulting to `less -FRX` when `stdout` is a TTY and output exceeds terminal height); never page when piped or `--no-pager` is passed. |
| **`EDITOR` / `VISUAL`** | Launch `$VISUAL` then `$EDITOR` when opening multi-line interactive edits (`git commit` style). |
| **`XDG_CONFIG_HOME` / `XDG_CACHE_HOME` / `XDG_STATE_HOME`** | Keep `$HOME` clean — store config, caches, and history in platform-standard user directories rather than littering `~/.mytoolrc` dotfiles unless conventional. |
| **`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`** | Respect standard proxy variables on any outbound HTTP/gRPC client. |

---

## 3. TTY vs. Non-TTY Behavior Matrix

| Surface Feature | Interactive Human (`isatty(stdout) == true`) | Piped / Redirected (`!isatty(stdout)`) or `--plain` | Structured (`--json` / `--jsonl`) |
| --- | --- | --- | --- |
| **Table headers & padding** | Aligned columns + concise `UPPER`/`Bold` header | **No** decorative borders; `TAB`-separated single-line rows | Valid JSON array or newline-delimited JSON objects |
| **Long cell values** | Middle/end truncate to terminal width (`cols`) | **Full untruncated values** (never emit `…` into pipes!) | Full untruncated typed values (`int`, `bool`, ISO-8601 UTC string, `null`) |
| **ANSI colors & glyphs** | Semantic ANSI / OKLCh (unless `NO_COLOR`) | **Zero** ANSI escape bytes | **Zero** ANSI escape bytes |
| **Progress & spinners** | `stderr` in-place `4–10 Hz` bar (`isatty(stderr)`) | Quiet (or milestone log lines on `stderr` if `--verbose`) | Quiet on `stdout`; structured error object on failure |
| **Timestamps & sizes** | Relative + human (`2m ago`, `14.2 MiB`) | ISO-8601 UTC (`2026-11-15T21:56:00Z`) & exact bytes/base units | ISO-8601 UTC & numeric bytes/milliseconds |

---

## 4. Model `--help` & Three-Part Error Layouts

### 4.1 Scannable, Example-Led `--help` Template

```text
Deploy a service revision safely to a target environment.

Usage:
  shipctl deploy [service] --env <name> [options]

Examples:
  # Preview changes against staging without modifying state
  shipctl deploy billing-api --env staging --dry-run

  # Roll out image tag to production and stream health checks
  shipctl deploy billing-api --env prod --image v2.8.1

  # Emit machine-readable deployment receipt for CI pipelines
  shipctl deploy billing-api --env prod --image v2.8.1 --yes --json

Common Options:
  -e, --env <name>        Target environment (dev, staging, prod) [env: SHIPCTL_ENV]
  -i, --image <tag>       Container tag or digest to deploy
  -n, --dry-run           Print planned changes and affected instances without applying

Output & Automation:
      --json              Output structured JSON result to stdout
  -y, --yes               Skip interactive confirmation in scripts
  -q, --quiet             Suppress non-error status messages on stderr
      --color <when>      Colorize output: auto, always, never [default: auto]
  -h, --help              Print help (use '--help-all' for advanced flags)
```

### 4.2 Three-Part Actionable CLI Error (`stderr`)

Every CLI error answers **(1) What failed**, **(2) Why / Context**, and **(3) Exact
copy-pasteable fix**:

```text
error: cannot delete database 'orders-primary' in environment 'prod' without confirmation
  --> context: 'orders-primary' has 4 active read replicas and 1.8 TiB of live data ( stdin is not a TTY )
  help: run with '--dry-run' to inspect blast radius, or pass '--confirm=orders-primary' to delete non-interactively:
        shipctl db delete orders-primary --env prod --confirm=orders-primary
```
