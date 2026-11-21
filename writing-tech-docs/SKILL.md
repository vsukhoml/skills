---
name: writing-tech-docs
description: >-
  Writes, revises, and reviews technical documents for human readers: decision
  documents (design documents, proposals, specifications, ADRs, RFCs, execution
  plans, technical reports) and developer documentation (READMEs, how-to
  guides, references, runbooks, release notes). Use when drafting or
  restructuring a technical document, shortening a document without losing
  requirements, simplifying English for international or non-native readers, or
  checking a draft before human review. Includes a lint script for measurable
  limits. Don't use for source code, code comments, commit messages, chat
  replies, marketing copy, or slides.
last_updated: 2026-11-20
---

# Writing technical documents for human readers

Optimize structure, content selection, and writing style first for the activity
of your stated readers: reviewing, deciding, or executing a task. Reader review
and decision time is almost always the tightest bottleneck in finalizing a
document and making sound decisions. Spending 4 times as many tokens to
restructure, tighten, and polish the document for reader ease is worth the cost.
Write for a busy reader who scans before reading and can have limited English.
Spend words on clear structure and complete grammar, and spend zero words on
filler, praise, stagecraft, or repetition.

The 32 rules in this file work inside any template. Each rule has a name and a
stable ID (`R1` to `R32`). The lint script and a review finding cite a rule by
its ID. In all other text, write the name of the rule and put the ID in
parentheses. In this file, `{skill_dir}` is the directory that contains this
file.

## Workflow

The mode selects the steps, and the profile selects the rules. Table 1 gives the
steps and the result of each mode.

Mode   | When                                    | Steps          | You deliver
------ | --------------------------------------- | -------------- | -----------
Write  | No draft exists.                        | 1 to 7         | A new document and a report.
Revise | A draft exists. The author wants edits. | 1 to 7         | The edited draft and a report.
Review | The author wants comments only.         | 1, 2, 6, and 7 | Comments on key findings only.

*Table 1: Review mode comments on key findings without changing the draft.*

### Scope by task and authorship

Match how strictly you apply the rules to the requested task and to who authored
the document:

-   **New draft or major revision:** Apply all profile rules and fix every
    review and lint finding. On an existing document, inspect and correct the
    structure first (R1 to R4, R9 to R11, and R17), then polish prose. Use this
    depth when creating a document or revising a draft, especially on
    user-authored or agent-drafted documents.
-   **Narrow edit to another author's document:** Apply all rules, including
    structure rules, to the sections that you add or revise. Leave untouched
    sections alone unless the user asks for a broader cleanup. If an untouched
    section has a structural defect, report it with a brief fix proposal.
-   **Review and comment:** Inspect the full check results, especially on
    another author's document, then comment only on key findings (see
    [Reports](#reports)). Include structural defects that hide decisions, repeat
    definitions, or pick the wrong container. Omit comments on non-essential
    style choices or phrasing that is less concise than possible when meaning is
    clear. Never add `[Open: question]` markers in Review mode, and post open
    issues as comments instead.

### Upfront framing questions

Before drafting, revising, or reviewing, check whether the prompt and draft make
these 3 framing inputs clear:

-   **Intended audience:** The role of the readers and what they already know.
-   **Document type:** The exact form, such as a design document, ADR,
    specification, execution plan, README, how-to guide, or runbook.
-   **Target outcome:** The decision that readers must make, or the task that
    readers must complete after reading.

If any framing input that shapes structure or content is missing or unclear, ask
the user right away before drafting, revising, or reviewing. Do not guess
silently, and do not defer structural questions until after completing the draft
or review. If the context points to a reasonable guess without certainty,
propose that guess as the default answer and list the other reasonable options.
Only in a non-interactive run where asking is impossible, state the default
assumption in the report and record an open item below the summary.

### Steps

1.  **Name the reader, document type, and result:** Confirm the audience,
    document type, and prior knowledge via
    [Upfront framing questions](#upfront-framing-questions). Complete "After
    reading, the reader can decide ..." for a decision document, or "After
    reading, the reader can ..." for developer docs. If only background is
    unstated, assume a peer who does not know this system, and state that
    assumption.
2.  **Select the profile and the size:** Pick the profile with
    [Profiles](#profiles). Check any open-questions section for open and closed
    items (see [Open items](#open-items)). Size a decision document by reversal
    cost (R21). For developer docs, read the
    [developer documentation guide](references/developer_docs.md) and match the
    reader's job. In Review mode, compare draft size with risk.
3.  **Write or fix the outline:** Write the opening summary, headings, and first
    sentences in purpose, direction, detail order (R3). This outline is a
    working step, not a deliverable, and must convey the result alone. In Revise
    mode, audit and fix the existing structure before editing prose (R1 to R4,
    R17). Reorder layers, fix section sizes and heading depth, and unify
    duplicate homes. Move raw data to an appendix, and rename unclear headings
    unless external anchors must stay fixed.
4.  **Write or restructure the sections:** Read the
    [examples](references/examples.md). Select the format of each piece of
    content with Table 3. Load `tech-docs-diagrams` to decide when to insert,
    replace, or split a diagram (R11). Apply the rules of the profile, from "Structure" to "Coverage and decisions", and follow
    [Open items](#open-items) for tracked questions. In Revise mode, apply the
    structural fixes from step 3 and convert misfit containers (Table 3), then
    edit prose cleanly.
5.  **Polish for reader ease and plain language:** Read the
    [plain English guide](references/plain_english.md), and apply R25 to R32.
    Spend extra passes (up to 4 times the drafting tokens) polishing structure,
    content, and style for the reader's review, decision, or task. In Write
    mode, cut every word and sentence that gives the reader no fact.
6.  **Check:** Run the lint script with the profile, plus the
    `tech-docs-diagrams` checks if diagrams appear. In Revise mode, pass
    `--compare` (and `--allow-restructure` when step 3 changed headings or
    section order). Then do the manual checks in
    [Check before review](#check-before-review). Fix all findings in Write and
    full Revise modes, and filter to key findings in Review mode.
7.  **Report:** Write the report for the mode. See [Reports](#reports).

## Profiles

A decision document asks the reader to approve or reject something. Developer
documentation helps the reader to do a task or to find a fact. The same rules
for sentences and words apply to both. Table 2 gives the rules that change.

Topic                        | Decision document                              | Developer documentation
---------------------------- | ---------------------------------------------- | -----------------------
Examples                     | Design document, proposal, ADR, RFC, report    | README, how-to guide, reference, runbook, release notes
Opening summary (R2)         | Problem, measured effect, mechanism, main cost | What the thing is, who uses it, the first result
Document order (R3)          | Purpose, overview of the direction, detail     | Purpose, shortest path to a result, detail and reference
Status of a claim (R8)       | In parentheses after the claim                 | In the report only
Frame of a table (R12)       | A lead-in sentence and a caption               | A heading can be the lead-in. A caption only for a conclusion.
Table cell (R10)             | 15 words                                       | 30 words in a reference table or a catalog
Code names (R15)             | 2 for each behavior                            | No limit if the names are the content
Claims and decisions (R21-R24) | All 4 rules apply                              | Not applied. Put a warning before each destructive step.
Lint option                  | `--profile decision` (the default)             | `--profile docs`

*Table 2: Developer documentation has no decision, so the rules for decisions
do not apply to it.*

If one document has both jobs, select the profile by the first job of the
reader. A README with one design section is developer documentation.

## Limits for all modes

These 6 limits protect the technical content:

-   **Facts stay exact:** Keep numbers, units, identifiers, quoted messages, and
    requirement meanings exact. Quote source text verbatim, or paraphrase
    without quotation marks. Compute totals by script, not by hand. If the
    source contradicts the draft, keep the draft and record an open item.
-   **No invented facts:** Separate current behavior from proposed behavior, and
    never describe a proposal or untested recovery step as working. Record an
    open item instead of inventing a value, reason, or test. A conclusion that
    follows directly from stated facts is permitted. Mark it "derived" and list
    it in the report. Ground facts in code, specs, and design docs.
-   **No guessed meaning:** If context gives one probable meaning, use it and
    list it in the report. If two meanings are probable, keep the author's words
    and record an open item. For "should", a prediction gets "we expect", a team
    action joins the proposal, and component behavior stays as an open item.
-   **Code meaning stays untouched:** In Revise mode, do not change code logic,
    commands, paths, or identifier names. You can add a missing code fence or
    language tag, and replace curly quotes with straight ASCII quotes. Outside
    `Makefile` recipes, you can replace tabs with spaces. If wrapping a wide
    line can change syntax or meaning, keep the line and report the finding.
-   **Fix structure, respect required templates:** On an existing draft without
    a required template, fix broken structure directly (R1 to R4, R9 to R11,
    R17). Reorder layers, split or merge mis-sized sections, convert misfit
    containers, and clarify weak headings. Keep required headings and order only
    for a mandatory template, and put a missing opening summary below the title.
    Keep exact heading words only when external links depend on those anchors,
    and list structural heading changes in the report.
-   **Targeted edits, no injected voice:** In Revise mode, keep clear sentences
    that follow the rules while fixing structural defects. On a narrow edit to
    another author's draft, edit target sections and report surrounding
    structural defects. Return a clean draft unchanged. Do not break clear
    sentences into fragments, add dramatic openings, or invent opinions to sound
    human.

## Open items

Authors often share early drafts with unresolved questions to collect feedback
from readers. A draft can list those questions in a dedicated section, while
`[Open: question]` markers flag untracked gaps that need input from the author.

### Tracked open questions section

If a draft has a section that lists open items or open questions, apply these 4
rules:

-   **No duplicate markers:** Do not add `[Open: question]` markers in that
    section or in the body for items already listed there as open. Skipping
    duplicate markers also keeps the lint script from counting tracked questions
    as `OPEN` items.
-   **Open and closed status:** Track which items in the section are open and
    which items are closed. A document can keep decided items in this section to
    preserve a decision record. If the section keeps decided items, ensure that
    its structure marks each item as open or closed. Use a table column, a
    repeated item field, or an `(open)` or `(closed)` label before or after the
    item name.
-   **Comments on trade-offs:** If the section has a table column or a repeated
    field for comments on each item, review those comments. Keep comments on
    open items concise, direct, and factual. State the consequences of each
    option without flowery words, exaggerated pros or cons, or category bias
    (R24). Ground each added point in stated facts or verified source behavior,
    and do not decide the open item.
-   **Consistent status in the body:** Verify that the rest of the document
    treats each open item as undecided. If another section states an open
    question as a settled decision, rewrite that text as one possible option and
    point to the open item. If an item in the section is closed, verify that the
    body matches the recorded decision.

### Inline markers for untracked gaps

In Write and Revise modes, apply these 7 rules to missing facts or untracked
questions outside an open-questions section. In Review mode, never insert
`[Open: question]` markers into the draft, and leave open issues as comments
instead:

-   **Marker:** Write `[Open: question]` as a separate paragraph, with an empty
    line above it and below it. A long marker can continue on the next line. Put
    it after the paragraph, the list, or the table that needs the fact. Each
    marker asks about one fact or one missing structure. Write each marker one
    time, and do not repeat it in the summary.
-   **Priority:** Write a marker only if the answer can change the decision,
    the meaning of a requirement, or the result of a procedure. Put each other
    gap in the report.
-   **Missing structure:** If the draft has no facts for an invariant, a
    coverage list, or a disqualifier, do not build an empty structure. If the
    structure belongs to a one-way step, write one marker. In all other cases,
    report the gap.
-   **Goal without a commitment:** If the author wants a value but does not
    require it, state it as a goal with its number. Do not write "must".
-   **Vague claim:** If a claim without a number supports the decision, keep the
    claim and add a marker. If the claim is only praise, delete it and list it
    in the report. A vague word in quotation marks is still vague.
-   **Fact that nobody knows:** If the author states that a value is not
    known, write "not measured" or "not known" in the text. Do not write a
    marker, because the author has no answer.
-   **Before human review:** Leave the markers in the text for the author.
    Before sharing the draft, the author answers each marker or moves the
    question to the open-questions section. If markers remain, state in the
    first line of the report that untracked markers wait for the author.

The lint script prints each `[Open: question]` marker with the label `OPEN` and
counts those markers apart from the findings. A marker does not fail the lint,
unless you pass `--strict`.

## Reports

The report tells the author what changed and what stays open.

In Write mode and Revise mode, the report has at most these 6 parts:

-   **Reader and decision:** The role of the reader, and the sentence from
    step 1.
-   **Changes:** List structural fixes (reordered layers, split or merged
    sections, renamed headings, moved appendices, and container conversions)
    with their rule IDs. Also list prose changes by rule ID and each deleted
    claim with its reason. In Write mode, omit this part.
-   **Readings and derivations:** Each meaning that you selected for an unclear
    text, and each conclusion that you derived.
-   **Open items:** Each inline marker as a numbered question, and the items
    still open in any open-questions section.
-   **Facts not verified:** Each checkable fact that you did not compare with
    its source, and each claim without a status.
-   **Findings not corrected:** Each lint finding and each failed check that
    stays, with the reason.

In Review mode (whether posting inline document comments or a review report),
use the check results to find real defects, then report only key findings:

-   **Key findings only:** Comment on missing or conflicting contracts and
    invariants, or missing failure paths and units (R5, R8, R16, R22, R23). Also
    comment on biased comparisons, missing disqualifiers, and open questions
    stated as settled decisions (R7, R21, R24). Flag structural defects with a
    fix: missing summaries, inverted order, mis-sized sections, deep headings,
    or duplicate homes (R1 to R4, R17). Flag wrong containers, diagram defects,
    and ambiguous actors or modals that hide obligations (R10, R11, R14, R28).
-   **Skip style and conciseness nits:** Omit comments on non-essential style
    choices or phrasing that is less concise than possible when meaning is
    clear. Include style nits only when the user asks for a full copy-edit.
-   **Open issues as comments:** Never add `[Open: question]` markers to the
    draft in Review mode. Leave missing facts, unverified assumptions, and open
    questions as comments with a concrete question or suggested text.
-   **Order and deduplication:** Put decision, contract, and trade-off findings
    before structural findings. Report a repeated pattern one time with its
    locations.
-   **Parts and format:** Give the rule IDs, the quoted text, and the proposed
    text or question to the author. Follow the rules in this file, with no
    length limit on quotations.

## Format selection

Each type of content has one format that costs the reader the least effort.

Content                                           | Format          | Limit
------------------------------------------------- | --------------- | -----
Decision, invariant, or reason                    | Short paragraph | 5 sentences, about 100 words
Parallel items, steps, or named short items       | List            | 3 to 7 items, short explanation per item
Multi-paragraph items (most >= 1 paragraph)       | Short sections  | Body at least 3x heading length (R1)
Comparison of options, or if-then logic           | Table           | 5 columns, 15 words in a cell
Topology, boundaries, states, or message sequence | Diagram         | 5 to 9 boxes, 12 arrows (see R11)
Code, interface, or message layout                | Code block      | 25 lines, 72 characters on a line (limit 80)
Full schemas, proofs, inventories, or raw data    | Appendix        | Outside the main path

*Table 3: The task of the reader selects the format. Variety is not a reason.*

## Rules

### Structure

-   **R1. Page-sized sections:** Keep each section to one screen, which is at
    most 400 words of prose. Split a longer section at a sub-problem. Use
    separate sections for a set of items only if most items need a full
    paragraph or more. Do not create sections in which most sections hold only 1
    or 2 sentences. Keep each leaf heading at least 3 times shorter than its
    section body. Otherwise use a list or merge the text into its parent
    section, unless the template requires the heading.
-   **R2. Answer first:** Start the document and each section with the
    conclusion, the decision, or the governing constraint. The opening
    summary has 3 to 5 sentences. It states the problem and its measured effect,
    the proposed mechanism, and the main cost. Background and rejected options
    come later.
-   **R3. Purpose, direction, then detail:** Order the document in 3 layers
    below the opening summary. The first layer states the purpose: the problem,
    the reason to act now, measurable goals, and non-goals. A non-goal is an
    expected result that the author excludes, not the negative of a goal. The
    second layer gives the direction in one section, with the decision and its
    reason. The third layer gives the detail: contracts, failure paths,
    coverage, and rollout. A reader who stops after any layer has a complete
    picture at that depth. Use the same order inside long sections, and define
    each term, constraint, or model before the first sentence that uses it. Move
    full schemas, raw measurements, long code, and rare-case catalogs to an
    appendix.
-   **R4. One home for each item (DRY):** Follow the DRY ("do not repeat
    yourself") style. Define each requirement, design decision, design option,
    or open question one time, concisely and directly, with all required
    details. Give the item an ID, a short name, or both, matching the document
    convention for items of that type. In every other place, refer to the item
    by its ID or short name without repeating its definition. State only the
    consequences of that definition for the context of the section that
    references it. An opening summary can state a result one time, and no
    closing section repeats the summary.

### Selection of information

-   **R5. Exact contracts:** State each requirement, precondition, invariant,
    trust boundary, failure path, recovery path, limit, unit, and non-goal
    exactly. Do not remove one of them to save space. Shorten the wording, not
    the precision. For each interface, state what the caller must guarantee,
    what the provider guarantees, and the state after a failure.
-   **R6. Cut low-signal text:** Delete textbook explanations that the readers
    know, the history of the draft, and comments about the document itself.
    Delete lists of changed files, types, functions, and line numbers. Version
    control already records them. Omit routine imports and boilerplate from code
    blocks, and mark omitted lines with a short comment.
-   **R7. Problem without the solution:** Describe the problem as a failure,
    risk, or cost that a reader can observe in the system before the change. Do
    not describe it as the absence of your solution, for example "the system has
    no cache". Define success as a result that a person can verify without your
    deliverable.
-   **R8. Status of each claim:** Give the status of each important claim in
    parentheses after the claim: measured, calculated, estimated, derived,
    verified in source, cited, or assumed. If most facts have one status, state
    that status one time below the summary, for example "The team reports all
    facts below". Then mark only the claims with a different status. Compare
    each checkable fact with its primary source before review: paths, names,
    sizes, and measurements. If you cannot read the source, list the fact in the
    report as not verified. For a scope cut, state what is deferred, the reason,
    and the tracking record. Replace each "TBD" placeholder with the fact or
    with an open item. A status in parentheses does not count toward the length
    of a sentence.

### Lists, tables, diagrams, and code blocks

-   **R9. Lists for parallel items:** Move 3 or more parallel items, conditions,
    or failure modes out of a sentence into a vertical list. Keep 2 parallel
    items in the sentence. If a sentence has more than 7 parallel items, do not
    make a list of them. Group the items, or point to the section that holds
    them. Use numbers only if the order matters. Give all items the same
    grammatical form. Write each action and each condition as a complete clause
    with an actor and a verb.
-   **R10. Tables for conditions and comparisons:** Replace branching prose with
    a table. Do the same for a comparison of 3 or more options across 3 or more
    attributes. Put one fact in each cell, and split or transpose any table
    wider than 5 columns. Do not build a table that has only an optional number
    or short ID, an item name or link, and a prose explanation. Use a numbered
    or bulleted list instead, or use short sections if most items need a full
    paragraph or more (see R1). In a list, highlight the optional ID and title
    in bold or underline, then add the explanation after a colon or clean break.
    In short sections, turn the optional ID and item name into a heading at the
    matching level and put the explanation below it.
-   **R11. Diagrams from source code:** Load the `tech-docs-diagrams` skill when
    a section covers boundaries or branching flows, or when 3 or more actors
    interact. Insert a diagram whenever `tech-docs-diagrams` advises one, and
    use a list or table for linear steps or option comparisons. Format and embed
    every diagram in Markdown or Google Docs according to `tech-docs-diagrams`
    rules (D1 to D10). Keep diagram labels to 1 to 3 words (limit 5) without
    item IDs, and put extra details in a keyed block below.
-   **R12. A frame for each block:** Introduce each list, table, diagram, and
    code block with a complete sentence that states its purpose. Before a code
    block, state whether the block shows current behavior, a proposed contract,
    a data layout, or an example. Put a short caption in italics below each
    table and figure. The caption states the conclusion, not the title. A
    frame that only repeats the heading above it is warm-up text. Table 2 gives
    the frames that developer documentation needs.

### Sentences and paragraphs

-   **R13. One claim in each sentence:** Aim for 15 to 20 words in a sentence.
    The limit is 25 words. A paragraph has one topic and at most 5 sentences. A
    reader can restate the paragraph in one sentence. Do not join two claims
    with a semicolon or a dash. When you add a fact to an existing document,
    give the fact its own sentence.
-   **R14. Active voice, literal verb:** Write in the active voice.
    Make the component or person that acts the subject of the sentence. Use the
    passive voice only if the actor is unknown, or if the actor is each possible
    caller or user. Use a literal verb, for example "rejects",
    "signs", "retries", or "drops". Replace a noun that hides a verb: write
    "validate", not "perform validation of". Replace a vague verb such as
    "handles" with the real action. Order the clauses as condition, trigger,
    result.
-   **R15. Plain words before code names:** Explain the behavior in plain words
    first. Then add at most 2 identifiers in parentheses for each behavior. Move
    the other identifiers to an appendix. A reviewer must be able to follow the
    logic without the source code. The limit does not apply if the identifiers
    are the content, for example in a list of flags or paths.
-   **R16. Numbers, not praise:** Replace a subjective word such as "fast",
    "scalable", or "lightweight" with a bounded quantity, a unit, and a
    condition. An example is "at most 40 ms for 99% of requests at 10 000
    requests in a second". Delete filler such as "it is worth noting that". A
    standard term stays, for example "minimal base image" or "fast path".

### Typography

-   **R17. Predictable headings:** Use at most 3 heading levels. Write short
    topic labels in sentence case, without a colon and without a slogan. The
    headings and the first sentence of each section form a complete outline.
-   **R18. Bold for structure only:** Use bold for headings, table headers, and
    list lead-ins of 1 to 8 words (such as an optional ID and item title). Do
    not make a sentence bold. Keep bold below 10% of the text. Readers skip
    plain text that is near bold text, and caveats are usually plain text.
-   **R19. One role for each style:** Use monospace only for literal code,
    commands, paths, and protocol tokens. Format each code block with a language
    tag, spaces instead of tabs, straight ASCII characters, and at most 72
    characters on a line (limit 80). See
    [Code blocks in Markdown and Google Docs](#code-blocks-in-markdown-and-google-docs).
    Use italics only for captions and for the first definition of a term. Do not
    underline body sentences, unless underlined titles mark list lead-ins
    consistently (R10). Attach each link to a descriptive noun, not to a raw
    address or to the word "here".
-   **R20. A calm page:** Use sentence case in all text. Do not write words in
    capital letters for emphasis. Use at most one callout box on a page, for a
    hazard or a critical invariant. Do not use color as decoration.

### Verifiable claims

-   **R21. Depth by cost of reversal:** Size the document by the cost to reverse
    the decision. A reversible change in one component gets a short proposal of
    at most 750 words in the count of the lint script. Mark each one-way step,
    for example a destructive data migration, immutable code, a published
    format, or the deletion of data that has no other copy. A deletion on a
    stated schedule is not a one-way step, for example backup retention or log
    rotation. A one-way step gets full contracts, coverage, and alternatives. If
    the draft does not show whether a step is reversible, record an open item.
-   **R22. Named, enforced, tested claims:** Define each requirement and each
    invariant once with an ID, a short plain name, or both, matching the naming
    convention of the document (R4). State one falsifiable sentence, the
    mechanism that enforces it, and the test that verifies it. For an
    assumption, state the result if the assumption is false. If the document
    needs IDs and sets no convention, use short prefixes such as REQ, INV, and
    ASM with a number. In other sections, refer to the claim by its ID or short
    name without repeating its definition, and state only its local consequences
    (R4).

### Coverage and decisions

-   **R23. Stated coverage and stated negatives:** Name the cases that you
    examined: restart, partial failure, power loss, upgrade, rollback, and
    version mismatch. Examine also the concerns of the system type, for example
    performance, security, privacy, monitoring, cost, and integration with other
    systems. For each concern or objection that the reader can have, write the
    result with its reason, also if the result is "no effect". Name the risks
    and the uncertain points that the reviewer must examine.
-   **R24. Factual, unbiased comparisons:** Describe each option and trade-off
    concisely and directly as verified facts, without flowery language or
    opinions such as "we recommend". Do not exaggerate benefits or drawbacks of
    any option. Compare all options, including "no change" if possible, across
    the same criteria in a table. Avoid category bias by including every
    material criterion, including categories such as cost, latency, complexity,
    or risk that favor competing options. Do not select only the categories that
    tilt the result toward one option. If a material category lacks facts in the
    draft or source, record an open item or report the gap instead of omitting
    that category. For a settled decision, state the chosen option after the
    table with the deciding criterion and the fact that disqualifies each
    rejected option. Mark a reason that follows from 2 stated facts as
    "derived", or record an open item if no stated fact gives the reason.

### Plain English for international readers

-   **R25. Common words, one term:** Select the most common word that is exact.
    Use the same term for the same thing in the full document. A reader with
    limited English assumes that a new word means a new thing. Define each
    abbreviation and each local term at its first use. Keep the standard
    technical terms of the field.
-   **R26. Literal language:** Do not use idioms, metaphors, humor, or
    references to one culture. Replace a phrasal verb with one verb: write
    "configure", not "set up". A standard technical term stays, for example
    "rollback". Write "for example" and "that is", not the Latin abbreviations.
    Do not use contractions.
-   **R27. Complete and explicit grammar:** Keep the articles and the word
    "that". Limit a chain of nouns to 3 nouns. Give each pronoun one possible
    referent, and put a noun after "this" and "these". Put the condition before
    the result: "If the check fails, the device restarts." Prefer a positive
    statement to a negative statement.
-   **R28. Fixed meanings and formats:** Use "must" for a requirement, "must
    not" for a prohibition, "can" for an ability or permission, and "might" for
    a possibility. Use "will" for a future fact, and "we expect" for an
    unverified prediction. Do not write advice as an opinion. In a decision
    document, state the action as a part of the proposal, with the fact that
    requires it. In developer documentation, write the instruction with its
    condition: "If the table has more than 10 000 rows, use the batch command."
    Do not use "should", "may", "could", or "would", because each word has more
    than one meaning. Write a quantity of 2 or more as digits, with its unit.
    Write a date as year, month, day, for example 2031-04-09. Do not use a
    relative date such as "next week".

### Grounded, non-synthetic prose

-   **R29. System-specific text only:** Delete any sentence that can move
    unchanged to a document for another system. Delete warm-up sentences that
    only restate a heading, and paragraphs that repeat an earlier claim in new
    words. Outside migration and decision-history sections, describe how the
    system works in the target state, not the edit history that produced it.
-   **R30. Direct statements, not stagecraft:** State what a component is or
    does directly. Do not write negative contrast setups such as "It is not X.
    It is Y." unless the text corrects a stated misconception. Do not write
    dramatic colon reveals, rhetorical questions, announcements of candor, or
    sentences that label your own point important or clever.
-   **R31. Named sources and bounded scope:** Name the primary document,
    standard, or test behind each external claim, instead of writing "studies
    show" or "experts agree". Mark a measurement from another hardware model,
    workload, or version as "assumed" until a test verifies it on the target
    system. Remove chat markup, draft placeholders, and AI-tool tracking
    parameters from links.
-   **R32. Plain copulas and literal modifiers:** Write "is" and "has" instead
    of inflated verbs such as "serves as" or "boasts". Do not attach human or
    moral adjectives such as "honest" to inanimate nouns such as "metric" or
    "shape". Do not end a sentence with a participle commentary clause such as
    "highlighting" or "underscoring".

## Code blocks in Markdown and Google Docs

A reviewer reads a code block to verify an interface, an invariant, or a data
layout, not to compile a file. Remove lines that do not serve that check, and
format the block so that lines never wrap or shift columns.

Shape each code block so that a reviewer can scan it:

-   **Role before line 1:** State in the lead-in sentence whether the block
    shows current behavior, a proposed contract, a wire layout, or a
    counterexample (R12).
-   **Contract only:** Keep only the signature, fields, or lines that affect the
    decision, in 25 lines or fewer. Replace imports and boilerplate with a short
    comment such as `// ... unchanged fields ...` (R3, R6).
-   **Diffs for small edits:** If a change alters 1 to 5 lines of an interface
    or configuration, show a `diff` block with 2 to 3 context lines.
-   **Reasons in prose:** Explain design reasons outside the block, where
    reviewers in Markdown or Google Docs can attach comments to one sentence.
    Put short comments on the line above a statement for units, offsets, or
    invariants, never at the end of a long line.
-   **No ASCII boxes:** Use a table (R10) or a diagram (R11) instead of aligned
    text art inside a code block.
-   **Copyable commands:** In commands that a reader copies, omit the shell
    prompt (`$` or `#`), replace secrets with uppercase placeholders, and define
    each placeholder below the block.

Table 4 gives the rules that keep code readable in Markdown and in Google Docs.

Aspect      | Markdown                                                          | Google Docs
----------- | ----------------------------------------------------------------- | -----------
Container   | Use triple backticks with a language tag (`go`, `python`, `text`). | Insert `@Code block` (`Insert > Building blocks > Code block`) with the language.
Import      | Put blank lines around the fence. Indent fences inside a list.    | Enable Markdown in `Tools > Preferences`, then use `Edit > Paste from Markdown`.
Line width  | Aim for 72 characters on a line (limit 80) to avoid scrolling.    | Keep lines to 72 characters so 10 pt code fits Letter and A4 pages.
Indentation | Indent and align with 2 or 4 spaces, never tab characters.        | Use spaces only. Google Docs tabs jump to 12.7 mm stops and break columns.
Characters  | Keep straight ASCII quotes (`"`, `'`), `--` flags, and `...`.     | Turn off "Use smart quotes" in `Tools > Preferences` to keep ASCII characters.
Page flow   | If a block contains triple backticks, wrap it in 4 backticks.     | Set "Keep with next" on the lead-in and "Keep lines together" on short blocks.

*Table 4: Normal paste and manual Courier New paragraphs break code in Google
Docs.*

For inline code in Google Docs (R19), set a monospace font such as `Roboto Mono`
at 0.5 to 1 pt below the body font size.

## Conflicts between rules

Human review, decision making, or task execution is the tightest bottleneck, so
spend extra tokens whenever polish lowers reader effort. These 4 principles
decide a conflict between rules:

1.  **Reader effort before writing or token cost:** Optimize structure, content,
    and style for the reader's review, decision, or task, even at 4 times the
    token cost. Keep structure and grammar words that lower effort for readers
    with limited English.
2.  **Layers before one average depth:** Write the main path for an informed
    peer. Put deeper context in an appendix.
3.  **Reader task before format habit:** The task of the reader selects the
    format. Do not select a format for variety.
4.  **Risk before uniform depth:** Spend detail where the cost to reverse an
    error is high.

Table 5 gives the resolution of the common conflicts.

Conflict                                | Rules        | Resolution
--------------------------------------- | ------------ | ----------
Short text against complete grammar     | R13, R27     | Keep articles, "that", and repeated nouns. Cut filler and repetition.
More context against less context       | R3, R6, R25  | Define a term in 10 words or fewer. Move background to an appendix.
Local repetition against one home       | R4           | Keep one home. Refer by ID or short name and state local effects.
Summary against one home                | R2, R4       | The summary states the result one time. The body gives the proof.
Stated negatives against short text     | R6, R23      | Write one line for each expected concern. Delete sections that nobody expects.
Item IDs against plain words            | R4, R15, R22 | Match the doc convention. Pair an opaque ID with its short name.
Full contracts against a short document | R5, R21      | Reduce the number of topics. Do not reduce the precision of a contract.
Lists against causal reasoning          | R9, R14      | Use lists for parallel items. Keep a chain of reasons in prose.
Technical term against common word      | R25, R26     | Keep the standard technical term. Make the words around it plain.
Template against answer first           | R2           | Keep the template. Put the summary directly below the title.
Answer first against a derived decision | R2, R24      | Start the section with the criterion that decides. State the decision after the table.
Complete table rows against one home    | R4, R10      | A comparison table can repeat a number, so that each row is complete.
Template against the document order     | R3           | Keep mandatory template order. Reorder ad-hoc drafts to 3 layers.
Cell limit against exact facts          | R5, R10      | Keep the facts. Move a long cell to a list below the table.
Existing headings against structure     | R1, R3, R17  | Restructure and clarify headings in Revise mode. Freeze words only for external links.
Frames against no warm-up text          | R12, R29     | Omit a frame that only repeats the heading. Report the lint finding.
Status of a claim against short text    | R8, R13      | Keep the status. It does not count toward the sentence limit.

*Table 5: Structure and precision win against a low word count.*

The [rationale](references/rationale.md) gives the reason and the evidence for
each rule. Read it if an author disputes a rule, or if Table 5 does not cover a
conflict.

## Check before review

### Automated lint and preservation check

Run the lint script on the Markdown file with the profile from step 2. In Revise
mode, pass `--compare` to verify that code blocks, identifiers, links, and
numbers from the original draft stay intact. Add `--allow-restructure` when step
3 intentionally reordered, split, merged, or renamed headings:

```bash
python3 {skill_dir}/scripts/doc_lint.py draft.md
python3 {skill_dir}/scripts/doc_lint.py --profile docs README.md
python3 {skill_dir}/scripts/doc_lint.py --compare original.md draft.md
python3 {skill_dir}/scripts/doc_lint.py --compare original.md draft.md \
  --allow-restructure
```

The script prints each finding as file, line, rule ID, and advice. The final
line prints the counts of findings, open items, and words, and exits with 1 on
findings. Correct each finding, or tell the author why the text stays.

Run the script at most 3 times to correct findings. This limit stops a loop on
findings that have no correction. A first run on the original in Revise mode
and one last run after the manual checks do not count. Put the findings that
stay in the report.

These 5 conditions change the command:

-   **Copy in another directory:** The script resolves relative links from the
    directory of the file. If you check a copy, pass `--link-root` with the
    directory of the original file.
-   **Unreadable file:** Send the text to standard input and give `-` as the
    file name.
-   **Structural revision in Revise mode:** Pass `--allow-restructure` with
    `--compare` when you reorder, split, merge, or rename sections, or move code
    to an appendix. The script still checks that code blocks, identifiers,
    links, and numbers stay intact. List heading changes in the report.
-   **New number in Revise mode:** `--compare` reports each number that the
    original does not contain. A count that you derived from the draft is
    permitted. List it in the report as derived.
-   **Open items in a pipeline:** Pass `--strict` if a draft with open items
    must fail.

### Lint limits

The script has these 3 limits:

-   **Rules without a check:** The script has no check for R5, R6, R7, R21, R22,
    and R23. For R24, it checks loaded comparison words only, so category bias
    is manual. For R11, it checks image alternative text only, so run the
    `tech-docs-diagrams` linter on diagrams. For R29 and R30, it checks only
    known phrases. For the other rules, it measures lengths, counts, preserved
    tokens, and known words.
-   **Text without a check:** For code blocks, the script checks the frame,
    length, language tag, width, tabs, and quote characters, and skips their
    words. It skips inline code and text in double quotes. Put
    `<!-- doc-lint: off -->` above a verbatim region and `<!-- doc-lint: on -->`
    below it. Its word count excludes tables and code blocks.
-   **No proof:** A lint result without findings does not prove that the
    document is clear or accurate. A finding on a standard term or on a quoted
    name is not a defect. Keep the term and list the finding in the report.

### Manual checks

Do these 7 manual checks after the lint:

1.  **Skim and structure check:** Read only the summary, headings, first
    sentences, and captions. Headings move from purpose to direction to detail,
    and first sentences form one chain without forward terms. On an existing
    draft, confirm you fixed broken order, mis-sized sections, and deep headings
    rather than copying them. The problem, decision, and reader action are clear
    (R1 to R3, R12, R17).
2.  **Contract check:** Each invariant, failure path, limit, unit, and scope cut
    is exact. Another engineer can build the design from the text and state why
    it was chosen. No number or source is invented (R5, R8, R16, R22, R31).
3.  **DRY and portability check:** Each requirement, decision, option, or open
    question has one home with an ID or short name matching the document
    convention. Other sections cite that ID or name without repeating the
    definition, stating only local consequences. No sentence fits another system
    unchanged, and no code inventory sits in the main path (R3, R4, R6, R29).
4.  **Coverage and open-item check:** Each one-way step is marked, and each
    expected concern has a result. Option comparisons stay concise and factual
    without exaggerated trade-offs or omitted categories that favor other
    options (R24). Settled decisions state their deciding criterion and
    disqualifiers, while open questions stay undecided in body prose (R21, R23,
    R24). Any tracked closed item shows its status, and comments state balanced
    trade-offs.
5.  **Format check:** No sentence holds 3 or more parallel items or 2 or more
    conditions. No table holds only an optional ID, a name or link, and prose.
    Leaf headings stay at least 3 times shorter than their body, and sibling
    sections are not mostly 1 or 2 sentences. Diagrams satisfy
    `tech-docs-diagrams` (D1 to D10). Blocks have frames, and code stays within
    72 characters (R1, R3, R9 to R12, R19).
6.  **Actor and directness check:** Each sentence names the actor and the
    action, without stagecraft, negative contrast setups, inflated copulas, or
    trailing commentary participles. The problem statement does not contain the
    solution (R7, R14, R15, R30, R32).
7.  **Translation check:** Each thing has one term. Each pronoun has one
    referent. Read the 3 longest sentences word by word with only the dictionary
    meaning of each word. If the meaning changes, rewrite the sentence (R25 to
    R28).

## References

-   The [developer documentation guide](references/developer_docs.md) selects
    page types and structures procedures, references, troubleshooting, and
    runbooks.
-   The [plain English guide](references/plain_english.md) has the word choices,
    the grammar patterns, the number formats, and the synthetic patterns to
    remove for R25 to R32.
-   The [examples](references/examples.md) show 12 texts before and after the
    rules. The final example is developer documentation.
-   The [rationale](references/rationale.md) has the reason, the evidence, and
    the limits of the evidence for each rule.
