# Digest format, watchlist, and automation setup

This reference provides the collector CLI commands, `watchlist.json` schema,
scheduled cron configuration, and worked digest templates for
`tech-docs-review-round`.

## Collector CLI recipes (`review_round_collect.py`)

Run collection and watchlist updates through the bundled script in
`{skill_dir}/scripts/review_round_collect.py`:

```bash
# Collect across watchlist.json + 3-day Drive auto-discovery:
python3 {skill_dir}/scripts/review_round_collect.py collect \
  --lookback-days 3 \
  --output /tmp/round_report.json

# Collect on explicit Google Doc URLs without Drive auto-discovery:
python3 {skill_dir}/scripts/review_round_collect.py collect \
  --doc "https://docs.google.com/document/d/DOC_ID/edit?resourcekey=KEY" \
  --no-auto-discover \
  --output /tmp/round_report.json

# Manage ~/.cache/tech-docs-review-round/watchlist.json:
python3 {skill_dir}/scripts/review_round_collect.py watchlist \
  --add "https://docs.google.com/document/d/DOC_ID/edit?resourcekey=KEY" \
  --deadline 2026-11-30
python3 {skill_dir}/scripts/review_round_collect.py watchlist --mute DOC_ID
python3 {skill_dir}/scripts/review_round_collect.py watchlist --list
```

Advance the `ack` baseline locally after reviewing or applying a round (or pass
`--refresh-live` after editing document prose yourself):

```bash
# Promote local digest_<tab_id>.md -> ack_<tab_id>.md (keeps collaborator
# replies posted after last_digest_utc un-acked for the next round):
python3 {skill_dir}/scripts/review_round_collect.py ack \
  --doc DOC_ID \
  --set-thread AAA1=complex_fix \
  --set-thread AAA2=ready_to_resolve \
  --defer-thread AAA3 --defer-days 7

# Re-pull live tabs into ack_<tab_id>.md after direct prose edits:
python3 {skill_dir}/scripts/review_round_collect.py ack \
  --doc DOC_ID \
  --refresh-live
```

## Watchlist schema (`~/.cache/tech-docs-review-round/watchlist.json`)

Store explicit review targets, muted document IDs, optional pending approver
emails, and title exclusion patterns in `watchlist.json`:

```json
{
  "documents": [
    {
      "doc_id": "EXAMPLE_DOC_ID",
      "url": "https://docs.google.com/document/d/EXAMPLE_DOC_ID/edit",
      "role": "author",
      "deadline": "2026-11-30",
      "approvers": [
        {"emailAddress": "reviewer@example.com", "status": "pending"}
      ],
      "active": true
    }
  ],
  "muted_doc_ids": [
    "ARCHIVED_OR_NOISY_DOC_ID"
  ],
  "exclude_title_regexes": [
    " - Notes by Gemini$",
    " - Transcript$"
  ]
}
```

## Scheduled daily automation (`cron`)

Schedule unattended read-only collection on an off-hour weekday minute
(`7 8 * * 1-5`) to avoid top-of-the-hour API quota spikes:

```bash
# crontab -e
CRON_TZ=America/Los_Angeles
SKILLS=~/.gemini/config/skills/tech-docs-review-round
COLLECT="$SKILLS/scripts/review_round_collect.py"
OUT=~/.cache/tech-docs-review-round/latest_report.json
7 8 * * 1-5 python3 "$COLLECT" collect --output "$OUT"
```

Pair the JSON report with your coding agent CLI in non-interactive read-only
mode to render the daily Markdown digest without mutating Google Workspace.

## Digest output templates

### Multi-document header and quiet-day heartbeat

When two or more documents are checked in one run, start with Table 1 and skip
full sections for quiet documents (RR10). Keep active documents in separate
per-document sections below Table 1. Number `[R1]` to `[RN]` sequentially across
the batch so every individual edit, reply, or resolution has a unique ID (RR6).

Document         | Role and trigger       | Action counts | Radar alerts             | Status
---------------- | ---------------------- | ------------- | ------------------------ | ------
CSP Key Rotation | Author (`watchlist`)   | `3 G1, 1 G2`  | `2` (`warn_2`, due)      | Active
Peer Auth Guide  | Collab (`open_thread`) | `1 G1, 1 G3`  | `1` (`ready_to_resolve`) | Active
DPE Attestation  | Author (`revised`)     | `0`           | `1` (`warn_1` in `2 d`)  | Quiet

*Table 1: Cross-document overview lets the author jump straight to active
documents while keeping visibility into quiet ones.*

On a single quiet document, output only the 3-line heartbeat:

```markdown
**DPE Attestation** ([Open Doc](https://docs.google.com/document/d/ID/edit)):
Quiet since `2026-11-22 08:07 UTC` (0 new comments, edits, or stage shifts).
Open threads: `2` awaiting reviewers (latest digest already acked).
Next alert: `XYZ` (`bob@`, complex fix) hits `warn_1` on `2026-11-25`.
```

### Active document header, clean edits, and staleness radar

Open each active document section with its cumulative window since
`last_ack_utc`, clean collaborator edits, and staleness radar (RR7):

```markdown
## 1. CSP Key Rotation ([Open Doc](https://docs.google.com/document/d/ID1/edit))
Source: `watchlist` (due `2026-11-30`) | Cumulative since ack `2026-11-21`:
2 comments, 1 suggestion, 1 edit, 2 radar alerts (`1` deferred, `9` legacy).

### Clean collaborator edits (no action needed)
| Section | Editor | Change since last ack | Verdict |
| :--- | :--- | :--- | :--- |
| `2.1` | `alice@` | Passive SPI bound (`<= 20 MHz`). | Matches §1, anchors ok |

### Staleness and approver radar
| Thread | Category | Stage and idle | Activity / Cal | ID |
| :--- | :--- | :--- | :--- | :--- |
| `carol@` (`AAA1`) | Complex fix | `warn_2` (`5.2 d`) | §5 (`+2 d`) | `[R2]` |
| `dave@x` (`AAA2`) | Complex fix | `due` (`7.4 d`) | No OOO cal | `[R3]` |
```

### Per-document action queues (1 unique ID per atomic action)

Never combine multiple documents into one item, and never bundle multiple
separate replies or resolutions under one unsplit ID (RR6, RR7):

```markdown
### Group 1: Small high-certainty (`Size: S`, `Cert: High`)
- **[R1]** `[Imp: High | Size: S | Cert: High]` Suggestion `s1` (`bob@`, §3.2)
  - Verdict: Good retry bound (`5`), but leaves Table 2 Row 4 (`3`) stale.
  - Action: Accept `s1`, set Table 2 Row 4 to `5`, and resolve `suggest.s1`:
    `Done: accepted and updated Table 2 Row 4 to 5 attempts.`
- **[R2]** `[Imp: Low | Size: S | Cert: High]` `warn_2` (`5.2 d`) on `AAA1`
  - Action: Post check-in reply (or skip until `7 d` closure on `2026-11-26`):
    `+carol@example.com FYI checking if Section 4.1 resolves your concern.`
- **[R3]** `[Imp: Low | Size: S | Cert: High]` Stale fix (`7.4 d`) on `AAA2`
  - Action: Resolve `AAA2` without mentioning elapsed days (`C11`):
    `Done: updated key-slot bounds in Section 2.`

### Group 2: Important (`Imp: High`, sorted `S` -> `M` -> `L`)
- **[R4]** `[Imp: High | Size: M | Cert: Med]` Edit regression (`frank@`, §4.3)
  - Verdict: `15 min` polling breaks Goal G3 (`<= 5 min` revocation SLA).
  - **[R4A]** (Recommended): Require `<= 60 s` push + `5 min` poll fallback.
  - **[R4B]**: Relax Goal G3 in Section 1.2 to `<= 15 min`.
```

Follow with separate numbered document sections (`## 2. Peer Auth Guide ...`)
continuing the `[R5]`..`[RN]` sequence across the batch.
