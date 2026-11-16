# Defect Prevention & Design for Debuggability Reference (`debug`)

---

## 1. Make Illegal States Unrepresentable (State Machines Over Boolean Soup)

### Anti-Pattern: Orthogonal Booleans & Nullable Pointers

```rust
// BAD: 2 * 2 * 2 * 2 = 16 states, most contradictory (e.g., connected=true && error=Some(...))!
struct Connection {
    connecting: bool,
    connected: bool,
    session_key: Option<[u8; 32]>,
    last_error: Option<ErrorCode>,
}
```

### Fix: Closed Sum Type + Explicit Transition Function

```rust
// GOOD: Every representable value is valid by construction; compiler enforces exhaustive match!
enum ConnectionState {
    Disconnected { last_error: Option<ErrorCode> },
    Connecting { started_at_ms: u64, attempt: u8 },
    Established { session_key: [u8; 32], since_ms: u64 },
}
```

* **Transition table discipline:** Implement state transitions in **one pure function**
  `step(state: ConnectionState, event: Event, now_ms: u64) -> (ConnectionState, Action)`
  and log unexpected `(state, event)` pairs explicitly instead of scattering field
  mutations across 12 callbacks!

---

## 2. Parse, Don't Validate + Newtypes Against Argument Swaps

1. **Boundary Proof Types:**
   * Instead of calling `validate_email(s)` in 4 handlers (and forgetting in the 5th!)
     while passing raw `string` everywhere, make the constructor of `EmailAddress` the
     **only** way to obtain one (`parse_email(raw) -> Result<EmailAddress, ParseErr>`).
2. **Prevent Positional Transpose Bugs:**
   * `fn copy_range(src_offset: usize, dst_offset: usize, byte_len: usize)` invites
     silent catastrophic swaps! Wrap distinct quantities (`SrcOffset(usize)`,
     `DstOffset(usize)`, `ByteLen(usize)`) or pass a named struct / builder.

---

## 3. High-Density Paired Assertions & `check_rep()` Verifiers

### A. Positive + Negative Space & Paired Boundary Assertions

Assert invariants at **both ends** of every serialization, storage, or IPC seam:

```c
// Producer side (before writing frame to flash/socket):
ASSERT_INVARIANT(hdr.payload_len <= MAX_FRAME_BYTES);
ASSERT_INVARIANT(hdr.crc32 == compute_crc32(payload, hdr.payload_len));

// Consumer side (immediately after reading frame back):
if (hdr.payload_len > MAX_FRAME_BYTES) return ERR_CORRUPT_FRAME; // Untrusted wire/flash = typed error!
```

* **Rule of thumb (NASA JPL / TigerStyle):** Aim for `>= 2` meaningful invariant
  assertions per stateful function (precondition + postcondition / conservation check
  such as `total_before == total_after`).
* **Never put side effects inside `assert(...)`!** `assert(queue_pop(&q, &item))`
  disappears completely if compiled with `-DNDEBUG`! Keep production-critical bounds
  checks active in release builds (`release_assert` / explicit panic/abort on corrupt
  memory invariants).

### B. Data-Structure Representation Checkers (`check_rep()`)

Whenever building a custom tree, ring buffer, LRU cache, order book, or index, write a
`check_rep()` function verifying **global structural invariants**:
* `map.len() == linked_list.count_nodes()`
* No cycles, `head`/`tail` pointers consistent when `len == 0` and `len == 1`
* Sorted keys strictly monotonic, sum of shard balances equals ledger total

Call `debug_assert!(self.check_rep().is_ok())` at the exit of every mutating method in
unit, property, and fuzz tests — **bugs crash on the exact mutation that broke the
invariant instead of 500 calls later!**

---

## 4. Inject Nondeterminism & Deterministic Simulation Testing (`DST`)

Distributed, concurrent, and timer-driven bugs are notorious "heisenbugs" *only* when
code reaches directly into the OS for time, randomness, and scheduling:

| Source of Nondeterminism | Hard-to-Debug Direct Call | Debuggable Seam (Replayable from `u64` Seed!) |
| --- | --- | --- |
| **Wall / Monotonic Time** | `time.Now()` / `clock_gettime()` / `Date.now()` | Injected `Clock` trait / `clock: () => number` (`SimClock::advance(5 * Second)` or Kotlin `runTest` `TestScope` virtual time tests 24h expiry in `10 µs`!) |
| **Randomness / IDs / Jitter** | `os.urandom` / thread `rand()` / `Math.random()` | Seeded deterministic `Rng` (`ChaCha8Rng::seed_from_u64(seed)`, TypeScript `fast-check` `{ seed }`) — always print `--seed` on test start! |
| **Network / Disk Faults** | Live sockets / OS filesystem | Simulated transport/storage fault injector dropping, reordering, delaying, or tearing writes deterministically from `seed` |
| **Hash-Map Iteration Order** | Randomized hash seed per run | Sort keys at deterministic output boundaries; support seeded hashers in replay mode |

* **Payoff:** A `1-in-50,000` split-brain or timeout race discovered overnight by a
  fuzzer prints `FAIL: seed=0x9e3779b97f4a7c15` and reproduces **100% of the time on
  every run in `< 50 ms`** under a single-threaded step debugger!

---

## 5. In-Memory Flight Recorders & Live Inspection Hooks

Steady-state `DEBUG` logging is too expensive to keep on in production, yet when a rare
fault hits, you desperately want the **last 256 internal events**:

1. **Per-Process / Firmware Ring-Buffer Flight Recorder:**
   * Maintain a fixed-size, lock-free or per-thread circular array of compact binary
     events `(timestamp_ticks, event_id, arg0, arg1)` in RAM (`4–64 KB`; `.noinit` SRAM
     with CRC header on MCUs).
   * Overwrite oldest entries in `O(1)` (`~5–15 ns`, zero allocations, zero I/O).
   * Dump the ring **automatically on panic / assertion failure / watchdog reset / `5xx`
     error**, or on demand via an admin diagnostic command / `SIGUSR1`!
2. **Idempotent `dump_state()` Diagnostic Snapshot:**
   * Expose an internal diagnostic command dumping queue depths, active state-machine
     states, lock holders, in-flight request ages, and config digest — **read-only,
     bounded in output size, and redacting all credentials/PII**.
