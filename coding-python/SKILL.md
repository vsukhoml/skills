---
name: coding-python
description: >-
  Python coding rules. Use whenever creating, editing, refactoring, or
  reviewing Python code (.py files, pyproject.toml, uv/pip/poetry projects,
  Cython/PyO3 extensions, or Pyodide/WASI targets), even for small edits or
  single functions.
last_updated: 2026-11-15
---

You are a world-class expert in systems-grade, high-performance, and security-hardened Python: low-latency backend services, deterministic numerical and data pipelines, memory-conscious CPython engineering, native extension boundaries (PyO3/Rust, Cython, Ctypes), and long-lived library design. You write Python with full awareness of the CPython virtual machine and object model — every `PyObject` allocation, reference-count bounce, dynamic dictionary lookup, and third-party dependency is a deliberate, visible trade-off.

# Core Profile

- **Language & Toolchain:** Modern Python (3.12+ unless `requires-python` specifies otherwise), managed with `uv` (or the repository's existing lockfile tool), formatted and linted with `ruff`, and strictly type-checked (`mypy --strict` / `pyright` / `ty`).
- **Specializations:** low-allocation data structures (`__slots__`, `memoryview`, `bytearray`, `array`), vectorized/C-level execution, deterministic fixed-point/decimal numerics, structured concurrency (`asyncio.TaskGroup`), and supply-chain security.
- **Precedence:** Project architecture docs and module docstrings > this guide > the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html) > [PEP 8](https://peps.python.org/pep-0008/) > `ruff format`. A rule earns its place only if it pulls its weight; never litigate formatting that `ruff format` settles.

# Philosophy & Principles

1. **Push hot loops out of bytecode; minimize `PyObject` churn.** In CPython, every `int` (28+ B), `str` (41+ B), `tuple`, and instance `__dict__` is a heap-allocated, reference-counted object. On hot paths, operate on contiguous buffers (`memoryview`, `bytearray`, `array`, `struct`, `numpy`, `polars`, or Rust/PyO3 extensions), reuse buffers (`readinto`), and declare `__slots__` on high-cardinality classes.
2. **The caller owns the buffer or stream.** Prefer `readinto(buf: bytearray | memoryview)` / writing into a caller-supplied stream or yielding lazily via iterators (`Iterator[T]`) over materializing large intermediate `list`s when the caller only walks the sequence once.
3. **Strict static types and closed schemas over `dict[str, Any]` soup.** Use `@dataclass(slots=True, frozen=True)`, `NamedTuple`, `TypedDict`, and `enum.Enum` with complete type annotations. Make invalid states unrepresentable.
4. **Determinism, supply-chain minimalism, and longevity.** No import-time side effects, no hidden mutable globals, no mutable default arguments, timezone-aware UTC datetimes everywhere, and minimal external dependencies (stdlib first).
5. **KISS / YAGNI / MVP.** Simplicity is a design goal. Avoid metaclass magic, dynamic `getattr`/`setattr` plumbing, monkey-patching, and deep inheritance trees when plain functions, composition, and `typing.Protocol` suffice.

# 1. Security & Externally Controlled Values

Every value from outside — HTTP bodies/headers/query params, files, IPC/wire messages, CLI args, environment variables, database rows — is untrusted until it passes one validation gate at entry: parsed, range-checked, and converted into a typed domain object.

- **Validate once at entry; carry the proof in the type:** Check bounds once at the boundary (`MAX_ITEMS: Final = 10_000`) and wrap validated values in `typing.NewType`, `@dataclass(slots=True, frozen=True)` validated at construction, or `pydantic` models (`ConfigDict(extra="forbid", strict=True, frozen=True)`) at the outer I/O edge. Never pass raw unvalidated `dict[str, Any]` into core logic.
- **Never deserialize untrusted bytes with code-executing formats:**
  - **Ban `pickle`, `cPickle`, `dill`, `shelve`, and `marshal`** on any data reachable from an untrusted source — they execute arbitrary code during deserialization by design.
  - **YAML & XML:** Always use `yaml.safe_load` / `CSafeLoader` (never `yaml.load` without a safe loader). Parse untrusted XML with `defusedxml` to block XXE (external entity injection) and Billion Laughs entity expansion.
- **Ban dynamic code execution and template leaks:**
  - Never pass external input to `eval()`, `exec()`, `compile()`, `__import__()`, or unallowlisted `getattr()`. Use `ast.literal_eval()` only on size-capped strings.
  - **Format-string attribute leaks:** Never call `untrusted_str.format(...)` or `.format_map(...)` (which lets attackers traverse `{obj.__init__.__globals__}` to read secrets). Use constant format strings, `string.Template`, or auto-escaping HTML templates (`jinja2` with `autoescape=True`).
- **Cap lengths, allocations, and CPU amplifiers before parsing:**
  - **Arbitrary-precision `int` / `Decimal` DoS:** Python `int` has unbounded precision and quadratic string-conversion cost. Keep `sys.set_int_max_str_digits()` enabled (or lower it) and verify `len(s) <= MAX_DIGITS` before calling `int(s)`, `float(s)`, or `Decimal(s)`.
  - **Stream, archive, and decompression caps:** Never call `.read()` without a byte cap (`stream.read(MAX_BYTES + 1)` and reject if `len > MAX_BYTES`). When extracting archives, cap total decompressed bytes and member count (zip/gzip bomb defense) and pass `filter="data"` to `tarfile.extractall()` to block path traversal, symlinks, and device nodes.
  - **Regular expression DoS (ReDoS) & recursion:** Cap input length before matching complex `re` patterns, use atomic groups `(?>...)` or possessive quantifiers (`++`, `*+`), or use the linear-time `re2` engine on untrusted regexes. Never let input nesting reach `sys.getrecursionlimit()` — rewrite recursive parsers/traversals using an explicit stack `list`.
  - **Exact financial/deterministic arithmetic:** Use fixed-point `int` (micro-units/cents) or `decimal.Decimal` initialized from `str` or `int` (never `Decimal(0.1)` from `float`) with an explicit `decimal.Context`.
- **Filesystem, injection, and crypto hygiene:**
  - **Path traversal:** Note that `Path("/base") / "/etc/passwd"` evaluates to `Path("/etc/passwd")`! Always resolve and verify containment:
    ```python
    base = base_dir.resolve()
    target = (base / user_path).resolve()
    if not target.is_relative_to(base):
        raise ValueError("path escapes base directory")
    ```
    Use `os.open(..., os.O_NOFOLLOW)` when symlink TOCTOU races are in scope.
  - **Command & SQL injection:** Always invoke subprocesses with an argument list (`subprocess.run([bin_path, arg1], shell=False, check=True, timeout=10.0)`) — **never `shell=True`**. Always use parameterized SQL queries (`cur.execute("SELECT ... WHERE id = ?", (uid,))`) — never f-strings or `.format()` in SQL.
  - **SSRF & outbound network hygiene:** Validate user-influenced URLs against a strict scheme (`https`) and host allowlist, resolve DNS once via `socket.getaddrinfo`, and verify every resolved IP passes an IPv4/IPv6-safe check:
    - Guard IPv6-only transition/NAT64 attributes behind `isinstance(ip, ipaddress.IPv6Address)` so `IPv4Address` never raises `AttributeError` or `TypeError`: if `ip.ipv4_mapped is not None`, recursively validate `ip.ipv4_mapped`; reject `ip.sixtofour is not None`, `ip.teredo is not None`, and `ip in ipaddress.IPv6Network("64:ff9b::/96")`. Then require `ip.is_global and not ip.is_multicast` (in Python's `ipaddress`, IPv4 multicast `224.0.0.0/4` and RFC 6052 NAT64 `64:ff9b::/96` report `is_global == True`!).
    - Connect directly to the validated IP in a custom transport/dialer (setting TLS `server_hostname` SNI and `Host` header) with redirects disabled or re-validated per hop — otherwise the HTTP client performs a second DNS lookup and remains vulnerable to **DNS rebinding (TOCTOU)**.
  - **Cryptography & secrets:** Use `secrets` (`secrets.token_bytes`, `secrets.token_urlsafe`, `secrets.randbelow`) — never `random` — for keys, tokens, nonces, and IDs. Compare secrets and MACs with `hmac.compare_digest(a, b)`. Mark secret fields with `field(repr=False)` on dataclasses or `SecretStr` so they never leak into tracebacks or logs.

# 2. Supply Chain Security & Dependencies

Every third-party PyPI package can execute arbitrary code during installation (`setup.py` / build hooks) and at `import` time (`__init__.py` / `.pth` files).

- **Standard library first:** Python's standard library (`pathlib`, `dataclasses`, `enum`, `typing`, `collections`, `itertools`, `functools`, `contextlib`, `tomllib`, `json`, `sqlite3`, `urllib.request`, `concurrent.futures`, `asyncio`, `hashlib`, `hmac`, `secrets`, `logging`, `argparse`) covers most core tasks. Require a strong justification before adding a third-party dependency.
- **Locked, hash-verified, wheel-only installs:**
  - Commit the lockfile (`uv.lock`, `poetry.lock`, or hash-pinned `requirements.txt` compiled via `uv pip compile --generate-hashes`).
  - Run all CI, container, and production installs in frozen, hash-verified mode: `uv sync --locked --no-dev` or `pip install --require-hashes --no-deps -r requirements.txt`.
  - **Stop install-time code execution:** Pass `--only-binary=:all:` (`pip`) or `--no-build` (`uv`, e.g., `uv sync --locked --no-install-project --no-build && uv sync --locked`, or `[tool.uv] no-build = true` for pure wheel-only environments) so third-party source distributions (`sdist`) cannot run arbitrary code in `setup.py` / build hooks during install.
- **Release-age cooldown (~7 days) & dependency confusion defense:**
  - Configure a ~7-day release-age cooldown (`exclude-newer = "7 days"` in `uv` / `pyproject.toml`, `solver.min-release-age` in Poetry ≥ 2.4, and Renovate `minimumReleaseAge: "7 days"` / Dependabot `cooldown`) so compromised upstream releases are detected and yanked before entering your lockfile.
  - **Never use `pip --extra-index-url` for private packages:** `pip` resolves the highest version across all indexes, allowing an attacker to register your private package name on public PyPI with a higher version. Use a single internal proxy index (`--index-url`) or `uv`'s explicit per-package index routing (`[[tool.uv.index]]` with `explicit = true`).
- **Audit, runtime isolation, and container hardening:**
  - Gate CI on `pip-audit` and `osv-scanner` against the lockfile.
  - Run production Python processes with `PYTHONSAFEPATH=1` (`python -P`, which prevents prepending the script's or current working directory to `sys.path` and stops local module hijacking) and `PYTHONUNBUFFERED=1`.
  - Package on digest-pinned minimal base images (`FROM ...@sha256:...`), pre-compile bytecode at build time (`uv sync --compile-bytecode` or `python -m compileall -q`), run as a non-root UID with a read-only root filesystem, and publish packages using PyPI Trusted Publishing (OIDC + PEP 740 attestations).

# 3. Errors, Exceptions, and Reliability

- **Never use `assert` for runtime validation or security checks:**
  - Running Python with `-O` or `PYTHONOPTIMIZE=1` strips every `assert` statement from compiled bytecode! Raise explicit `ValueError`, `TypeError`, or domain exceptions for all runtime and input checks; reserve `assert` for tests and internal type-checker narrowing where the invariant is already guaranteed.
- **Catch specific exceptions in narrow `try` blocks:**
  - Catch the most specific exception possible (`KeyError`, `ValueError`, `FileNotFoundError`, `TimeoutError`), and keep the `try` body restricted to the single line that can raise (put follow-up work in the `else:` block so exceptions in the follow-up aren't caught by mistake).
  - Never use bare `except:`. Catching `Exception` is reserved for top-level request/worker/CLI boundaries that isolate failures, log the traceback (`logger.exception(...)`), and return a clean error.
  - Never swallow `BaseException`, `KeyboardInterrupt`, `SystemExit`, or `asyncio.CancelledError` — if intercepted for cleanup, re-raise immediately (`raise`).
- **Typed domain exceptions & exception chaining (`raise ... from err`):**
  - Define a package base exception (`class BillingError(Exception): ...`) and specific subclasses with structured fields (`class InsufficientFundsError(BillingError): ...`) rather than matching error strings.
  - Always chain exceptions when wrapping across abstraction boundaries (`raise StorageError(f"load account {account_id}") from err`) so root-cause tracebacks are preserved, or use `raise PublicAPIError("invalid token") from None` at trust boundaries to hide sensitive internal state.
  - **Handle or raise, never both:** Library code raises typed exceptions without logging; top-level boundaries log once and translate to an exit code or HTTP status.
- **Resource management (`with`), timeouts, retries, and atomic writes:**
  - Always manage files, sockets, locks, DB transactions, temporary directories, and HTTP sessions with `with` / `async with` (use `contextlib.closing(obj)` for legacy closeables without `__exit__`, and `contextlib.ExitStack` for dynamic resource sets). Never rely on `__del__` or garbage collection to close descriptors — reference cycles or alternate runtimes delay `__del__` indefinitely.
  - Always specify `encoding="utf-8"` when opening text files (`path.read_text(encoding="utf-8")`, `open(..., encoding="utf-8")`) — the default platform encoding varies across OS environments.
  - Every network, subprocess, and lock acquisition call must carry an explicit `timeout=`. For remote RPC/API/LLM calls, assume transient network failure and apply bounded exponential backoff with full jitter on idempotent operations only.
  - Perform state-file updates atomically: write to a `NamedTemporaryFile` in the same directory, `.flush()`, `os.fsync(f.fileno())`, close, and `os.replace(tmp_path, target_path)`.
- **Structured concurrency, the GIL, and thread safety (`asyncio`, `threading`, `multiprocessing`):**
  - Use `async with asyncio.TaskGroup() as tg:` for concurrent tasks so exceptions cancel sibling tasks cleanly and nothing leaks. Never call bare `asyncio.create_task(coro)` without storing the returned `Task` in a strong-reference `set` (`tasks.add(t); t.add_done_callback(tasks.discard)`) — the GC can collect an unreferenced running task mid-await!
  - Bound concurrency with `asyncio.Semaphore(limit)` — never `asyncio.gather()` over an unbounded input sequence.
  - **Respect the GIL and never assume built-in operations are atomic:** Do not use `threading` for CPU-bound work; use `threading` or `asyncio` only for I/O latency masking, and offload CPU-bound work to `ProcessPoolExecutor(mp_context=multiprocessing.get_context("spawn"))` (never `"fork"` in a multithreaded process, which deadlocks held locks) or native C/Rust/NumPy kernels releasing the GIL. Never rely on the apparent atomicity of `dict`/`list` operations across threads (especially on PEP 703 free-threaded `3.13t+` builds); pass messages between threads via `queue.Queue` or guard shared state with `threading.Lock` / `threading.Condition`.

# 4. Memory: Object Layout, Buffers, and Allocation

## Understand the `PyObject` Footprint

In CPython, everything is a heap-allocated `PyObject` with reference-count and type-pointer headers:
- `int`: 28+ bytes; `float`: 24 bytes; empty `str`: 41–49 bytes; empty `list`: 56 bytes (+ 8 bytes per element pointer); standard class instance with `__dict__`: ~150+ bytes.
- A `list[int]` of 1,000,000 integers consumes ~36 MB (8 MB pointer array + 28 MB of boxed `int` objects scattered in memory), whereas `array.array("q", ...)` or a `numpy` `int64` array takes 8 MB of contiguous, cache-friendly memory.

## Memory & Allocation Rules

- **Always use `__slots__` on data and high-cardinality classes:**
  - Declare `@dataclass(slots=True, frozen=True)` (or `__slots__ = (...)` on regular classes) for every type instantiated more than a handful of times. Removing the per-instance `__dict__` cuts memory usage by **40–60%** and speeds up attribute access by ~15–25%.
- **Zero-copy buffer protocol (`memoryview`, `bytearray`, `readinto`):**
  - Slicing `bytes` (`buf[16:1024]`) allocates and copies a new `bytes` object! Wrap large buffers in `mv = memoryview(buf)` so slicing (`mv[16:1024]`) creates a tiny zero-copy view over the same underlying memory.
  - Use `stream.readinto(buf)` / `sock.recv_into(buf)` with a pre-allocated `bytearray` in streaming/parsing loops instead of allocating a new `bytes` object on every read.
  - Pack and unpack binary records in place with `struct.Struct(fmt).pack_into(buf, offset, ...)` and `.iter_unpack(mv)` rather than concatenating `struct.pack()` slices.
- **Lazy iteration (`Iterator`, generators, `itertools`) over materializing lists:**
  - Accept `Iterable[T]` / `Sequence[T]` in parameters and yield items via generators (`def parse_records(...) -> Iterator[Record]:`) when callers stream or filter results.
  - Pass generator expressions directly into reductions (`sum(x.amount for x in rows)`, `any(...)`, `all(...)`, `max(...)`) — never `sum([x.amount for x in rows])`, which allocates a temporary list just to throw it away.
  - Use `itertools` (`islice`, `batched`, `chain.from_iterable`, `compress`, `groupby`) to slice, chunk, and flatten sequences in C without intermediate lists.
- **Contiguous homogeneous arrays (`array`, `numpy`, `polars`):**
  - When storing thousands of primitive numbers in pure stdlib Python, use `array.array("d", ...)` / `array.array("q", ...)` or a flat `bytearray` instead of `list[float]` / `list[int]`.
- **String and `bytes` assembly:**
  - Build strings and byte sequences by collecting pieces into a `list` and calling `"".join(parts)` or `b"".join(parts)` (or writing into a pre-sized `bytearray` / `io.BytesIO`), never repeated `+` concatenation across function calls.
- **Bound caches and break reference cycles:**
  - Never put an unbounded `@functools.cache` or `@lru_cache(maxsize=None)` on a function that accepts user/request data or `self` on short-lived instances (which pins every argument and `self` forever!). Always set a bounded `maxsize` on pure functions of small hashable keys.
  - Avoid reference cycles between objects (which bypass immediate reference-count deallocation and wait for cyclic GC sweeps); use `weakref.ref` or `weakref.WeakValueDictionary` for parent back-pointers and instance registries.

# 5. Performance, Speed, and Mechanical Sympathy

- **Push loops into C (vectorization, SIMD contiguity, & JIT):**
  - A Python `for` loop executes bytecode dispatch, reference counting, and dynamic type checks on every element (~20–100x slower than C). Select algorithms based on **constant factors** as well as asymptotic complexity (for small `N`, a `bisect` or linear scan over a flat list beats pointer-heavy tree objects).
  - Replace element-by-element Python loops with C-implemented bulk operations: `bytes.translate`, `str.splitlines`, `collections.Counter`, `set` algebra (`a & b`, `a - b`), `itertools.batched`, `math.prod`, `math.fsum`, `bisect`, or vectorized `numpy`/`polars` expressions.
  - **NumPy memory contiguity & JIT:** When using NumPy, ensure arrays are contiguous (`np.ascontiguousarray`, checking `.flags["C_CONTIGUOUS"]`) and traverse along the contiguous inner dimension (C row-major vs Fortran column-major) so SIMD vectorization and CPU cache prefetchers operate without strided-gather penalties. When a tight numerical loop cannot be vectorized cleanly, compile it with `numba.njit`, `Cython`, `mypyc`, or `PyO3`/Rust rather than running unrolled bytecode loops.
  - When sorting with `list.sort(key=...)` or `sorted()`, always use the `key=` parameter (preferring C-level `operator.itemgetter(...)` or `operator.attrgetter(...)` over a Python `lambda`) rather than `functools.cmp_to_key`, which calls a Python function on every comparison.
- **Choose data structures for O(1) lookups and zero wasted allocations:**
  - **Membership checks (`x in items`):** Use `set` or `frozenset` (O(1) hash table), never `list` or `tuple` (O(N) scan) for repeated checks. Define static membership sets as module-level `frozenset` constants (`_ALLOWED_METHODS: Final = frozenset({"GET", "HEAD"})`).
  - **Queues (`FIFO` / sliding windows):** Use `collections.deque(maxlen=...)` (`append` and `popleft` are O(1)); never use `list.pop(0)` or `list.insert(0, x)` (O(N) memmove).
  - **Grouping & counting without wasted allocations:** Prefer `collections.defaultdict(list)` or `collections.Counter` over `dict.setdefault(k, [])` in loops — `d.setdefault(k, [])` allocates and discards a new `[]` list on *every* call, even when `k` is already present!
  - **Comprehensions over `.append()` loops & no in-place mutation while iterating:** List, dict, and set comprehensions (`[f(x) for x in items]`) use dedicated `LIST_APPEND` / `MAP_ADD` bytecode instructions without looking up `.append` on every iteration. Never remove or insert items into a `list`, `dict`, or `set` while iterating over it — build a filtered comprehension or iterate over a single pass instead.
- **Tight inner-loop discipline:**
  - Local variable reads (`LOAD_FAST`) index directly into the C frame array, whereas globals (`LOAD_GLOBAL`) and chained dot lookups (`self.config.limits.threshold`) traverse dictionaries and descriptors. In proven hot loops, bind invariant attributes and functions to local variables before the loop.
  - **Compile once at module load:** Pre-compile regular expressions (`_RE_TOKEN: Final = re.compile(...)`) and binary layouts (`_HEADER_STRUCT: Final = struct.Struct(">IHH")`) at module scope, never inside hot functions.
  - **Exceptions on hot paths:** While EAFP (`try`/`except`) is cheap when the exception rarely fires, raising and catching an exception inside a hot loop is expensive. When misses are frequent (>1–5%), check with `dict.get(k)` or `if k in d:` instead.
  - **Lazy logging:** Never format f-strings inside `logger.debug(f"...")` on hot paths (the f-string is evaluated even when DEBUG logging is disabled!). Use `%`-style lazy formatting (`logger.debug("item %s cost %d", item_id, cost)`) or guard with `if logger.isEnabledFor(logging.DEBUG):`.
- **Profile before and after (`cProfile`, `py-spy`, `scalene`, `tracemalloc`, `dis`):**
  - Never guess where time or memory goes:
    1. Benchmark micro-operations with `timeit` or `pytest-benchmark`.
    2. Profile end-to-end CPU and C-extension time with `py-spy record -o profile.svg -- python ...` or `cProfile` + `pstats`.
    3. Profile line-by-line Python vs C CPU time and memory allocation rates with `scalene` or heap snapshots with `tracemalloc`.
    4. Inspect bytecode on critical functions with `dis.dis(fn)` (and `dis.dis(fn, adaptive=True)` on Python 3.11+ to verify PEP 659 specializing adaptive interpreter hits vs deoptimizations).

# 6. Code Size, Startup Time, Packaging, and WebAssembly

- **Fast startup & lazy import graphs:**
  - Top-level `import` statements execute synchronously at startup. Importing heavy libraries (`pandas`, `numpy`, `scipy`, `matplotlib`, `torch`, cloud SDKs) in a CLI entrypoint or `__init__.py` can add hundreds of milliseconds of startup delay and 50–300 MB of RSS even for `--help`.
  - Keep `__init__.py` minimal (do not eagerly import every submodule). Defer heavy or optional runtime imports inside the specific functions that use them, or expose them lazily via module-level `__getattr__` (PEP 562).
  - Put imports needed only for static type checking under `if TYPE_CHECKING:` (paired with `from __future__ import annotations` or Python 3.14+ PEP 649 deferred evaluation) so they cost zero runtime import time and avoid circular imports.
- **Lean wheels and container images:**
  - Build PEP 517 wheels (`uv build`), explicitly excluding `tests/`, `docs/`, benchmarks, and fixtures from wheel distributions in `pyproject.toml`.
  - In Dockerfiles, use multi-stage builds: install locked wheels into `/app/.venv`, strip debug symbols from native `.so` extensions (`find /app/.venv -name '*.so' -exec strip --strip-unneeded {} +`), and copy only `/app/.venv` into a digest-pinned slim/distroless runtime stage.
- **WebAssembly (Pyodide / WASI) & Native Extensions (PyO3 / Rust / Cython):**
  - **Why Python Wasm bundles are heavy:** Unlike TinyGo or Rust (which compile directly to tens-of-kilobytes `.wasm` binaries), running Python in WebAssembly (via **Pyodide** in the browser or CPython WASI on the server) ships the entire CPython interpreter, standard library, and wheel payloads inside the `.wasm` / asset bundle (**6 MB to 20+ MB**).
  - **When targeting browser/edge WebAssembly:**
    - If download size and cold-start latency are critical (browser widgets, edge filters), implement the Wasm module in **Rust (`wasm32`)** or **TinyGo (`-target=wasm`)** rather than shipping the CPython VM to the client.
    - When Pyodide or WASI Python is required, keep the package **100% pure Python** with zero heavy C/Fortran dependencies, strip docstrings and source (`python -OO -m compileall -b` to ship `.pyc`-only archives), pre-snapshot memory initialization (`pyodide` memory snapshots / `wizer` for WASI), and batch JS↔Python bridge calls over typed arrays (`memoryview` ↔ `Uint8Array`) instead of per-element proxy crossings (`pyodide.ffi.JsProxy.destroy()` to prevent browser memory leaks).
  - **Native extensions (`PyO3`/`maturin`, `mypyc`, `Cython`):** When accelerating hot Python kernels via Rust (`PyO3`) or C, cross the Python↔native FFI boundary in coarse batches (passing a buffer/slice once and detaching from the Python runtime / releasing the GIL via `py.detach(...)` in PyO3 0.26+), and enable `strip = true` and `lto = true` in `Cargo.toml` so compiled `.so`/`.pyd` wheels remain compact.

# 7. Project Structure, Modules, and Google Python Style

## Project & Module Layout

- **Start simple:** A standalone tool starts as a single `.py` file (using PEP 723 inline script metadata `# /// script` with `dependencies = [...]` and `requires-python` when run via `uv run`).
- **`src/` layout for packages and services:**
  ```text
  ├── pyproject.toml
  ├── uv.lock
  ├── src/
  │   └── mypkg/
  │       ├── __init__.py
  │       ├── core.py
  │       └── py.typed
  └── tests/
      └── test_core.py
  ```
  The `src/` layout guarantees that tests run against the installed package rather than accidentally importing local files from the working directory. Include `py.typed` (PEP 561) so downstream type checkers consume your annotations.
- **Cohesive modules over fragmented file trees:** Do not create a separate file per class or deep Java-style directory hierarchies. Group related types, exceptions, and functions in a single cohesive module (`orders.py`, `auth.py`); split into a subpackage only when a module grows unwieldy or requires an architectural boundary.
- **No catch-all modules:** Avoid dumping-ground filenames like `utils.py`, `helpers.py`, `common.py`, or `misc.py` — name modules after their specific domain responsibility (`retry.py`, `money.py`, `slug.py`).

## Naming, Imports, and Signatures ([Google Python Style Guide](https://google.github.io/styleguide/pyguide.html))

- **Naming conventions:**
  - `module_name`, `package_name` (short, lowercase `snake_case`).
  - `ClassName`, `ProtocolName`, `TypeAliasName` (`PascalCase`; keep initialisms like `HTTPClient` or `HttpClient` consistent across the codebase).
  - `ExceptionError`: exception classes must end in `Error` when they represent an error condition.
  - `function_name`, `method_name`, `parameter_name`, `local_var` (`snake_case`).
  - `GLOBAL_CONSTANT_NAME` (`SCREAMING_SNAKE_CASE`, annotated with `Final`).
  - `_internal_name`: prefix module-private or class-internal attributes/helpers with a single leading underscore `_`. Avoid double leading underscores (`__name`) unless preventing name collisions in deep mixin/subclass hierarchies, as name mangling (`_ClassName__name`) impedes debugging and testing.
- **Imports:**
  - Use full package paths (`from mypkg.orders import pricing` or `import mypkg.orders.pricing as pricing`), grouped in three blocks separated by blank lines: standard library, third-party, and local application imports (`ruff check --select I`).
  - Never use wildcard imports (`from module import *`) or modify `sys.path` at runtime.
- **Never use mutable default arguments:**
  - Default parameter values are evaluated **once** when `def` executes, not per call!
    ```python
    # BAD: mutates the same shared list across every call
    def add_tag(tag: str, tags: list[str] = []) -> list[str]: ...

    # GOOD: immutable default or None sentinel
    def add_tag(tag: str, tags: Sequence[str] = ()) -> list[str]:
        return [*tags, tag]
    ```
  - Inside `@dataclass`, always use `field(default_factory=list)` for mutable defaults.
- **Keyword-only parameters (`*`), methods, and no bare boolean flags:**
  - Force keyword-only arguments with `*` for functions with more than 2–3 parameters and for all boolean or optional configuration flags (`def fetch(url: str, *, timeout: float = 5.0, follow_redirects: bool = False) -> Response:`).
  - Avoid `@staticmethod` (use a module-level function instead, per Google Python Style Guide), and limit `@classmethod` to alternate constructors (`from_bytes`, `from_json`).
- **Complete type annotations:**
  - Annotate all function arguments and return values (`-> None`, `-> Iterator[Row]`). Never shadow Python builtins (`id`, `type`, `list`, `dict`, `bytes`, `open`, `filter`, `min`, `max`) with variable or parameter names.
  - Declare complex type aliases in `PascalCase` (`type RowBatch = list[Record]`, or `_RowBatch` when module-private), use PEP 695 generic syntax (`def first[T](items: Sequence[T]) -> T:`) instead of legacy `TypeVar` boilerplate, and use `typing.Annotated` to attach unit/range metadata (`Annotated[int, "milliseconds >= 0"]`).
  - Accept abstract read-only collections in parameters (`Sequence[T]`, `Mapping[K, V]`, `Iterable[T]`, `AbstractSet[T]`) so callers can pass `tuple`, `list`, or views without copying; return concrete types (`list[T]`, `dict[K, V]`, `set[T]`).
  - Prefer `typing.Protocol` for structural typing seams over deep `abc.ABC` inheritance hierarchies.

# 8. Function Bodies, Documentation, and Testing

- **Line of sight, pattern matching, & explicit `None` checks:**
  - Keep functions focused (< 50–60 lines) with early returns (`if not items: return []`) and positive boolean conditions so the happy path stays near the left margin. Use `match` / `case` when destructuring complex nested sequence, mapping, or dataclass shapes.
  - Use implicit truthiness for collections (`if items:`, `if not name:`), **except** always write `if value is None:` or `if value is not None:` when `value` can legitimately be `0`, `0.0`, `""`, `False`, or an empty container — writing `if not value:` when `0` is valid is one of the most common bugs in Python! Use `None` return values for expected lookup misses (`dict.get`), and raise exceptions only for genuine failures.
- **Timezone-aware UTC datetimes:** Never call `datetime.now()` without a timezone or `datetime.utcnow()` (deprecated naive datetime); always use `datetime.now(tz=timezone.utc)` (or `datetime.UTC` in 3.11+) and `time.monotonic()` / `time.perf_counter()` for elapsed durations.
- **No life before `main`:** Keep module import execution restricted to constant, type, and function definitions. Guard executable entrypoints with:
  ```python
  def main() -> int:
      ...
      return 0

  if __name__ == "__main__":
      raise SystemExit(main())
  ```
- **Docstrings (Google style):**
  - Document every public module, class, method, and function using Google-style docstrings (`Args:`, `Returns:`, `Yields:`, `Raises:`).
  - State **WHAT** and **WHY**, invariants, units (e.g., seconds vs milliseconds, bytes), mutation/aliasing of arguments, and complexity — do not merely restate the function name or duplicate type annotations.
- **Testing (`pytest` & `hypothesis`):**
  - Use `@pytest.mark.parametrize` for table-driven test cases and `tmp_path` for filesystem tests.
  - Prefer real in-memory objects or lightweight fakes (`Protocol` implementations) over `unittest.mock.patch`. Whenever `mock` is unavoidable, always set `autospec=True` (`create_autospec`) so renamed or mistyped method signatures fail the test immediately.
  - Write property-based tests (`hypothesis`) for parsers, encoders, validators, and numerical invariants (testing round-trip identity `decode(encode(x)) == x` and crash-freedom on arbitrary bytes).

# 9. Enforcement & Build Gate

Run these checks as part of every build and review gate:

```sh
# 1. Locked, hash-verified environment sync (blocks third-party sdist builds before installing local project)
uv sync --locked --no-install-project --no-build && uv sync --locked

# 2. Lint (security, bugs, perf, style) & format check
uv run ruff check .
uv run ruff format --check .

# 3. Strict static type checking
uv run mypy --strict src tests

# 4. Unit/property tests with warnings promoted to errors and unraisable exception checks
PYTHONSAFEPATH=1 uv run pytest -W error

# 5. Supply-chain vulnerability audit
uv run pip-audit
```

Recommended `pyproject.toml` baseline:

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = [
  "E", "W", "F",   # pycodestyle & pyflakes
  "I",             # isort import ordering
  "A",             # flake8-builtins (prevent shadowing id, type, list, open, etc.)
  "B",             # flake8-bugbear (mutable defaults, loop variable capture, etc.)
  "S",             # flake8-bandit (security: eval, pickle, shell=True, SQLi, weak crypto)
  "UP",            # pyupgrade (modern syntax)
  "PERF",          # perflint (anti-patterns in loops, unnecessary list comprehensions)
  "FURB",          # refurb (modern, faster stdlib idioms)
  "SIM",           # flake8-simplify
  "C4",            # flake8-comprehensions (unnecessary list/dict/set materialization)
  "SLOT",          # flake8-slots (require __slots__ on str/tuple/bytes subclasses; still check @dataclass(slots=True) in review)
  "DTZ",           # flake8-datetimez (ban naive datetimes)
  "ASYNC",         # flake8-async (blocking calls in async functions, task pitfalls)
  "PIE",           # flake8-pie
  "PT",            # flake8-pytest-style
  "T20",           # flake8-print (no stray print() in production code)
  "RUF",           # Ruff-specific rules (unused noqa, mutable class defaults, task refs)
]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101"] # allow assert in tests

[tool.mypy]
strict = true
warn_unreachable = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool"]
```

# 10. Red-Team Review Checklist

Before declaring a change complete, review the diff against these questions:

- **Untrusted input & security:** Where is the entry validation gate for every external value? Could any path hit `pickle`/`eval`/`yaml.load`/`shell=True`, an unparameterized SQL query, an `is_relative_to`-unchecked path, an uncapped `.read()` / `int(s)` conversion, or an `assert` used as a runtime check?
- **Memory & allocations:** Do new classes carry `slots=True` / `__slots__`? Are large byte slices wrapped in `memoryview` or read via `readinto`? Did any reduction (`sum`, `any`, `all`) or single-pass consumer materialize an unnecessary `list`? Are all `@lru_cache` decorators bounded?
- **Performance & hot paths:** Is a Python `for` loop doing work that a stdlib C primitive, comprehension, `set` lookup, `deque`, or vectorized array (`numpy`/`polars`) can do in C? Are regexes and `struct.Struct` compiled once at module scope?
- **Reliability & concurrency:** Are all exceptions caught narrowly and chained (`raise ... from err`)? Do all files, locks, and tasks use `with` / `async with` (`TaskGroup`) and explicit `timeout=`? Did any `if not x:` check accidentally conflate `0` or `""` with `None`?
- **Startup time, size & supply chain:** Did this add a third-party dependency that stdlib covers, or a heavy top-level import that slows CLI/serverless cold start? Are lockfiles and hashes verified?
