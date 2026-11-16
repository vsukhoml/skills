# Examples before and after the rules

Each example shows a text before the rules in a code block, and the same text
after the rules. An example that contains an open item shows the text after the
rules in a code block also. All numbers and names in the examples are invented.

## Opening summary

This example applies 4 rules: answer first (R2), problem without the solution
(R7), one claim in each sentence (R13), and numbers, not praise (R16).

```text
Over the last few quarters we have been looking into ways to improve the
firmware update experience, which is currently quite slow and has caused a
number of issues in the field. After evaluating several approaches we came up
with a lightweight delta update mechanism that should significantly reduce
update times while being robust against power loss.
```

After the rules, the summary states the problem, the mechanism, and the cost:

A firmware update over the serial link takes 190 s, and 3% of updates fail after
a power loss (measured, release 4.1, 12 000 devices). We propose to send only
the changed flash pages and to write them to the inactive image slot. The boot
code changes the active slot only after the signature check passes. The
estimated update time is 25 s (calculated from page counts, not measured). The
cost is 6 KiB of code and one flash page for the page map.

The first text gives no number, so the author supplied each number. If the
author has no number, write "not measured".

## Conditions

This example applies 2 rules: tables for conditions and comparisons (R10), and
a frame for each block (R12).

```text
If the device is locked and the request comes over USB, the command is
rejected, but if it comes over the internal bus it is allowed only when the
owner has enabled it; when the device is unlocked, both transports are
accepted, except that USB requests are rate limited.
```

After the rules, Table 1 gives the result for each state and each transport.

Device state | Transport    | Result
------------ | ------------ | ------
Locked       | USB          | The device rejects the command.
Locked       | Internal bus | The device accepts the command if the owner enabled it.
Unlocked     | USB          | The device accepts the command and limits the rate.
Unlocked     | Internal bus | The device accepts the command.

*Table 1: A locked device does not accept a command from USB.*

## Sentences

This example applies the rules for sentences (R13, R14, and R15) and for
literal language and complete grammar (R26 and R27).

```text
Validation of the incoming frame is performed by the parser, which handles
malformed input gracefully, and once it's done the result is surfaced to the
caller via ERR_FRAME_LEN, ERR_FRAME_CRC or ERR_FRAME_SEQ, etc.
```

After the rules, each sentence has one actor and one action. The marker asks for
the meaning of the word "gracefully", because the first text does not state it.

```markdown
The parser examines the length, the checksum, and the sequence number of each
frame. If one of them is wrong, the parser returns an error code to the caller
(`ERR_FRAME_LEN`, for example). Appendix A lists all error codes.

[Open: What does the parser do with a wrong frame after it returns the code?]
```

## Requirement

This example applies 2 rules: named, enforced, tested claims (R22), and stated
coverage and stated negatives (R23).

```text
The counter should never go backwards, even after crashes.
```

After the rules, the requirement has a plain name, a mechanism, a test, and its
coverage:

-   **Counter order:** The attempt counter does not decrease after a
    restart or a power loss.
-   **Enforcement:** The storage code writes the new counter value to flash
    before the command returns a result.
-   **Verification:** The power-loss test stops the power at each flash write.
    Then it reads the counter after the restart.
-   **Coverage:** The author examined restart, power loss, and rollback to the
    previous firmware. An upgrade has no effect, because the counter format does
    not change.

The author supplied the mechanism, the test, and the coverage. Other sections
refer to this invariant as "the counter order", without an ID. The next example
shows the text if the author did not supply the facts.

## Missing facts

This example applies the limits "No invented facts" and "No guessed meaning".

```text
The counter should never go backwards, even after crashes. The overhead is
minimal.
```

After the rules, the words of the author stay, and each marker asks one
question in a separate paragraph. The subject of "should" is a component, so
the word stays. The text has no empty list for the mechanism, the test, or the
coverage.

```markdown
The counter should never go backwards, even after crashes.

[Open: Is this sentence a requirement? If it is, which mechanism enforces it,
and which test verifies it?]

The overhead is minimal.

[Open: How much time and how much flash does one counter update use?]
```

The lint script reports the words "should" and "minimal" as findings, and both
markers as open items. These findings stay until the author answers. List them
in the report.

## Alternatives

This example applies the rule for a decision from a comparison (R24).

```text
Option A has pros and cons. Option B is also interesting and might be worth
considering. We could also do nothing for now.
```

After the rules, the text states 2 criteria, compares each option with them, and
states the decision as the result. The author supplied each number.

The update must continue after a power loss (the criterion that decides), and
the change must use at most 8 KiB of flash. Table 2 compares the 3 options with
these criteria.

Option               | After a power loss                  | Flash cost | Trade-off
-------------------- | ----------------------------------- | ---------- | ---------
A: page map in flash | The update continues from the map.  | 4 KiB      | One more flash write for each page.
B: page map in RAM   | The map is lost. The update fails.  | 0 KiB      | No flash wear.
No change            | 3% of updates fail (measured).      | 0 KiB      | No engineering work.

*Table 2: Only option A continues an update after a power loss.*

Option B and the option "no change" do not meet the first criterion. Option A
meets both criteria. Therefore the design stores the page map in flash.

## Code block

The example applies 4 rules: detail in its layer (R3), cut low-signal text (R6),
block frames (R12), and one role for each style (R19). The draft places an
untagged snippet with headers, boilerplate, and a wide trailing comment directly
below a heading.

````text
## Replay check
```
#include <stdint.h>
#include <stdbool.h>
#include "storage.h"

int check_frame(struct ctx *c, const uint8_t *buf, size_t len) {
  if (c == NULL || buf == NULL) { return -1; }
  uint64_t seq = load_u64_be(buf + 4); // sequence is at byte 4, big-endian
  if (seq <= c->high_water) { return ERR_REPLAY; }
  c->high_water = seq;
  return persist_high_water(c->flash, seq);
}
```
````

After the rules, the lead-in states that the block defines the proposed
contract. Imports and plumbing disappear, the comment sits above its field, and
each line stays within 72 characters:

```c
// Proposed wire header at byte 0 of each signed command frame.
struct frame_header {
  uint32_t magic;
  // Monotonic counter in big-endian order; must exceed high_water.
  uint64_t sequence;
};
```

The prose outside the block states the replay rejection (`ERR_REPLAY`) and the
flash write order before the command returns.

## Synthetic prose

This example applies the 4 rules for grounded, non-synthetic prose (R29 to R32)
to a paragraph with synthetic stagecraft and unverified claims.

```text
In this section, let us explore the ingestion gateway. Reliability is a
top priority for modern distributed systems. The gateway is not just a
proxy. It serves as a pivotal safety boundary, underscoring our focus on
stability. Studies show that bursty clients cause cascading failures
(see [paper](https://example.org/overload?utm_source=chatgpt.com)).
The key detail: a token bucket drops excess frames.
```

After the rules, the portable filler, negative contrast, commentary clause, and
tracking parameter disappear, and an open item marks the missing facts:

```markdown
The ingestion gateway is the trust boundary for client frames. A token
bucket in the gateway drops frames above the client rate limit (see the
[overload study](https://example.org/overload)).

[Open: What are the token rate, the burst size, and the primary citation
for the overload study?]
```

## Developer documentation

This example applies the profile for developer documentation to a section of a
README. The rules are answer first (R2), a frame for each block (R12), literal
language (R26), and fixed meanings and formats (R28).

```text
## Getting Started

It's super easy to get up and running! Just clone the repo & run the
installer, then you should be good to go. Requires python/uv.

$ git clone https://example.org/acme/logtail.git
$ cd logtail && ./install.sh --prefix=/opt/logtail
$ logtail --token abc123 tail prod

Note: we recommend using --json if you're piping the output somewhere.
```

After the rules, the section states the result first. Each step gives the
location, the action, and the expected output. The heading keeps its words.

````markdown
## Getting started

`logtail` prints the log of one service to the terminal. After these 2 steps,
the terminal shows new log lines of the service.

Prerequisites: Python and `uv`.

1.  In an empty directory, download the source and run the installer:

    ```bash
    git clone https://example.org/acme/logtail.git
    cd logtail
    ./install.sh --prefix=/opt/logtail
    ```

    The installer prints `installed: /opt/logtail/bin/logtail`.
2.  Read the log of one service:

    ```bash
    logtail --token TOKEN tail SERVICE
    ```

    `TOKEN` is your read token. `SERVICE` is the service name, such as `prod`.

If another program reads the output, add `--json`.
````

The author supplied the output of the installer. The rewrite has these 5
differences from a decision document:

-   **Summary:** The summary states what the tool does and the first result. It
    has no problem, no mechanism, and no cost.
-   **Commands:** The commands have no shell prompt. A placeholder in capital
    letters replaces the token, and the text below the block defines it.
-   **Advice:** The sentence with "we recommend" becomes an instruction with its
    condition.
-   **Status:** No claim has a status in parentheses. The report lists the
    commands that nobody ran on a clean machine.
-   **Missing fact:** The draft does not give the versions of Python and `uv`.
    The versions do not change the result of the procedure for most readers.
    Therefore the gap is in the report, and the text has no marker.
