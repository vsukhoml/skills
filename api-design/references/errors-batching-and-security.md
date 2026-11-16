# Agent-Consumable Error Schemas, Typed Batching & API Security Reference (`api-design`)

---

## 1. Two-Horizon Structured Error Schema (`RFC 9457` / Agent-Ready)

Always return structured HTTP error payloads with `Content-Type: application/problem+json`
(never HTML or plain-text proxy error pages) so client SDKs and LLM tool callers
parse every `4xx`/`5xx` deterministically.

### 1.1 Horizon A Example — Expanded `400`/`422` Validation Error (Zero Internal Leakage)

Gives an LLM tool caller, CLI, or SDK **100% of the contract facts needed to fix its
next request in one turn**, while referencing zero internal tables or code paths:

```json
{
  "type": "https://api.example.com/errors/validation-failed",
  "status": 400,
  "code": "VALIDATION_FAILED",
  "title": "Request parameters failed contract validation.",
  "retryable": false,
  "trace_id": "019330a4-7e12-7b40-9c11-8a2f40d1e902",
  "errors": [
    {
      "pointer": "/dryRun",
      "code": "UNKNOWN_FIELD",
      "message": "Unknown field 'dryRun'.",
      "did_you_mean": "dry_run"
    },
    {
      "pointer": "/items/2/amount_minor",
      "code": "OUT_OF_RANGE",
      "message": "Must be an integer between 1 and 100000000.",
      "constraint": { "type": "integer", "min": 1, "max": 100000000 }
    },
    {
      "pointer": "/currency",
      "code": "INVALID_ENUM",
      "message": "Unsupported currency code.",
      "allowed_values": ["USD", "EUR", "GBP", "JPY"]
    }
  ]
}
```

### 1.2 Horizon B Example — Opaque `500` / `401` / Cross-Tenant `404`

```json
{
  "type": "https://api.example.com/errors/internal-error",
  "status": 500,
  "code": "INTERNAL_ERROR",
  "title": "An unexpected internal error occurred.",
  "retryable": true,
  "retry_after_ms": 1000,
  "trace_id": "019330a4-7e12-7b40-9c11-8a2f40d1e902"
}
```

### 1.3 Internal Exception -> Public Error Translation Table

Never serialize raw error objects (`err.Error()`, `str(exc)`, `zod/serde` internal
class paths, or DB driver messages) directly to the wire:

| Internal Fault Caught at Boundary | Leaky Anti-Pattern (FORBIDDEN) | Safe Public Mapping |
| --- | --- | --- |
| Unique index violation on caller's *own* workspace slug | `"pq: duplicate key value violates unique constraint \"workspaces_slug_key\""` | `409 CONFLICT` · `code: "SLUG_ALREADY_IN_USE"` · `pointer: "/slug"` |
| Unique index violation on global `/signup` email (enumeration sensitive) | `"Email alice@corp.com already exists in table users"` | `202 Accepted` (out-of-band email) or generic policy-approved signup conflict |
| Caller requests `/v1/invoices/inv_99` owned by another tenant | `403 "Invoice inv_99 belongs to tenant org_42"` | `404 NOT_FOUND` (identical to nonexistent `inv_99`) |
| Upstream payment/DB timeout or connection refused | `"dial tcp 10.0.14.82:5432: connect: connection refused"` | `503 SERVICE_UNAVAILABLE` · `retryable: true` · `retry_after_ms: 2000` + `trace_id` |
| SQL syntax / panic / nil dereference | Stack trace with `/srv/app/internal/billing/charge.go:142` | `500 INTERNAL_ERROR` + `trace_id` (log full stack internally!) |

---

## 2. High-Performance Typed Batching Contract

### 2.1 Request & Partial-Success Response (`POST /v1/items:batchCreate`)

```json
// Request (capped at max_items = 100, atomic = false for independent partial retries)
{
  "atomic": false,
  "dry_run": false,
  "items": [
    { "idempotency_key": "k-001", "sku": "SENSOR-A1", "qty": 10 },
    { "idempotency_key": "k-002", "sku": "UNKNOWN-SKU", "qty": 5 }
  ]
}

// Response (HTTP 200 or 207; results[] strictly 1:1 positional with request items[])
{
  "summary": { "succeeded": 1, "failed": 1 },
  "trace_id": "019330a4-8810-7000-8123-001122334455",
  "results": [
    {
      "index": 0,
      "status": 201,
      "data": { "id": "itm_01J...", "sku": "SENSOR-A1", "qty": 10 }
    },
    {
      "index": 1,
      "status": 422,
      "error": {
        "code": "SKU_NOT_FOUND",
        "pointer": "/items/1/sku",
        "message": "SKU 'UNKNOWN-SKU' does not exist in active catalog.",
        "retryable": false
      }
    }
  ]
}
```

* **Why positional `results[index]` + per-item `idempotency_key` wins:** If item `0`
  succeeded and item `1` hit a transient `503` or fixable `422`, an agent or SDK
  retries *only* item `1` (or safely re-sends both using the same
  `idempotency_key`s without creating duplicate records!).
* **Database implementation rule:** Inside the handler, execute batch operations
  using set-based queries (`WHERE id = ANY($1)` / multi-row `INSERT ... VALUES` /
  pipelined RPCs) — **never** a `for` loop running `100` sequential DB round-trips!

---

## 3. Schema Design for LLM Tool-Calling & Codegen Ergonomics

When an API doubles as an OpenAPI / MCP / function-calling tool surface for agents:

1. **Keep top-level tool/operation count compact:** Prefer `1` orthogonal filterable
   `list_orders(status?, customer_id?, created_after?, cursor?, limit?)` endpoint
   over `8` overlapping endpoints (`get_open_orders`, `get_orders_by_customer`,
   `get_recent_orders`).
2. **Put hard constraints inside JSON Schema / Protobuf metadata** (`minimum`,
   `maximum`, `maxLength`, `maxItems`, `enum`, `format: "date-time"`, `pattern`) so
   constrained decoding and client generators know bounds *before* making a network
   call.
3. **Echo canonical state after mutations:** Return the updated representation
   (including server-computed `version`/`etag` and normalized fields) from `POST`/
   `PATCH` so callers do not burn an extra `GET` round-trip.

---

## 4. Security & Abuse-Hardening Checklist

* **Authentication & Authorization:**
  * Enforce object-level **and** function-level authorization (`BOLA`/`BFLA`) on
    every item ID inside single **and batch** requests (`items[]` containing `99`
    owned IDs + `1` foreign tenant ID must reject the unauthorized item!).
  * Pin JWT `alg`, verify `iss` + `aud` + `exp` + `nbf`, bound token lifetime, and
    avoid `Bearer` tokens in URL query parameters.
* **Rate Limiting & Cost Accounting:**
  * Charge **batch endpoints proportionally to item count** (`1` batch of `100`
    items consumes `100` item-tokens, not `1` request-token, so attackers cannot
    bypass rate limits `100x` via batching!).
  * Always emit `Retry-After` on `429` and `503` so well-behaved clients and agents
    back off deterministically instead of thundering-herding.
* **Webhook Delivery:**
  * Guard user-supplied webhook target URLs against **SSRF** (resolve DNS once at
    connect time and block loopback, link-local `169.254.169.254` cloud metadata,
    and RFC 1918 / ULA private ranges!).
