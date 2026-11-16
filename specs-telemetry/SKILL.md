---
name: specs-telemetry
description: >-
  Telemetry, observability, and trace-debugging design for the SPECS suite,
  from firmware (tokenized logs, crash-survivable ring buffers, flash and
  battery budgets) to mobile, desktop, CLI, and cloud services (wide events,
  bounded metrics, sampling, traces), with privacy-safe diagnostics. Use when
  specifying or auditing logging, metrics, tracing, crash reporting, or
  diagnostic data.
last_updated: 2026-11-15
---

# First-Principles Telemetry, Privacy & Trace Debugging (`specs-telemetry`)

Designs and audits **telemetry as a bounded physical and architectural contract**
before code is written — from `16 KiB`-SRAM client microcontrollers running in ISR
context over BLE/UART/CAN, up to battery-powered mobile/desktop apps, CLIs, and
high-throughput distributed backends.

> **Purpose-first, substrate-neutral rule:** Specify telemetry by **observer-effect
> budgets (cycles, RAM, flash erase endurance, battery/radio duty cycle, bytes),
> event/span schemas, redaction invariants, and causal correlation contracts** —
> never by assuming infinite bandwidth, wall-clock NTP, JSON strings, or a single
> vendor SDK. Present concrete mechanisms (`e.g., compile-time string tokenizers
> like pw_tokenizer/defmt, CBOR/Protobuf, W3C Trace Context, OpenTelemetry,
> Perfetto .pftrace`) strictly as target-matched examples.

Consult [references/telemetry-patterns-and-schemas.md](references/telemetry-patterns-and-schemas.md)
for substrate tier selection (`Firmware/RTOS` vs. `Client/CLI` vs. `Cloud`),
retrieval-path & backend build-vs-reuse matrices, `.noinit` crash-survivable
flight recorders, canonical wide-event schemas, and privacy/security guardrails.

Telemetry budgets, event schemas, and redaction invariants written into `docs/`
(spec, design, or ADR) are **technical documents that people read to make a
decision**: when **drafting or restructuring a technical document** or
**checking a draft before human review**, apply any available
technical-document writing skill alongside the `specs` Document Quality &
Reviewability Standard.

---

## 0. Pre-Design Intake: Constraints, Retrieval Path & Backend Reuse vs. Build

Never prescribe a telemetry format or backend before locking four physical facts:

1. **Memory, Storage & Execution-Context Constraints:**
   * **RAM & NVS budget:** Exact bytes available for volatile ring buffers (`512 B`
     vs. `64 KiB` vs. `16 MiB`), `.noinit`/backup-SRAM presence, and non-volatile
     sector geometry/endurance.
   * **Latency & `XIP` flash-stall hazards:** Identify whether events fire inside
     `NMI`/fast `ISR` (`< 1 µs`, lock-free), real-time control loops, or worker
     threads — and check whether erasing/writing internal Flash stalls CPU
     instruction fetch (**Execute-in-Place `XIP` stall**, which blocks interrupts
     for `10–100 ms` unless deferred to idle or written to external non-XIP
     QSPI/SPI flash or FRAM!).
2. **How Telemetry Is Retrieved & Stored Off-Device:**
   * **Physical Bench / RMA Pull (Air-Gapped):** `JTAG/SWD` (`RTT`/`SWO`), `UART`
     dump, `USB` CDC/MSC, `CAN` UDS (`ISO 14229` DTCs), NFC/optical tap, or SD card.
   * **Companion / Proxy Courier:** Opportunistic pull over `BLE GATT`, `USB`, or
     `Wi-Fi SoftAP` via a mobile/desktop app or service laptop (firmware needs
     zero IP/TLS stack — companion app authenticates and forwards!).
   * **Field-Bus / Edge Concentrator:** `CAN` / `RS-485` / `Thread` / `LoRaWAN` ->
     local gateway -> backend.
   * **Direct IP Stream:** `MQTT` / `CoAP` / `HTTPS` / `OTLP` directly to collector.
3. **Telemetry Backend: Reuse Existing vs. Thin Adapter vs. Project-Specific (`specs-adr`):**
   * **Default — Reuse existing backend:** Use standard collectors + existing
     metrics/logs/traces/crash stores (or an embedded fleet diagnostics platform)
     whenever standard OTLP/minidump/wide-event ingestion fits.
   * **Preferred hybrid for constrained devices — Thin Stateless Ingest &
     Detokenizer Gateway -> Existing Backend:** Build *only* a small stateless
     edge adapter (`~300–600 LoC`) that authenticates devices, enforces quotas,
     detokenizes binary frames + symbolizes coredumps against `Build-ID` `.elf`
     files, anchors `(boot_id, mono_tick)` to UTC, and forwards standard OTLP /
     wide events / Parquet into your existing observability store!
   * **Build a project-specific telemetry backend ONLY when concrete constraints
     disqualify existing stacks** (record via `specs-adr` with explicit
     disqualifiers: air-gapped/on-prem/classified mandate, byte-billed satellite/
     LoRa/CAN-UDS custom transport, fleet cardinality/retention economics where
     generic SaaS per-span pricing exceeds columnar object/ClickHouse/DuckDB
     storage by `10–100x`, or closed-loop domain workflows such as automated
     RMA/warranty/OTA-rollback state machines driven directly by fault signatures).

---

## 1. Law 1 — Bound the Observer Effect (Never Break What You Measure)

Instrumentation that alters real-time control timing (`printf` over slow UART
causing a race to vanish or a watchdog to trip!), blocks a caller when a collector
is unreachable, drains a client battery, or wears out flash sectors is a **system
defect**:

1. **$O(1)$, Allocation-Free, Non-Blocking Hot Path:**
   * Recording a trace point or metric on a hot path (interrupt handler `ISR`,
     real-time control/audio/render loop, or `p99` RPC) **must** execute in bounded
     time with **zero dynamic heap allocation** and **zero blocking I/O**.
   * **Drop, never block:** When a ring buffer or egress queue fills, overwrite the
     oldest low-priority slot (or drop the new event) and atomically increment a
     `dropped_events` counter so telemetry loss is explicitly visible without
     stalling execution.
2. **Budget Physical Resources Explicitly in `SPEC-NNNN`:**
   * **CPU & ISR latency ceiling** (e.g., `<= 50 cycles` per trace event in ISR).
   * **RAM & Non-Volatile Storage endurance:** Bound ring-buffer SRAM bytes and
     **rate-limit non-volatile Flash/EEPROM writes** (e.g., max `N` coredump/metric
     flushes per day + wear-leveled circular sectors so a crash loop cannot burn
     through `10,000` NOR flash erase cycles in an hour!).
   * **Energy & Link MTU:** Piggyback client/firmware uploads onto existing radio
     wake windows (`BLE`, cellular, Wi-Fi), sizing frames to link MTU (`20–244 B`
     BLE, `8/64 B` CAN, metered LTE-M) rather than waking radios for chatty heartbeats.

---

## 2. Law 2 — Match Wire Encoding to the Substrate (Tokenized Binary -> Wide Events)

Never format human ASCII strings on constrained or real-time hot paths:

| Substrate Tier | Hot-Path Encoding Contract | Why |
| --- | --- | --- |
| **Tier A: Firmware / Bare-Metal / RTOS / Hard Real-Time** | **Compile-time Deferred Tokenization + Varints** (strip format strings & file/line names into an off-target `.elf` / token DB section keyed by **Build-ID**; emit only a `16/32-bit` token ID + raw binary args, e.g., `pw_tokenizer`, `defmt`). | Cuts ROM/Flash footprint by `50–80%`, reduces `100 B` string logs to `4–12 B` binary frames, runs in `< 1 µs` without `snprintf`, and avoids leaking readable internal symbols on physical bus sniffing. |
| **Tier B: Mobile / Desktop / Edge / High-Rate Streams** | **Compact Binary Frames** (CBOR, Protobuf, FlatBuffers, binary ring buffers) batched & compressed for store-and-forward upload. | Minimizes battery, mobile data, and local SQLite/disk churn while preserving strict field types. |
| **Tier C: Cloud Services & Standard CLIs** | **Canonical Structured Wide Events** (`JSON`/`JSONL`/`OTLP`) — accumulate context in memory and flush **1 structured wide event / root span** per unit of work in `defer`/`finally`. | Eliminates scattered unstructured text logs while supporting instant high-cardinality slicing in log/trace stores. |

* **Mandatory `build_id` stamp:** Every crash dump, tokenized frame batch, or wide
  event **must** carry the exact immutable **Build-ID** (e.g., ELF `.note.gnu.build-id`,
  Mach-O UUID, or commit digest) so off-device detokenizers and symbolicators never
  mis-decode frames across firmware/app versions!

---

## 3. Law 3 — High-Signal Event Taxonomy & Cardinality Control

Whether on an MCU or a cloud cluster, delete routine polling chatter and instrument
**five high-signal classes**:

1. **Unit-of-Work / Command Summaries (Canonical Wide Event or Compact Record):**
   * `1` record per RPC, job, CLI command, or firmware command/OTA/sensor cycle:
     operation enum, outcome (`ok` | `client_err` | `fault` | `timeout`), compact
     `error_code` enum, duration, retry/CRC-error count, and work volume.
2. **Boot, Reset-Reason & Hardware/OS Fault Forensics:**
   * Record hardware **Reset-Reason register** at every boot (`Power-On`,
     `Brownout/Supply-Droop`, `Hardware Watchdog`, `Software Panic/Assert`, `Pin
     Reset`, `OTA Rollback` + active `A/B` slot), plus compact **fault state** on
     crash (PC, LR, SP, fault status registers like ARM `CFSR`/`HFSR`/`BFAR` or
     RISC-V `mcause`/`mepc`, active task ID, and pruned stack/register minidump).
3. **Saturation, Health Watermarks & Drop Counters (`USE` + `RED`):**
   * Track high-water marks rather than noisy per-tick logs: per-task **stack
     high-water mark**, heap/pool peak, max ISR/main-loop latency, queue/DMA/UART
     overrun counts, flash wear/bad-block counters, battery internal-resistance /
     voltage droop under load, radio `RSSI`/`SNR`/retransmits, and `dropped_events`.
4. **Domain Invariant (`INV-NNNN`) & Degraded-Mode Transitions:**
   * Calibration out-of-bounds, watchdog pre-bark warning, sensor bus recovery,
     circuit-breaker open, or stale-cache fallback.
5. **Security & Trust-Boundary Audit Events (Isolated Retention):**
   * Secure-boot / OTA signature failures, debug-port (`JTAG`/`SWD`) unlock events,
     key rotation/provisioning, auth denials, and support break-glass access
     (`specs-gtm`).

* **Strict Metric vs. Event Cardinality Split:** Keep time-series counters/histograms
  on **statically bounded enums/integers** (`<= ~200` series per metric; compact
  integer metric IDs on firmware). Put high-cardinality IDs (`device_pseudo_id`,
  `tenant_id`, `request_id`) in **Events/Spans**, bridging spikes via **Exemplars**.

---

## 4. Law 4 — Crash-Survivable Flight Recorders, Clock Anchors & Trace Debugging

Traces turn days of blind hardware/cloud guesswork (and timing-altering `printf`
heisenbugs!) into 1-pass root-cause isolation:

1. **Monotonic Hardware Time + Retroactive UTC Anchoring:**
   * Never trust wall-clock RTC at boot or across NTP/BLE jumps. Stamp spans and
     events with `(boot_id, monotonic_ticks)` (`64-bit rollover-extended
     DWT->CYCCNT`, `mtime`, `CLOCK_MONOTONIC`). Emit a
     `ClockSyncAnchor { boot_id, mono_tick, utc_ns }`
     event whenever a companion phone, GNSS, or NTP syncs so ingestion pipelines
     reconstruct exact UTC timelines retroactively!
2. **Crash-Survivable In-Memory Flight Recorder (`.noinit` RAM -> Flash / Dump):**
   * Continuously record ultra-cheap micro-spans (IRQ entry/exit, state-machine
     edges, bus transactions, lock waits, RPC hops) into a fixed-size circular ring
     buffer.
   * **On firmware/embedded devices:** Place the ring buffer in **uninitialized
     retention RAM (`.noinit` / backup SRAM)** guarded by a magic word + `CRC32`.
     When a hard fault or hardware watchdog resets the MCU, the bootloader/next
     boot validates the `.noinit` CRC, packages the pre-reset trace + fault
     registers into a wear-budgeted flash crash slot, and queues it for
     **store-and-forward** upload (acknowledging before erase!).
   * **On servers, desktop, mobile & CLIs:** Keep the per-task/process ring buffer
     in RAM (`0` I/O cost when healthy) and flush **only** on error, latency breach,
     hang, crash, or user `"Export Diagnostics"` / `--trace-dump`.
3. **Cross-Boundary Causal Trace Bridging (Cloud <-> Mobile/Host <-> Firmware):**
   * Propagate `128-bit` W3C `traceparent` across HTTP/gRPC/SQL (`/*traceparent*/`)
     and **Span Links** across async queues.
   * Across constrained buses (`BLE`, `USB`, `UART`, `CAN`), propagate a compact
     `16/32-bit` **command correlation ID** (`cmd_seq`) and have the host/companion
     gateway stitch decoded firmware ring-buffer spans under the originating client/
     cloud `trace_id` — exporting a **single unified timeline** (e.g., **Perfetto
     `.pftrace` / Chrome Trace JSON / JSONL**) for 1-pass human and agent debugging!

---

## 5. Law 5 — Privacy & Security by Construction (Devices to Cloud)

1. **Hardware & Location Identifiers Are Sensitive PII (`specs-gtm`):**
   * Raw BLE/Wi-Fi MACs, serial numbers, IMEI/ICCID, nearby Wi-Fi BSSIDs / cell
     towers (precise geolocation!), and raw physiological/audio streams are personal
     data. Correlate via **rotating/pseudonymous enrollment IDs** or salted HMACs
     decoupled from customer identity so GDPR Right-to-Erasure never requires
     rewriting immutable archives or reflashing hardware.
   * Wrap keys, PINs, Wi-Fi PSKs, tokens, and PII in `Secret<T>` / `Redacted<T>`
     types so neither structured loggers nor binary fault stack dumps leak secrets
     (scrub or exclude crypto key buffers from coredump RAM regions!).
2. **Harden Ingress, Consent & Physical Extraction:**
   * **Default opt-in** for client/device usage telemetry (separating minimal
     safety-critical fault diagnostics where legally disclosed; honoring offline/
     air-gapped & `DO_NOT_TRACK=1` modes).
   * Authenticate device uploads, enforce **per-device rate/byte quotas** at the
     gateway (preventing one rogue/faulty unit from flooding fleet ingestion),
     ignore untrusted external `sampled=1` / `baggage` headers, and escape control/
     ANSI bytes against log/terminal injection.
