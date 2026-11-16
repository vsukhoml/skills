---
name: api-design
description: >-
  Designs and reviews backend, library, SDK, and agent/tool APIs (REST,
  gRPC/Protobuf, streaming, webhooks): self-correcting validation errors,
  strict unknown-field rejection, dry-run, idempotency, batching, pagination,
  field masks, Zero-Trust security, and minimal surface. Use when adding or
  changing an endpoint, RPC, public function signature, tool schema, or error
  contract, or when reviewing an API diff.
last_updated: 2026-11-15
---

# First-Principles API Design (`api-design`)

Designs and reviews **HTTP/REST, gRPC/Protobuf, streaming, webhook, and library/tool
APIs** so they are **effortless for both human developers and LLM/agent callers to
use correctly**, **fast at scale**, **hardened against abuse and reconnaissance**,
and **radically minimal in surface area**.

Consult [references/errors-batching-and-security.md](references/errors-batching-and-security.md)
for the two-horizon error schema (`RFC 9457` / gRPC `BadRequest`), safe vs. leaky
error translations, typed batch/partial-failure contracts, and JWT/webhook/rate-
limit checklists.

---

## 1. Surface & Entity Minimalism ("We Do Not Break Userspace")

Every public endpoint, parameter, entity, enum variant, or dependency is a
long-term maintenance and security liability:

1. **Earn every entity and endpoint:** Introduce a new resource, service, or field
   **only** when existing primitives cannot express the domain requirement cleanly.
   Everything that can be omitted *must* be omitted to keep cognitive load, operational
   cost, and attack surface small.
2. **Predictable, self-describing resource grammar (`google.aip.dev`):**
   * Use consistent plural resource nouns + standard methods (`GET /v1/orders`,
     `POST /v1/orders`, `GET /v1/orders/{id}`, `PATCH /v1/orders/{id}`,
     `DELETE /v1/orders/{id}`), reserving custom `:verb` actions (`POST
     /v1/orders/{id}:cancel`) strictly for state transitions that do not map cleanly
     to CRUD.
   * **Encode units & scales directly in field names:** Write `timeout_ms`,
     `amount_minor`, `max_bytes`, `expires_at` (`RFC 3339` UTC) — never ambiguous
     `timeout`, `amount`, or `size` that force callers or LLMs to guess!
   * Keep schemas **flat, orthogonal, and non-polymorphic** wherever possible: avoid
     deeply nested envelopes or "magic" string DSLs when typed fields work.
3. **Additive evolution over breaking `v2` forks:**
   * Evolve APIs additively (new optional request fields with safe defaults, new
     response fields that clients ignore when unknown). Bump major versions (`/v2`,
     `package foo.v2`) only when an invariant fundamentally changes.

---

## 2. Two-Horizon Errors: LLM/Client Self-Correction Without Internal Leakage

Vague `"400 Invalid input"` responses trap LLM agents and client integrators in
blind retry loops — while dumping raw DB/exception strings hands attackers schema
names, file paths, and enumeration oracles. Solve both with a **strict Two-Horizon
Error Contract** (`RFC 9457` Problem Details / `google.rpc.Status`):

| Error Horizon | HTTP / RPC Class | What to Return (High-Signal for Agents) | What to Strip / Mask (Zero Recon Leakage) |
| --- | --- | --- | --- |
| **Horizon A: Caller Contract Violations** | `400`, `409`, `413`, `415`, `422`, `429` (`INVALID_ARGUMENT`, `ALREADY_EXISTS`, `ABORTED`, `RESOURCE_EXHAUSTED`) | Machine `code` enum, **all** failing field `pointer`s (`"/items/1/qty"`), violated public rule (`min`, `max`, `allowed_values`, `expected_type`, `did_you_mean` for unknown fields), `retryable`, `retry_after_ms`, concrete `remediation` referencing **only public parameters**, and `trace_id`. | Raw regex source if proprietary, internal SQL constraint names (`idx_users_email_uniq`), parser stack frames, or values of *other* tenants' conflicting records. |
| **Horizon B: Auth, Tenancy, Existence & Server Faults** | `401`, `403`, `404`, `500`, `502`, `503`, `504` (`UNAUTHENTICATED`, `PERMISSION_DENIED`, `NOT_FOUND`, `INTERNAL`, `UNAVAILABLE`) | Generic stable `code` (`INVALID_CREDENTIALS`, `NOT_FOUND`, `INTERNAL_ERROR`), `retryable` (`bool`), `retry_after_ms` (on `503`), and `trace_id` for support correlation. | **Zero** stack traces, SQL/ORM errors, table/column names, OS paths, internal service hostnames/IPs, SDK versions, or **existence/timing oracles**! |

* **Anti-enumeration rule:** When an authenticated caller queries `/v1/projects/{id}`
  belonging to another tenant (or lacks read visibility), return **`404 Not Found`**
  identical in shape and timing to a nonexistent ID — never `403 Forbidden` when
  resource existence itself is confidential! Likewise, login/reset endpoints must
  never reveal whether an email/username exists.

---

## 3. Fast, Deterministic Input Validation & Safe Dry-Runs

Validate every request at the **outermost perimeter** before touching databases,
locks, queues, or paid downstream compute:

1. **Pre-parse wire bounds:** Enforce strict `Content-Type`, maximum request body
   bytes (`413 Content Too Large`), header size, and JSON/Protobuf nesting depth
   *before* full deserialization so malformed payloads cannot exhaust RAM/CPU.
2. **Reject unknown fields on write requests (`additionalProperties: false`):**
   * If an LLM or client sends `{"dryRun": true}` instead of `{"dry_run": true}`,
     silently ignoring unknown fields executes a **live production mutation**!
   * Reject unknown request fields with `400` + `"unknown field 'dryRun'; did you
     mean 'dry_run'?"`, and collect **all** field validation errors in a single pass
     rather than failing one field at a time across `6` round-trips.
3. **Closed scalar domains:** Bound every string (`min`/`max` bytes + `UTF-8` `NFC`
   validity + control-char rejection), number (integer or finite range — **reject
   `NaN`/`Infinity`**; use integer minor units or decimal strings for money), enum,
   ID prefix (`ord_...`), and array length (`1 <= len <= max_batch`).
4. **First-class `validate_only` / `dry_run`:** On state-mutating, billing, or bulk
   endpoints, support `dry_run: true` (running full schema, authz, and conflict
   validation and returning the planned diff/cost without committing state).

---

## 4. High-Performance Operations: Batching, Pagination, Masks & Async

Design APIs so callers never have to issue `1,000` serial requests in a loop:

1. **Typed Resource Batch Endpoints (`BatchGet`, `BatchCreate`, `BatchUpdate`):**
   * Prefer typed per-resource batch operations (`POST /v1/orders:batchGet`, `POST
     /v1/orders:batchCreate`) over untyped `"HTTP-in-HTTP"` sub-request multiplexers
     (which bypass route-level rate limits, authz, and schema validation!).
   * **Hard batch bounds:** Enforce `max_items` (`e.g., <= 100` or `<= 500`) and
     total byte ceiling on every batch call, advertising `max_batch_size` in schema
     descriptions and `400`/`413` errors.
   * **Explicit batch atomicity & partial-failure contract:**
     * Choose **Atomic (`all-or-nothing`)** when items form one logical unit, OR
     * **Ordered Per-Item Results (`results[0..N-1]` matching request index 1:1)**
       with per-item `{ status, data | error }` + **per-item `idempotency_key`** so
       clients retry *only* transient failed indices without duplicating successes!
2. **Cursor / Keyset Pagination (`O(log N)`):**
   * Every collection endpoint bounds `limit` (`default 50`, `max <= 200–1000`) and
     paginates via an opaque `cursor` / `page_token` (`next_cursor`, `has_more`) —
     avoiding `offset` scans and expensive `COUNT(*)` totals on large tables.
3. **Payload & Round-Trip Efficiency:**
   * **Sparse field masks (`fields` / `FieldMask`):** Let callers request only
     needed fields (or exclude expensive computed/joined sub-resources by default).
   * **Conditional requests & optimistic concurrency:** Emit `ETag` headers; honor
     `If-None-Match` (`304 Not Modified`) on reads and `If-Match` (`412 Precondition
     Failed`) on concurrent updates.
   * **Idempotency on every retriable write:** Require `Idempotency-Key` on
     non-idempotent `POST`/`PATCH` mutations — returning **`422
     IDEMPOTENCY_KEY_PAYLOAD_MISMATCH`** (`retryable: false`) when a key is
     reused with a different request-body hash, and **`409
     IDEMPOTENCY_KEY_IN_FLIGHT`** (`retryable: true`, with `retry_after_ms`)
     when a concurrent request with the same key is still executing!
   * **Async Operations (`202 Accepted`) & Streaming (`NDJSON`/SSE/gRPC):** Return
     an `Operation` handle (`GET /v1/operations/{id}`) for work `> 1–2 s`, and use
     framed streaming with backpressure for large exports or token streams.

---

## 5. Zero-Trust Security, Rate Limiting & Resilience

* **Strict token & JWT verification:** Pin allowed signing algorithms (`alg`
  allowlist — reject `none` and symmetric/asymmetric confusion!), require `iss`,
  `aud`, and short `exp`, forbid arbitrary `jku`/`x5u` URL fetches or unvalidated
  `kid` path/SQL characters, support revocation, and never pass bearer tokens in URL
  query strings (leaks via referrers and access logs!).
* **Abuse-at-code-speed defenses:** Enforce per-tenant/per-token rate limits,
  concurrency caps, and cost budgets (`RateLimit-Limit`, `RateLimit-Remaining`,
  `RateLimit-Reset`, `Retry-After`), circuit breakers + deadlines on upstream calls,
  and an operational kill-switch per costly feature/tenant.
* **Signed, replay-safe webhooks:** Sign outbound webhook payloads with `timestamp +
  HMAC-SHA256` (`v1=...`), rotate secrets with dual-key overlap, enforce short
  timestamp tolerance (`<= 5 min`), and include a unique `event_id` for receiver
  deduplication.

---

## Before You Finish (`api-design` Checklist)

| Smell / Anti-Pattern | Fix |
| --- | --- |
| `400` returns only `"Invalid input"` (agents guess blindly) OR `500` leaks SQL/stack trace | Use Two-Horizon `RFC 9457` errors: expanded field/constraint hints on `4xx`, opaque + `trace_id` on `5xx`/auth |
| Write endpoint silently ignores unknown fields (`dryRun` typo executes live delete!) | Reject unknown request fields (`400 UNKNOWN_FIELD` + edit-distance `"did you mean 'dry_run'?"`) |
| `403` vs `404` or response timing reveals whether another tenant's resource/email exists | Return uniform `404` on unauthorized tenant IDs and uniform `INVALID_CREDENTIALS` on auth |
| Callers forced into `N` serial `GET`/`POST` calls with no batch endpoint | Add typed `:batchGet` / `:batchCreate` with hard `max_items` cap + per-item idempotency |
| Unbounded list endpoint or `page=5000` `OFFSET` pagination | Enforce `max_limit` + opaque keyset `cursor` (`next_cursor`, `has_more`) |
| Retrying a timed-out `POST /payments` charges customer twice | Require `Idempotency-Key` persisted atomically with request-body hash check |
| Speculative endpoints/entities added "just in case" | Delete until a concrete caller workflow requires them |
