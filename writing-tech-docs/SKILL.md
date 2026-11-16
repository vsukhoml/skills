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
last_updated: 2026-11-15
---

# Writing technical documents for human readers

Write for a reader who is busy, scans before reading, and can have limited
English. The attention of that reader limits a review more than your writing
time does. Spend extra words on structure and on complete grammar. Spend no
words on filler, praise, stagecraft, or repetition.

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
Review | The author wants comments only.         | 1, 2, 6, and 7 | A list of findings.

*Table 1: Review mode does not change the draft.*

1.  **Name the reader and the result:** Write down the role of the reader, and
    what the reader knows before reading. The document starts from that
    knowledge. Then complete one sentence. For a decision document, the sentence
    is "After reading, the reader can decide ...". For developer documentation,
    the sentence is "After reading, the reader can ...", with the task of the
    reader. If the request and the draft do not give the role or the result,
    record an open item below the summary. If only the knowledge of the reader
    is missing, assume a reader who knows the field and does not know this
    system. State the assumption in the report.
2.  **Select the profile and the size:** Select the profile with
    [Profiles](#profiles). For a decision document, size the document by the
    cost to reverse the decision (R21). For developer documentation, read the
    [developer documentation guide](references/developer_docs.md) and match the
    page to the job of the reader. In Review mode, compare the size of the draft
    with the risk.
3.  **Write the outline:** Write the opening summary, the headings, and the
    first sentence of each section. Order the sections as purpose, overview of
    the direction, and detail (R3). A reader must understand the result from
    this outline alone. The outline is a working step, not a deliverable. In
    Revise mode, keep the headings of the draft and add only the missing parts.
4.  **Write the sections:** Read the [examples](references/examples.md). Select
    the format of each piece of content with Table 3. Apply the rules of the
    profile, from "Structure" to "Coverage and decisions". In Revise mode, edit
    the text in place.
5.  **Make the language plain and direct:** Read the
    [plain English guide](references/plain_english.md). Apply the rules in
    "Plain English for international readers" and in "Grounded, non-synthetic
    prose". In Write mode, then read the draft one more time and delete each
    word and each sentence that gives the reader no fact. The attention of the
    reader is the limit.
6.  **Check:** Run the lint script with the profile (and with `--compare` in
    Revise mode). Then do the manual checks in
    [Check before review](#check-before-review). In Review mode, read the plain
    English guide first. Each failed check is a finding.
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

-   **Facts stay exact:** Do not change a number, a unit, an identifier, a
    quoted message, or the meaning of a requirement. Quote source text word for
    word, or paraphrase without quotation marks. Do not type a computed total by
    hand if a script can compute it. If the source contradicts the draft, keep
    the draft and record an open item.
-   **No invented facts:** Separate current system behavior from proposed
    behavior, and do not describe a proposal or an untested recovery step as
    working. If a rule needs a fact that the draft does not contain, record an
    open item. Do not write a value, a reason, or a test that the author did not
    give. A conclusion that follows directly from the stated facts is permitted.
    Give it the status "derived", and list it in the report.
    Ground facts in the code, specifications, design docs.
-   **No guessed meaning:** If the context gives one probable meaning for a
    text, use that meaning and list it in the report. If two meanings are
    probable, keep the words of the author and record an open item. For
    "should", the meaning decides. A prediction gets "we expect". An action of
    the team is a part of the proposal. For the behavior of a component, keep
    the word and record an open item.
-   **Code meaning stays untouched:** In Revise mode, do not change code logic,
    commands, paths, or identifier names. You can add a missing code fence or
    language tag, and replace curly quotes with straight ASCII quotes. Outside
    `Makefile` recipes, you can replace tabs with spaces. If wrapping a wide
    line can change syntax or meaning, keep the line and report the finding.
-   **The template stays:** Keep the section order and the required headings of
    the template that the author uses. If the template has no place for the
    opening summary, put the summary directly below the title. In Revise mode,
    keep the words of each heading, because other pages link to them. You can
    change the case. Report the other heading findings.
-   **Targeted edits, no injected voice:** In Revise mode, keep each sentence
    that already follows the rules. Return a draft without findings unchanged.
    Do not break clear sentences into short fragments, add dramatic openings, or
    invent opinions to make the text sound human.

## Open items

An open item is a question that only the author can answer. Open items keep the
missing facts visible, and they keep guesses out of the text.

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
-   **Before human review:** Leave the markers in the text. The author answers
    each marker, or moves the question to a section "Open questions" with an
    owner and a tracking record. A document with markers is not ready for its
    readers. State this fact in the first line of the report.

The lint script prints each marker with the label `OPEN` and counts the markers
apart from the findings. An open item does not fail the lint, unless you pass
`--strict`.

## Reports

The report tells the author what changed and what stays open.

In Write mode and Revise mode, the report has at most these 6 parts:

-   **Reader and decision:** The role of the reader, and the sentence from
    step 1.
-   **Changes:** Each type of change with its rule ID, and each deleted claim
    with the reason. In Write mode, omit this part.
-   **Readings and derivations:** Each meaning that you selected for an unclear
    text, and each conclusion that you derived.
-   **Open items:** Each marker, as a numbered question.
-   **Facts not verified:** Each checkable fact that you did not compare with
    its source, and each claim without a status.
-   **Findings not corrected:** Each lint finding and each failed check that
    stays, with the reason.

In Review mode, the report is a list of findings with this form:

-   **Order:** Put the findings about content first: the decision, the
    contracts, the coverage, and the alternatives. The findings about sentences
    and words come after them.
-   **One finding for each pattern:** Report a repeated problem one time. List
    each occurrence with its line.
-   **Parts of a finding:** Give the rule IDs, the quoted text, and the proposed
    text.
-   **Absent content:** If the draft does not contain the content, give a
    question to the author in place of the proposed text.
-   **Format:** The report follows the rules in this file. A quotation from the
    draft has no length limit.

## Format selection

Each type of content has one format that costs the reader the least effort.

Content                                           | Format          | Limit
------------------------------------------------- | --------------- | -----
Decision, invariant, or reason                    | Short paragraph | 5 sentences, about 100 words
Parallel items, conditions, or steps              | List            | 3 to 7 items, 1 to 2 lines each
Comparison of options, or if-then logic           | Table           | 5 columns, 15 words in a cell
Topology, boundaries, states, or message sequence | Diagram         | 9 nodes, one relation type
Code, interface, or message layout                | Code block      | 25 lines, 72 characters on a line (limit 80)
Full schemas, proofs, inventories, or raw data    | Appendix        | Outside the main path

*Table 3: The task of the reader selects the format. Variety is not a reason.*

## Rules

### Structure

-   **R1. Page-sized sections:** Keep each section to one screen, which is at
    most 400 words of prose. Split a longer section at a sub-problem. Merge a
    one-sentence section into its parent section, unless the template requires
    the heading.
-   **R2. Answer first:** Start the document and each section with the
    conclusion, the decision, or the governing constraint. The opening
    summary has 3 to 5 sentences. It states the problem and its measured effect,
    the proposed mechanism, and the main cost. Background and rejected options
    come later.
-   **R3. Purpose, direction, then detail:** Order the document in 3 layers
    below the opening summary. The first layer is the purpose: the problem, the
    reason to act now, the goals with the measure of success, and the non-goals.
    A non-goal is a result that a reader can expect and that the author
    excludes. It is not the negative of a goal. The second layer is the overview
    of the direction: the approach in one section, with the decision and the
    reason for it. The third layer is the detail: contracts, failure paths,
    coverage, and rollout. A reader can stop after each layer and has a complete
    picture at that depth. Do not put a detail before the overview that gives it
    a place. Use the same order inside a long section. Each section follows from
    the sections before it: state a term, a constraint, or a model before the
    first sentence that depends on it. When the document presents the solution,
    the reader expects it. Move full schemas, raw measurements, long code, and
    catalogs of rare cases to an appendix.
-   **R4. One home for each fact:** State each definition, requirement, number,
    and failure chain in one place. In other places, point to it by name, for
    example "see Replay window (section 4.2)". A summary can state a result that
    the body explains. Do not add a closing section that repeats the summary.

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
    attributes. Put one fact in each cell. Split or transpose a table that is
    wider than 5 columns.
-   **R11. Diagrams for topology and flow:** Draw a diagram only for boundaries,
    state machines, and message sequences between actors. Use one relation type
    in each diagram. Do not mix build dependencies, runtime calls, and physical
    connections. If the viewer renders text diagrams such as Mermaid, prefer
    them to images. Machine translation cannot read text in an image, so explain
    each image label in the body text.
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
    lead-in keys of 1 to 6 words before a colon. Do not make a sentence bold.
    Keep bold below 10% of the text. Readers skip plain text that is near bold
    text, and caveats are usually plain text.
-   **R19. One role for each style:** Use monospace only for literal code,
    commands, paths, and protocol tokens. Format each code block with a language
    tag, spaces instead of tabs, straight ASCII characters, and at most 72
    characters on a line (limit 80). See
    [Code blocks in Markdown and Google Docs](#code-blocks-in-markdown-and-google-docs).
    Use italics only for captions and for the first definition of a term. Do not
    underline text that is not a link. Attach each link to a descriptive noun,
    not to a raw address or to the word "here".
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
-   **R22. Named, enforced, tested claims:** Give each requirement and each
    invariant a short plain name, one falsifiable sentence, the mechanism that
    enforces it, and the test that verifies it. For an assumption, state the
    result if the assumption is false. In the text, refer to a claim by its
    plain name, for example "the replay check". Add an ID only if the template
    or a tracking tool needs it. Then use the prefixes REQ, ASM, and INV with a
    4-digit number, and write the ID one time, at the definition: "Replay check
    (INV-0003)".

### Coverage and decisions

-   **R23. Stated coverage and stated negatives:** Name the cases that you
    examined: restart, partial failure, power loss, upgrade, rollback, and
    version mismatch. Examine also the concerns of the system type, for example
    performance, security, privacy, monitoring, cost, and integration with other
    systems. For each concern or objection that the reader can have, write the
    result with its reason, also if the result is "no effect". Name the risks
    and the uncertain points that the reviewer must examine.
-   **R24. A decision from a comparison:** Do not state a choice as an opinion,
    for example "we recommend" or "it is better to". State the criteria of the
    decision first, in one sentence or as the column headings of the table. Each
    criterion comes from a requirement, a goal, or a cost that the author gives.
    Do not add a criterion to complete the comparison. Compare each option with
    the same criteria in a table, and include the option "no change" if it is
    possible. Give the benefit, the cost, and the trade-off of each option as
    facts. After the table, state the decision as the result of the comparison.
    Name the criterion that decides, and the fact that disqualifies each
    rejected option. If the author gives a choice without a reason, a reason
    that follows from 2 stated facts has the status "derived". If no stated fact
    gives the reason, record an open item.

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

These 4 principles decide a conflict between rules.

1.  **Reader effort before word count:** Add structure and grammar words if they
    reduce the effort of the reader with the least English.
2.  **Layers before one average depth:** Write the main path for an informed
    peer. Put deeper context in an appendix.
3.  **Reader task before format habit:** The task of the reader selects the
    format. Do not select a format for variety.
4.  **Risk before uniform depth:** Spend detail where the cost to reverse an
    error is high.

Table 5 gives the resolution of the common conflicts.

Conflict                                | Rules       | Resolution
--------------------------------------- | ----------- | ----------
Short text against complete grammar     | R13, R27    | Keep articles, "that", and repeated nouns. Cut filler and repetition.
More context against less context       | R3, R6, R25 | Define a term in 10 words or fewer. Move background to an appendix.
Local repetition against one home       | R4          | Keep one home. Use a pointer that names the content of the target.
Summary against one home                | R2, R4      | The summary states the result one time. The body gives the proof.
Stated negatives against short text     | R6, R23     | Write one line for each expected concern. Delete sections that nobody expects.
Numbered IDs against plain words        | R15, R22    | Write the plain name in the text. An ID stays at the definition.
Full contracts against a short document | R5, R21     | Reduce the number of topics. Do not reduce the precision of a contract.
Lists against causal reasoning          | R9, R14     | Use lists for parallel items. Keep a chain of reasons in prose.
Technical term against common word      | R25, R26    | Keep the standard technical term. Make the words around it plain.
Template against answer first           | R2          | Keep the template. Put the summary directly below the title.
Answer first against a derived decision | R2, R24     | Start the section with the criterion that decides. State the decision after the table.
Complete table rows against one home    | R4, R10     | A comparison table can repeat a number, so that each row is complete.
Template against the document order     | R3          | Keep the section order of the template. Use the order inside each section.
Cell limit against exact facts          | R5, R10     | Keep the facts. Move a long cell to a list below the table.
Kept headings against heading rules     | R17         | In Revise mode, keep the words of the heading. Report the finding.
Frames against no warm-up text          | R12, R29    | Omit a frame that only repeats the heading. Report the lint finding.
Status of a claim against short text    | R8, R13     | Keep the status. It does not count toward the sentence limit.

*Table 5: Structure and precision win against a low word count.*

The [rationale](references/rationale.md) gives the reason and the evidence for
each rule. Read it if an author disputes a rule, or if Table 5 does not cover a
conflict.

## Check before review

### Automated lint and preservation check

Run the lint script on the Markdown file with the profile from step 2. In Revise
mode, pass `--compare` to verify that headings, code blocks, identifiers, links,
and numbers from the original draft stay intact:

```bash
python3 {skill_dir}/scripts/doc_lint.py draft.md
python3 {skill_dir}/scripts/doc_lint.py --profile docs README.md
python3 {skill_dir}/scripts/doc_lint.py --compare original.md draft.md
```

The script prints each finding as file, line, rule ID, and advice. The last line
gives the number of findings, the number of open items, and the number of words.
The exit status is 1 if the script has findings. Correct each finding, or tell
the author why the text stays.

Run the script at most 3 times to correct findings. This limit stops a loop on
findings that have no correction. A first run on the original in Revise mode
and one last run after the manual checks do not count. Put the findings that
stay in the report.

These 4 conditions change the command:

-   **Copy in another directory:** The script resolves relative links from the
    directory of the file. If you check a copy, pass `--link-root` with the
    directory of the original file.
-   **Unreadable file:** Send the text to standard input and give `-` as the
    file name.
-   **New number in Revise mode:** `--compare` reports each number that the
    original does not contain. A count that you derived from the draft is
    permitted. List it in the report as derived.
-   **Open items in a pipeline:** Pass `--strict` if a draft with open items
    must fail.

The script has these 3 limits:

-   **Rules without a check:** The script has no check for R5, R6, R7, R21, R23,
    and R24. For R22, it reports only an ID that occurs more than 2 times. For
    R11, it checks image alternative text only, so diagram topology and relation
    rules are manual. For R29 and R30, it checks only known phrases. For the
    other rules, it measures lengths, counts, preserved tokens, and known words.
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

1.  **Skim check:** Read only the summary, the headings, the first sentences,
    and the captions. The headings go from the purpose to the overview of the
    direction, and then to the detail. The first sentences form one chain of
    reasons, and no first sentence uses a term from a later section. The
    problem, the decision, and the request to the reader must be clear (R2, R12,
    R17).
2.  **Contract check:** Each invariant, failure path, limit, unit, and scope cut
    is present and exact. An engineer who did not write the document can build
    the design from it, and can state why the design was selected. No number or
    source is invented (R5, R8, R16, R22, R31).
3.  **One-home and portability check:** No claim has two homes. No sentence can
    move unchanged to a document for another system. No inventory of code is in
    the main path (R3, R4, R6, R29).
4.  **Coverage check:** Each one-way step is marked. Each expected concern has a
    result. The decision follows a comparison with stated criteria, and each
    rejected option has a disqualifier (R21, R23, R24).
5.  **Format check:** No sentence contains 3 or more parallel items, or 2 or
    more conditions. Each list, table, diagram, and code block has a frame. Code
    blocks show only the contract and stay within 72 characters on a line (R3,
    R9 to R12, R19).
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
-   The [examples](references/examples.md) show 9 texts before and after the
    rules. The last example is developer documentation.
-   The [rationale](references/rationale.md) has the reason, the evidence, and
    the limits of the evidence for each rule.
