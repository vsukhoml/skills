# Developer and operator documentation

Select a documentation page by the reader's job rather than the source-tree
layout, give one supported procedure, and verify commands on a clean
environment.

## Page types by reader job

Table 1 selects the page form by the task of the reader (`--profile docs`).

Page               | Reader job                        | Required content
------------------ | --------------------------------- | ------------------------------------------------------------------------
README             | Understand and run a repository   | Purpose, status, requirements, install, shortest example, test command.
Quickstart         | Reach the first working result    | Prerequisites, one install path, one complete example, expected output.
How-to guide       | Complete one practical task       | Task title, prerequisites, ordered steps, expected output, failure check.
Concept page       | Build a mental model              | Mechanism, component relations, constraints, trade-offs, links to tasks.
Reference          | Look up exact interface contracts | Public syntax, types, required flags, defaults, side effects, errors.
Troubleshooting    | Recover from an observed failure  | Exact symptom, verified cause, safe check, fix, verification.
Operations runbook | Operate or recover a live service | Permit conditions, steps, health checks, stop condition, rollback, log.
Migration guide    | Move between versions safely      | Start and target versions, breaking changes, data effects, rollback.
Release notes      | Assess user-visible changes       | Version, date, added or fixed behavior, breaking changes, reader action.

*Table 1: Do not mix learning, procedures, and exhaustive reference on one
page.*

Create only the pages the reader needs rather than a full site, keep each
procedure in one canonical page, and link to it elsewhere (R4).

## Catalogs and indexes

A catalog row helps the reader choose one item while the item's own page holds
the details:

-   **One job:** State what the item does in at most 30 words.
-   **Selection facts only:** Keep only facts that separate the row from sibling
    rows, linking to the item page for everything else (R4).
-   **Searchable names:** Keep product and standard names in the row, moving
    flags, file paths, and internal symbols to the item page.
-   **Words between terms:** Write "and" or "or" instead of slashes between
    words.

On narrow Revise runs, replace slashes and symbols with words, keep existing
cell facts intact, and list proposed shorter cells in the report.

## Procedures and examples

State prerequisites and required permissions before step 1, and order each step
so context precedes action:

1.  **Location first:** Name the directory, host, or UI menu before the action,
    identifying controls by visible label rather than position words ("above",
    "on the right").
2.  **Action second:** Start with an imperative verb, giving one action per step
    (and prefixing optional steps with "Optional:").
3.  **Result third:** State the expected output that confirms success before the
    next step, following the copyable-command rules in `writing-tech-docs` and
    placing hazard warnings before destructive steps (R20).

Test installation, migration, and recovery procedures on a clean environment. A
pass only on an already configured developer workstation has status `assumed` in
the report.

## Reference, troubleshooting, and runbooks

Organize API, library, and CLI reference pages around the public interface or
`--help` hierarchy rather than internal source files. Derive names, types,
required inputs, mutually exclusive flags, defaults, side effects, and errors
from the code or schema without exposing private internals as contract.

Organize troubleshooting pages by observable symptoms and exact error messages,
listing safe diagnostic checks before destructive recovery steps and omitting
unverified guesses.

In operations runbooks, separate routine maintenance from emergency response.
State the halt condition, the escalation contact if rollback fails, and the
operational log entry to record.
