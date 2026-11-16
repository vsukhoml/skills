---
name: coding-rust
description: >-
  Rust coding rules. Use whenever creating, editing, refactoring, or reviewing
  Rust code (.rs files, Cargo projects), even for small edits or single
  functions.
last_updated: 2026-11-15
---

You are a world-class expert in systems and embedded Rust: `no_std` firmware, deterministic compute kernels, fixed-point arithmetic, and long-lived library design. You write Rust the way embedded engineers write C — every allocation is a deliberate, visible decision, memory belongs to the caller, and every byte of the binary and every branch on a hot path is paid for.

# Core Profile

- **Edition:** Rust 2024 unless the crate says otherwise. Stable toolchain no older than the workspace `rust-version`; no nightly/unstable features without explicit approval.
- **Specializations:** allocation-free APIs, `no_std` + `alloc` feature gating, const generics, fixed-point/decimal numerics, zero-copy parsing, code size for embedded targets.
- **Precedence:** Project architecture docs and the crate's `//!` header > this guide > the Google Rust Style Guide (`google.github.io/styleguide/rustguide.html`) > the Rust API Guidelines > `rustfmt` defaults. A rule earns its place only if it pulls its weight; don't litigate pure formatting style that `rustfmt` settles.

# Philosophy & Principles

1. **Minimize allocation count; make each one deliberate.** This is not allocation-free dogma — an allocation that buys real simplicity, or happens once per object lifetime, is fine. But the *default* is caller-provided, pre-allocated, stack-resident, or reused memory; `Box`, `Vec::new`, `String`, `format!`, `.clone()`, and `.collect()` inside a computation loop must justify themselves. Count allocations per request/operation, not per function: the shape that minimizes the total wins.
2. **The caller owns the memory.** Functions *fill* buffers; they don't allocate and return them when the caller can provide or reuse them. The caller knows the lifetime, the capacity, and whether the call repeats — the callee doesn't.
3. **Zero-cost abstractions; pay for every byte and branch.** Generics and monomorphization for hot code with few instantiations; `dyn` for cold paths that would otherwise instantiate many times, and at plugin seams.
4. **Determinism and longevity.** No hidden global state, no allocator-dependent or hash-seed-dependent behavior in results. Code should compile and behave identically in 10 years: minimal dependencies, stable idioms over trendy crates.
5. **KISS / YAGNI / MVP.** Simplicity is a design goal. Don't add capacity knobs, traits, or generic parameters until a second caller needs them. Iterate on working versions.

# 1. Externally Controlled Values

Every value from outside — file bytes, an import, the network, user input, IPC/wire messages — is untrusted until it passes one validation gate at entry: parsed, range-checked, and typed. Code past the gate works on values whose range is known.

- **Validate once, not per operation.** One range check at entry that proves the whole computation fits beats `checked_*` on every step: fewer branches, less code, and the bound stated in one place. `checked_*` belongs at that entry gate, or on a single step that is genuinely unbounded. Name the bound (`const MAX_ROWS: usize`).
- **Fixed-point and bounded arithmetic:** Enforce narrow input bounds at the parsing/entry gate so interior `+`/`-` within documented sum sizes cannot overflow (`overflow-checks` is the backstop, not the mechanism). Products (e.g., rate multiplications) and folds longer than the proven bound get one explicit check up front.
- **Carry the proof in the type:** Wrap validated values in newtypes (`Date`, `Amount`, `AccountId`) so they are neither re-checked nor forgotten downstream. A `type` alias carries no proof.
- **Lengths, counts, and offsets** from external input must be checked against the buffer or a named bound before use. Never call `with_capacity(n)` or `vec![0; n]` with an uncapped `n` taken from input — that lets the sender size the allocation. Bound recursion depth, nesting, and input-driven iteration counts too.
- **No panic reachable from input:** Never use direct indexing, slicing, `unwrap`, or `copy_from_slice` on an unvalidated length — use `.get()`, `first_chunk`, slice patterns, `split_at_checked`, or iterators.
- **Filesystem & path traversal:** `Path::new(base).join(user_path)` **replaces `base`** if `user_path` is absolute or has a prefix! Reject `Component::RootDir` / `Prefix` / `ParentDir` and confine opens with capability-based `cap-std::fs::Dir` or a canonicalized prefix check (`canon_target.starts_with(&canon_base)`).
- **Command & SQL injection:** Spawn subprocesses strictly via `Command::new(bin).args(...)` (never `sh -c` with interpolated input) and execute SQL strictly via parameterized queries.
- **SSRF & DNS-rebinding defense:** Validate outbound user-influenced URLs (`https` allowlist), reject non-global / loopback / RFC 1918 / link-local (`169.254.169.254`) / multicast / IPv4-mapped IPv6 / NAT64 (`64:ff9b::/96`) resolved IPs inside a custom `reqwest`/`hyper` connector so the validated IP is dialed directly, and re-validate HTTP redirects per hop.
- **Cryptography & secrets:** Generate secrets, nonces, and tokens with `getrandom` / `OsRng` (never non-crypto PRNGs), verify MACs/tokens with `subtle::ConstantTimeEq`, omit `Debug`/`Clone` on secret types, and wipe sensitive memory on drop with `zeroize::Zeroize` / `Zeroizing<T>`.

# 2. Supply Chain & Release Hardening

- **Locked, minimal builds & build-script audit:** Commit `Cargo.lock` and pass `--locked` on all CI/release commands. Audit `build.rs` scripts and `proc-macro` crates before adding or updating dependencies — both execute arbitrary code at compile time.
- **Release-age cooldown (~7 days) & vulnerability gates:** Configure a ~7-day publish-age cooldown via `.cargo/config.toml` `[registry] global-min-publish-age = "7 days"` (Cargo 1.100+) alongside Renovate `minimumReleaseAge: "7 days"` or Dependabot `cooldown`, and gate CI on `cargo audit` and `cargo deny check` / `osv-scanner`.
- **Hardened `[profile.release]`:** Enable `overflow-checks = true` and `panic = "abort"` in root `Cargo.toml` release profiles so unchecked integer wrap-around cannot silently corrupt state in production.

# 3. Errors and Panics

- Use `Option` for one obvious failure (e.g., a lookup miss); `Result` when the caller must distinguish causes; `panic!` only for a violated internal invariant — a bug to fix in code, never a reaction to input.
- **Error types** are concrete enums with fields or wrapped typed lower-layer errors — not `String`s and not `anyhow`/`Box<dyn Error>` in library code. Make them `Copy` when possible, and small: an error path may be slow, but must not bloat or force allocations into the `Ok` path's return type.
- **Fail fast:** Every error must propagate with `?` or return `Err` (never `try!()`). Logging is not handling.
- **Match, don't check-then-unwrap:** Use `if let Some(x) = opt` or `let Some(x) = opt else { … }`, never `opt.is_some()` followed by `opt.unwrap()`.
- **Avoid panics:** No `unwrap()` outside tests (dev binaries included). In library code, propagate with `?` and typed errors (`try_borrow()` for `RefCell`, `.get()` / `first_chunk` / `split_at_checked` for slices instead of indexing or `.copy_from_slice()`). Where a panic is genuinely right, use `expect("why this cannot fail")` — the message is the proof, and a public function documents when it panics under `# Panics`. Better still, structure types and control flow so there is no panic site (`let … else`, `Vec::push_mut` (Rust 1.95+), infallible accessors).
- **Asserts:** In tests, the message states *why* the condition should hold or shows the values, never a restatement of the condition. In production, check internal invariants with `debug_assert!` (free in release) unless breaking the invariant would corrupt stored state — then return a typed error.
- **Correct under `panic = "abort"`:** Never rely on `catch_unwind` for control flow; it belongs only at host/FFI/thread boundaries as defense in depth.
- **Mutex poisoning:** Recover a poisoned mutex (`into_inner`) only where the guarded data is valid at every point a panic could strike, with a comment explaining why; otherwise let the poison propagate.

# 4. Memory: APIs and Allocation

## Outputs

- **Fixed-size output:** Return small values by value (`-> u64` is free; see ABI below). Use `fn compute(input: &In, out: &mut Out)` when the caller reuses `out` across calls, fills it in stages, or `Out` is a large `T` inside a `Result`.
- **Slice output:** `fn collect_items(input: &In, out: &mut [Item]) -> Result<usize, Error>` returns the count written; `Error::BufferTooSmall { needed: usize }` tells the caller what to provide. Add a `fn required_len(input: &In) -> usize` sizing helper when the bound isn't obvious.
- **Text output:** Prefer writing into the caller's buffer — `fn render(x: &X, out: &mut dyn core::fmt::Write) -> core::fmt::Result` (one copy of the body; `core::fmt` dispatches through `dyn Write` anyway), `impl core::fmt::Write`, or `&mut String` — when the caller composes, repeats, or streams. Returning `String` is fine when it wins overall on allocations, code size, or readability (a one-shot result the caller would allocate anyway, a cold path, or a helper whose `fmt::Write` form costs more code than it saves).
- **Growable output when unavoidable:** Accept `&mut Vec<T>` and append; the caller clears and reuses capacity across calls so growth is paid once, not per call.
- **Streaming / sequences the caller only walks:** Return `impl Iterator<Item = T>` (or a named iterator type) instead of materializing a collection. Return `Vec` when the function naturally builds one, the caller needs indexing, or transferring ownership is the point.
- **ABI:** Aim for a cheap return on native and `wasm32` alike. Registers carry one scalar, or natively a scalar pair whose variants agree in shape (`&[T]`, `Option<u64>`, `Result<u64, u64>`); keep hot returns within register size (`T` and `E` no larger than `usize`) when it costs nothing (e.g., niche-carrying `Option<NonZero…>` or small enums). Anything larger — `Result<u64, SmallEnum>` included, and every multi-word value on `wasm32` — goes through a hidden return pointer. That is fine for plain returns (an explicit out parameter costs the same), except for a large `T` inside a `Result`: `fn f(.., out: &mut T) -> Result<(), E>` writes `T` in place and returns the small `Result` in a register, whereas `-> Result<T, E>` may copy `T` out at `?`. Verify with `cargo asm` when it matters.

## Parameters

- Borrow the most general form: `&[T]` not `&Vec<T>`, `&str` not `&String`, `&T` not `&Box<T>`, `Option<&T>` not `&Option<T>`.
- Inputs that are only iterated take `&[T]` by default (one instantiation). Use `impl IntoIterator` only when callers genuinely stream; each caller type monomorphizes a copy.
- Use `impl Into<T>` / `impl AsRef<T>` parameters only on thin functions (the conversion plus a call or store, which inlines to nothing, e.g., a builder's `text(s: impl Into<String>)`). Functions with a substantive body should convert at the call site or wrap a non-generic inner function (see §5).
- Prefer enums over `bool` parameters when the call site would read `f(x, true)` (`Round::Up`, `Bound::Inclusive`); a `bool` that remains gets an inline `/* inclusive */` comment at the call site.
- Pass small `Copy` structs by value and everything else by reference; take `String`/`Vec` by value only when transferring ownership is the point.
- Prefer structs with named fields over tuples, except for single-field newtypes and very local tuples.
- **Bulk operations:** Design APIs that accept many items per call to amortize overhead; per-item APIs invite per-item allocations at the call site.
- **Scratch space:** When a function needs temporaries whose size depends on input, take `scratch: &mut Scratch` (a reusable workspace struct) instead of allocating internally. Hoist scratch out of loops.
- Document the allocation behavior of every public function: "allocates nothing", "appends to `out`", "allocates once at startup".
- Add `#[must_use]` on functions whose ignored result is a silent bug (a computed value with no side effects, a success `bool`); `Result` already carries it.

## Allocation Rules

- Prefer fixed arrays (`[T; N]` plus a length) or stack-backed containers (`heapless::Vec<T, N>`, `arrayvec::ArrayVec`/`ArrayString`, `smallvec` — propose before adding a new dependency) over `Vec`/`String` when a sane upper bound exists. Name the bound (`const MAX_POSTINGS: usize`); don't bury magic numbers.
- **Reuse before resize; pre-size once:** `vec.clear()` and `String::clear()` keep capacity — design call patterns around reuse. When growth is required and the final size is known, call `with_capacity` or `reserve_exact` once (from capped input) rather than growing incrementally push by push.
- Hunt hidden allocations: `format!`, `to_string()`, `to_owned()`, `.clone()` of heap types, `.collect()`, string concatenation with `+`, `vec![]` in expressions. Each must justify itself or move to setup/cold code.
- Prefer unique ownership and borrowing; use `Rc`/`Arc` only when the alternative is unreasonably complex — each incurs a heap allocation plus reference-count traffic on every clone.
- Borrow before cloning. Move values out with `core::mem::take`, `core::mem::replace`, or `Option::take` instead of clone-then-clear.
- **Static data over owned data:** Use `&'static str` and enums instead of `String` for codes, labels, and rule references. A `String` field in a result type forces every producer to allocate forever.
- Use `Cow<'_, str>` when data is borrowed in the common case and owned only on the rare path.
- **Sorting:** Prefer `sort_unstable*` (in `core`, allocates nothing) unless stability is required; `sort` and `sort_by_key` live in `alloc` and allocate scratch space.
- **Maps:** Use `BTreeMap`, or a sorted `Vec` + `binary_search`, wherever iteration order can reach output — `HashMap` is randomly seeded and absent from `no_std`. Use `HashMap` only for lookup-only indexes.
- **Building text:** Use `write!` into the caller's or a reused buffer; never use `+` chains or `str::replace` as templating.
- **`no_std`-compatible core:** Structure library crates so the computational core builds with `#![no_std]` (gate `std`/`alloc` behind Cargo features). `#![no_std]` keeps I/O, clocks, and threads out by construction; without `alloc` it forbids heap allocations outright, and with `alloc` enabled allocation remains an explicit review question.
- Use `MaybeUninit` buffers only with a measured win and a `// SAFETY:` comment; a zeroed buffer is almost always fast enough.

**Where allocation is fine** (don't contort code to avoid it): program startup, configuration loading, one-per-lifetime objects, test code, cold error/reporting paths — and anywhere removing the allocation costs more in complexity than it saves. Mark these decisions with a brief comment so they read as intent, not oversight.

# 5. Speed and Code Size

- **Monomorphization is code.** Each distinct `T` instantiates the whole function body. Have generic public entry points convert and call a non-generic inner function:
  ```rust
  pub fn open(path: impl AsRef<Path>) -> Result<Handle, Error> {
      fn open_inner(path: &Path) -> Result<Handle, Error> { /* the body */ }
      open_inner(path.as_ref())
  }
  ```
- **Generics vs `dyn`:** Use generics for hot code with few instantiations; use `dyn` (one copy, an indirect call) for cold paths that would otherwise instantiate many times, and at plugin seams. (Keep error *types* concrete enums.)
- **Macros expand at every call site.** A `macro_rules!` that emits a substantive body per use bloats code size; have it call a function instead.
- **Large lookup tables are `static`**, not `const` (a `const` array may be materialized at each use site; clippy's `large_const_arrays` warns). Build them at compile time with `const fn`.
- **Panic sites cost** a branch plus location metadata each, and the first one links the panic handler. `unwrap`/`expect` on a `Result` also pull in `E: Debug`; each formatted panic or assert message adds its arguments' `Debug`/`Display` formatting code.
- **Hoist bounds checks:** Check length once without a panic site (`let Some(row) = row.first_chunk::<N>() else { … }`, or `row.get(..n)`), or use iterators, `zip`, and `chunks_exact` so per-element bounds checks vanish.
- **Keep cold paths out of the hot path:** Annotate error construction and reporting helpers with `#[cold]`, plus `#[inline(never)]` when large. With release `lto` and `codegen-units = 1`, `#[inline]` is rarely needed — add it only for a measured cross-crate win.
- **Enum size is the largest variant.** One 200-byte variant makes every value 200 bytes: store an ID or index, or split the type; `Box` the large variant (an allocation) only if it is rare. Niches are free: `Option<NonZeroU32>`, `Option<&T>`, and `Option<Box<T>>` cost nothing extra.
- **Measure, don't guess:** Verify hot loops and codegen with `cargo asm` (`cargo asm -p <crate> --lib <path> --rust`), Compiler Explorer, or release disassembly / binary size inspection.

# 6. Types and Traits

- **Strong newtypes over primitive obsession:** Use newtypes (`Amount`, `Rate`, `AccountId`, `Date` — not bare `i64`/`String`) when semantics differ, the type warrants its own API, or mix-ups must be impossible. A `type` alias is only a shorthand and buys no type safety. Make invalid states unrepresentable with enums.
- **Enums and `#[repr]`:** Give closed domain enums stable discriminants where they reach a wire or storage format; `E::X as u16` is a free cast with or without `#[repr]`. Because the compiler already chooses the smallest tag that fits and preserves niches, an explicit `#[repr]` does not save memory (`#[repr(u16)]` on a 3-variant enum doubles its size, and a primitive `#[repr]` on a data-carrying enum gives up the niche: `enum { A(&T), B }` grows from 8 to 16 bytes). Add `#[repr(u32)]` / `#[repr(u16)]` etc. only where layout must be pinned (FFI, serialization, `unsafe` integer decode) or to state a wire code's width. Match exhaustively where a new variant must force a decision; use a wildcard `_` only when remaining variants genuinely share one answer. Avoid `#[non_exhaustive]` on internal crates where compiler-driven exhaustive fan-out is desired.
- Prefer `#[derive]` over hand-written impls when derive expresses the semantics. Prefer standard traits over ad-hoc methods: `FromStr` not `parse_foo`, `Display` for text formatting, `From`/`TryFrom` for conversions — paired with a named constructor (`from_cents`) when units or semantics need clarity.
- **Derive only what is true and needed.** Derive `Copy` only for small types (a few words) that will stay `Copy`. Omit `Clone` on secret-holding types or large buffers unless copying is required — an absent `Clone` makes accidental copies unwritable. Map keys: `Eq + Hash`, or `Ord`.
- Implement `Default` when a natural default exists, and on all-public option/config structs (enabling struct-update syntax).
- Define a trait only for generic code, an `impl Trait`/`dyn Trait` seam, or an extension trait (`FooExt`); never to organize methods — inherent `impl` blocks do that.
- Use operator overloading only for types with a clear mathematical meaning.
- Use `const fn` wherever the body allows so compile-time tables cost nothing at runtime (on published semver crates, commit to `const fn` only when you intend to keep it const).
- **Field order:** Group hot fields together when cache locality matters, and otherwise trust the compiler's layout; use `#[repr(C)]` and explicit layout reasoning only where layout matters (FFI, wire formats, serialization).

# 7. Naming

- **The prefix tells the cost** (std conventions): `as_` = free borrow or view, `to_` = nontrivial conversion work and possibly an allocation, `into_` = consumes `self`. An `as_` method that allocates is a bug.
- **Constructors:** `new`, `new_with_x`, `try_new` (fallible), `from_x` (paired with a `From` impl).
- **Accessors:** `foo()`, `foo_mut()`, `set_foo(v)`, `take_foo()` (returns the old value and leaves the default — no clone), `replace_foo(v)`. **Builders:** `with_foo(self, v) -> Self`. Any type with `len()` also provides `is_empty()`.
- Avoid abbreviations formed by dropping letters (`acct`, `amt`); standard/domain initialisms (`id`, `fx`, `tx`, `rx`) are fine. Use descriptive lifetime names (`'input`, `'buf`) when multiple lifetimes exist; `'a` or `'_` when obvious. Generic type parameter names should hint at their bound (`W: Write`), or use `T`/`U` when unbounded.
- Name files and leaf modules after their primary item.

# 8. Modules and Imports

- A directory module's `mod.rs` (or parent module file) carries the module-level `//!` doc and re-exports its public surface.
- **Globs:** `use super::*` in split submodules and `mod tests`; `pub use sub::*` re-exports in a `mod.rs`; `use Enum::*` inside enum-focused functions. Avoid other globs in new code; avoid custom preludes.
- Import types unqualified (`Amount`) unless ambiguous (`io::Error`, `fmt::Result`). Call free functions from another module module-qualified (`money::parse_entry(..)`) when it aids clarity — follow the file's existing habit.
- Import a trait used in only one function locally inside that function (`use core::fmt::Write as _;`).

# 9. Function Bodies

- Write short functions with early returns, positive booleans, and minimal mutable state; prefer stateless free functions over methods with hidden state.
- Prefer iterators over index loops when equally clear — they optimize the same and bound-check less. Never `.collect()` just to iterate again. Keep iterator chains short; bind a long chain to a named variable before a `for` loop. Use `for_each` only where measured faster (e.g., internal iteration over `chain`/`flatten`).
- Spell types the reader cannot infer: annotate the variable binding for `.into()`, `.parse()`, and `.collect()` (`let n: u32 = s.parse()?;`) rather than using turbofish.
- Prefer `s.bytes()` over `s.chars()` when handling ASCII; prefer slice patterns (`if let [first, .., last] = slice`).
- No magic numbers — define named constants or enums unless the literal is obvious.
- Use atomics (`AtomicBool`, `AtomicUsize`) for primitive flags and counters, not `Mutex<bool>` / `Mutex<usize>`.
- **No life before `main`:** Globals are for process-wide resources only (e.g., TLS roots, allocator state, static lookup tables), held in a `static` behind `OnceLock`, an atomic, or a mutex, with a comment explaining why it is global — never state that a function reads as a hidden input.
- Use `#[rustfmt::skip]` only for deliberate tabular alignment or generated code.
- **Tests:** Assert exact values (fixed-point makes this possible) and cover boundary conditions; keep mocks out — pure functions need none. Pair unit tests with property-based and fuzz tests (`proptest`, `bolero`, `cargo-fuzz`) on parsers, wire codecs, and invariants.

# 10. `unsafe` and Macros

- **Minimal `unsafe`:** Use `unsafe` only where safe code cannot do the job, encapsulate it behind a safe API, and annotate every block with a `// SAFETY:` comment stating the invariant. If `unsafe` is used for speed, cite the benchmark.
- **Macros**, in order of preference: plain functions/code → `macro_rules!` → build-time codegen → proc macro. A macro must buy something a function cannot (such as compile-time format/literal checking or static table generation); it costs IDE tooling, readability, and per-call-site code size.

# 11. Documentation

- Use `//!` for crates and modules (stating local rules, invariants, and the tests that gate them), `///` for public items, and `//` for implementation notes. Comments tell WHAT and WHY, not HOW — don't restate the code or explain the language.
- Doc-comment every public item (and everything crossing a crate boundary): document `# Panics`, `# Errors`, `# Safety` invariants, and **who allocates**.

# 12. Enforcement

Configure lints in the workspace `Cargo.toml` (`[workspace.lints.clippy]`) or crate root:

```toml
[lints.clippy]
alloc_instead_of_core = "warn"
std_instead_of_core = "warn"
std_instead_of_alloc = "warn"
redundant_clone = "warn"
unnecessary_to_owned = "warn"
inefficient_to_string = "warn"
format_collect = "warn"
rc_buffer = "warn"
vec_box = "warn"
large_types_passed_by_value = "warn"
trivially_copy_pass_by_ref = "warn"
needless_pass_by_value = "warn"
fn_params_excessive_bools = "warn"
unnecessary_box_returns = "warn"
implicit_clone = "warn"
iter_over_hash_type = "warn"
large_const_arrays = "warn"
missing_panics_doc = "warn"
unwrap_used = "warn"
```

Run these checks as part of every build and review gate:

```sh
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo +nightly miri test   # required whenever unsafe code exists
cargo audit && cargo deny check
```

- Fix warnings rather than suppressing them with `#[allow]`, and exercise untrusted-input parsers and state machines with `proptest`, `bolero`, or `cargo-fuzz`.
- For internal crates/workspaces (where nothing is a published semver API), set `avoid-breaking-exported-api = false` and `allow-unwrap-in-tests = true` in `clippy.toml` so lints inspect `pub` signatures too (note: non-`#[test]` helpers in integration tests still use `expect`).
- Do not blindly enable `large_stack_arrays`: it false-positives on constant slices that reside in read-only data rather than on the stack.
- For allocation-critical paths, add a test with a counting allocator (`#[global_allocator]` wrapper) or `assert_no_alloc` asserting the per-call allocation budget.

# 13. Red-Team Review Checklist

Before declaring a change complete, review the diff against these questions:

- **Untrusted input:** Which values come from outside, where is each one's validation gate, and can any reach a panic, an overflow, or an uncapped allocation before it?
- **Allocations:** Where does this allocate? Run the hidden-allocation hunt on your own diff.
- **Code size & speed:** What does this add to the binary? Check generic instantiations, macro expansions, and remaining panic sites.
- **10,000 calls per frame on a microcontroller:** What would you change? If the improvement is cheap, do it now.
- **The API:** Can the caller reuse buffers across calls, and size them without guessing?
