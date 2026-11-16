# Plain English for international readers

Use this guide with the rules for plain English (R25 to R28) and for grounded,
non-synthetic prose (R29 to R32). The reader reads English as a second
language, or reads a machine translation. That reader translates one sentence at
a time and finds unknown words in a dictionary. Each word must have its
dictionary meaning. Each sentence must have complete grammar.

Plain English does not remove technical content. Keep each technical term,
number, and condition. Change only the words around them. Use active voice.

## Words

Decide the terms before you draft. The rule is common words, one term (R25).

1.  **List the things:** List the components, states, messages, and actions that
    the document names.
2.  **Select one term for each thing:** Use the term from the source code or
    from the standard of the field.
3.  **Define each term one time:** Put the definition at the first use, in 10
    words or fewer.
4.  **Search for the other words:** After the draft, search for the terms that
    you did not select. Replace each one.

Table 1 shows the word groups that writers mix most.

Meaning                        | Words that writers mix
------------------------------ | --------------------------------------------
Make sure that a fact is true  | check, verify, validate, confirm, ensure
Something is wrong             | error, failure, fault, issue, problem, bug
Begin an operation             | start, run, launch, execute, invoke, trigger
Take something away            | delete, remove, erase, clear, drop, wipe
Values that control behavior   | configuration, settings, options, parameters
The party that sends a request | host, client, caller, user, application

*Table 1: Select one word in each row for the full document.*

If two words in a row have different technical meanings in your system, define
both words.

Some common words have two meanings. Table 2 gives a word with one meaning for
each of them.

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

*Table 2: A reader with a dictionary cannot know which meaning you intend.*

The lint script does not check the words in Table 2, because each word is
correct in one of its meanings. Check them when you read the draft.

The lint script has a longer list of words and phrases, with a replacement for
each one. This command prints the list:

```bash
python3 {skill_dir}/scripts/doc_lint.py --words
```

## Literal language

A phrase is literal if the dictionary meaning of each word gives the meaning of
the phrase. The rule is literal language (R26). These 7 types of text are not
literal:

-   **Idioms:** Write "by default", not "out of the box". Write "internally",
    not "under the hood".
-   **Phrasal verbs:** A verb with a small word such as "up", "out", or "off"
    often has a new meaning. Write "remove", not "get rid of".
-   **Latin abbreviations:** Write "for example" and "that is". Name the items
    of a list to its end, and do not write "etc.".
-   **Contractions:** Write "do not", "cannot", and "it is".
-   **Symbols as words:** Write "and", "or", "with", and "about" as words. Do
    not write "&", "/", "w/", or "~" in their place.
-   **References to one culture:** Do not refer to sports, seasons, holidays, or
    local history. Give the months, not "the third quarter".
-   **Humor and emphasis:** Do not use jokes, irony, rhetorical questions, or
    exclamation marks.

A standard technical term stays, also if it has the form of a phrasal verb or an
idiom. Examples are "rollback", "fallback", "handshake", and "boot".

## Grammar

Complete grammar tells the reader the role of each word. The rule is complete
and explicit grammar (R27). Table 3 shows the
patterns that cause the most errors.

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

*Table 3: Each change adds a word or a sentence, and removes one possible wrong
reading.*

Write in the active voice: the actor is the subject, and the verb states the
action. The passive voice is correct in these 2 cases only:

-   **Unknown actor:** "The log was deleted before the incident."
-   **Each possible actor:** "The command can be run from each directory."

In all other cases, find the actor in the source or in the draft. If the draft
does not name the actor of an obligation, record an open item. The lint script
reports each passive verb that has its actor after "by". It also reports a
document in which more than 20% of the sentences are passive.

## Modal verbs, numbers, and dates

Each modal verb has one meaning in the document. The rule is fixed meanings and
formats (R28). Table 4 gives the
meanings.

Word      | Meaning
--------- | -------------------------------------------------------
must      | A requirement. A design that does not meet it is wrong.
must not  | A prohibition.
can       | An ability or a permission.
might     | A possibility. The author does not know the result.
will      | A fact about the future.
we expect | A prediction that is not verified.

*Table 4: Each word in the table has one meaning.*

Advice has no word in Table 4. An opinion such as "we recommend" hides the
reason. In a decision document, compare the options with stated criteria, and
state the decision as the result (R24). In developer documentation, write the
instruction with its condition: "If the disk is full, delete the oldest log."

The words "should", "may", "could", and "would" are not in Table 4, because each
of them has more than one meaning. For "would", state the condition: "If the
check fails, the device restarts."

These 7 formats keep numbers and dates the same in all countries:

-   **Digits:** Write a quantity of 2 or more as digits: 3 retries, 28 rules.
-   **Unit:** Write a number, a space, and the unit: 40 ms, 4 KiB.
-   **Prefix:** Use KiB and MiB for powers of 2. Use kB and MB for powers of 10.
-   **Thousands:** Group digits with a space: 10 000. A comma or a point means a
    decimal separator in some countries.
-   **Range:** Write "from 3 to 7", not a dash between the numbers.
-   **Date and time:** Write 2031-04-09 and 14:30 UTC.
-   **Relative time:** Write "in version 3.2" or a date. Do not write
    "currently", "recently", or "soon".

## Text for machine translation

Many readers translate a document with a program. These 4 habits keep the
translation correct:

-   **Text outside images:** Explain each label of a diagram in the body text. A
    translation program cannot read an image.
-   **Complete list items:** Do not start a sentence in the lead-in and end it
    in the list items. The program translates each item alone.
-   **No invented abbreviations:** Do not create an abbreviation for one
    document. The program cannot expand it.
-   **One spelling:** Use American spelling or British spelling in the full
    document, not both.

## Synthetic patterns to remove

Table 5 shows synthetic patterns that add length or drama without adding
technical facts. The 4 rules for grounded, non-synthetic prose (R29 to R32)
remove them.

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

*Table 5: Each rewrite removes stagecraft and states the technical fact
directly.*
