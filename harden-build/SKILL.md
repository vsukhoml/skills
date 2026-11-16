---
name: harden-build
description: >-
  Production binary hardening and verification gates for C/C++, Rust, Go, and
  native Python wheels: compiler and linker exploit mitigations (PIE, RELRO,
  FORTIFY, CET, PAC/BTI, CFI) with an ELF checker script, sanitizers, fuzzing,
  MC/DC and mutation coverage, formal verification, and reproducible builds.
  Use when preparing a production release, auditing compiler or ELF flags,
  wiring fuzzing or coverage gates, or proving critical loops, parsers, or
  state machines.
last_updated: 2026-11-15
---

# Build-Time Binary Hardening & Software Assurance

Host, firewall, and container controls limit **blast radius after a bug fires**.
This skill eliminates the bug before deploy — or turns memory corruption and
invariant violations into immediate, unexploitable traps (`SIGILL`/`SIGABRT`)
at ~1–3% CPU cost and zero extra daemons.

Three rules govern everything below:

1. **Separate production exploit mitigations from CI bug-finding sanitizers.**
   Production builds get hardware/trap mitigations (`PIE`, `Full RELRO`, stack
   canaries, stack-clash, `_FORTIFY_SOURCE=3`, `CET` / `PAC+BTI`, trap-mode
   `CFI`, stdlib bounds checks, Rust `overflow-checks = true`). **Never ship
   `ASan`, `MSan`, `TSan`, or `LSan` runtimes to production**: they cost 2×–3×
   CPU/RAM, weaken ASLR, and parse `ASAN_OPTIONS` environment variables (a
   classic local privilege-escalation primitive on setuid/privileged binaries).
2. **Verify the compiled ELF, never the `Makefile`.** Subprojects, CMake
   `ExternalProject`, Rust `-sys` crates (`cc-rs`), `CGO`, prebuilt Python/Node
   `.so` wheels, and hand-written `.S` assembly files routinely drop `CFLAGS`
   or silently mark the stack executable (`GNU_STACK RWE`). Gate CI on the
   bundled `scripts/check-elf.sh --strict`.
3. **Match assurance depth to consequence.** Every untrusted parser gets
   coverage-guided fuzzing; security gates get branch/MC/DC + mutation
   coverage; the 1–5% core of critical loops, framing parsers, fixed-point
   math, and concurrency/consensus protocols gets bounded model checking or
   formal proof.

**Bundled tool:** `scripts/check-elf.sh` (read-only; uses only GNU `readelf`).

---

## 1. Compiler & Linker Hardening (Production Builds)

### C & C++ Production Baseline (GCC ≥ 13, Clang ≥ 17)

| Flag(s) | What it stops | Runtime cost / caveat |
| --- | --- | --- |
| `-O2 -D_FORTIFY_SOURCE=3` | Buffer overflows in `memcpy`, `snprintf`, `fgets`, etc., using dynamic object-size expressions (`__builtin_dynamic_object_size`) | ~0.5%. **Requires `-O1` or higher**; `-O0` silently disables fortification. Undefine first (`-U_FORTIFY_SOURCE`) if distro defaults set `=2`. |
| `-fstack-protector-strong` | Stack buffer overflows overwriting the return address | <1%. Protects functions with arrays, address-taken locals, or `alloca`. |
| `-fstack-clash-protection` | Large stack frames or `alloca` jumping over the kernel stack guard page into the heap ( paired with `-Werror=vla`) | <0.5%. Probes each stack page on allocation. |
| `-fPIE -pie` (exec) / `-fPIC -shared` (lib) | Fixed-address ROP/JOP gadgets; enables full ASLR for code and data | <1% on x86-64 / AArch64. |
| `-Wl,-z,relro,-z,now` | GOT overwrite attacks (resolves all PLT symbols at startup and mmaps `.got` read-only) | Small startup cost on binaries linking >100 shared libraries; 0 steady-state cost. |
| `-Wl,-z,noexecstack` | Shellcode execution on the stack (needed because one `.S` file missing `.note.GNU-stack` flips the whole binary to `RWE`) | 0. Pair with systemd `MemoryDenyWriteExecute=yes` (`harden-host` §6). |
| `-ftrivial-auto-var-init=zero` | Uninitialized stack variable info leaks and deterministic UAF/wild-pointer values | ~1%. (Not a substitute for `MSan` in CI.) |
| `-D_GLIBCXX_ASSERTIONS` (libstdc++) or `-D_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_FAST` (libc++) | Spatial out-of-bounds in `std::vector::operator[]`, `std::span`, `std::string_view`, `std::optional` — the largest real bug class in modern C++ | ~0.5–1.5%. Aborts cleanly on OOB instead of corrupting heap. |
| `-fno-delete-null-pointer-checks -fno-strict-overflow` | Compiler deleting null checks after an earlier deref, or optimizing away signed-overflow checks as UB | ~0.5%. Add `-fno-strict-aliasing` on legacy C/C++ that type-puns via pointers instead of `memcpy`. |

### Control-Flow Integrity (CFI): Hardware + Compiler

Enable **both** architectural hardware CFI (backward + coarse forward edge,
works across shared libraries) and compiler type-based forward-edge CFI where LTO
is feasible:

1. **x86-64 Intel CET / AMD Shadow Stack (`-fcf-protection=full`):**
   - Emits `ENDBR64` landing pads (**IBT**, forward-edge) and marks ELF
     `.note.gnu.property` with `IBT, SHSTK` (**Shadow Stack**, hardware
     backward-edge return-address protection).
   - Safe on older x86-64 CPUs (`ENDBR64` decodes as a `NOP`). Enforced in
     userspace on Linux ≥ 6.6 + glibc ≥ 2.39 when **every** linked `.so` carries
     the `SHSTK` note — one unannotated `.so` loaded at startup or via `dlopen`
     downgrades the process unless glibc CET tunables lock it (`harden-host` §4).
2. **AArch64 PAC + BTI (`-mbranch-protection=standard`):**
   - Cryptographically signs return addresses on entry and verifies before `ret`
     (**PAC-RET**, backward-edge) and enforces `BTI` landing pads on indirect
     jumps/calls (forward-edge). Also uses `HINT`/NOP-space instructions for
     backward compatibility.
   - On ARMv8.5-A+ hardware with Memory Tagging Extension (**MTE**), add
     `-march=armv8.5-a+memtag` and enable sync/async heap tag checks via glibc
     tunables (`GLIBC_TUNABLES=glibc.mem.tagging=3`) on internet-facing C/C++
     daemons to catch spatial OOB and use-after-free in hardware.
3. **Clang LTO Forward-Edge CFI (`-flto -fvisibility=hidden -fsanitize=cfi -fsanitize-trap=cfi`):**
   - Validates every C++ virtual call and indirect C function-pointer call
     against the exact compile-time signature/class hierarchy.
   - **Critical production detail:** Always pair `-fsanitize=cfi` with
     **`-fsanitize-trap=cfi`** (and `-fno-sanitize-recover=all`). Without
     `-fsanitize-trap=cfi`, Clang links the UBSan diagnostic runtime. With trap
     mode, violations emit a 2-byte `ud2` / `brk` instruction: zero runtime
     library, no symbol leaks, ~1% CPU overhead.
   - Requires `-fvisibility=hidden` (or explicit export maps). If your binary
     calls function pointers into uninstrumented `dlopen` plugins, either use
     `-fsanitize=cfi-nvcall,cfi-vcall,cfi-derived-cast,cfi-unrelated-cast`
     (skipping `cfi-icall`) or `-fsanitize=kcfi` for freestanding/plugin ABIs.
4. **Trap-mode integer & bounds hardening on exposed C parsers:**
   - For internet-facing C parsers (TLS, DNS, HTTP, media, wire framing), add
     `-fsanitize=bounds,signed-integer-overflow,shift,null -fsanitize-trap=all`.
     Undefined overflows and array overruns abort immediately instead of
     computing a wrapped `malloc(len)` size.

Canonical hardened C/C++ production invocation (Clang):

```sh
CFLAGS="-O2 -U_FORTIFY_SOURCE -D_FORTIFY_SOURCE=3 \
  -fPIE -fstack-protector-strong -fstack-clash-protection \
  -ftrivial-auto-var-init=zero -fno-delete-null-pointer-checks -fno-strict-overflow \
  -fcf-protection=full -flto=thin -fvisibility=hidden \
  -fsanitize=cfi -fsanitize-trap=cfi -fno-sanitize-recover=all"
CXXFLAGS="$CFLAGS -D_GLIBCXX_ASSERTIONS"
LDFLAGS="-pie -flto=thin -fvisibility=hidden -fsanitize=cfi -fsanitize-trap=cfi -fno-sanitize-recover=all -Wl,-z,relro,-z,now,-z,noexecstack"
```

*(On `aarch64`, replace `-fcf-protection=full` with `-mbranch-protection=standard`.)*

### Rust, Go, and Native Extensions (`.so` Wheels / Addons)

- **Rust (`Cargo.toml` + `RUSTFLAGS`):**
  - Safe Rust prevents memory corruption, **not** silent release-build integer
    wraparound (`u32` wrap in size/fee math) or vulnerabilities inside `unsafe`
    blocks and C `-sys` crates (`openssl-sys`, `libsqlite3-sys`, `zstd-sys`).
  - Put in workspace `Cargo.toml`:
    ```toml
    [profile.release]
    overflow-checks = true   # trap integer wrap in prod (~1% cost; use wrapping_* when intended)
    panic = "abort"          # drop unwind tables/gadgets; smaller binary
    lto = "thin"
    codegen-units = 1
    strip = "symbols"
    ```
  - Enforce Full RELRO (`RUSTFLAGS="-C relro-level=full"`, default on Linux
    x86_64) and build container/server binaries with **`cargo auditable build
    --release`** so compressed dependency metadata lands in `.dep-v0` (readable
    by Trivy/Grype/`osv-scanner` even inside `FROM scratch`).
  - Export hardened `CFLAGS` (above, minus `-fPIE`/`-pie` which `cc-rs` manages
    via `-fPIC`) during `cargo build` so vendored C `-sys` crates inherit
    `_FORTIFY_SOURCE=3`, `-fstack-protector-strong`, `-fstack-clash-protection`,
    and `-fcf-protection=full` / `-mbranch-protection=standard`!
  - On nightly toolchains for high-assurance targets, rebuild `std` with
    `-Z build-std --target <triple>` alongside `RUSTFLAGS="-Z cf-protection=full"`
    (x86-64) or `RUSTFLAGS="-Z branch-protection=bti,pac-ret"` (AArch64) — without
    `-Z build-std --target <triple>`, precompiled `libstd` lacks CET/BTI notes and
    the linker drops them from the final ELF — and add `-Z sanitizer=cfi -C lto`
    when FFI boundaries link with Clang LTO.
- **Go:**
  - **Prefer `CGO_ENABLED=0`** (`CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -buildid="`).
    Pure Go removes libc, dynamic loaders, GOT/PLT, and C memory unsafety
    completely, while `-s -w` strips DWARF/symbol tables **without** removing
    `.go.buildinfo` (so `govulncheck` and SBOM scanners still work).
  - **When `CGO_ENABLED=1` is unavoidable** (SQLite, PKCS#11, hardware acceleration):
    build with `-buildmode=pie` and export `CGO_CFLAGS="-O2 -D_FORTIFY_SOURCE=3
    -fstack-protector-strong -fstack-clash-protection -fcf-protection=full"` and
    `CGO_LDFLAGS="-Wl,-z,relro,-z,now,-z,noexecstack"`.
  - When regulated cryptography is required, Go ≥ 1.24 supports native FIPS
    mode (`GOFIPS140=v1.0.0`) without pulling in OpenSSL via CGO.
- **Python, Node.js, Ruby, and JNI native extensions:**
  - A Python or Node service loading prebuilt wheels/addons (`cryptography`,
    `pillow`, `lxml`, `numpy`, `sharp`, custom Cython/PyO3/N-API modules) runs
    native ELF shared libraries in-process. Audit the `.venv` / `node_modules`
    tree with `scripts/check-elf.sh` — prebuilt `manylinux` wheels compiled on
    old toolchains frequently lack Full RELRO, stack-clash, or CET!

### Reproducible Builds & CI ELF Gate

Make builds deterministic so anyone (or a second independent CI runner) can
recompute the exact SHA-256 of a signed release (`harden-supply-chain`):

- Export `SOURCE_DATE_EPOCH=$(git log -1 --pretty=%ct)`, `TZ=UTC`, `LC_ALL=C`.
- C/C++: `-ffile-prefix-map="$PWD"=. -fno-record-gcc-switches`.
- Go: `-trimpath -ldflags="-buildid="`.
- Rust: `RUSTFLAGS="--remap-path-prefix=$PWD=. --remap-path-prefix=${CARGO_HOME:-$HOME/.cargo}=/cargo" cargo build --locked --release`.

Verify every built binary and `.so` in CI (and inside `Dockerfile` builder
stages before copying to `FROM scratch`):

```sh
# Fails (exit 1) on executable stack, RWX segments, dynamic NO-PIE, Partial/No RELRO,
# or accidentally linked ASan/TSan/MSan/UBSan runtimes.
# Scope --require-cfi (CET IBT+SHSTK / AArch64 BTI+PAC) to C/C++ and nightly -Z build-std Rust:
bash <skill-dir>/scripts/check-elf.sh --strict --require-cfi -- /out/c_or_cpp_app
# Use --strict (without --require-cfi) for stable Rust (prebuilt libstd lacks CET notes) and prebuilt Python wheels:
bash <skill-dir>/scripts/check-elf.sh --strict -- /out/rust_app /venv
```

---

## 2. Sanitizers & Continuous Fuzzing

Unit tests check inputs the author imagined. Coverage-guided fuzzing mutates
inputs guided by edge/comparison instrumentation to find the inputs nobody
imagined.

### Mandatory Fuzzing Scope

Write a fuzz target before exposing **any** of these to untrusted bytes:

- Wire framing, RPC/protobuf/JSON/CBOR/YAML/MsgPack/ASN.1 decoders
- HTTP headers, cookies, URL/path normalizers, query/filter DSL parsers
- Auth tokens (JWT/PASETO/macaroons), cryptographic envelopes, X.509/SSH keys
- File, image, PDF, archive (`tar`/`zip` zip-slip & decompression-bomb caps!),
  and compression wrappers
- Stateful protocol machines (feed a fuzzed *sequence of commands/frames*, not
  just single packets)

### Sanitizer Matrix (CI & Fuzzers Only — Never Production)

| Sanitizer | Catches | Where to run |
| --- | --- | --- |
| **ASan + LSan** (`-fsanitize=address`) | Heap/stack/global OOB, use-after-free, double-free, memory leaks (`detect_leaks=1`) | Every PR test run + primary fuzz build (`-O1 -fno-omit-frame-pointer`) |
| **UBSan** (`-fsanitize=undefined,integer` or narrow set) | Signed overflow, null/misaligned deref, shift OOB, enum/bool out-of-range, vptr type confusion | Paired in the same build as ASan (`UBSAN_OPTIONS=print_stacktrace=1:halt_on_error=1`) |
| **MSan** (`-fsanitize=memory -fsanitize-memory-track-origins=2`) | Reads of uninitialized heap/stack memory (requires instrumented libc++/deps; Clang only) | Nightly C/C++ CI + dedicated fuzz target |
| **TSan** (`-fsanitize=thread` / `go test -race`) | Data races and lock-order inversions | Every PR concurrency suite |
| **Miri** (`cargo +nightly miri test`) | Rust `unsafe` UB: Tree/Stacked Borrows aliasing violations, uninit reads, misaligned pointers, FFI layout mismatches | Every crate containing `unsafe` |

*(Want ultra-cheap production heap UAF/OOB sampling without ASan's risks? Use
**GWP-ASan** in Scudo/TCMalloc at <0.5% overhead.)*

### Ecosystem Fuzzing Recipes

- **C / C++ (`libFuzzer` or `AFL++`):**
  ```sh
  clang -g -O1 -fno-omit-frame-pointer \
    -fsanitize=fuzzer,address,undefined \
    fuzz_parse_frame.c src/frame.c -o fuzz_parse_frame
  ./fuzz_parse_frame -max_len=65536 -timeout=2 corpus/ seeds/
  ```
  For formats with magic bytes or checksums, run **AFL++** with `afl-clang-lto`
  + **`CMPLOG`** (`AFL_LLVM_CMPLOG=1`) so multi-byte comparisons split
  automatically, or `libprotobuf-mutator` for structure-aware grammar fuzzing.
- **Rust (`cargo-fuzz` or `bolero`):**
  Prefer **`bolero`** when starting fresh: one `bolero::check!()` target runs as
  a standard `cargo test` regression test, `proptest`, `cargo fuzz` (`libFuzzer`
  + ASan), `AFL++`, **and** a `cargo kani` formal proof harness!
- **Go (native `testing.F`):**
  ```sh
  # Replay checked-in seed + crasher corpus on every PR (<2s):
  go test -race ./...
  # Coverage-guided fuzzing gate in CI / nightly:
  go test -fuzz=^FuzzParseToken$ -fuzztime=60s ./internal/auth
  ```
- **Python & JVM:**
  Use **`Hypothesis`** (property-based + `@example` regression database) everywhere,
  paired with **`Atheris`** when Python wraps C/C++/Rust native extensions
  (instrument the native extension with `-fsanitize=address,fuzzer-no-link` so
  Atheris guides C-level branches too!). Use **`Jazzer`** on the JVM.

### High-Signal Fuzz Oracles (Catch Logic Bugs, Not Just Crashes)

A memory-safe parser in Go, Rust, or Python rarely segfaults — its security
bugs are **panics, algorithmic DoS (OOM / CPU hang), canonicalization
divergences, and round-trip mismatches**. Assert these inside every fuzz target:

1. **No panic / bounded time & memory:** Set `-rss_limit_mb=512 -timeout=2`.
   Assert output size/work is bounded (`output.len() <= MAX_EXPANSION`) to catch
   decompression/allocation bombs (`100 B` input allocating `2 GiB`).
2. **Round-trip identity:** `let x = decode(bytes)?; assert_eq!(decode(&encode(&x))?, x);`
3. **Canonicalization idempotence:** `assert_eq!(normalize(&s), normalize(&normalize(&s)));`
   (catches path-traversal and WAF/auth URL-normalization bypasses).
4. **Differential fuzzing:** Feed the exact same fuzzed input to two
   implementations (`fast_simd_parser(b) == simple_ref_parser(b)`) — any
   disagreement on accept/reject or parsed fields is an immediate bug.

Run **ClusterFuzzLite** in GitHub Actions (pinned by commit SHA) for 60–300 s of
PR diff-fuzzing, plus scheduled nightly runs with a persistent corpus cache.
Every crasher becomes a permanent regression file in git.

---

## 3. High Code Coverage & Mutation Testing

### Why Line Coverage Alone Lies

90% **line** coverage routinely hides:
- Unchecked `err != nil` / `NULL` / overflow rollback branches on multi-clause
  lines
- Short-circuit boolean bypasses in security checks (`if is_internal ||
  verify_hmac(req)` tested only with `is_internal = true` gives 100% line
  coverage while `verify_hmac` is broken!)
- "Assertion-free" tests that execute code for coverage numbers without checking
  the output or post-failure state

### Tiered Coverage Standard

Measure **branch coverage** everywhere, and **MC/DC** (Modified
Condition/Decision Coverage — every atomic boolean condition independently
shown to affect the decision outcome) on security gates:

| Code tier | Minimum gate | Extra verification |
| --- | --- | --- |
| **Tier 1 — Security & correctness core:** auth/ACL/session gates, parsers, crypto/token logic, billing/ledger math, state machines | **≥ 90–95% branch coverage** + **100% error/rejection-path coverage** | **MC/DC** on multi-condition gates + **mutation testing** |
| **Tier 2 — Domain & service handlers** | **≥ 80–85% branch coverage** | Integration tests covering rollback/timeout rows |
| **Tier 3 — CLI glue, generated code, thin wiring** | Exclude generated code from denominator; smoke-test wiring | Do not write assertion-free filler tests |

Commands by toolchain:

```sh
# C/C++ (Clang >= 18 supports native MC/DC with -fcoverage-mcdc!):
clang -O1 -g -fprofile-instr-generate -fcoverage-mapping -fcoverage-mcdc \
  tests/auth_test.c src/auth.c -o auth_test
LLVM_PROFILE_FILE="auth.profraw" ./auth_test
llvm-profdata merge -sparse auth.profraw -o auth.profdata
llvm-cov report --show-branch-summary --show-mcdc-summary ./auth_test \
  -instr-profile=auth.profdata
# (GCC >= 14 equivalent: -fprofile-arcs -ftest-coverage -fcondition-coverage -> gcov -bc)

# Rust (branch coverage; requires nightly toolchain):
cargo +nightly llvm-cov --all-features --workspace --branch --fail-under-branches 85

# Go (atomic mode with race detector):
go test -race -covermode=atomic -coverprofile=coverage.out ./...

# Python (branch coverage enforced):
pytest --cov=src --cov-branch --cov-fail-under=85
```

### Mutation Testing: Proving Tests Actually Catch Bugs

Run mutation testing on **Tier 1** files so flipped comparisons (`<` → `<=`),
deleted early returns (`return Err(Unauthorized)`), and swapped logical operators
(`&&` → `||`) are proven to fail the test suite:

- **Rust:** `cargo mutants --file src/auth.rs --file src/parser.rs`
- **Python:** `mutmut run --paths-to-mutate src/auth/`
- **C / C++:** `mull-runner` (LLVM bitcode mutator) or `dextool mutate`
- **Go:** `gremlins unleash ./internal/auth`

Treat any surviving mutant in an auth check, bounds guard, or ledger invariant
as a missing test assertion — never silence it with dummy lines.

---

## 4. Formal Methods: Proving Critical Loops, Algorithms & Protocols

Fuzzing explores millions of inputs; **formal verification exhausts all `2^64`
inputs or all interleavings mathematically**. Applied to whole CRUD apps it
drowns in effort; applied to the **small, load-bearing core** (50–500 lines) it
eliminates entire classes of catastrophic bugs permanently.

### Target Selection (Where Formal Methods Pay Off)

Prove code that sits on one of these five boundaries:

1. **Critical loops & framing parsers:** Length-prefixed packet/TLV/ring-buffer
   loops where an off-by-one or non-advancing cursor causes OOB read/write or
   infinite-loop DoS.
2. **Fixed-point, financial, quota & fee arithmetic:** Proving zero overflow,
   monotonicity, and conservation (`sum(splits) == total`) across all valid
   64/128-bit bounds.
3. **Access-control, rate-limiter & token-bucket evaluators:** Proving no
   sequence of timestamps/requests grants tokens above capacity or bypasses a
   deny rule.
4. **Concurrent, lock-free & distributed state machines:** Retry/idempotency
   keys, lease/fencing tokens, WAL crash recovery, and replication protocols.
5. **Constant-time cryptographic / secret-handling routines.**

### The 4-Step Verification Escalation Ladder

Start at Step 1 (hours) and climb only as far as the component's reversal/blast
cost warrants:

#### Step 1: Automated Bit-Vector & Symbolic Equivalence (`Z3`, `Lean 4 bv_decide`, `CrossHair`)
- When optimizing a hot loop, bit-twiddling routine, branchless range check, or
  fixed-point calculation, prove equivalence across **every** 64/128-bit input:
  - **Z3 (`python3-z3` / `z3-solver`):** Model `BitVec('x', 64)` and verify
    `solver.check(fast != spec) == unsat` in a 15-line Python test.
  - **Lean 4 (`bv_decide`):** `Std.Tactic.BVDecide` (Lean ≥ 4.12) bit-blasts
    `BitVec` and `Bool` goals to bundled CaDiCaL, prints concrete counterexamples
    when a claim is false, and checks an **LRAT proof certificate inside Lean's
    trusted kernel** (`bv_decide?` caches a `bv_check` certificate for fast CI):
    ```lean
    import Std.Tactic.BVDecide

    def satAdd64 (x y : BitVec 64) : BitVec 64 :=
      if x + y < x then BitVec.allOnes 64 else x + y

    theorem satAdd64_monotonic (x y : BitVec 64) :
        x <= satAdd64 x y ∧ y <= satAdd64 x y := by
      simp only [satAdd64]
      bv_decide
    ```
- In Python, run **`crosshair check`** alongside `Hypothesis` on pure domain
  functions with preconditions/postconditions.

#### Step 2: Bit-Precise Bounded Model Checking on Production Code (`Kani`, `CBMC`)
Proves **actual Rust or C source code** (no separate modeling language) free of
panics, buffer overflows, pointer/slice OOB, division by zero, signed/unsigned
overflow, and assertion failures up to a loop bound — or unbounded with a
**loop contract**:

- **Rust (`cargo kani`):**
  ```rust
  // Proves parse_tlv_frames never panics, overflows, or stalls on ANY <= 64-byte buffer:
  #[cfg(kani)]
  #[kani::proof]
  #[kani::unwind(65)]
  fn proof_tlv_loop_terminates_and_stays_in_bounds() {
      let buf: [u8; 64] = kani::any();
      let len: usize = kani::any_where(|&n| n <= buf.len());
      let _ = parse_tlv_frames(&buf[..len]);
  }
  ```
  For loops with large/symbolic bounds, use Kani's **`#[kani::loop_invariant(...)]`**
  to prove the loop inductively in seconds without unrolling `2^32` iterations.
- **C (`cbmc`):**
  ```sh
  # --unwinding-assertions is MANDATORY: without it, CBMC silently truncates deeper
  # loops instead of proving that the loop bound is never exceeded!
  cbmc parser.c --function parse_packet \
    --bounds-check --pointer-check --signed-overflow-check \
    --unsigned-overflow-check --div-by-zero-check --nan-check \
    --unwind 33 --unwinding-assertions
  ```

#### Step 3: Deductive Verification & Executable Reference Models (`Lean 4`, `Frama-C WP`, `Aeneas`, `Verus`, `SAW`)
When bounded unwinding isn't enough (arbitrary-length buffers, authorization
engines, ledger math, crypto kernels), prove invariants inductively or against a
verified functional specification:

- **Lean 4 (`lean` / `lake`) — Two High-ROI Production Patterns:**
  1. **Executable Reference Model + Differential Fuzzing (AWS Cedar pattern; language-agnostic):**
     Write a 100–300 line pure functional model of your authorization policy
     evaluator, quota/fee ledger, or protocol state machine in **Lean 4**, prove
     soundness, monotonicity, and termination theorems (`lake build` + reject
     `sorryAx` via `#print axioms` / `leanchecker`), and differentially fuzz the
     production C/Rust/Go/Python implementation against the compiled Lean oracle
     (`lean_spec(x) == prod_impl(x)`).
  2. **Rust-to-Lean Extraction (`Charon` + `Aeneas`):** Translate safe Rust MIR
     (parsers, bignum/crypto loops, data structures) directly into pure Lean 4
     definitions so proofs track real Rust source without `unsafe` drift.
- **Unbounded C Loops (`Frama-C WP`):** Every proven loop must establish **three
  properties**:
  1. **Loop invariant:** True on entry and preserved by every step (`0 <= i <= len`).
  2. **Frame / `loop assigns` clause:** Exact memory locations mutated by the loop.
  3. **Loop variant (ranking function):** Integer bounded below by `0` that
     **strictly decreases** every step (e.g., `len - i`) — proving **termination**
     (zero infinite-loop DoS!).

```c
/*@ requires \valid_read(buf + (0 .. len - 1));
  @ assigns \nothing;
  @ ensures -1 <= \result < (integer)len;
  @*/
ssize_t find_delim(const uint8_t *buf, size_t len, uint8_t delim) {
  /*@ loop invariant 0 <= i <= len;
    @ loop invariant \forall integer k; 0 <= k < i ==> buf[k] != delim;
    @ loop assigns i;
    @ loop variant len - i;
    @*/
  for (size_t i = 0; i < len; i++) {
    if (buf[i] == delim) return (ssize_t)i;
  }
  return -1;
}
// Verify: frama-c -wp -wp-rte find_delim.c   (-wp-rte proves zero runtime UB!)
```

For inline Rust deductive proofs, use **`Verus`** or **`Creusot`**; for
cryptographic C/Rust/LLVM equivalence against RFC specs, use Galois **`SAW` /
`Crucible`**.

#### Step 4: Concurrency & Distributed Protocol Model Checking (`TLA+` / `Apalache` / `Quint`, `Loom`)
Most high-severity production incidents in memory-safe services come from **message
reordering, retries, node crashes mid-transaction, and lock-free/async races**:

- **Distributed / stateful protocols:** Write a 60–150 line **`TLA+`** (checked
  with `tlc` or symbolic `Apalache`), **`Quint`**, or **`Alloy`** model directly
  from the protocol specification's safety invariants before coding. Check:
  - **Safety invariants:** e.g., `AtMostOneLeaseOwner`, `LedgerConserved`,
    `RevokedTokenNeverAcceptedAfterWindow`.
  - **Temporal liveness:** no deadlock/livelock under packet drop + retry.
- **In-process concurrency (Rust / C++):** Exhaust thread interleavings
  deterministically in CI with **`loom`** (exact permutation model checking for
  atomics/lock-free queues) or **`shuttle`** (randomized concurrency scheduler
  with shrinking).

### Constant-Time & Compiler Side-Channel Verification

Modern optimizing compilers (`Clang`/`GCC` `-O2`/`-O3`) routinely recognize
branchless C/Rust masks and rewrite them back into conditional jumps (`jne`),
silently re-introducing timing side channels (as in KyberSlash).

- Use audited constant-time primitives: `subtle` (Rust), `crypto/subtle` (Go),
  `hmac.compare_digest` (Python), `CRYPTO_memcmp` / `timingsafe_bcmp` (C) with
  value barriers so LLVM cannot prove mask values are `0`/`-1` and branch on them.
- **Verify the compiled binary, not the source:**
  - Inspect generated machine code (`objdump -d` — zero conditional branches or
    secret-indexed memory lookups inside secret loops).
  - Run **`ctgrind`** (Valgrind taint-marking secret inputs as `UNDEFINED` so
    any secret-dependent branch or memory address immediately triggers a
    Valgrind error in CI!) or **`dudect`** statistical timing checks.

---

## 5. High-Expected-Value Tool Discovery & Safe Installation

Before running build/assurance gates — or when reviewing a high-consequence
codebase — **probe what is already installed** and recommend missing tools
**only where Expected Value (`EV`) is clearly positive**:

$$\text{EV} = P(\text{subtle high-impact bug}) \times \text{Blast Radius} - \text{Setup \& CI Cost}$$

1. **Inventory locally first (read-only):**
   ```sh
   for t in gcc clang lld llvm-cov readelf valgrind afl-fuzz \
            cargo-fuzz cargo-llvm-cov cargo-mutants cargo-kani cargo-auditable \
            cbmc frama-c z3 lean lake tlc apalache quint; do
     printf '%-16s %s\n' "$t" "$(command -v "$t" 2>/dev/null || echo MISSING)"
   done
   ```
2. **Apply the EV filter:**
   - **High EV (proactively suggest tool + offer to install):** Untrusted
     network/file parsers, C/C++/CGO/`unsafe` Rust memory paths, authorization
     or policy engines, financial/quota/ledger fixed-point math, cryptographic or
     secret-handling code, and lock-free, WAL, or distributed retry/consensus
     protocols.
   - **Low EV (stay quiet):** Internal CRUD glue, CLI wrappers, or stateless
     formatting code where compiler flags + unit tests + standard linters suffice.
3. **Ask before installing, and use supply-chain-safe install commands (`harden-supply-chain`):**
   - Never install packages without explicit user consent, and **never suggest
     unverified `curl ... | sh`**.
   - Prefer signed OS packages (`apt` / `dnf`), `--locked` Cargo installs, or
     release archives verified with `sha256sum -c` / `gh attestation verify`.

| High-EV Workload / Gap | Recommended Tool(s) | Supply-Chain-Safe Install (Debian/Ubuntu / Cross-Platform) |
| --- | --- | --- |
| Clang ThinLTO/CFI linking & `-fcoverage-mcdc` branch/MC/DC reports | `lld`, `llvm` (`llvm-cov`, `llvm-profdata`) | `sudo apt install lld llvm` |
| C/C++ coverage-guided & `CMPLOG` fuzzing on untrusted parsers | `clang` (`libFuzzer`), `AFL++` | `sudo apt install clang afl++` |
| Fast 64/128-bit bit-vector & fixed-point equivalence proofs (any language) | `Z3` (`z3`, `python3-z3`) | `sudo apt install z3 python3-z3` *(or `uv pip install z3-solver`)* |
| C/C++ bounded model checking (framing loops, ring buffers, pointer bounds) | `CBMC` | `sudo apt install cbmc` |
| Unbounded C deductive loop & memory-safety proofs (ACSL) | `Frama-C WP` | `sudo apt install opam && opam init && opam install frama-c` |
| Rust bit-precise panic/loop proofs, mutation testing & binary SBOM | `Kani`, `cargo-mutants`, `cargo-auditable` | `cargo install --locked kani-verifier cargo-mutants cargo-auditable && cargo kani setup` |
| Executable reference specs + differential fuzzing, `bv_decide`, or Rust extraction (`Aeneas`) | **Lean 4** (`elan`, `lean`, `lake`) | Download `elan-<arch>-unknown-linux-gnu.tar.gz` from `github.com/leanprover/elan/releases`, verify `sha256sum -c` against release digest, then `tar -xzf ... && ./elan-init -y --default-toolchain leanprover/lean4:stable` |
| Distributed / stateful protocol invariants & thread-interleaving proofs | `Quint` / `Apalache` / `TLA+`, Rust `loom` | `cargo add --dev loom` *(in-process)*; verified `Quint`/`Apalache` GitHub release binary *(protocols)* |
| Binary-level constant-time crypto verification (`ctgrind` taint checks) | `Valgrind` (`memcheck.h`) | `sudo apt install valgrind libc6-dbg` |

---

## Verification Checklist (Record in Audit / Release Gate)

- `scripts/check-elf.sh --strict` passes on **every** production binary and
  bundled `.so` extension (plus `--require-cfi` on x86-64/AArch64 C/C++ and
  nightly `-Z build-std` Rust builds; use `--strict` without `--require-cfi` for
  stable Rust and prebuilt Python wheels), with **zero** `SANITIZER!`, `NO-PIE`,
  `partial-relro`, or `executable-stack` flags.
- CI runs `ASan + UBSan + LSan` and `TSan` / `-race` (plus `Miri` on Rust
  `unsafe`), and replays the fuzz regression corpus on every PR.
- Every untrusted parser/decoder has an active fuzz target with size/time caps
  and round-trip or differential assertions.
- Tier-1 security/invariant modules meet ≥ 90% **branch** coverage (and MC/DC on
  compound auth/policy decisions) with zero surviving critical mutants.
- Critical loops, framing parsers, fixed-point math, and stateful concurrency
  protocols carry `Lean 4` (`lake build` / `bv_decide`, zero `sorryAx`) / `Kani`
  / `CBMC --unwinding-assertions` / `Frama-C WP` / `TLA+` / `Loom` checks wired
  into CI so code drift breaks the proof gate.
