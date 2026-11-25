# Examples before and after the rules

Each section below shows a draft snippet before and after applying the rules in
`writing-tech-docs`.

## Opening summary

Applies answer first (R2), problem without the solution (R7), one claim per
sentence (R13), and numbers, not praise (R16):

```text
Over the last few quarters we have been looking into ways to improve the
firmware update experience, which is currently quite slow and has caused a
number of issues in the field. After evaluating several approaches we came up
with a lightweight delta update mechanism that should significantly reduce
update times while being robust against power loss.
```

After the rules, the summary states the problem, mechanism, and cost (using "not
measured" whenever the author lacks a measurement):

A firmware update over the serial link takes 190 s, and 3% of updates fail after
a power loss (measured, release 4.1, 12 000 devices). We propose to send only
the changed flash pages and to write them to the inactive image slot. The boot
code changes the active slot only after the signature check passes. The
estimated update time is 25 s (calculated from page counts, not measured). The
cost is 6 KiB of code and one flash page for the page map.

## Conditions

Applies tables for conditions (R10), block frames (R12), and front-loaded
conditions (R27):

```text
If the device is locked and the request comes over USB, the command is
rejected, but if it comes over the internal bus it is allowed only when the
owner has enabled it; when the device is unlocked, both transports are
accepted, except that USB requests are rate limited.
```

After the rules, Table 1 gives the result for each state and transport.

Device state | Transport    | Result
------------ | ------------ | ------
Locked       | USB          | The device rejects the command.
Locked       | Internal bus | If the owner enabled the bus, the device accepts the command.
Unlocked     | USB          | The device accepts the command and limits the rate.
Unlocked     | Internal bus | The device accepts the command.

*Table 1: A locked device rejects every USB command.*

## Key-description table

Applies section density, lists, and table rules (R1, R9, R10) to a 3-column
table of short IDs, names, and 2-sentence explanations:

```text
| ID | Component    | Role                                             |
| -- | ------------ | ------------------------------------------------ |
| C1 | Frame parser | Checks packet length and CRC. Drops bad frames.  |
| C2 | Key cache    | Holds the session key in SRAM. Clears on reset.  |
| C3 | Audit log    | Writes rejected codes to a 256-entry ring log.   |
```

Because each item needs only 2 sentences, a bold-lead-in list beats a table or
stub subsections. Use child headings only when most items need at least a
paragraph:

-   **C1. Frame parser:** Checks the length and checksum of each incoming
    packet. Drops any frame that fails a check and increments the error counter.
-   **C2. Key cache:** Holds the active session key in SRAM. If the host closes
    the session or resets the bus, the cache clears the key slot.
-   **C3. Audit log:** Appends each rejected command code to the flash ring
    buffer. Keeps the latest 256 entries across power cycles.

## Sentences

Applies sentence, active-voice, symbol-cap, and explicit-grammar rules (R13 to
R15, R26, R27):

```text
Validation of the incoming frame is performed by the parser, which handles
malformed input gracefully, and once it's done the result is surfaced to the
caller via ERR_FRAME_LEN, ERR_FRAME_CRC or ERR_FRAME_SEQ, etc.
```

After the rules, each sentence names one actor and action, and an open marker
asks what "gracefully" means:

```markdown
The parser examines the length, the checksum, and the sequence number of each
frame. If one of them is wrong, the parser returns an error code to the caller
(`ERR_FRAME_LEN`, for example). Appendix A lists all error codes.

[Open: What does the parser do with a wrong frame after it returns the code?]
```

## Requirement

Applies named, enforced, tested claims (R22) and stated coverage (R23):

```text
The counter should never go backwards, even after crashes.
```

After the rules, the invariant states its name, mechanism, test, and coverage:

-   **INV-01. Counter order:** The attempt counter does not decrease after a
    restart or a power loss.
-   **Enforcement:** The storage code writes the new counter value to flash
    before the command returns a result.
-   **Verification:** The power-loss test stops the power at each flash write.
    Then it reads the counter after the restart.
-   **Coverage:** The author examined restart, power loss, and rollback to the
    previous firmware. An upgrade has no effect, because the counter format does
    not change.

## DRY references

Applies one home per item (R4) where a rollback section repeats `INV-01` in
full:

```text
## Rollback

During a rollback to firmware 4.0, the attempt counter must never decrease
after a restart or power loss, so the storage code writes the new counter
value to flash before returning. Because of this flash write, firmware 4.0
reads the latest counter value without a migration step.
```

After the rules, the section points to `INV-01 (Counter order)` and states only
its local rollback consequence:

```markdown
## Rollback

Because `INV-01` (Counter order) persists every increment before the command
returns, firmware 4.0 reads the latest counter value directly after a rollback
without a migration step.
```

## Missing facts

Applies "No invented facts" and "No guessed meaning":

```text
The counter should never go backwards, even after crashes. The overhead is
minimal.
```

Because a component is the subject of "should", the original wording stays and
each missing fact gets one standalone marker:

```markdown
The counter should never go backwards, even after crashes.

[Open: Which mechanism enforces non-decreasing counter updates across crashes?]

The overhead is minimal.

[Open: How much time and flash does one counter update consume?]
```

## Alternatives

Applies factual, unbiased comparisons (R24) to a biased prose pitch:

```text
Option A (page map in flash) is a clean, superior design that guarantees
resilient updates. Option B (page map in RAM) is prohibitive under power
loss, and doing nothing is unacceptable.
```

After the rules, the section opens with the deciding criteria and states the
disqualifiers after Table 2. All 3 options compare across 4 material attributes,
including flash cost where Option B wins.

The update must continue after a power loss, and the change must use at most 8
KiB of flash. Table 2 compares the 3 options across all 4 material criteria.

Option               | After a power loss                 | Flash space | Extra flash writes     | Work
-------------------- | ---------------------------------- | ----------- | ---------------------- | ----
A: page map in flash | Continues update from the map.     | 4 KiB       | 1 write per flash page | 3 days
B: page map in RAM   | Loses map. Update fails.           | 0 KiB       | 0 writes               | 1 day
No change            | Fails on 3% of updates (measured). | 0 KiB       | 0 writes               | 0 days

*Table 2: Only option A continues an update after a power loss, at a cost of 4
KiB and 1 write per page.*

Option B and "No change" fail the power-loss requirement. Option A meets both
required limits, so the design stores the page map in flash.

## Code block

Applies R3, R6, R12, and R19 to an untagged snippet with boilerplate and a wide
trailing comment:

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

After the rules, the lead-in frames the proposed contract, boilerplate
disappears, and comments sit above fields within 72 characters:

```c
// Proposed wire header at byte 0 of each signed command frame.
struct frame_header {
  uint32_t magic;
  // Monotonic counter in big-endian order; must exceed high_water.
  uint64_t sequence;
};
```

Prose outside the block states replay rejection (`ERR_REPLAY`) and flash write
ordering before return.

## Synthetic prose

Applies R29 to R32 to synthetic stagecraft and unverified citations:

```text
In this section, let us explore the ingestion gateway. Reliability is a
top priority for modern distributed systems. The gateway is not just a
proxy. It serves as a pivotal safety boundary, underscoring our focus on
stability. Studies show that bursty clients cause cascading failures
(see [paper](https://example.org/overload?utm_source=chatgpt.com)).
The key detail: a token bucket drops excess frames.
```

After the rules, filler, negative contrast, commentary participles, and URL
trackers disappear, and standalone markers ask one question each:

```markdown
The ingestion gateway is the trust boundary for client frames. A token
bucket in the gateway drops frames above the client rate limit (see the
[overload study](https://example.org/overload)).

[Open: What token rate and burst size does the gateway enforce?]

[Open: Which primary paper or incident report is the overload study?]
```

## Tracked open questions

Applies the open-questions section rules without adding duplicate `[Open: ...]`
markers:

```text
## Key storage

The daemon stores the session key in the kernel keyring. On reboot, the
daemon fetches a fresh key from the provisioning service.

## Open questions

| Item | Question | Comments |
| --- | --- | --- |
| Rotation | Every 24 h or per boot? | Decided: rotate per boot. |
| Key store | Kernel keyring or TPM? | Ask the security team. |
```

After the rules, body prose frames the open choice as an option pointing to the
table:

```markdown
## Key storage

In one option under review, the daemon stores the session key in the
kernel keyring (see Key store in Open questions). On reboot, the daemon
fetches a new key from the provisioning service (see Rotation).
```

Table 3 marks open against closed status and states factual trade-offs.

Item      | Status | Question                | Trade-offs and decision notes
--------- | ------ | ----------------------- | -----------------------------
Rotation  | Closed | Every 24 h or per boot? | Per-boot rotation avoids timer state. RAM loss clears keys.
Key store | Open   | Kernel keyring or TPM?  | Keyring adds 0 ms. TPM blocks root reads and adds 12 ms.

*Table 3: Only the key-store question remains open for reviewer feedback.*

## Developer documentation

Applies `--profile docs` (R2, R12, R26, R28) to a README quickstart:

```text
## Getting Started

It's super easy to get up and running! Just clone the repo & run the
installer, then you should be good to go. Requires python/uv.

$ git clone https://example.org/acme/logtail.git
$ cd logtail && ./install.sh --prefix=/opt/logtail
$ logtail --token abc123 tail prod

Note: we recommend using --json if you're piping the output somewhere.
```

After the rules, the section states the first result upfront and orders each
step as location, action, and expected output. Advice becomes a conditional
instruction:

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
