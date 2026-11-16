---
name: web-hardening
description: >-
  Security hardening of the HTTP surface of a web app, with performance kept:
  security headers, default-on CSRF, hash-allowlisted CSP, XSSI prefixes,
  BREACH-scoped compression, asset pipelines, and conformance tests. Use when
  adding or changing backend routes or handlers, response headers, cookies,
  sessions, or CSRF, serving static assets or JSON, enabling compression or
  caching, or reviewing web security, even for one small endpoint.
last_updated: 2026-11-15
---

# Web hardening (security × performance)

A transferable method for security-hardening an HTTP backend's surface while keeping request
latency and CPU cost low — structuring headers, request gates, typed response writers, CSP,
and compression so safety holds by construction and is enforced by conformance tests.

## The four principles everything else follows from

1. **One owner per security concern.** Security headers, request gates, and response-shape
   rules each live in exactly ONE file. A property enforced in one place is a property a
   reviewer can verify in one place — and one a new handler cannot forget or weaken.
   Anything set per-handler will eventually be set wrong or not at all.

2. **Default-on protection; exemptions are data, not absent code.** Protection applies to
   every route that exists or will ever exist; opting OUT is an explicit, commented entry in
   a table (`routeGuards`), each stating *why* the route has no attack surface of that kind.
   The failure mode this kills: a new state-changing handler shipping unprotected because
   its author didn't know to add a check. With a table, the unlisted default is the safe one.

3. **Safe by construction, not by review.** Handlers never hand-set Content-Type or build
   responses ad hoc — they call typed writers (`writeJSON`/`writeHTML`/`writeDownload`)
   that bundle the safety properties (XSSI prefix, charset, attachment disposition) with the
   media type. An unsafe response becomes hard to *express*, not merely against the rules.

4. **Conformance tests, not promises.** Every "we always/never do X" claim gets a test that
   would fail if it stopped being true. The four patterns that carry the design:
   - **Source scan**: no file outside the owner file names a security header.
   - **Exemption honesty**: every route exempted as "bearer-only" provably rejects a request
     authenticated only by a cookie.
   - **Emission crawl**: crawl every HTML route, extract each inline script/style, assert its
     hash is in the CSP — an unregistered inline block fails the build, not the browser.
   - **Uniform-rule sweep**: hit every JSON endpoint, assert the prefix/headers. A rule with
     carve-outs can't be tested; make the rule uniform so it can be.

## Request-gate order (middleware wraps the whole mux)

Host validation → Fetch-Metadata isolation → CSRF gate → cache discipline → handler.
Blocked requests still get the security headers (an error response is still a response) and
still get metered (wrap security *inside* observability).

- **Host validation**: allowlist derived from deploy config (TLS domain + www + operator
  extras); off when nothing is configured (dev). Exempt the health endpoint — an IP-addressed
  LB probe must not take the site down to protect the word "ok".
- **Fetch Metadata**: FAIL OPEN when `Sec-Fetch-*` is absent — those headers come only from
  browsers, so native clients, webhooks, and crawlers sail through; the policy only ever
  tightens a real cross-site browser request. Refuse cross-site subresource/fetch loads AND
  cross-site framing destinations. Don't rely on this for CSRF — it's depth, not the defense.
- **CSRF**: see the taxonomy below. Cap the form body (`MaxBytesReader`) *before* parsing.
- **Cache discipline**: any request carrying a credential (cookie, Authorization) or under
  `/api/` defaults to `Cache-Control: no-store`; public handlers set their own and win.

## Guard taxonomy (why a route is exempt from CSRF)

CSRF exists because browsers attach ambient credentials to requests the user never intended.
A route's guard names which credential model it uses — and therefore whether CSRF applies:

| guard | credential | CSRF surface |
|---|---|---|
| `guardXSRF` (default) | session cookie | yes — same-origin signal + signed double-submit token |
| `guardBearer` | Authorization header only | none — no ambient credential (test enforces it) |
| `guardSigned` | signature over the body (webhooks) | none — the sender is a server |
| `guardCapability` | high-entropy URL is the whole capability | none — nothing ambient to abuse |

CSRF token lessons:
- Token = `nonce.HMAC(server_key, "csrf|" + origin + "|" + session_id + "|" + nonce)` (using a
  random pre-login anti-fixation cookie ID as `session_id` before authentication, then rotating
  both the session and CSRF cookies at login): origin-bound (worthless at another deployment),
  key-rotatable, and **session-bound**. Session-unbound tokens (`HMAC(key, origin | nonce)`)
  allow **cookie tossing** whenever `__Host-` is unavailable (plain HTTP dev/LAN, or sibling
  subdomains), because an attacker on a sibling subdomain or MITM path can mint or harvest a
  valid token for their own browser and plant a `Domain=`/path-scoped CSRF cookie on the victim.
- **Keep the token stable within a session (rotate at login/privilege change, never per render).**
  Per-render rotation breaks multi-tab and back-button forms with spurious 403s. Pair `__Host-`
  (on HTTPS) + `SameSite=Strict` with session binding so the cookie is both unpinnable and
  useless to any other session.
- Reject a *repeated* token parameter outright — duplicate-parameter resolution is where
  parser-differential attacks live. There is no legitimate request with two tokens.
- On failure, distinguish intent: a declared foreign Origin is an attack → hard 403; a
  same-origin miss is a stale form → 303 back to the GET, which re-issues a matching token
  (self-heal, no dead end). Portal pages that embed the token are `no-store`.
- A missing token field must fail, not skip the check ("validate only if present" is a bypass).

## Response shapes

- **JSON**: `application/json; charset=utf-8` + `)]}'\n` XSSI parser-breaker + `Content-
  Disposition: attachment` — on EVERY JSON response, no carve-outs (uniformity is what makes
  it testable). Clients strip the prefix tolerantly (optional), so rollout order doesn't matter.
  Error bodies carry fixed generic copy — never internal error strings, paths, or stacks.
- **HTML**: compile-time literals or a contextually auto-escaping template engine. No handler
  concatenates request data into markup. Error pages: fixed copy per status, no request echo.
- **Bytes you don't vouch for** (client-uploaded blobs, relayed upstream bodies, downloads):
  `application/octet-stream` + attachment with a server-chosen filename. A proxy/relay PINS
  the response Content-Type rather than echoing upstream's — otherwise a compromised upstream
  chooses how a browser interprets bytes served from YOUR origin.
- Account-enumeration discipline: one generic failure message for unknown-user and
  bad-password; spend a dummy hash for unknown users so timing doesn't tell them apart;
  constant-time comparison for every secret (tokens, codes, webhook signatures).

## CSP

Hash-allowlist inline content; compute the policy ONCE at startup. The trick that makes it
maintainable: every inline block the binary can emit is a *named constant/function*
(`inlineThemeScript()`, `oauthBridgeScript`) that both the page template and the policy
hash — so markup and policy cannot drift, and the emission-crawl test catches a new block.
`script-src` = hashes only when you serve no script files (stronger than `'self'`);
`object-src/base-uri/frame-ancestors 'none'`; pair `require-trusted-types-for 'script'` with
`trusted-types 'none'` (when zero dynamic DOM sink policies are needed) or an explicit
`trusted-types <policy-name>` allowlist (without `trusted-types`, scripts can still call
`trustedTypes.createPolicy(...)` arbitrarily) to close DOM sinks at runtime. Concede narrowly
and visibly (e.g. `style-src-attr 'unsafe-inline'` for legacy inline style= attributes —
attribute styles can't execute script).

## Compression — a security decision first

Compressing a response that mixes a **secret** with **attacker-influenced content** is the
BREACH side channel: the compression ratio leaks the secret. Therefore:
- gzip is **opt-in per route**, applied at the registration site (visible in the router),
  never as a global middleware. Public, token-free routes only — never login/portal pages
  (CSRF token in body), never `/api/` (session tokens in JSON).
- Compress at **build time** where content is static: emit `asset.gz` beside the identity
  file (deterministic — `mtime=0` — so the committed bytes are diff-stable), embed both,
  serve the pre-gzipped bytes directly. Zero per-request CPU for the hottest assets.
- Runtime gzip (articles, generated pages): pooled writers; pass Range requests and non-200s
  through uncompressed; `Vary: Accept-Encoding`.

## Asset pipeline & caching

- **Minify at build time with machine-checked preconditions.** A safe minifier is only safe
  under stated source constraints (no `calc()`, no descendant-combinator-before-pseudo, no
  structural chars in strings…). Encode each constraint as a check that FAILS THE BUILD with
  instructions — the constraint outlives the person who knew about it.
- **One shared bundle across surfaces**; scope collision-prone vocabulary structurally
  (e.g. every marketing rule under `body.site`, a class only marketing pages set) instead of
  relying on "these files are never loaded together" — that claim rots the day it's false.
- **Embedded content gets a build-time Last-Modified.** Inject a build stamp (`-ldflags`);
  fall back to the executable's mtime. Embedded FS files have zero mtime — without this,
  every response is uncacheable-by-date; with it, returning visitors get 304s until the next
  deploy. Embedding itself is a defense: zero filesystem reads → no traversal surface.
- Modest `max-age` + Last-Modified revalidation beats aggressive caching you can't bust.

## Performance discipline that touches security

- **Rate-limit BEFORE expensive work.** The KDF that protects passwords (Argon2id, 64 MiB) is
  a memory-DoS amplifier on any unauthenticated route that reaches it. The limiter is the
  first gate, ahead of CSRF and parsing. (This was a real found bug: the browser signup form
  bypassed the limit its JSON twin enforced.)
- **Bound every input before parsing it**: request body caps per shape (a JSON API body is
  KBs, not MBs), form-body cap before `ParseForm`, `MaxHeaderBytes`, server read/write/idle
  timeouts. Unbounded parse cost is free amplification for an unauthenticated caller.
- **Precompute what is per-request-constant**: CSP string, error pages, page templates, docs
  pages — build once at startup. The 404 path is the most-hammered junk route on a public
  server; it should allocate nothing.
- **One filesystem/directory listing per request** — resolve metadata once and pass it down;
  a handler that re-lists to find what it already knows is the common accidental O(2n).
- Hoist duplicated auth-resolution into helpers (`requireSession`, `householdOf`) — dedup is
  a security property here: five copies of a fallback is five places for one bug.
- Durability: whole-file atomic writes (temp → fsync → rename) for small JSON state; hash
  content *while* streaming to temp when the name depends on the digest.

## When adding a new route — the 60-second checklist

1. Which guard? If not cookie-authenticated, add the exemption row WITH its reason.
2. Responses through the typed writers only. New inline script/style? Register its hash.
3. Any secret in the response body? Then it must not be on a compressed route.
4. Input caps: body size, parameter validation to typed values, reject repeated params.
5. Expensive work (KDF, upstream calls, big parse)? Rate-limit or entitle-gate in front.
6. Static/embeddable output? Cache headers + build-time Last-Modified; precompute if constant.
7. Run the conformance tests — they exist to catch what this checklist missed.
