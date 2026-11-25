# Google Docs comment mechanics, API recipes, and examples

This reference gives the Google Docs sidebar layout constants, Google Drive and
Docs REST API patterns, stale-thread timestamp checks, and Review and Triage
card examples.

## Sidebar geometry and folding constants

Table 1 lists the Google Docs layout and API limits for right-margin comment
cards.

Parameter                     | Value in Google Docs               | Practical impact on comments
----------------------------- | ---------------------------------- | ----------------------------
Margin card width             | `282 px` (`246` to `258 px` text)  | Wraps `14 px` text at `34` to `38` chars (5 to 7 words) per line.
`"Show more"` fold threshold  | `150 px` (about 7 wrapped lines)   | Single-paragraph cards of 15 to 45 words stay unfolded (C4).
Collapsed preview height      | `78 px` (about 3 visible lines)    | Cards past `150 px` show only about 100 characters until clicked.
Previewed replies in margin   | `2` replies (`3` in Stream drawer) | Middle replies collapse behind `"X more replies"` once a thread grows.
Maximum comment UTF-8 payload | `2048` bytes                       | Hard Drive/Docs API rejection above `2048` UTF-8 bytes (C6).

*Table 1: Blank lines (`\n\n`) burn 20 px each and push even 30-word comments
over the `150 px` fold cliff.*

## Google Drive and Docs REST API recipes

### Inspect comments, timestamps, suggestion IDs, and anchors

Fetch comment threads via the Google Drive API v3 (`files/{fileId}/comments`)
and inspect tabs and suggestions via the Google Docs API v1 (`documents.get`):

```bash
# List comment threads (including quotedFileContent anchors and replies):
DRIVE="https://www.googleapis.com/drive/v3/files/DOC_ID"
curl -sS -G -H "Authorization: Bearer $TOKEN" "$DRIVE/comments" \
  --data-urlencode "includeDeleted=false" \
  --data-urlencode "fields=comments(id,resolved,content,replies)"

# Fetch multi-tab AST with inline Suggesting-mode IDs:
DOCS="https://docs.googleapis.com/v1/documents/DOC_ID"
curl -sS -G -H "Authorization: Bearer $TOKEN" "$DOCS" \
  --data-urlencode "includeTabsContent=true" \
  --data-urlencode "suggestionsViewMode=SUGGESTIONS_INLINE"
```

Construct direct thread deep links as
`https://docs.google.com/document/d/DOC_ID/edit?disco=COMMENT_ID` (keeping
`resourcekey=KEY` before `&disco=COMMENT_ID` when link-shared). For C11
stale-thread checks, compare the latest reply timestamp against that author's
timestamps across `comments` and `revisions`. Subtract known absences longer
than 1 week.

### Post Review comments, replies, and Triage resolutions

Create comments and replies through `files/DOC_ID/comments` and
`comments/COMMENT_ID/replies`, keeping plain Google Docs formatting (`*bold*`,
`_italic_`, bare URLs) under `2048` UTF-8 bytes (C6):

```bash
# Post a new margin comment with quotedFileContent context:
DRIVE="https://www.googleapis.com/drive/v3/files/DOC_ID"
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" "$DRIVE/comments?fields=id,content" \
  -d '{"content":"Blocking: Specify retry cap in Section 2.",
       "quotedFileContent":{"value":"retries failed client RPCs"}}'

# Resolve an agreed fix with an outcome note (C11):
curl -sS -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "$DRIVE/comments/COMMENT_ID/replies?fields=id,action" \
  -d '{"action":"resolve",
       "content":"Done: added the 15-minute TTL cap in Section 3.2."}'
```

In Triage mode (`documents.batchUpdate`), splice targeted edits inside the
paragraph instead of recreating whole blocks so open comment anchors stay
attached (C9). Drive API rejects deleting any reply that carries a `resolve` or
`reopen` action (`HTTP 400`), so verify C11 eligibility before resolving.

## Worked examples for Review and Triage

### Review mode: front-loading and splitting loosely connected points

Counterexample bundling two issues and burying the defect past character 100:

```markdown
Bad (bundled, 46 words, defect buried after polite filler):
Thanks for writing up the key rotation section! Looking at the rollover
paragraph, it seems like if a verifier rejects an unknown key ID during
rollout, canary servers fail requests, and also we need to document who
owns the emergency revocation runbook and revocation propagation time.
```

Split loosely connected points into separate cards, and front-load any card past
45 words in its first 100 characters (C4, C5, C7):

```markdown
Good card 1 (25 words, unfolded):
Blocking: Rejecting unknown key IDs during rollout breaks verification
while signers canary new keys. Pre-distribute next-epoch public keys 24
hours before signing activation.

Good card 2 (52 words, summary in first 89 chars):
Question (blocking): Missing revocation propagation bound and on-call
owner in Section 4.3. Without a hard cache TTL ceiling across regional
proxies, compromised signing keys remain accepted at edge verifiers long
after emergency key rotation completes. Specify the maximum propagation
delay (for example, <= 5 minutes) and link the owning team runbook.
```

### Triage mode: `@person` threads and 15-minute sync proposals

On a thread directed at another `@person` where your design context helps (C1,
C11), contribute your view without closing the thread:

```markdown
Thread reply on @bob thread (32 words, left open):
Added the hardware-counter budget (4 KiB NVRAM) in Section 3.4 so the
rollout constraint is explicit. +bob@example.com leaving open to confirm
whether factory provisioning needs a separate slot.
```

At 4 or more participants or 4 to 5 non-converging Triage replies (C12, C13),
propose a 15-minute sync in the thread. Notify the user in chat with the
`?disco=COMMENT_ID` link:

```markdown
Thread reply (33 words):
Two options remain open: stateless JWT revocation lists against
synchronous session introspection (logged in Section 5.2).
+alice@example.com +bob@example.com proposing a 15-minute sync to pick one
before freeze.
```
