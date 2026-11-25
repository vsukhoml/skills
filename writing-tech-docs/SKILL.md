---
name: writing-tech-docs
description: >-
  Writes, revises, reviews, and triages technical documents for human readers:
  decision documents (design documents, proposals, specifications, ADRs, RFCs,
  execution plans, technical reports) and developer documentation (READMEs,
  how-to guides, references, runbooks, release notes). Use when drafting,
  restructuring, shortening, or reviewing a technical document, triaging
  incoming review comments, or simplifying English for international readers.
  Don't use for source code, code comments, commit messages, chat replies,
  marketing copy, or slides.
last_updated: 2026-11-24
---

# Writing technical documents for human readers

Optimize structure, content selection, and style first for your readers' job:
reviewing, deciding, or executing a task. Reader review and decision time is the
tightest bottleneck, so spending up to 4 times the drafting tokens on polish is
worth the cost. Write in plain, direct language for busy readers and non-native
English readers, with zero filler, praise, stagecraft, or repetition.

Each rule below has a stable ID (R1 to R32) cited by `doc_lint.py` in
`{skill_dir}`.

## Workflow

Table 1 selects the steps and output for each workflow mode.

Mode   | When                                                | Steps          | You deliver
------ | --------------------------------------------------- | -------------- | -----------
Write  | No draft exists.                                    | 1 to 7         | A new document and a report.
Revise | Editing or restructuring an existing draft.         | 1 to 7         | The updated draft and a report.
Review | Leaving feedback without modifying the draft body.  | 1, 2, 6, and 7 | Comments or report on key findings.
Triage | Addressing others' comments on your or shared docs. | 1, 2, 4, 6, 7  | Anchor-safe fixes, replies, resolutions.

*Table 1: Match the workflow mode to whether you author, edit, review, or
triage comments.*

### Scope by task and authorship

Match how strictly you apply the rules to the task and document ownership:

-   **New document or requested restructuring:** Apply all profile rules and fix
    every finding. Enforce full structural rules (R1 to R4, R9 to R11, R17),
    including an opening summary, 3-layer order, page-sized sections,
    single-home DRY items, and task-matched containers. On an existing document,
    reorganize sections or rename headings only when the user explicitly
    requests restructuring. Verify fact preservation with
    `--compare --allow-restructure`, and list heading changes in the report.
-   **Standard revision or narrow edit:** Apply all rules inside added or
    revised sections while keeping existing section order and heading words
    intact. Leave untouched sections alone, verify preservation with
    `--compare`, and report structural defects instead of reorganizing
    unprompted.
-   **Review and comment:** Follow [Reports](#reports), loading
    `tech-docs-comments` (`Review` mode) for Google Docs comments and
    suggestions.
-   **Incoming comment triage:** Load `tech-docs-comments` in Triage mode to
    address open threads, protect anchors, and resolve selectively. Contribute
    design context on `@person` threads when helpful.

### Steps

1.  **Confirm framing upfront:** Verify 3 inputs in the prompt or draft:
    **intended audience** (role and prior knowledge), **document type** (design
    doc, ADR, spec, README, runbook), and **target outcome**. Ask the user right
    away before drafting, revising, or reviewing if any structural input is
    unclear, proposing the likeliest default and alternatives. In
    non-interactive runs, state the default assumption in the report (adding an
    `[Open: ...]` marker below the summary only in Write or Revise mode). When
    only minor background is unstated, assume a domain peer unfamiliar with this
    system and note it in the report.
2.  **Select profile and size:** Pick the profile in Table 2, inspect any
    open-questions section (see [Open items](#open-items)), and size decision
    docs by reversal cost (R21). For developer docs, load the
    [developer documentation guide](references/developer_docs.md) to pick the
    page type.
3.  **Draft or audit the outline:** In Write mode or requested restructuring,
    build or fix the opening summary, 3-layer order, and section sizes (R1 to
    R3). Flatten deep headings, unify duplicate homes, and ensure the outline
    alone conveys the result (R4, R17). On existing documents without a
    restructuring request, keep existing headings and section order and note
    structural defects for the report.
4.  **Write or revise sections:** Route each block via Table 3, load
    `tech-docs-diagrams` when boundaries or multi-actor flows appear (R11), and
    apply R1 to R24 and [Open items](#open-items). In Write mode or requested
    restructuring, convert misfit blocks to the right container and move raw
    data to an appendix. Load [examples](references/examples.md) when
    calibrating `[Open: ...]`, DRY (R4), or option-table (R24) rewrites.
5.  **Polish language and clarity:** Apply R25 to R32 across extra editing
    passes so every sentence is plain, literal, and effortless to scan. Load the
    [plain English guide](references/plain_english.md) when simplifying dense
    prose, disambiguating overloaded jargon, or resolving R25 to R32 findings.
6.  **Lint and check:** Run `doc_lint.py` (plus `diagram_lint.py` on diagrams)
    and complete the [Manual checks](#manual-checks). In Revise mode, pass
    `--compare`, adding `--allow-restructure` only when restructuring was
    requested. Fix all findings in Write and Revise modes, or filter to key
    findings in Review mode.
7.  **Report or comment:** Deliver the report or Google Docs comments per
    [Reports](#reports).

## Profiles

Table 2 lists the rules that differ between decision documents and developer
documentation.

Topic                          | Decision document                              | Developer documentation
------------------------------ | ---------------------------------------------- | -----------------------
Examples                       | Design document, proposal, ADR, RFC, report    | README, how-to guide, reference, runbook, release notes
Opening summary (R2)           | Problem, measured effect, mechanism, main cost | What the thing is, who uses it, the first result
Document order (R3)            | Purpose, overview of the direction, detail     | Purpose, shortest path to a result, detail and reference
Status of a claim (R8)         | In parentheses after the claim                 | In the report only
Frame of a table (R12)         | A lead-in sentence and a caption               | A heading can be the lead-in. A caption only for a conclusion.
Table cell (R10)               | 15 words (30 words in an appendix)             | 30 words in a reference table or a catalog
Code names (R15)               | 2 for each behavior (unlimited in an appendix) | No limit if the names are the content
Claims and decisions (R21-R24) | All 4 rules apply                              | Not applied. Put a warning before each destructive step.
Lint option                    | `--profile decision` (the default)             | `--profile docs`

*Table 2: If one document has both jobs, select the profile by the first job of
the reader.*

## Limits for all modes

These 6 limits protect technical accuracy across every mode:

-   **Facts stay exact:** Never alter a number, unit, identifier, quoted
    message, or requirement meaning. Quote source text verbatim or paraphrase
    without quotes, and compute totals by script rather than by hand. If a
    source contradicts the draft, keep the draft and record an open item.
-   **No invented facts:** Separate current behavior from proposed behavior, and
    never describe a proposal or untested recovery step as working. Ground facts
    in code, specs, or design docs, or record an open item. Direct deductions
    from stated facts take the status "derived" and appear in the report.
-   **No guessed meaning:** Use a single probable meaning and list it in the
    report. If 2 meanings are plausible, keep the author's words and record an
    open item. Outside specs with normative "should", rewrite predictive
    "should" as "we expect" and team "should" as a proposal step or conditional
    imperative. Keep component "should" with an open item.
-   **Code semantics stay untouched:** Never alter code logic, commands, paths,
    or symbol names during revision. Add missing language tags, replace smart
    quotes with straight ASCII, and replace tabs with spaces outside `Makefile`
    recipes. Keep wide lines whose wrapping might alter syntax and report them.
-   **Structure, templates, and anchors:** Build clean structure from the start
    on new documents (R1 to R4, R9 to R11, R17). Keep required template headings
    and order, placing the summary below the title if the template has no
    summary slot. On existing documents, preserve section order and heading
    words (adjusting case only) and report structural defects. Reorganize
    sections or rename headings only when the user explicitly requests
    restructuring.
-   **Targeted edits, no synthetic voice:** Keep sentences that already satisfy
    the rules, touch only target sections on narrow edits, and never add
    dramatic hooks, fragments, or invented opinions.

## Open items

### Tracked open questions section

When a draft includes an open-questions section, apply these 4 rules:

-   **No duplicate markers:** Never add `[Open: question]` markers in that
    section or in the body for items already tracked there as open.
-   **Open and closed status:** When decided items stay for history, mark each
    item open or closed via a column, field, or `(open)` or `(closed)` label.
-   **Factual trade-off notes:** Keep any comment or trade-off field concise,
    direct, and factual without flowery words or category bias (R24). Ground
    added points in stated or source-verified facts without deciding the item.
-   **Consistent body prose:** Ensure body sections frame open items as
    undecided options pointing to the open item, and ensure closed items match
    the body.

### Inline markers for untracked gaps

In Write and Revise modes, use `[Open: question]` for untracked missing facts
(in Review mode, post comments instead):

-   **Standalone marker:** Place `[Open: question]` as its own paragraph with
    blank lines above and below, directly after the affected block. Ask one
    question per marker without repeating it in the summary.
-   **Decision-changing gaps only:** Add a marker only when the answer can alter
    the decision, a requirement contract, or a procedure outcome. List minor
    gaps in the report.
-   **Missing one-way structure:** Do not invent empty invariant or coverage
    lists. Add one marker if the step is one-way (R21), or report the gap.
-   **Uncommitted goals and vague claims:** State non-mandatory targets as goals
    with numbers rather than "must". Add a marker after vague claims that back a
    decision, and delete pure praise (listing deletions in the report).
-   **Unmeasured facts:** When the author confirms a value is unknown, write
    "not measured" or "not known" in prose without adding a marker.

## Reports

In Write and Revise modes, include up to 6 compact parts in your reply (omitting
`Changes` in Write mode). Cover **Reader and decision**, **Changes** (rule IDs
and deleted claims), and **Readings and derivations**. Follow with **Open
items** (noting at the top if inline markers await the author), **Facts not
verified**, and **Findings not corrected**.

In Review mode, inspect all checks and report only **key findings**. Prioritize
missing or conflicting contracts, invariants, failure paths, or units (R5, R8,
R16, R22, R23). Flag biased comparisons, missing disqualifiers, settled-looking
open items (R7, R21, R24), and misread-causing structure, diagram, or passive
defects (R2 to R4, R10, R11, R14, R28). Omit non-essential style nits unless
asked for a full copy-edit, order contract and decision defects before
structure, and report repeated patterns once.

For offline Markdown or chat reviews, cite rule IDs, quote the text, and propose
a fix or question. For Google Docs reviews, follow `tech-docs-comments`
(`Review` mode: 1-to-2-sentence Suggesting edits with reason notes, or compact
prefixed comments without repeating quotes or internal rule IDs).

## Format selection

Table 3 selects the lowest-effort container for each type of content.

Content                                           | Format          | Limit
------------------------------------------------- | --------------- | -----
Decision, invariant, or causal chain              | Short paragraph | 5 sentences, about 100 words
Parallel items, steps, or named short items       | List            | 3 to 7 items (or 2 multi-line steps)
Multi-paragraph items (most >= 1 paragraph)       | Short sections  | Body at least 3x heading length (R1)
Comparison of options, or if-then logic           | Table           | 5 columns, 15 words in a cell
Topology, boundaries, states, or message sequence | Diagram         | 3 to 9 boxes, 12 arrows (see R11)
Code, interface, or message layout                | Code block      | 25 lines, aim for 72 chars (limit 80)
Full schemas, proofs, inventories, or raw data    | Appendix / Tab  | Outside main path (`<= 3` Docs tabs)

*Table 3: Select the container that fits the reader's task, never for visual
variety.*

## Rules

### Structure

-   **R1. Page-sized sections:** Keep each section to one screen (at most 400
    words of prose), splitting longer sections at sub-problems. In Google Docs,
    default to Pageless format so 400-word sections read at a glance, keeping
    Paged format only if already set. Never shrink font size or spacing to fit a
    page (R20). Use child sections only when most items need at least a
    paragraph, avoiding 1-to-2-sentence sibling stubs. Keep leaf headings at
    least 3 times shorter than their body unless a template requires them.
-   **R2. Answer first:** Open the document and every section with the
    conclusion, decision, or governing constraint. Keep the opening summary to 3
    to 5 sentences stating the problem, measured effect, mechanism, and main
    cost, placing background and rejected options later.
-   **R3. Purpose, direction, then detail:** Order decision docs as purpose,
    chosen direction in one section, and detail (contracts, failures, coverage,
    rollout), summarizing rejected designs in an alternatives section. Keep
    required template headings (security, privacy, rollout) with a 1-line
    `Not applicable` reason when unused. Define terms before first use, and move
    full schemas, raw data, and long code to an appendix or at most 3 Google
    Docs child tabs.
-   **R4. One home for each item (DRY):** Define each requirement, decision,
    option, or open question once with an ID, a short name, or both matching the
    document convention. Pair any opaque ID or section number with a 2-to-4-word
    plain slug, such as `INV-2 (monotonic epoch)`. Elsewhere, refer to that ID
    or short name without repeating its definition, stating only local
    consequences, and never repeat the summary in a closing section.

### Selection of information

-   **R5. Exact contracts and worked examples:** State every requirement,
    precondition, invariant, trust boundary, failure and recovery path, limit,
    unit, and non-goal without losing precision. Specify caller guarantees,
    provider guarantees, and post-failure state on interfaces. Pair each
    non-trivial formula, layout, or boundary rule with a compact example
    (`<= 10` lines or 1 table row) showing concrete inputs and outputs.
-   **R6. Cut low-signal text:** Delete textbook explanations peers already
    know, drafting history, comments about the document itself, and prose lists
    of changed files, types, functions, or line numbers. Omit routine imports
    and boilerplate from code blocks with a short omission comment.
-   **R7. Problem without the solution:** State the problem as an observable
    failure, risk, or cost in the current system. Never frame it as the absence
    of your solution ("the system has no cache"), and define success
    independently of your deliverable.
-   **R8. Status of each claim:** Mark important claims in parentheses (excluded
    from sentence word counts): measured, calculated, estimated, derived,
    verified in source, cited, reported, or assumed. Also mark unverified gaps
    as not measured, not verified, or not known. If one status covers most
    claims, state it once below the summary and mark only exceptions. Verify
    checkable facts against primary sources or list them in the report as not
    verified. State deferred scope with its reason and tracker, and replace
    every `TBD`.

### Lists, tables, diagrams, and code blocks

-   **R9. Lists for parallel items:** Extract 3 to 7 parallel items, conditions,
    or failure modes (or 2 multi-line steps) into a vertical list. Keep 2 short
    items in a sentence, and keep causal reasoning chains in prose. Group sets
    larger than 7 or point to an appendix. Number lists only when sequence or
    priority matters, keep items grammatically parallel, and write each action
    or condition with an actor and verb.
-   **R10. Tables for conditions and comparisons:** Replace branching prose and
    comparisons of 3 or more options across 3 or more attributes with a table
    (never per-option "Pros and Cons" lists). Cap tables at 5 columns and 15
    words per cell. Repeat a baseline number if needed so rows stand alone, and
    move longer details below the table. Never merge cells or leave cells empty
    (write "0", "None", "N/A", or "Not measured"). Put units in headers, round
    summary trade-offs to 2 or 3 effective digits, and sort rows
    deterministically. Never build `(optional ID, name, prose explanation)`
    tables: use lists or sections instead.
-   **R11. Diagrams from source code:** Load `tech-docs-diagrams` when a section
    covers component or trust boundaries, branching or cyclic flows, or 3 or
    more interacting actors. Insert, format, and embed source-backed diagrams in
    Markdown and Google Docs per `tech-docs-diagrams` (D1 to D11).
-   **R12. A frame for each block:** Introduce each list, table, diagram, and
    code block with a complete sentence stating its purpose. Omit frames that
    merely repeat the heading above and note the lint finding in the report.
    State whether a code block shows current behavior, a proposed contract, a
    wire layout, or an example. Place a 1-line italicized conclusion caption
    below each table and figure (see Table 2 for developer docs).

### Sentences and paragraphs

-   **R13. One claim in each sentence:** Aim for 15 to 20 words per sentence
    (limit 25 words), splitting long sentences instead of dropping articles,
    "that", or repeated nouns. Keep each paragraph to one topic and at most 5
    sentences. Never join clauses with semicolons or dashes, and give newly
    inserted facts their own sentence.
-   **R14. Active voice, literal verb:** Put the acting component or person in
    the grammatical subject with a literal verb ("rejects", "signs", "retries",
    "drops"). Replace nominalizations ("validate", not "perform validation of")
    and vague verbs ("handles"). Never hide who owns an obligation behind an
    agentless passive ("must be validated"). Use passive voice only when the
    actor is unknown or is every possible caller, and order clauses as
    condition, trigger, result.
-   **R15. Plain words before code names:** State behavior in plain words first,
    then add at most 2 identifiers in parentheses per behavior so reviewers
    follow the logic without reading source code. Move extra symbols to an
    appendix, and skip the 2-identifier cap when symbols are the subject (such
    as flag or API lists).
-   **R16. Numbers, not praise:** Replace subjective words ("fast", "scalable")
    with bounded quantities, units, and conditions, such as "at most 40 ms at
    99% and 10 000 QPS". Delete throat-clearing filler ("it is worth noting
    that"), while keeping standard terms ("fast path", "minimal base image").

### Typography

-   **R17. Predictable headings:** Use at most 3 section heading levels in
    sentence case, without colons, slogans, `&`, or dashes. In Google Docs,
    format each document or tab title with the Title style, never Heading 1, and
    start top-level tab sections at Heading 1. Add an orienting sentence when
    child headings do not immediately divide a section. Never open a section
    with bare "This" or "It", and ensure headings plus first sentences form a
    standalone outline.
-   **R18. Bold for structure only:** Restrict bold to headings, table headers,
    and 1-to-8-word list lead-ins. Keep bold under 10% of body characters and
    never bold full sentences.
-   **R19. One role for each style:** Reserve monospace for literal code,
    commands, paths, and tokens, using Markdown inline and fenced code with a
    language tag. Indent code with spaces, use straight ASCII, and aim for 72
    characters per line (limit 80). Reserve italics for captions and first-use
    definitions, avoid body underlining except list lead-ins, and attach links
    to descriptive nouns.
-   **R20. A calm page and readable body size:** Keep default 11 pt Normal text
    (Arial, Inter, or Roboto) with harmonized Title and Heading 1 to 3 styles
    (R17) and standard spacing. Never shrink Normal text (especially below 10
    pt, such as 9.5 pt) or tighten spacing to cram a page. Avoid `ALL CAPS`
    emphasis (except uppercase normative spec keywords per R28) and decorative
    text colors. Omit informational "Note" and "Tip" callouts in decision docs
    and never stack callouts back to back. Place hazard warnings (`<= 1` per
    page in decision docs, or before each destructive step in developer docs)
    with trigger, loss, and safe action.

### Verifiable claims

-   **R21. Depth by cost of reversal:** Reversible single-component changes fit
    in 750 lint-counted words. One-way steps (destructive migrations, immutable
    code, published wire formats, unbacked deletions, excluding scheduled log or
    backup expiry) require full contracts, coverage, and alternatives. Mark each
    one-way step or record an open item if reversibility is unclear.
-   **R22. Named, enforced, tested claims:** Give each requirement, invariant,
    and assumption a doc-convention ID or short name (defaulting to REQ, INV, or
    ASM prefixes if needed, per R4). State one falsifiable sentence, the
    enforcing mechanism, and the verifying test (or the consequence if an
    assumption fails).

### Coverage and decisions

-   **R23. Stated coverage and stated negatives:** State the outcome and reason
    (including "no effect") for restart, partial failure, power loss, upgrade,
    rollback, and version mismatch. Cover performance, security, privacy,
    monitoring, cost, and integration concerns, and name open risks.
-   **R24. Factual, unbiased comparisons:** Compare all viable options
    (including "no change") across every material criterion in one table.
    Include cost, latency, complexity, or risk criteria that favor competing
    options, recording an open item or report gap if facts are missing. State
    verified facts without flowery language, exaggerated pros or cons, or "we
    recommend". Open the section with the deciding criterion, and state the
    chosen option and each rejected option's disqualifier after the table.

### Plain English for international readers

-   **R25. Plain words, domain terms, one term:** Use plain, everyday words and
    direct sentence structures, avoiding flowery or rarely used words and ornate
    constructions. Keep established technical jargon of the target domain (such
    as "quorum" or "idempotent") instead of awkward paraphrases. Define
    abbreviations and local terms at first use in 10 words or fewer, and use one
    term per concept throughout. When domain jargon reuses a common English word
    (such as "seal", "lease", "witness", "tombstone", or "claim"), clarify its
    technical meaning on first use. Pair it with a qualifying noun ("deletion
    tombstone", "consensus witness") so broader readers distinguish it from the
    everyday word. Never use the same word in both its technical sense and its
    everyday sense in one document.
-   **R26. Literal language:** Avoid idioms, metaphors, humor, contractions, and
    Latin abbreviations ("for example" and "that is", never "etc."). Write words
    instead of symbols ("and", "with", "about", never ampersands, plus signs,
    "w/", tildes, or "vs."). Replace phrasal verbs with single verbs
    ("configure", not "set up") while keeping standard terms ("rollback"), and
    write calendar months instead of fiscal quarters.
-   **R27. Complete and explicit grammar:** Keep articles and "that", cap noun
    chains at 3 nouns, give pronouns one clear referent, and place a noun after
    "this" or "these". Front-load positive conditions ("If the check fails, the
    device restarts") and rewrite double negations or trailing "unless" clauses
    positively. Place "only" directly before what it restricts, and split mixed
    "and" / "or" conditions into lists or tables.
-   **R28. Fixed meanings and modals:** Default to "must" (requirement), "must
    not" (prohibition), "can" (ability or permission), "might" (possibility),
    "will" (future fact), and "we expect" (prediction). Strongly prefer
    replacing "should", "may", "could", and "would" with a conditional
    imperative ("If X exceeds Y, run Z") or a fixed-meaning verb whenever
    possible. In formal or semi-formal specs that define normative keywords
    (such as RFC 2119), normative "SHOULD" and "MAY" are permitted. Lowercase
    normative "must", "should", and "may" are also permitted when a spec
    introduces normative keywords in lowercase (keep one case style throughout).
    Prefer "each" over "all" or "any", strip loophole words ("if possible", "as
    appropriate", "when necessary", "ideally", "typically"), and format
    quantities and `YYYY-MM-DD` dates explicitly.

### Grounded, non-synthetic prose

-   **R29. System-specific text only:** Delete sentences that fit another system
    unchanged, heading restatements, and reworded claim repeats. Outside
    migration or history sections, describe target-state behavior rather than
    drafting or commit chronology.
-   **R30. Direct statements, not stagecraft:** State what a component is or
    does directly, avoiding "It is not X; it is Y" contrasts unless correcting a
    stated misconception. Avoid dramatic colon reveals, rhetorical hooks,
    narrated candor, and self-praise.
-   **R31. Named sources and bounded scope:** Cite the primary document,
    standard, or test rather than "studies show", and mark cross-hardware or
    cross-workload numbers as `assumed` until verified on target. Strip chat
    citations, placeholders, and AI URL tracking parameters.
-   **R32. Plain copulas and literal modifiers:** Use "is" and "has" instead of
    inflated verbs ("serves as", "boasts"). Avoid human or moral adjectives on
    inanimate nouns ("honest metric") and drop trailing commentary participles
    ("highlighting", "underscoring").

## Code blocks and Google Docs styles

Keep code blocks focused on contracts (`<= 25` lines, R6, R19) and apply native
Google Docs styles:

-   **Diffs and comments:** Use a `diff` block with 2 to 3 context lines for
    1-to-5-line changes. Explain design rationale in prose outside the block for
    inline comments, and put short unit or invariant notes above lines rather
    than at line end.
-   **Copyable commands:** Omit shell prompts (`$` or `#`), replace secrets with
    UPPERCASE placeholders, and define each placeholder below the block.
-   **Creating Google Docs with native code blocks:** Never fake code blocks
    with manual "Courier New" or "Roboto Mono" paragraph fonts, "1x1" tables, or
    plain-text `insertText` calls. Import fenced Markdown as a Google Doc
    (`files.create` converting "text/markdown") so every fence becomes a native
    code block. Tag fences with concrete languages ("rust", "go", "python",
    "bash", "c"), avoiding bare fences or "text" and "plaintext" tags that print
    "None". In the Google Docs UI, insert `@Code block` ("Insert > Building
    blocks > Code block") or run "Edit > Paste from Markdown". Turn off smart
    quotes in "Tools > Preferences" before pasting code.
-   **In-place Google Docs code edits:** Update existing Docs through
    Markdown-aware sync tools or `@Code block` building blocks rather than
    monospace "Normal text" runs. Style inline code via Markdown import or
    `updateTextStyle` ("Roboto Mono", 0.5 to 1 pt below body size). Never pass
    literal backticks to `replaceAllText`.
-   **Google Docs title and headings:** When importing Markdown into Google
    Docs, write top-level tab sections as `#` (Heading 1), with subsections at
    levels 2 and 3 (R17). Format the opening document or tab title line with the
    Title paragraph style (`"namedStyleType": "TITLE"`), never "#".

## Rule priority

Resolve tensions between rules in 4 tiers. Put (1) **reader comprehension and
review ease** first (keep complete grammar and exact contracts over low word
count). Follow with (2) **layered depth** (peer-level main path, deep context in
appendices), (3) **task-matched container** (Table 3), and (4) **reversal risk**
(R21). See [rationale and evidence](references/rationale.md) when an author
disputes a rule.

## Check before review

### Automated lint and preservation check

Run `doc_lint.py` (at most 3 fix passes). Wrap intentional counterexamples
between `<!-- doc-lint: off -->` and `<!-- doc-lint: on -->`:

```bash
python3 {skill_dir}/scripts/doc_lint.py draft.md
python3 {skill_dir}/scripts/doc_lint.py --profile docs README.md
python3 {skill_dir}/scripts/doc_lint.py --compare original.md draft.md
python3 {skill_dir}/scripts/doc_lint.py --compare original.md draft.md \
  --allow-restructure
```

Pass `--compare` on revisions of existing documents to verify heading, code,
identifier, link, and number preservation. Add `--allow-restructure` only when
the user requested restructuring, and list heading changes in the report. Pass
`--link-root DIR` when linting a copy outside its source directory, or `-` to
read stdin. Pass `--strict` when open items or advisories must exit non-zero.
Rewrite `R28 (advisory)` modal hits as conditional imperatives whenever
possible, and list kept standard terms under `Findings not corrected`.

### Manual checks

Verify these 7 semantic checks after running `doc_lint.py`:

1.  **Skim and structure (R1-R3, R12, R17):** Reading only the summary,
    headings, first sentences, and captions conveys the problem, chosen
    direction, and reader decision without undefined forward terms. New
    documents (and existing documents when restructuring was requested) follow
    the 3-layer order, page-sized section limits, and `<= 3` heading levels.
2.  **Contracts and provenance (R5, R8, R16, R22, R31):** Every invariant,
    failure state, bound, unit, enforcement mechanism, verification test, and
    primary source is explicit and uninvented.
3.  **DRY and specificity (R3, R4, R6, R29):** Each item has one home referenced
    by ID or slug elsewhere, main paths omit symbol inventories, and prose stays
    system-specific.
4.  **Risk, options, and open items (R21, R23, R24):** One-way steps and fault
    scenarios are covered, option tables include criteria favoring competitors
    without bias, and open items stay undecided in body prose.
5.  **Diagrams and containers (R9 to R11):** Parallel items, conditional logic,
    and source-backed diagrams (checked with `tech-docs-diagrams` D1 to D11) use
    their lowest-effort container.
6.  **Active obligation owners (R7, R14, R30, R32):** Every obligation names its
    actor without stagecraft, negative contrasts, or solution-framed problems.
7.  **Plain words and overloaded jargon (R25 to R28):** Concepts use one term
    and pronouns have single referents. Domain jargon reusing a common English
    word is clarified on first use and never mixed with its everyday sense.

## References

-   Load [developer documentation](references/developer_docs.md) when selecting
    page types or structuring procedures, references, troubleshooting, or
    runbooks (`--profile docs`).
-   Load [plain English](references/plain_english.md) when simplifying prose for
    international readers, disambiguating overloaded jargon, or fixing R25 to
    R32 findings.
-   Load [examples](references/examples.md) when calibrating before-and-after
    rewrites for `[Open: ...]`, DRY references, option tables, or READMEs.
-   Load [rationale](references/rationale.md) when an author disputes a rule or
    asks for empirical citations.
