# Contract Extraction & Boundary Characterization Reference (`refactoring`)

---

## 1. The Pre-Refactor Behavioral Contract Ledger

Before altering structure, produce a compact ledger grounded in source code (`file:line`
citations) and git history (`git log -S <symbol>` / `git log -L <start>,<end>:<file>`):

```markdown
### Behavioral Contract Ledger: <Module / Subsystem>

1. **Implicit Requirements Extracted (`REQ`):**
   - `REQ-EXT-01` (`billing.go:142-168`): Discounts apply *before* tax calculation, clamped at `0` (never negative invoice total).
   - `REQ-EXT-02` (`billing.go:204`, commit `a81f20c`): Duplicate `request_id` within 24h returns cached receipt without re-charging.

2. **User-Observable Surface (`Hyrum's Law`):**
   - **Inbound:** `CalculateInvoice(ctx, req) -> (Invoice, error)`, CLI `invoice preview --json`.
   - **Outputs & Quirks:** Line items returned sorted by `(sku ASC, line_index ASC)`; empty `discounts` serializes as `[]` (NOT `null`!).
   - **Outbound Side Effects:** Writes 1 row to `ledger_entries` + emits `invoice.created` event inside same DB transaction.
   - **Suspected Bugs Found (DO NOT change during refactor!):** `billing.go:189` truncates half-cent toward zero instead of banker's rounding — logged for separate owner review.

3. **Internal Invariants (`INV`):**
   - `INV-01`: `invoice.TotalCents == invoice.SubtotalCents - invoice.DiscountCents + invoice.TaxCents`.
   - `INV-02`: Lock order strictly `accountMu -> ledgerMu`.

4. **Boundary Coverage Audit:**
   - [x] Happy multi-item invoice (`billing_test.go:40`)
   - [ ] MISSING: Empty `discounts` JSON `[]` vs `null` wire shape -> **Add characterization test first!**
   - [ ] MISSING: Concurrent duplicate `request_id` replay -> **Add characterization test first!**
```

---

## 2. Writing High-Signal Characterization Tests at Boundary Seams

### A. Why Public Seams Beat Private Unit Mocks During Refactoring

* **Fragile test (Anti-Pattern):** Tests `privateHelper_computeBucket()` and asserts
  `mockRepo.expect_call("fetch_row", times=2)`. The instant you batch those 2 queries
  into 1 or inline `privateHelper`, the test breaks even though external behavior is
  100% preserved!
* **Resilient boundary test:** Invokes the **public module/API/CLI boundary** against
  in-memory / ephemeral real state (or a fake at the outermost I/O trait) and asserts
  **returned outputs + final observable state/events**.

### B. Characterization Discovery Loop (Feathers's Technique)

When legacy logic is opaque and undocumented:
1. Write a test calling the public boundary with a concrete input and a dummy assertion
   (`assert_eq!(actual, "CAPTURE_ME")` or snapshot serializer).
2. Run the test $\rightarrow$ inspect the actual output produced by the legacy code
   $\rightarrow$ verify via code reading that it isn't non-deterministic garbage (strip/
   inject timestamps & random IDs!) $\rightarrow$ lock the verified actual behavior as
   the characterization assertion.
3. Systematically cover **all boundary equivalence partitions**:
   * Empty / zero / single-element / max-bound inputs
   * Malformed inputs & every error return code / exception type
   * Tie-breaking, Unicode/locale edge cases, and zero/negative/overflow boundaries
   * State-transition sequences (idempotent retry, out-of-order events, partial failure)

### C. Differential Property / Fuzz Oracles (Gold Standard for Algorithmic Rewrites)

When replacing a complex parser, calculator, compiler pass, serializer, or data
structure, **the legacy implementation itself is an executable specification**:

```rust
// Keep `legacy_parse` in a test-only module during the refactor and compare on 10,000 inputs!
proptest! {
    #[test]
    fn refactored_matches_legacy_across_input_space(raw in any::<Vec<u8>>()) {
        let old_res = legacy::parse_frame(&raw);
        let new_res = refactored::parse_frame(&raw);
        prop_assert_eq!(new_res, old_res);
    }
}
```

* Once `10,000+` random/structured inputs + the deterministic edge-case corpus pass
  with zero divergences, promote the edge corpus to permanent unit tests and delete
  `legacy::parse_frame`.
* **Polyglot differential-oracle runners:** Apply the same `legacy(x) == candidate(x)`
  harness across ecosystems with Rust `proptest` / `bolero`, Python `hypothesis`,
  TypeScript `fast-check`, Kotlin `Kotest` property testing / `jqwik`, Go `go test -fuzz`
  (`FuzzX`), and C/C++ `libFuzzer`.

---

## 3. Minimal "Enabling Seams" (Breaking Hard-Wired Dependencies Safely)

What if legacy code cannot be boundary-tested yet because it calls `SystemTime::now()`,
global singletons, or external HTTP clients directly inside a 500-line method?

Apply **only mechanical, zero-logic dependency-breaking moves** first (with compiler/IDE
verification):
1. **Extract & Override / Parameterize Function with Default:**
   * Turn `fn process(order: Order)` calling `now()` into `fn process(order: Order)`
     delegating straight to `fn process_at(order: Order, now: Instant)` — zero change to
     existing callers, instant deterministic seam for characterization tests!
2. **Extract Outbound Interface (Thin Port):**
   * Wrap raw external SDK/socket calls in a 1-to-1 thin interface *without* changing
     call order, parameters, or error handling yet; record outbound calls in the test
     fake so characterization tests capture exact side-effect sequences.
3. **Run the 1-Minute Sabotage Check:**
   * Flip one `+` to `-` or `<` to `<=` inside the legacy body, run the new boundary
     suite, watch it fail, and `git restore .` the sabotage. Now you have **earned** the
     right to refactor!
