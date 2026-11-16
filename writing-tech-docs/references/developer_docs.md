# Developer and operator documentation

Select a documentation page by the job of the reader, not by the source file
layout. Separate current system behavior from proposed behavior. Give one
supported procedure, and verify commands on a clean environment.

## Page types by reader job

Table 1 selects the page form by the task of the reader.

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

Developer documentation uses the profile "Developer documentation" in Table 2
of the skill file. Run the lint script with `--profile docs`.

Create only the pages that the reader needs. Do not turn a request for one page
into a full documentation site. Keep each procedure on one page, and link to
that page from other pages. Each procedure has one home (R4).

## Catalogs and indexes

A catalog row helps the reader to select one item. The page of the item holds
the detail. Write each description cell with these 4 limits:

-   **One job:** State what the item does in at most 30 words.
-   **Selection facts only:** Keep the facts that separate the item from the
    other rows. Move each other fact to the page of the item, and link to that
    page. Each fact has one home (R4).
-   **Names that a reader searches for:** Keep product names and the names of
    standards, because a reader finds the row with them. Move flags, file names,
    and internal identifiers to the page of the item.
-   **Words between terms:** Write "and" or "or" between terms, not a slash.
    The lint script reports a cell with 2 or more such slashes.

In Revise mode, these limits are advice for the author, not edits. Replace
symbols and slashes with words, and read the page of the item if a slash can
mean "and" or "or". Do not remove a fact from a cell, and do not add text about
when to select the item. Put each proposed shorter cell in the report.

## Procedures and examples

State prerequisites and required permissions before step 1. Use a numbered list
if the order matters, and a bulleted list if the order does not matter.

Order each procedural step so that the reader sees the context before acting:

1.  **Location first:** Name the directory, host, or menu before the action.
2.  **Action second:** Start the action with an imperative verb, with one action
    in each step.
3.  **Result third:** State the expected output that confirms success before the
    next step.
4.  **Optional marker:** Start an optional step with "Optional:".
5.  **Copyable commands:** Omit the shell prompt ("$" or "#") in commands that a
    reader copies, replace secrets with uppercase placeholders, and define each
    placeholder below the block.
6.  **Warnings before risk:** Put a warning before a destructive step, and state
    the trigger condition and the data or service loss.

Identify controls by their visible label or heading, not by position words such
as "above" or "on the right".

Test installation, migration, and recovery steps on a clean state. A pass on an
already configured developer machine has the status "assumed", not "measured".
Put the status in the report, not in the page.

## Reference, troubleshooting, and runbooks

Organize application, library, and command-line reference pages around the
public interface or "--help" hierarchy, not around internal source files. Derive
names, types, required inputs, mutually exclusive flags, defaults, side effects,
and errors from the code, schema, or parser. Do not expose private internals as
part of the public contract.

Organize troubleshooting pages by observable symptoms and exact error messages.
List safe diagnostic checks before destructive recovery steps, and do not list
guesses as causes.

In an operations runbook, separate routine maintenance from emergency response.
State the stop condition that halts the procedure, the owner to contact if
rollback fails, and the record that the operator must leave.
