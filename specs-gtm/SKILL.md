---
name: specs-gtm
description: >-
  Go-to-market constraints for the SPECS suite: turns commercial, regulatory,
  privacy and AI-data-use, licensing, SLO, support, and app-store or
  marketplace requirements into specs, ADRs, guardrails, and store-submission
  packs. Use early when scoping the commercial or distribution model of a
  product, and before launch when preparing policies, certifications, or App
  Store and Google Play listings.
last_updated: 2026-11-15
---

# SPECS Go-To-Market, Compliance & Marketplace Synthesis (`specs-gtm`)

Prevents the two classic GTM engineering failures:

1. **Late discovery of one-way architectural doors** — finding out at launch
   that GDPR erasure breaks immutable event logs, an `AGPLv3` or `CC-BY-NC`
   dependency poisons commercial distribution, `99.95%` SLA forbids table-locking
   migrations, or Apple/Google reject the app for missing full account deletion,
   16 KB native page alignment, or a reviewer demo-account bypass.
2. **Policy-to-code & store-disclosure drift** — shipping boilerplate Privacy
   Policies, App Store Nutrition Labels, Play Data Safety forms, or screenshots
   that contradict what the codebase, SDKs, and UI actually do.

> **Legal boundary (mandatory):** Frame all generated legal, privacy, terms, and
> regulatory mappings explicitly as **engineering-verified factual inputs and
> structural drafts for review by qualified legal/compliance counsel**, never as
> standalone legal advice.
>
> **Language & tool neutrality (mandatory):** Applications span every language,
> UI toolkit, and runtime. Express every requirement (`REQ-*`), invariant
> (`INV-*`), and publishing workflow by its **purpose and observable contract**,
> never by mandating a specific third-party tool; mention concrete tools strictly
> as optional stack-matched examples (`e.g., ...`).

Consult [references/marketplace-and-compliance.md](references/marketplace-and-compliance.md)
for the 6-pillar architectural impact matrix, App Store / Play Store / Web &
Cloud Marketplace checklists, character-limit budgets, and deterministic
screenshot-pipeline layout.

---

## Choose the Operating Mode

Detect which mode fits the current project stage (or run Mode A -> Mode B across
the project lifecycle):

| Mode | When to Run | Primary Output |
| --- | --- | --- |
| **Mode A: Upstream Architectural Intake** | Early product/feature scoping (alongside `specs`, `specs-grill`, `specs-adr`) before schemas, dependencies, and auth harden | `docs/specs/gtm-constraints/spec.md` (`REQ-*`, `INV-*`), one-way-door ADRs via `specs-adr`, and guardrail handoff to `specs-tools` |
| **Mode B: Code-Grounded Launch & Store Pack** | Pre-release, certification prep, or marketplace submission on an existing codebase | Policy-vs-code gap audit + `docs/gtm/*` governance inputs + versioned `store/*` listings, disclosures, screenshot shot-plan, and reviewer notes |

All Markdown specs, ADRs, runbooks, and policy inputs produced by this skill are
**technical documents that people read to make a decision** — apply plain
English for international or non-native readers, activate any available
technical-document writing skill, and obey the `specs` Document Quality &
Reviewability Standard before human review.

---

## Mode A: Upstream Commercial & Marketplace Architecture Synthesis

### 1. Ground Reality & Scope Only Relevant Channels

Read `GLOSSARY.md`, `docs/adrs/index.md`, `docs/specs/index.md`, the project's
dependency, build, and platform manifests (whatever language or packaging system
the repo uses), and any existing `docs/gtm/` or `store/` directories.

Skip irrelevant questions immediately (never ask mobile IAP questions on a pure
CLI/backend tool, or multi-tenant RLS questions on an offline single-user app).

### 2. Interrogate the 6 High-Reversal-Cost GTM Pillars

Walk the unresolved pillars concisely (leading each question with a grounded
`(Recommended)` default):

1. **Distribution & Marketplace Channels:**
   * Where does this ship? *(Web SaaS, Apple App Store, Google Play, desktop
     stores/notarized installers, OS package repos, browser extension stores,
     cloud/B2B app marketplaces, Self-Hosted/BYOC/SDK/CLI)*.
   * **Marketplace architectural hooks:**
     * *Account lifecycle:* If users can create accounts, Apple (`5.1.1(v)`) and
       Google Play mandate **full in-app account + data deletion** (not soft
       deactivation), and Google Play additionally mandates a **public web
       deletion URL** usable after uninstall. Third-party social login on iOS
       requires **Sign in with Apple** (`4.8`) including token revocation.
     * *Monetization seam:* Digital goods/subscriptions inside mobile store apps
       must route through a clean billing adapter supporting the store's native
       in-app purchase API, server-side entitlement verification, and purchase
       restoration (e.g., StoreKit on Apple platforms, Play Billing on Android),
       unless an explicit reader/B2B/multi-platform exemption holds.
     * *Target locales & lightweight i18n tier:* Lock launch markets, scripts
       (`LTR` only vs. `RTL` / CJK), currencies, and store-listing locales
       upfront — selecting the **lightest `specs` i18n tier** (`Tier 0` Unicode-
       clean single-locale, `Tier 1` compile-time static catalogs, `Tier 2` data-
       sliced multi-script/RTL, or `Tier 3` OTA bundles) to avoid both one-way
       schema debt and heavyweight runtime bloat.
     * *Deterministic Screenshot Seed & Reviewer Sandbox:* Build a non-PII
       **demo/fixture seed mode** (for reproducible localized store screenshots)
       and an isolated **Reviewer Sandbox Account** (with scoped OTP/MFA/hardware
       bypass so human store reviewers can log in and test every gated screen).
2. **Privacy, Residency & Data/AI-Use Policy:**
   * What data classes enter the system (`PII`, `PHI`, `PCI`, customer source/IP,
     telemetry)? Which jurisdictions apply (`GDPR`, `UK GDPR`, `CCPA/CPRA`,
     sector rules)?
   * **Architectural impact:** Retention TTLs on every PII store; erasure
     strategy when using immutable logs/backups (**crypto-shredding** via
     per-subject/per-tenant keys vs. strict PII pointer table); regional data
     residency (`EU` vs `US` cells); customer data & AI policy (**zero-data-
     retention** LLM endpoints, opt-out from model training/analytics, explicit
     sub-processor inventory).
3. **Security Posture & Target Certifications:**
   * Target bar: *Baseline / Enterprise Security Questionnaire / SOC 2 Type II /
     ISO 27001 / HIPAA / PCI-DSS*?
   * **Architectural impact:** **Scope isolation first** (tokenize/offload PCI
     or PHI at the edge so core services stay out of scope); mandatory
     `TenantContext` / RLS isolation; enterprise SSO (OIDC/SAML), SCIM, MFA;
     tamper-evident **security audit log** (distinct from debug logs) capturing
     actor, tenant, target, reason, and before/after state.
4. **IP Protection, Trade Secrets & Licensing:**
   * Outbound model: *Proprietary SaaS, Proprietary Distributed Binary/SDK/App,
     Open-Core, or Permissive OSS*?
   * **Architectural impact:** Explicit inbound **SPDX license allow/deny policy**
     (e.g., banning `AGPL-3.0*` in networked SaaS; banning `GPL*` and static
     `LGPL*` in proprietary mobile/desktop binaries; banning `CC-BY-NC*` or
     non-commercial model weights/fonts/datasets in commercial products). If
     shipping client/on-prem binaries, keep crown-jewel algorithms, keys, and
     proprietary weights behind a server boundary or signed entitlement check.
5. **SLOs, SLAs, Disaster Recovery & Blast Radius:**
   * Target availability (`99.0%` vs `99.9%` vs `99.99%`), latency (`p95`/`p99`),
     and `RPO` / `RTO`?
   * **Architectural impact:** Zero-downtime **expand-contract** schema
     migrations; idempotency keys + bounded retries/timeouts; **per-tenant rate
     limits & bulkheads** (preventing one tenant from burning shared error
     budgets); user-journey SLI metrics at public module seams.
6. **Supportability, Break-Glass & Offboarding:**
   * How does support debug a customer failure without raw production DB/SSH
     access?
   * **Architectural impact:** Customer-visible correlation/`trace_id` on errors;
     redacted diagnostic read views and flight-recorder/trace bundles
     (`specs-telemetry`, keeping opt-in client/CLI telemetry and zero-PII logs
     aligned with GDPR erasure); dual-logged, time-boxed **support impersonation /
     break-glass** tokens; idempotent usage/seat metering; full tenant **data
     export & offboarding** path.

### 3. Synthesize Artifacts & Wire Guardrails

1. Write `docs/specs/gtm-constraints/spec.md` (`SPEC-NNNN`) capturing concrete,
   falsifiable `REQ-NNNN` and `INV-NNNN` across the active pillars (update
   `docs/specs/index.md` and `GLOSSARY.md` terms).
2. For each choice passing the `specs` 3-Gate Filter (hard to reverse,
   surprising without context, real trade-off), record a focused ADR via
   **`specs-adr`**.
3. Hand off to **`specs-tools`** to enforce those constraints structurally (SPDX
   license gate, migration/PII/tenant linters, 16 KB ELF / manifest checks,
   screenshot smoke runner, and cold-diff `privacy-compliance-reviewer`,
   `slo-operability-reviewer`, or `store-readiness-reviewer` gates).

---

## Mode B: Code-Grounded Policy, Certification & Store Publishing Pack

### 1. Audit Code Reality First (Zero Unverified Claims)

Before drafting any external policy, disclosure form, or store listing, inspect
the repository to extract **ground truth**:

* **Data & SDK inventory:** All DB schemas/migrations, analytics/crash/ads/AI
  SDKs, outbound network domains, cookie/storage keys, and retention/deletion
  code paths.
* **Dependency & asset licenses:** Lockfiles, vendored code, fonts, icons, and
  ML weights/datasets.
* **Permissions & binary traits:** Requested OS/runtime permissions, privacy
  manifests, native binary alignment/signing traits, extension host permissions,
  and OAuth scopes across target platforms (e.g., iOS `Info.plist` /
  `PrivacyInfo.xcprivacy`, Android `AndroidManifest.xml` / 16 KB `.so` page
  alignment, browser `manifest.json`).
* **Auth, deletion & billing flows:** Sign-in providers, in-app + web deletion
  endpoints, store/web billing adapters, and demo/seed fixtures.

### 2. Report Blocking Readiness Gaps First

Present a **Go / No-Go Gap Table** separating:
* **`BLOCKING` store/regulatory rejections** (e.g., soft-delete instead of real
  account purge, missing web deletion URL for Play Store, undeclared SDK tracking
  in platform privacy disclosures, copyleft library linked into a proprietary app
  binary, unaligned native shared libraries, or missing reviewer demo bypass).
* **`DRIFT` warnings** where desired GTM claims exceed current code behavior.

### 3. Generate Version-Controlled Governance & Store Artifacts

After confirming target paths with the user, generate only the artifacts needed
for this product's channels (default `docs/gtm/` and `store/`, adapting to any
existing store-sync layout the repo already uses):

1. **Governance & Enterprise Trust Pack (`docs/gtm/`):**
   * `data-inventory-and-subprocessors.md`: Table of every personal/customer data
     element, purpose, storage location, encryption, TTL, deletion path, and
     third-party sub-processor (verified in code).
   * `privacy-and-data-use-inputs.md`: Engineering-accurate inputs for Privacy
     Policy, Cookie/SDK disclosure, Customer Data & AI-Training/ZDR Policy, and
     DPA Annexes *(marked as factual engineering draft for legal review)*.
   * `security-and-compliance-matrix.md`: Control mapping (SOC 2 TSC / ISO 27001
     Annex A / GDPR Art. 25 & 32 / HIPAA) pointing each control to concrete repo
     files, CI checks, and operational runbooks.
   * `slo-and-support-playbook.md`: User-journey SLIs/SLOs, error-budget policy,
     RPO/RTO backup-restore verification, customer support tiers, and audited
     break-glass procedure.
   * `NOTICE` / `third-party-licenses.md`: Complete attribution & SPDX summary.
2. **Marketplace Listing & Asset Pack (`store/`):**
   * **Character-verified listing copy** (obeying exact store byte/char caps in
     [references/marketplace-and-compliance.md](references/marketplace-and-compliance.md)):
     App Name/Title, Subtitle / Short Description, Promotional Text, Keywords,
     Full Description, Release Notes, Category, Age/Content Rating inputs, and
     required public URLs (Privacy Policy, Support, Marketing, Web Account
     Deletion).
   * **Code-matched store privacy & permission disclosures:**
     Platform privacy questionnaires and manifests mapped from actual code/SDKs
     (e.g., Apple Nutrition Labels + `PrivacyInfo.xcprivacy`, Google Play Data
     Safety answers) plus per-permission reviewer justifications.
   * **Screenshot & Preview Video Production Spec (`store/screenshots-plan.md`):**
     Ordered 5–8 frame narrative per required device/viewport class, specifying
     for each frame:
     1. Exact value proposition headline (`<= 6` words, localized);
     2. Real in-app route/screen + deterministic `demo-seed` fixture state (clean
        normalized system status bar, realistic synthetic data, zero third-party
        trademarks or PII);
     3. Automated UI-capture target driving the app's presentation layer across
        required viewports and locales (using whatever UI automation harness fits
        the stack, e.g., native UI test runners, headless browser runners like
        Playwright, desktop framebuffer scripts, or mobile wrappers like Fastlane).
   * **App Review Packet (`store/review-notes.md`):** Non-expiring demo account
     credentials, reviewer sandbox trigger steps, hardware/geofence/MFA test
     instructions, and concise justification for any sensitive entitlement or
     background mode.
