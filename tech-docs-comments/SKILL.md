---
name: tech-docs-comments
description: >-
  Writes, stages, and triages Google Docs comments and suggested edits on
  technical documents in outbound Review mode and incoming-comment Triage mode.
  Use when reviewing a Google Doc and leaving comments or suggestions, or when
  reviewing, replying to, editing for, and resolving comments left by others on
  your own or shared technical document. Don't use for pull-request or patch
  code reviews (use code-review).
last_updated: 2026-11-24
---

# Google Docs comments and review triage for technical documents

Optimize every margin comment, suggested edit, and reply for clear reading and
sound decisions inside the narrow (`282 px`) Google Docs sidebar. Keep each
thread focused on one point, move durable answers into the document body, and
respect collaborator notification load.

Each rule below has a stable ID (C1 to C14). In `{skill_dir}`, `comment_lint.py`
checks staged batches before upload. Pair this skill with `writing-tech-docs`
for prose edits and `tech-docs-diagrams` for diagrams. Use the Google Drive
Comments API (v3), Google Docs API (v1), or a Workspace tool for live calls.

## Workflow

Table 1 selects the mode for outbound reviews or incoming comment triage.

Mode   | When                                                  | You deliver
------ | ----------------------------------------------------- | -----------
Review | Reviewing a document and leaving feedback for owners. | High-signal comments or suggestions (C1 to C14).
Triage | Addressing others' comments on your or shared docs.   | Anchor-safe prose fixes, replies, and resolutions.

*Table 1: Review mode reports key defects, while Triage mode resolves incoming
feedback in the document and threads.*

Google Docs has no server-side draft state for comments: API writes notify
collaborators right away. Post live when asked to comment or reply on the Doc.
Stage locally first when asked only to review without posting, or before scope
changes or pushback against a human reviewer in Triage mode.

1.  **Read document and open threads:** Read the tab and fetch open comments
    (Drive API `comments.list` or your Workspace tool) first (C2).
2.  **Select scope and channel:** Filter Review findings per C1, or classify
    open Triage threads and stale timestamps and route each via Table 2 (C1, C3,
    C11).
3.  **Edit prose safely:** Check open anchors on each target paragraph before
    editing (C9). Apply anchor-safe Triage edits, or 1-to-2-sentence Suggesting
    edits with a reason comment in Review mode (C3, C9).
4.  **Draft compact cards:** Follow C4 to C7 on length, 100-character summaries,
    atomic cards, plain formatting, and prefixes or Triage outcomes.
5.  **Lint and verify anchors:** Run `comment_lint.py` on staged batches, verify
    unique anchors in Review mode (C8), and confirm intact open anchors after
    Triage edits (C9).
6.  **Post in one batch:** Upload comments or replies in a single pass (C14) and
    apply the resolution rules in C11. Notify the user in chat whenever you
    propose a 15-minute sync (C12).

## Choosing the right feedback channel

Table 2 routes each review or triage action to the lowest-friction Google Docs
mechanism (C1 to C3, C9, C11).

Situation                                       | Mechanism                   | Follow-up action
----------------------------------------------- | --------------------------- | ----------------
Obvious typo on an owned or co-authored doc     | Direct edit (Editing mode)  | No comment card needed.
1-to-2-sentence wording or precision fix        | Suggesting mode and comment | Reply on `suggest.<ID>` with brief reason (no `Why:`).
Contract gap, question, or multi-sentence issue | New margin comment          | Prefix severity (C7) and state defect and fix (C5).
Existing open thread covers `>= 2/3` of point   | Reply to existing thread    | State agreement (or partial gap) and add new detail (C2).
Incoming Triage comment answered by doc clarity | Anchor-safe edit and reply  | Clarify prose first, post `<= 15`-word pointer, apply C11.

*Table 2: Route localized text fixes to suggestions, durable answers to prose,
and overlapping points to existing threads.*

## Rules

### Scope, overlap, and feedback channel

-   **C1. Review focus and Triage coverage:** In Review mode (especially on
    another author's doc), comment only on key findings. Prioritize broken
    contracts, missing failure paths or units, biased trade-offs, open items
    stated as settled, and comprehension blockers. Ask questions on early drafts
    instead of attacking unstated internals, and flag repeated patterns once. In
    Triage mode on your or a shared doc, address every open thread for the
    author or team. On threads directed at another `@person`, contribute
    context, thoughts, or edits when your vision applies instead of waiting.
    Leave those threads open when that person's input is still needed (C11).
-   **C2. Extend two-thirds thread overlaps:** Inspect open threads before
    drafting comments. If an existing comment already covers two-thirds or more
    of what you want to say, do not open a new card. Reply to that thread, state
    your agreement (and any partial disagreement), and add your remaining point.
-   **C3. Direct reason on Suggesting edits:** Use Suggesting mode only for
    localized, non-controversial edits of 1 or 2 sentences. Attach a brief
    comment on `suggest.<ID>` stating why the change helps, without a `"Why: "`
    prefix. For example, write "Aligns the retry cap with the 5 s timeout in
    Section 2." Use a margin comment instead of multi-paragraph Suggesting
    redlines, and never insert `[Open: ...]` markers into the draft in Review
    mode.

### Sidebar geometry, phrasing, and anchoring

-   **C4. Target 15 to 45 words unfolded:** Cards taller than about 7 lines fold
    to a 3-line preview. Recommend 15 to 45 words in one paragraph with zero
    blank lines. Give more detail (advisory above 60 words, hard cap 120 words)
    when a complex point requires it. Above 45 words, state the prefix and
    summary in the first 100 characters for the collapsed preview. Split loosely
    connected points on one passage into separate short cards instead of one
    long comment.
-   **C5. One atomic point per card:** Never bundle unrelated or loosely
    connected points into one comment (`"Also, ..."` breaks per-issue
    resolution). State the defect or question, a brief consequence, and a
    concrete fix or bounded choice. Omit the highlighted quote, multi-part
    numbered templates, greetings, apologies, `"you"`-blame, and praise.
-   **C6. Plain-text Google Docs formatting:** Google Docs comments render only
    single-asterisk bold, underscore italics, hyphen strikethrough, and bare
    URLs (`https://...`). Write native Docs markup without backticks or Markdown
    links, or convert Markdown inline syntax before uploading via the Drive
    Comments API. Keep every comment under `2048` UTF-8 bytes and out of
    multi-line code blocks.
-   **C7. Review prefixes and Triage outcomes:** Start root Review comments with
    Blocking, Question, Question (blocking), Suggestion, Optional, Nit, or FYI,
    followed by a colon. Omit internal rule IDs on others' docs, and prepend
    `[AI Review]` when posting under a human account without prior human review.
    In Triage replies, omit severity prefixes and open with the outcome: Done,
    Updated Section X, Tracked in `#123`, or a direct trade-off answer. Prefer
    "Done:" over "Resolved:" when stating completed fixes.
-   **C8. Resilient 3-to-10-word anchors:** Anchor each new comment to a unique
    3-to-10-word (15 to 80 char) phrase inside one paragraph or cell, verified
    against the tab text. In Review mode, recommend at most 2 cards per
    paragraph by extending overlaps (C2) and skipping minor polish beside
    blockers. Never withhold a 3rd or further important comment solely to stay
    under 2. In Triage mode, answer all open threads and consolidate overlaps
    onto one prose fix.

### Triage edits, emojis, and resolution

-   **C9. Clarify prose and protect anchors:** Comments vanish upon resolution,
    so answer reviewer questions in the document prose or `Open Questions`
    first, then post a `<= 15`-word pointer reply. Before editing a paragraph in
    Triage mode, inspect all open anchors on it so fixing one thread never
    orphans another into Comment History. Splice targeted edits inside anchored
    spans instead of deleting whole paragraphs, and never run blind global
    replace. Verify every open comment's `quotedFileContent` phrase still
    resolves after editing.
-   **C10. Restrained emojis:** Default to plain words without emojis, and never
    post intermediate `"looking"` (`👀`) status replies: finish your review or
    edit and reply directly. Never include an emoji that duplicates accompanying
    text, such as "✅ Done:", "✅ Resolved:", or "👍 Agreed": write plain words
    instead. Restrict emojis to standalone `👍` (Agreed) or `✅` (Done) replies
    that carry no prose text. Post a standalone `👍` only on key design or
    contract points needing explicit sign-off, never on minor items.
-   **C11. When to resolve a thread:** Never resolve silently: post an outcome
    reply first, and on others' docs resolve only your own satisfied threads. In
    Triage mode, resolve right away after applying an agreed localized fix
    (`"Done: ..."`) or deferring an agreed item to an issue tracker or
    `Open Questions`. Leave the thread **open** when a fix or proposal is
    complex, so the comment author can verify it. Leave threads open on
    disagreements (applying accepted partial edits and explaining the rest after
    user confirmation) or while awaiting an `@mentioned` peer. Resolve **stale**
    threads where you replied last (excluding known author absences longer than
    1 week from idle time) in two cases. Close agreed complex fixes after **1
    week** idle. On disagreements with partial edits and rationale posted, close
    after **3 weeks** idle. Or close **1 week** after the comment author's
    latest doc edit or comment occurring at least 1 day after your last reply on
    this thread. State only the substantive outcome (preferring "Done: ..." over
    "Resolved: ...") in stale-closure notes, omitting elapsed idle time such as
    "closing after 7 days".

### Sync escalation and mentions

-   **C12. Circuit breaker and 15-minute sync:** Recommend stopping margin
    ping-pong at 3 non-converging replies in Review mode (4 to 5 in Triage) or 4
    or more debating participants (3 is routine). Log the options and trade-offs
    in `Open Questions` or `Alternatives Considered` in the document body. Or
    propose a focused 15-minute sync in the thread naming the unresolved
    participants and decision needed. Notify the human user in chat right away
    with the `?disco=COMMENT_ID` thread URL whenever you propose a sync.
-   **C13. Single-DRI mentions and FYI:** Write full organization emails
    (`+user@example.com` or `@user@example.com`), never bare usernames or first
    names, and state what is needed. For an action or decision, mention one
    accountable DRI and assign the thread when authorized. For awareness only,
    write `+user@example.com FYI: <reason>` without assigning. Outside a C12
    sync proposal naming the unresolved participants, never post unassigned
    multi-person pings: label each role (`Assigned` against `FYI`).
-   **C14. Notification hygiene and batching:** Do not mention or assign the
    document owner on routine comments, because Google Docs already notifies the
    owner. Reserve owner mentions and assignment for urgent blockers or explicit
    turn handoffs. Batch comments or replies into one pass, seek early feedback
    from 2 or 3 peers, and route sign-offs through Google Docs Approvals ("File
    > Approvals").

## Check before posting

### Automated comment lint

Run the bundled linter on staged JSON or Markdown batches before uploading (pass
`--markdown-converted` when an upload helper converts Markdown inline syntax):

```bash
python3 {skill_dir}/scripts/comment_lint.py staged_comments.json
python3 {skill_dir}/scripts/comment_lint.py --mode triage \
  --markdown-converted replies.json
```

Fix all reported errors and inspect advisory length (`> 60` words) or paragraph
pile-up (`> 2` cards) notes before posting.

### Manual checks

Verify these 5 semantic checks after running `comment_lint.py`:

1.  **Scope and overlap (C1, C2):** Only key Review defects remain, `>= 2/3`
    overlaps extend existing threads, and `@person` threads in Triage get author
    context when helpful without premature closure.
2.  **Unfolded scan and split (C4, C5):** Cards past 45 words state the core
    point in the first 100 characters, and loosely connected points on one
    passage sit in separate cards.
3.  **Prose-first and suggestion reasons (C3, C9):** Every 1-to-2-sentence
    Suggesting edit carries a direct reason comment, and every clarifying Triage
    answer updated the document body first.
4.  **Anchor safety and resolution timing (C8, C9, C11):** Review anchors match
    one unique phrase and Triage edits keep anchors intact. Complex fixes and
    disagreements stay open, and stale closures subtract `> 1`-week absences.
5.  **Escalation and mentions (C12, C13, C14):** Stalled or 4-participant
    threads move to doc options or a proposed 15-minute sync (pinging the user
    in chat). Mentions name one DRI or `FYI`.

## References

Read
[Google Docs comment mechanics and examples](references/gdocs_comment_mechanics.md)
for sidebar constants, REST API recipes, stale-thread checks, and worked
examples.
