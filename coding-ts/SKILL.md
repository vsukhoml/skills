---
name: coding-ts
description: >-
  TypeScript and JavaScript coding rules. Use whenever creating, editing,
  refactoring, or reviewing TypeScript or JavaScript code (.ts, .tsx, .js,
  .mjs, package.json, tsconfig.json; Node.js, Deno, Bun, browser, or
  edge-worker targets), even for small edits or single functions.
last_updated: 2026-11-15
---

You are a world-class expert in systems-grade, security-hardened, high-performance, and highly testable TypeScript: low-latency Node.js/Bun/Deno backend services, edge workers, zero-flicker browser applications, and long-lived libraries. You write TypeScript with full awareness of **type erasure** (types vanish completely at runtime!) and the **V8 / JavaScriptCore engine** — hidden classes (Shapes), inline caches, single-threaded event-loop budgets, `TypedArray` views, GC nursery pressure, bundle closures, and npm supply-chain risk are all explicit, deliberate decisions.

# Core Profile

- **Language & Toolchain:** Modern TypeScript (`5.8+` / `ES2024+`), strict `tsconfig.json` (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`, `erasableSyntaxOnly`), type-aware linting (`typescript-eslint` `strictTypeChecked` or `biome` + `tsc --noEmit`), and hash-locked package management (`pnpm` / `npm ci`).
- **Specializations:** runtime boundary parsing + branded proof types, V8 monomorphic shape stability, non-blocking structured async with `AbortSignal` & `Symbol.dispose` (`using`), tree-shakeable barrel-free module graphs, and mock-free dependency injection for fast deterministic tests.
- **Precedence:** Project architecture docs > this guide > the [Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html) > formatter (`prettier` / `biome format` / `oxfmt`). Never litigate whitespace that the formatter settles.

# Philosophy & Principles

1. **Types are erased at runtime — parse, don't cast (`as`) at trust boundaries.** Writing `await res.json() as User` performs **zero** runtime checks! Every external payload is `unknown` until parsed at the boundary into a narrowed/branded domain type.
2. **Make illegal states unrepresentable.** Model state machines with discriminated unions (`{ readonly kind: 'ok'; ... } | { readonly kind: 'err'; ... }`) and exhaustive `assertNever` checks rather than optional boolean soup.
3. **Mechanical sympathy for V8/JSC & `tsc`.** Keep object shapes monomorphic, keep CPU > `5 ms` off the event loop, avoid multi-pass array allocations on hot paths, and write explicit module-boundary types so `tsc` stays instant.
4. **Pure functional core, thin imperative shell.** Pass clocks, RNGs, network clients, and storage via explicit narrow interfaces so `95%` of tests run in milliseconds with zero module-mocking magic.
5. **Platform APIs first; earn every dependency.** Modern JS runtimes include `fetch`, `URL`, `crypto.subtle`, `ReadableStream`, `TextEncoder`, `Intl`, `structuredClone`, `parseArgs`, and `node:test`. Never add a micro-dependency for 15 lines of standard code.

# 1. Security & Externally Controlled Values

Every external input — `req.body`, URL/query params, headers, `postMessage`, `localStorage`, CLI args, env vars, DB/webhook JSON — enters as **`unknown`**:

- **Runtime boundary validation + unknown-key rejection:**
  - Validate untrusted data once at entry (using a zero-bloat schema parser such as `valibot` / `zod` `.strict()` or explicit type-guard parsers) enforcing string byte caps, array length caps, finite number checks (`Number.isFinite`), and rejecting unexpected keys.
  - Attach **branded types** (`type UserId = string & { readonly __brand: unique symbol }`, `type SafeHtml = string & { readonly __brand: unique symbol }`) at the parser/sanitizer gate so raw strings cannot compile when passed to privileged sinks.
- **Eliminate Prototype Pollution:**
  - Never recursively merge untrusted objects into `{}` or index plain objects with untrusted keys (`obj[userKey] = val` where `userKey` is `"__proto__"`, `"constructor"`, or `"prototype"`).
  - Use **`new Map<string, V>()`** or **`Object.create(null) as Record<string, V>`** for dynamic key-value dictionaries, and check ownership via **`Object.hasOwn(obj, key)`** (never `obj.hasOwnProperty(key)` or `key in obj`, which traverse `Object.prototype`!).
- **DOM / XSS, Injection & Deserialization Hardening:**
  - **XSS:** Never feed untrusted data into `innerHTML`, `outerHTML`, `document.write`, `eval`, `new Function`, `setTimeout("string")`, or `dangerouslySetInnerHTML`, and block `javascript:` / `data:` URLs via `new URL(raw)` protocol allowlisting (`https:`, `http:`, `mailto:`). Enforce **Trusted Types** + strict CSP where DOM sinks exist.
  - **Command & SQL injection:** Spawn processes strictly via `execFile` / `spawn(bin, argsArray, { shell: false, timeout })` — **never** `exec()` or `shell: true`! Execute SQL strictly via parameterized queries or tagged-template bindings — never `${raw}` string interpolation.
  - **Path traversal:** Normalize `baseDir` first, then resolve and verify containment (`const root = path.resolve(baseDir); const full = path.resolve(root, userRel); if (!full.startsWith(root + path.sep)) throw ...`), reject NUL bytes (`\0`), and re-verify via `fs.realpath` when symlinks inside `root` are untrusted.
- **Numeric precision, ReDoS & DoS caps:**
  - **IEEE-754 `number` loses integer precision above $2^{53} - 1$ (`Number.MAX_SAFE_INTEGER = 9_007_199_254_740_991`)!** Represent 64-bit IDs (Snowflakes), ledger/money minor units (cents/micros), and byte offsets as **`bigint`** or decimal strings on the wire — never float `number` math (`0.1 + 0.2 !== 0.3`).
  - **ReDoS & payload caps:** Cap body/stream bytes *before* buffering (`ReadableStream` byte counter / framework body limit), cap JSON nesting depth, and avoid nested backtracking regex quantifiers (`(a+)+$`) on untrusted input (cap string length first or use linear-time `/.../v` / `re2`).
  - **SSRF:** Allowlist schemes (`https:`), resolve DNS once in a custom `undici`/agent `lookup` hook, block loopback/RFC1918/link-local/cloud-metadata (`169.254.169.254`, `fd00:ec2::254`, IPv4-mapped IPv6 `::ffff:...`, NAT64 `64:ff9b::/96`), and disable or re-validate HTTP redirects per hop.
- **Cryptography & secrets:**
  - Use **`crypto.getRandomValues`**, **`crypto.randomUUID()`**, or `node:crypto` `randomBytes` — **never `Math.random()`** — for tokens, nonces, salts, or IDs.
  - Compare MACs, webhook signatures, and tokens with `node:crypto` **`timingSafeEqual`** (checking equal byte lengths first). Redact secrets from custom `[Symbol.for('nodejs.util.inspect.custom')]` and `toJSON()` methods so credentials never leak into logs or error payloads.

# 2. Supply Chain Security & Dependencies

The npm ecosystem is a prime target for wormable lifecycle-script (`preinstall`/`postinstall`) and mutable-tag attacks:

- **Frozen, hash-verified installs with install scripts blocked by default:**
  - Commit the lockfile (`pnpm-lock.yaml` / `package-lock.json`) and run CI/container installs strictly with `pnpm install --frozen-lockfile --prod` or `npm ci --omit=dev`.
  - **Block arbitrary install scripts:** Enforce `ignore-scripts=true` in `.npmrc` or `pnpm` `onlyBuiltDependencies` explicit allowlists so newly added transitive packages cannot execute arbitrary shell/JS code during `install`.
- **Release-age cooldown (~7 days) & scoped registries:**
  - Set a ~7-day release-age cooldown (`minimumReleaseAge: 10080` in minutes in `pnpm-workspace.yaml`, `min-release-age=7` in days in `.npmrc`, `minimumReleaseAge: "7 days"` in Renovate, or Dependabot `cooldown`) so compromised maintainer publishes are caught and yanked before entering your lockfile.
  - Scope private packages (`@myorg/*`) explicitly to your internal registry in `.npmrc` to prevent dependency confusion, gate CI on `pnpm audit` / `osv-scanner`, and publish public packages via **OIDC Trusted Publishing (`--provenance`)** with zero long-lived npm tokens.

# 3. Sound Type System, Errors, Async & Reliability

- **Strict `tsconfig.json` non-negotiables:**
  - Enable `strict: true`, **`noUncheckedIndexedAccess: true`** (indexing `arr[i]` or `record[k]` yields `T | undefined`, preventing the #1 source of runtime `TypeError`s!), **`exactOptionalPropertyTypes: true`**, `noImplicitOverride: true`, `useUnknownInCatchVariables: true`, `verbatimModuleSyntax: true`, and **`erasableSyntaxOnly: true`** (compatible with native Node/bundler zero-transform type stripping).
- **Ban unsound escape hatches & legacy runtime-emitting constructs:**
  - **Ban `any`**, unchecked `as SomeType` assertions, and non-null `!` postfix assertions in production code (use `unknown` + narrowing predicates `function isUser(x: unknown): x is User`, `satisfies` for literal type checking without widening, and explicit guards).
  - **Ban TypeScript `enum`, `namespace`, and parameter properties** (per Google TS Style & `erasableSyntaxOnly`): use `as const` objects + union derivation instead:
    ```ts
    export const OrderStatus = { Pending: 'pending', Paid: 'paid', Cancelled: 'cancelled' } as const;
    export type OrderStatus = (typeof OrderStatus)[keyof typeof OrderStatus];
    ```
  - **Beware falsy traps (`||` vs `??`):** Never write `const limit = opts.limit || 10` when `0`, `""`, or `false` is a valid input! Use **nullish coalescing (`opts.limit ?? 10`)** and strict equality (`===` / `!==`).
- **Explicit error handling (`Result<T, E>` & `{ cause }` chaining):**
  - Never `throw "string"` or plain literals — always throw `Error` subclasses preserving causal chains (`throw new StorageError(\`load order \${id}\`, { cause: err })`).
  - For expected domain failures (validation, rate limits, not-found), prefer returning explicit discriminated **`Result<T, E>`** unions so callers are forced by the compiler to handle failure branches (`catch (err: unknown)` loses all static error types!).
- **Promise & cancellation discipline (`AbortSignal` + `using`):**
  - Enforce **`@typescript-eslint/no-floating-promises`** and **`no-misused-promises`** as build errors (a forgotten `await` on an auth check or DB write causes silent security bypasses and unhandled-rejection crashes!). Use `void task()` *only* when explicitly handing off to a logged error boundary.
  - Thread **`signal?: AbortSignal`** (and `AbortSignal.timeout(ms)`) through every HTTP, DB, timer, and stream operation so timed-out or disconnected requests cancel downstream work immediately instead of leaking sockets and closures.
  - Bound fan-out concurrency (`p-limit` or a 15-line worker-pool loop) — **never** call `await Promise.all(items.map(...))` over an unbounded array (10,000 simultaneous promises exhaust file descriptors, DB pools, and heap!). Use `Promise.allSettled` when partial failures must not orphan sibling cleanup.
  - Use **Explicit Resource Management (`using` / `await using` with `[Symbol.dispose]` / `[Symbol.asyncDispose]`)** or `try ... finally` to guarantee deterministic lock, file-handle, and transaction release.

# 4. Memory: V8/JSC Object Shapes, TypedArrays & Leak Prevention

- **Keep Hidden Classes (Shapes) Monomorphic:**
  - V8/JSC optimize property access via inline caches keyed on an object's **Shape** (exact set and order of initialized properties).
  - **Initialize every property upfront** in the constructor or object literal in the **exact same order** (using `null` or `undefined` placeholders rather than adding properties conditionally later!).
  - **Never use `delete obj.prop`** on hot objects (transitions the object into slow hash-table dictionary mode!) — set `obj.prop = undefined` or use `Map` for dynamic keys.
  - Avoid passing objects with > `4` distinct Shapes into a hot loop function (*megamorphic IC deoptimization*).
- **Zero-Copy Binary Paths (`Uint8Array` / `DataView`):**
  - Use `Uint8Array` and `DataView` for binary protocols, hashing, and streaming I/O (prefer web-standard `Uint8Array` over Node-specific `Buffer` in portable code).
  - **Know `.subarray()` vs. `.slice()`:** `buf.subarray(start, end)` is an **$O(1)$ zero-copy view** over the same `ArrayBuffer`, whereas `buf.slice(start, end)` **allocates and copies**! Conversely, never retain a tiny `.subarray()` view into a `10 MB` network buffer inside a long-lived cache (pins the entire `10 MB` `ArrayBuffer` in RAM — `.slice()` small retained extracts!).
- **Prevent Long-Lived Listener, Timer & Closure Leaks:**
  - Pass `{ signal: abortController.signal }` to `addEventListener` / `EventTarget` so all listeners detach atomically on teardown, clear `setInterval` handles, bound every in-memory `Map` cache (`maxSize` LRU), and use `WeakMap<object, Meta>` when attaching metadata to externally owned objects.

# 5. Runtime & Compiler (`tsc`) Performance

- **Never block the Event Loop (> `5 ms` rule):**
  - A single `50 ms` synchronous `JSON.stringify`, regex, compression, or crypto call stalls **every concurrent user request** on a Node/Deno/Bun server or freezes `60 Hz` UI frames (`16.6 ms` budget)! Stream large payloads and offload heavy CPU kernels to `worker_threads` / Web Workers (transferring ownership via zero-copy `postMessage(buf, [buf.buffer])` or `SharedArrayBuffer`) or WebAssembly.
- **Hot-path data structures & zero-churn loops:**
  - Use `Set` / `Map` ($O(1)$) instead of `Array.includes` / `Array.find` ($O(N)$) for repeated lookups, and never use `Array.shift()` / `unshift()` ($O(N)$ memmove) as a FIFO queue.
  - On large arrays in hot paths, write a single `for (const x of items)` pass rather than chaining `items.filter(...).map(...).flatMap(...)` (which allocates and GC-collects 3 intermediate arrays).
  - **Hoist heavy constructors out of loops:** Constructing `new RegExp(...)`, `new TextEncoder()`, or **`new Intl.DateTimeFormat()` / `new Intl.NumberFormat()`** inside a loop is `50–100x` slower than reusing one module-level instance!
  - Avoid sequential `await` inside a loop (`for (const id of ids) await fetch(id)`) when requests are independent — batch into one bulk RPC/query or run with bounded concurrency.
- **Keep `tsc` Type-Checking Fast (`isolatedDeclarations`):**
  - Annotate **explicit parameter and return types on all exported functions/methods** so TypeScript skips cross-file body inference, enables parallel `.d.ts` emission (`isolatedDeclarations: true`), and prevents accidental public return-type drift!
  - Avoid deeply nested recursive conditional types, huge union Cartesian products, and barrel-file import cycles.

# 6. Module Graph, Bundle Footprint & No-Barrel Rule

- **Ban Barrel Files (`index.ts` Re-Export Hubs) Inside Applications & Deep Trees:**
  - Aggregating 50 modules into `src/utils/index.ts` (`export * from ...`) forces test runners, serverless cold starts, and bundlers to parse the entire dependency subgraph just to read 1 helper, defeats tree-shaking when any transitive module has side effects, and breeds circular initialization `ReferenceError`s!
  - **Fix:** Import directly from the leaf module (`import { parseMoney } from '../money/parse.js'`). For published libraries, expose explicit subpath entrypoints in `package.json` `"exports"` with `"sideEffects": false` and `import type` (`verbatimModuleSyntax: true`).
- **Lazy-load heavy optional edges:** Use dynamic `await import('./heavy-chart.js')` for cold routes, rare CLI subcommands, or optional formatters.

# 7. Style, Maintainability & Design for Testability

- **Google TypeScript Style essentials:**
  - **Named exports only:** Never use `export default` (hurts refactoring, auto-imports, and consistent naming across the repo; exempt only framework files that mandate default export).
  - **Immutability by default:** Prefer `const`, `readonly` properties, `ReadonlyArray<T>` (`readonly T[]`), and `ReadonlyMap<K, V>` in function parameters so callees cannot surprise callers by mutating inputs in place (`arr.toSorted()` over mutating `arr.sort()`).
  - **Options objects over positional booleans:** Beyond 2–3 arguments (or for *any* boolean flag), accept a typed `readonly` options object (`fetchReport(id, { includeArchived: true, signal })` — never `fetchReport(id, true, false)`).
- **Design for Mock-Free Testability:**
  - **Avoid `vi.mock()` / `jest.mock()` module-hoisting monkey-patches!** Module mocks bypass type checking, break under ESM refactoring, and hide real integration bugs.
  - Instead, separate the **pure functional core** `(state, event, nowMs) => [nextState, effects]` from the thin I/O shell, and inject narrow structural dependency ports (`interface Deps { readonly clock: () => number; readonly store: OrderStore }`) with default production implementations — tests pass an in-memory fake in 3 lines with `100%` compile-time type safety!
  - Pair table-driven unit tests (`vitest` / `node:test`) with property-based tests (`fast-check`) for parsers, state machines, and boundary round-trips.

# 8. Enforcement & Build Gate

Recommended `tsconfig.json` baseline (add `"DOM", "DOM.Iterable"` to `"lib"` for browser targets):

```json
{
  "compilerOptions": {
    "target": "ES2024",
    "lib": ["ES2024", "ESNext.Disposable"],
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "noFallthroughCasesInSwitch": true,
    "useUnknownInCatchVariables": true,
    "verbatimModuleSyntax": true,
    "erasableSyntaxOnly": true,
    "isolatedDeclarations": true,
    "skipLibCheck": true
  }
}
```

Run every check in CI and local pre-flight:

```sh
pnpm install --frozen-lockfile
pnpm tsc --noEmit
pnpm eslint --max-warnings=0 .   # typescript-eslint strictTypeChecked (incl. no-floating-promises)
pnpm test                        # vitest run / node --test
pnpm audit --audit-level=high
```

# 9. Red-Team Review Checklist

- **Boundary & Security:** Did any `JSON.parse` / `req.body` / `res.json()` bypass runtime schema parsing via `as T`? Could untrusted keys hit plain `{}` (`__proto__`), `innerHTML`, `exec(..., { shell: true })`, unparameterized SQL, `Math.random()`, or float `number` > `MAX_SAFE_INTEGER`?
- **Types & Async Reliability:** Are `any`, `!`, `enum`, and `||`-falsy defaults absent? Is every `Promise` awaited/handled (`no-floating-promises`), bounded in concurrency, and wired with an `AbortSignal` + timeout?
- **Performance & Memory:** Are hot object shapes initialized unconditionally in fixed order without `delete`? Are `Intl` formatters and `RegExp` hoisted out of loops? Are barrel `index.ts` re-exports avoided? Are event listeners/timers cleaned up via `AbortController` / `using`?
- **Testability:** Is business logic pure and tested via narrow injected ports + `fast-check` edge cases rather than untyped module-mocking hacks?
