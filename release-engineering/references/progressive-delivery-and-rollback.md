# Progressive Delivery, Compatibility & Instant Rollback Reference (`release-engineering`)

---

## 1. "Build Once, Promote Digest" Pipeline Topology

```text
[Commit + Lockfile]
        │
        ▼
[Hermetic Reproducible Build]
  • Produces stripped immutable artifact (@sha256:abc...) + detached symbols (Build-ID)
  • Runs fast unit/golden/ELF/size gates
  • Attaches SBOM + provenance attestation + cryptographic signature
        │
        ▼  (Zero recompilation downstream — exact @sha256:abc... promoted!)
[Stage 1: Ephemeral / Integration / HIL Env] ──► Contract, migration dry-run & smoke tests
        │
        ▼
[Stage 2: Production Ring 0 (Dogfood / 1% Canary, Single AZ)] ──► Automated SLI comparison vs. baseline
        │
        ▼
[Stage 3: Production Ring 1 (10% -> 50% -> 100%, Staggered Across Regions/AZs)]
```

* **Configuration injection rule:** Never bake `PROD_DB_URL` or feature toggles into
  the compiled binary or image layers. Inject environment configuration via typed,
  startup-validated files/env vars — and roll out **configuration changes** through
  the exact same `1% -> 10% -> 100%` rings as binary changes!

---

## 2. Backward & Forward Compatibility Matrix (`N-1` / `N-2`)

Instant rollback works **only** if reverting the binary from `vN` back to `v(N-1)`
never crashes on data or messages written during `vN`'s canary window:

| Boundary | Safe Additive Change (`Rollback-Safe`) | Breaking Change (`Requires Multi-Release Expand/Contract`) |
| --- | --- | --- |
| **Protobuf / Wire Messages** | Add new optional field with unused field number; `v(N-1)` ignores unknown fields | Reusing a deleted field tag number (`reserve` deleted numbers & names forever!), changing wire type, making field required |
| **JSON / REST APIs** | Add optional request param with default; add new response field | Removing/renaming response field, tightening request enum/bounds before clients upgrade |
| **Database Schema** | Add nullable column; `CREATE INDEX CONCURRENTLY`; `ADD CONSTRAINT ... NOT VALID` | Renaming/dropping column or table in the same deploy as code removal |
| **Job Queue / Event Payloads** | Add optional field; consumers ignore unknown fields | Deploying producer emitting new event `type` *before* all worker consumers know how to handle it (**deploy consumers first, producers second!**) |

---

## 3. Zero-Drop Graceful Shutdown (`SIGTERM`) Sequence

In rolling orchestrators (Kubernetes, systemd socket handoff, cloud load balancers),
endpoint removal (`Endpoints`/`EndpointSlice` propagation to `kube-proxy`/Envoy/ALB)
races *in parallel* with `SIGTERM` delivery to the process! Exiting immediately on
`SIGTERM` causes `502 Bad Gateway` resets on in-flight and newly routed packets:

1. **Receive `SIGTERM`:** Flip `/readyz` probe to **`503 Draining`** immediately,
   **keep `/healthz` liveness `200`** (so the orchestrator doesn't `SIGKILL` early),
   and **keep the listening socket open** during propagation delay (`2–5 s`)!
2. **Stop accepting new work:** Close listener (`http.Server.Shutdown` / gRPC
   `GracefulStop` / stop pulling queue jobs).
3. **Complete in-flight work** within bounded drain budget (e.g., `15–25 s` inside a
   `30 s` `terminationGracePeriodSeconds`), checkpoint resumable background tasks,
   flush telemetry buffers, and `exit(0)`.

---

## 4. Brick-Proof Firmware `A/B` OTA & Anti-Rollback State Machine

Remote client hardware cannot be "SSH'd into" when an OTA update crashes on boot:

```text
[Slot A: Active & Confirmed (v1.4)] ──► Downloads & verifies signed delta/image into inactive [Slot B (v1.5)]
        │
        ▼
[Bootloader: Sets Slot B = PENDING_TRIAL (trial_boots_remaining = 3), arms Hardware Watchdog, resets]
        │
        ├──► [v1.5 Panics / Watchdog Barks / Brownouts Before Confirm]
        │           └──► Bootloader decrements counter ──► Reverts automatically to [Slot A (v1.4)] + reports OTA_ROLLBACK fault!
        │
        └──► [v1.5 Boots, Passes Self-Test + Bus/Radio Check]
                    └──► Calls boot_set_confirmed() ──► [Slot B = CONFIRMED_ACTIVE]
                         (Optional: bump monotonic eFuse anti-rollback security version ONLY after confirmation!)
```

* **Immutable bootloader golden rule:** Keep the Stage-1 bootloader tiny, minimal,
  and cryptographically verify images (`Ed25519`/`ECDSA` + monotonic security version
  check) **in RAM/flash before jumping** — never overwrite the recovery bootloader
  during routine application OTAs!
