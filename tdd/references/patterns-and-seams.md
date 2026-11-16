# Seam Testing, Oracles & Boundary Isolation (`tdd`)

## 1. Behavioral Seam Tests vs. Implementation-Coupled Tests

### Good: Observable behavior through the public interface

```go
// Verifies state transition through the public store seam; survives SQL/schema refactors.
func TestReserveStock_PreventsDoubleAllocation(t *testing.T) {
    inv := inventory.NewMemoryStore()
    _ = inv.Seed(ctx, "SKU-1", 5)

    _, err := inv.Reserve(ctx, "ORD-1", "SKU-1", 4)
    if err != nil {
        t.Fatalf("first reserve failed: %v", err)
    }
    _, err = inv.Reserve(ctx, "ORD-2", "SKU-1", 2)
    if !errors.Is(err, inventory.ErrInsufficientStock) {
        t.Fatalf("got %v, want ErrInsufficientStock", err)
    }
}
```

### Bad: Side-channel peeking & internal mock coupling

```go
// BAD 1: Queries internal SQL table instead of reading through public API.
row := db.QueryRow("SELECT reserved_qty FROM stock_rows WHERE sku = 'SKU-1'")

// BAD 2: Asserts internal collaborator call sequence; breaks on harmless refactor.
mockLedger.ExpectCall("lockRow", "SKU-1").Times(1)
```

---

## 2. Independent Oracles vs. Tautological Tests

Agents frequently produce **tautological tests** when implementing calculations,
parsers, or serializers — copying the same formula into both `src/` and `tests/`
so a wrong assumption passes 100% of tests.

### Bad: Recomputes the implementation formula

```python
# BAD: Test duplicates the bracket arithmetic it is supposed to verify.
def test_marginal_tax():
    income = Decimal("115000")
    expected = (income - Decimal("100525")) * Decimal("0.24") + Decimal("17400")
    assert compute_tax_2026_single(income) == expected
```

### Good: Independent worked literal or golden fixture vector + invariant

```python
# GOOD 1: Worked figure taken independently from statutory worksheet / spec table.
# Source: SPEC-0004 Worked Example 2 (Single filer, $115,000 taxable -> $20,874.00)
def test_single_filer_24pct_bracket_worked_example():
    assert compute_tax_2026_single(Cents(11_500_000)) == Cents(2_087_400)

# GOOD 2: Algebraic invariant at bracket boundary (continuity: +1 cent income
# increases tax by at most 1 cent when marginal rate <= 100%).
def test_bracket_cliff_continuity_invariant():
    at_cap = compute_tax_2026_single(Cents(10_052_500))
    above_cap = compute_tax_2026_single(Cents(10_052_501))
    assert Cents(0) <= (above_cap - at_cap) <= Cents(1)
```

---

## 3. Where to Fake / Mock: System Boundaries Only

| Dependency | Action in Seam Tests | Why |
| --- | --- | --- |
| **Own domain modules, parsers, calculators, state machines** | **Never mock** — call real code | Mocking internals hides integration mismatches and locks call structure. |
| **Database / persistence** | Prefer fast in-memory contract adapter (verified by shared contract test) or isolated local test DB | Keeps seam tests behavioral without mocking SQL strings. |
| **Wall clock & timers** | Inject narrow `Clock` / `now` function | Eliminates flaky `sleep()` calls and tests expiry cliffs deterministically. |
| **RNG / UUIDs / nonces** | Inject seeded deterministic source in tests | Makes failure reproduction deterministic. |
| **Third-party HTTP / RPC** | Inject narrow domain client interface (`PaymentGateway.Charge`) backed by a deterministic fake | Avoids brittle generic HTTP/fetch request-matching mocks. |

* **TypeScript / JavaScript:** Inject narrow structural dependency ports (`{ readonly nowMs: () => number; readonly store: OrderStore }`) into pure core/handler functions rather than using module-hoisting `vi.mock()` / `jest.mock()` monkey-patches, which bypass static type checking, break on ESM file splits, and hide contract drift.
* **Kotlin / JVM / Android:** Prefer compact in-memory `interface` fakes and constructor-injected `CoroutineDispatcher`s driven deterministically under `runTest` over internal `MockK` bytecode mocks, keeping host-JVM seam tests fast and resilient to refactors.

### Narrow Boundary Interface Pattern

```rust
// GOOD: Narrow domain capability at the external boundary; trivial to fake deterministically.
pub trait Clock {
    fn now_unix_ms(&self) -> i64;
}

pub fn verify_lease(lease: &Lease, clock: &impl Clock) -> Result<(), LeaseError> {
    if clock.now_unix_ms() >= lease.expires_at_ms {
        return Err(LeaseError::Expired);
    }
    Ok(())
}
```
