# Plain English for international readers

Non-native English readers and machine translators parse one sentence at a time
using primary dictionary meanings. Keep established technical concepts, numbers,
and conditions intact while making surrounding words and grammar plain and
unambiguous (R25 to R32).

## Words, domain jargon, and overloaded English terms

Table 1 lists synonym groups that writers mix by accident. Pick one word per
concept across the document unless two words name distinct defined mechanisms
(R25).

Meaning                        | Words that writers mix
------------------------------ | --------------------------------------------
Make sure that a fact is true  | check, verify, validate, confirm, ensure
Something is wrong             | error, failure, fault, issue, problem, bug
Begin an operation             | start, run, launch, execute, invoke, trigger
Take something away            | delete, remove, erase, clear, drop, wipe
Values that control behavior   | configuration, settings, options, parameters
The party that sends a request | host, client, caller, user, application

*Table 1: Select one word per row across the full document.*

Plain language never bans established technical jargon of the target domain
(such as "nonce", "quorum", "idempotent", or "attestation"). However, when
domain jargon reuses an everyday English word, readers outside that
sub-specialty or using a dictionary can misread it as the ordinary word. Table 2
shows how to disambiguate overloaded English jargon on first use and avoid
dual-sense collisions (R25).

Jargon word | Everyday reading | Unambiguous first use and qualifier
----------- | ---------------- | -----------------------------------
"seal"      | close or approve | Pair as "TPM-sealed key" (*seal*: bind to PCR state).
"lease"     | rental contract  | Pair as "leader lease" (time-bounded lock epoch).
"witness"   | human observer   | Pair as "consensus witness node" or "log witness".
"tombstone" | grave marker     | Pair as "deletion tombstone record" on first use.
"ticket"    | bug or pass      | Write "session ticket" for auth and "bug" for issues.
"claim"     | assertion        | Write "JWT claim field", and use "statement" for prose.

*Table 2: Never use an overloaded word in both its technical sense and its
ordinary English sense in the same document.*

Table 3 lists common English words with multiple meanings that `doc_lint.py`
cannot flag automatically. Replace each with its single-meaning word when
reviewing prose.

Word    | Two meanings                | Write
------- | --------------------------- | --------------------------
"since" | Time, or reason             | "because" for a reason
"as"    | Time, reason, or comparison | "because" or "while"
"once"  | One time, or after          | "after" or "one time"
"while" | Time, or contrast           | "although" for a contrast
"when"  | Time, or condition          | "if" for a condition
"over"  | Position, or quantity       | "more than" for a quantity
"last"  | Final, or previous          | "final" or "previous"
"right" | Correct, or direction       | "correct"

*Table 3: Replace multi-meaning connectors so readers never guess between time
and cause.*

Run `doc_lint.py --words` to inspect the full automated replacement table:

```bash
python3 {skill_dir}/scripts/doc_lint.py --words
```

## Grammar

Table 4 shows rewrites that remove structural ambiguity in complex sentences
(R14, R27).

Pattern                 | Before                                                  | After
----------------------- | ------------------------------------------------------- | -----
Keep the word "that"    | "Verify the device accepts the key."                    | Verify that the device accepts the key.
Keep the articles       | "Send request to server, wait for reply."               | Send the request to the server. Then wait for the reply.
Break a chain of nouns  | "flash page erase time limit"                           | the time limit to erase a flash page
Put a noun after "this" | "This causes a reset."                                  | This error causes a reset.
Repeat the noun         | "The host sends the key to the chip, and it stores it." | The host sends the key to the chip. The chip stores the key.
Put the condition first | "The device restarts if the check fails."               | If the check fails, the device restarts.
Start a new sentence    | "The buffer overflows, causing a reset."                | The buffer overflows. This overflow causes a reset.
Use the positive form   | "Do not leave the port unlocked."                       | Lock the port.
Name the actor          | "The key is erased."                                    | The boot code erases the key.
Use a one-word verb     | "The service has been restarted."                       | The service restarted.

*Table 4: Complete grammar removes wrong parses for non-native readers.*

## Modal verbs and normative spec keywords

Outside formal or semi-formal specifications, "should", "may", "could", and
"would" carry multiple meanings. Strongly prefer replacing them with a
conditional imperative or one of the 6 fixed-meaning forms in R28 whenever
possible, as shown in Table 5.

Ambiguous modal   | Rewrite as conditional imperative or fixed meaning
----------------- | --------------------------------------------------
"should" / advice | "If the table exceeds 10 000 rows, run the batch command."
"should" (claim)  | "must" (requirement) or "we expect" (unverified prediction).
"may"             | "If debug mode is active, log the header", "can", or "might".
"could"           | "can" (ability) or "might" (possibility).
"would"           | "If the check fails, the device restarts."

*Table 5: Conditional imperatives state the exact trigger and action without
hiding whether an item is required.*

Formal and semi-formal specs that define normative keywords (for example citing
RFC 2119 or a conventions section) can use "MUST", "SHOULD", and "MAY".
Semi-formal specs can also introduce lowercase normative "must", "should", and
"may", provided the chosen case stays consistent throughout.

## International numbers, dates, and machine translation

Format numbers and dates so they read identically across locales, and structure
blocks so machine translators preserve meaning (R28):

1.  **Digits and units:** Write quantities of 2 or more as digits separated from
    units by a space (such as 3 retries or 40 ms). Use `KiB` for base-2 and `kB`
    for base-10.
2.  **Thousands and ranges:** Group thousands with spaces (`10 000`) rather than
    locale-dependent commas or periods, and write prose ranges with "to"
    (`3 to 7`).
3.  **Absolute dates and times:** Write `2026-11-23` and `14:30 UTC` or a
    release number (such as release 3.2), never "currently", "recently", or
    "soon".
4.  **Translation-safe blocks:** Explain every diagram label in body prose, and
    keep each list item a complete clause rather than splitting sentences across
    bullets. Avoid single-document coined acronyms and stick to one English
    spelling variant.

## Synthetic patterns to remove

Table 6 shows synthetic stagecraft patterns removed by R29 to R32.

Pattern           | Before                                               | After
----------------- | ---------------------------------------------------- | -----
Portable filler   | "Reliability and security are top priorities here."  | Delete the sentence, or state the failure limit.
Diff history      | "We added a map to replace the linear scan."         | The index maps each key to its block offset.
Negative contrast | "The problem is not latency. It is jitter."          | Packet jitter causes the audio drops.
Colon reveal      | "The detail that makes this work: a second queue."   | A second queue isolates control frames from bulk data.
Self-labeling     | "That second rule is the key insight here."          | Delete the comment and state the effect of the rule.
Narrated candor   | "To be transparent, we did not test cold starts."    | We did not measure cold starts.
Weasel source     | "Studies show that retries amplify load."            | Name the paper or outage report, or mark an open item.
Inflated copula   | "The gateway serves as the entry point."             | The gateway is the entry point.
Moral modifier    | "The histogram gives an honest shape of latency."    | The histogram records 99.9% latency without loss.
Trailing "-ing"   | "The daemon batches writes, underscoring stability." | The daemon batches writes and cuts disk writes by 60%.

*Table 6: State the concrete system behavior directly without stagecraft.*
