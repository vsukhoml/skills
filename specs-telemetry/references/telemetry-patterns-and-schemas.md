# First-Principles Telemetry Reference: Firmware, Client & Cloud (`specs-telemetry`)

Concrete blueprints for sizing telemetry across bare-metal/RTOS firmware, client/CLI
applications, and distributed backends.

---

## 1. End-to-End Hardware-to-Cloud Architecture Blueprint

```text
[Client Firmware / MCU]
  • ISR / RTOS tasks emit 4–12 B tokenized binary events (no snprintf, no malloc)
  • Ring buffer in .noinit SRAM (magic + CRC32) survives Panic & Watchdog Reset
  • Fault handler (stack-safe, IRQ-masked, key-RAM scrubbed) snapshots regs + stack
  • Next boot moves .noinit snapshot -> wear-budgeted Flash Store-and-Forward slot
        │
        │  Opportunistic MTU-sized chunks (BLE / USB / UART / MQTT / LTE-M) + ACK
        ▼
[Companion Client / Edge Gateway / Ingestion Collector]
  • Authenticates device, enforces per-device byte/rate quota, strips link metadata
  • Matches frame Build-ID -> detokenizes strings & symbolizes PC/LR via ELF/DWARF
  • Anchors (boot_id, mono_tick) -> UTC and bridges 16-bit cmd_seq -> W3C trace_id
        │
        ▼
[Unified Debugging & Observability Views]
  • Perfetto (.pftrace) / JSONL causal timeline (Cloud RPC -> App -> BLE -> MCU ISR)
  • Bounded fleet health metrics (crash-free sessions %, brownout rate, stack peak)
```

---

## 2. Firmware & Constrained-Device Design Checklist (`SPEC-NNNN` Contracts)

When specifying telemetry for firmware, embedded Linux, or IoT/wearable/automotive
devices, lock these nine invariants explicitly:

| Dimension | Failure Mode Without Spec | First-Principles Requirement (`REQ-*` / `INV-*`) |
| --- | --- | --- |
| **1. String Elimination** | `printf` format strings consume `40 KiB` Flash and stall ISR for `2 ms` at `115200` baud | Strip format strings to `.elf` non-loadable section at compile time; transmit `[token_u32, varint_args...]` (`<= 16 B`). |
| **2. Build-ID Binding** | Firmware `v1.2.1` frame decoded with `v1.2.0` table produces silent garbage values | Embed immutable `Build-ID` (`8–20 B`) in every boot/crash header; reject or quarantine unmatched detokenization. |
| **3. Watchdog Survival** | Hardware watchdog resets hung MCU, wiping SRAM and erasing all clues of what deadlocked | Keep flight-recorder ring + `last_active_task_pc` in `.noinit` RAM with `CRC32`; harvest on boot when `reset_reason == WATCHDOG`. |
| **4. Safe Fault Handler** | Crash handler calls RTOS mutex, `malloc`, or async flash driver inside `HardFault_Handler` and double-faults! | Fault path runs polling-only, stack-bounded, interrupts masked, writing only to `.noinit` RAM or reserved panic flash sector. |
| **5. Key-RAM Scrubbing** | Full SRAM coredump inadvertently uploads AES/TLS private keys or user PINs in stack/bss | Link sensitive crypto/credential buffers into a dedicated `.secrets_ram` linker section **excluded** from coredump regions (`INV-*`)! |
| **6. Flash Wear Cap** | Boot-looping unit writes a `16 KiB` coredump every `2 s`, destroying NOR flash in `6 hours` | Enforce monotonic flash-write token bucket (e.g., max `5` full coredumps per `24 h`; increment compact boot-loop counter thereafter). |
| **7. Clockless Ordering** | Device boots with dead coin-cell (`t = 0`), events arrive out of order in cloud DB | Key telemetry by `(device_pseudo_id, boot_count, mono_tick)`; bind to wall-clock UTC only via explicit sync-anchor records. |
| **8. Store-and-Forward Priority** | Verbose debug trace fills `64 KiB` flash buffer and drops the critical HardFault coredump | Partition separate ring quotas by priority (`Partition 0: Crash/Reset/Security` never overwritten by `Partition 2: Trace`). |
| **9. XIP Flash-Erase Stall** | Writing telemetry to internal MCU NOR flash stalls `XIP` instruction fetch for `40 ms`, dropping motor/radio ISRs | Buffer in SRAM/FRAM on active paths; flush to internal flash only in safe idle/shutdown windows or external non-XIP storage. |

---

## 2.5 Retrieval Mechanics & Backend Reuse-vs-Build Matrix (`ADR-NNNN` Input)

Select the lightest off-device pipeline that satisfies physical connectivity,
detokenization, retention, and cost constraints:

| Option | Architecture | Choose When | Disqualifiers (`Why Not`) |
| --- | --- | --- | --- |
| **1. Pure Existing Stack** | Native `OTLP` / `JSONL` / standard minidump -> existing Collector & TSDB/Trace/Crash store | Cloud services, CLIs, desktop/mobile apps with IP connectivity and standard symbolication | Cannot parse `4 B` custom MCU tokenized frames, `CAN UDS` records, or custom `.noinit` register layouts natively. |
| **2. Thin Edge Detokenizer + Existing Backend** *(Default for firmware)* | Device binary chunks -> **Stateless Detokenizer/Symbolizer Service** (keyed by `Build-ID` `.elf`) -> emits standard `OTLP` / Wide Events / `Perfetto` into existing backend | BLE/MQTT/USB/gateway-connected firmware needing compact on-device RAM/wire format without maintaining custom DBs or UI dashboards | Air-gapped sites where external SaaS is forbidden, or ultra-high-volume raw waveform/sensor streams exceeding observability SaaS budgets. |
| **3. Project-Specific Telemetry Store** | Device/Client -> Custom Ingest API -> Columnar/Object Store (`ClickHouse`, `DuckDB`/`Parquet`, `TimescaleDB`, or embedded `SQLite` field tool) + domain workflow hooks | Air-gapped/defense/medical appliances; field-technician offline USB/CAN service tools; `100k+` device fleets with domain-coupled OTA rollback / RMA automation or `10–100x` SaaS cost gap | High maintenance burden if built merely out of NIH when Option 1 or 2 satisfies every `REQ-NNNN`. |

---

## 3. Canonical Wide Event / Root Span Blueprint (Services & Rich Clients)

For Tier B/C systems (backends, desktop/mobile apps, CLIs), initialize one context
record per unit of work and flush **once** at completion:

| Field Group | Canonical Keys | Rule |
| --- | --- | --- |
| **Identity & Build** | `trace_id`, `span_id`, `service` / `app_id`, `build_id`, `boot_id` (clients) | Fresh `trace_id` at untrusted public ingress (link external `traceparent` via Span Link). |
| **Work & Outcome** | `operation` (`ota.apply`, `orders.capture`), `outcome`, `error.code`, `retryable` | Bounded enums/templates only — never raw URLs or unstructured exception prose! |
| **Critical-Path Timing** | `duration_ms` (or `duration_us`), `cpu_time`, `io_wait`, `db_ms`, `lock_wait_ms` | Separates compute vs. lock contention vs. I/O stall in a single record. |
| **Volume & Watermarks** | `items`, `bytes_in`, `bytes_out`, `retries`, `dropped_events`, `sample_rate` | Preserves unbiased aggregate math under sampling and exposes saturation early. |
| **Pseudonymous Scope** | `tenant_id`, `actor_pseudo_id` / `device_pseudo_id`, `hw_rev`, `feature_flags` | Surrogate or rotating-salt HMAC IDs only — zero raw PII, MACs, serials, or secrets! |

---

## 4. Unified Trace Debugging Playbook (1-Pass Root-Cause Isolation)

Convert every substrate's flight-recorder output (`Segger RTT` / `SWO` / UART
detokenized binary frames, local CLI/test `TRACE_DUMP=bug.jsonl`, and cloud spans)
into a common trace schema (**Perfetto `.pftrace` / Chrome `traceEvents` JSON /
JSONL**) so one methodology debugs everything:

| Symptom | What the Unified Trace Reveals Immediately | Required Instrumentation Seam |
| --- | --- | --- |
| **Firmware watchdog / brownout reset** | `.noinit` pre-reset trace shows radio TX burst coinciding with `vbat_mv` droop + SPI flash erase stall | `reset_reason`, `vbat_mv` min watermark, ISR/task switch trace tokens in `.noinit` ring |
| **BLE / USB command feels laggy (`400 ms`)** | Companion app waited `380 ms` on BLE connection interval before MCU `cmd_seq` span ran in `2 ms`! | Shared `cmd_seq` bridging mobile span -> firmware span + BLE connection-interval attribute |
| **Backend N+1 or pool starvation** | `180 ms` gap before first DB span (`pool.acquire` stall) or `200` serial `1.5 ms` query spans | `pool.acquire` / `mutex.wait` spans (`> 1 ms`) + parameterized `db.query.hash` |
| **Flaky integration / HIL (Hardware-in-Loop) test** | Test fails assertion; attached `.jsonl`/`.pftrace` artifact shows exact state-machine edge & timeout race | Automatic flight-recorder dump on test failure (`0` extra print-rerun cycles!) |

---

## 5. Privacy & Security Guardrail Matrix (`specs-tools` Handoff)

| Threat | Invariant (`INV-*`) | Deterministic Structural Check (`specs-tools`) |
| --- | --- | --- |
| **Keys/PINs in logs or coredumps** | Zero credentials, keys, or raw PII in any log, span, or RAM dump region | `Secret<T>`/`Redacted<T>` types + linker script `.secrets_ram` exclusion check + canary test |
| **Hardware/Location PII tracking** | Zero raw MAC, IMEI, serial, or Wi-Fi BSSID/GPS in operational telemetry | Schema allowlist + rotating enrollment token decoupled from user account table |
| **Flash wear / Storage DoS** | Telemetry writes cannot exceed daily flash-erase or collector-quota budget | Unit/HIL fault-loop test asserting flash write limiter trips after `N` dumps; gateway rate limit |
| **ROM bloat / ISR stall** | Zero runtime format-string literals or heap allocs in firmware trace macros | ELF section-size budget check + banned `snprintf`/`malloc` AST check in `isr/` & `trace/` paths |
| **Metric cardinality explosion** | Metric labels accept only statically bounded enums (`<= 200` combinations) | Compile-time enum wrapper API for metrics; dynamic strings rejected by compiler/linter |
