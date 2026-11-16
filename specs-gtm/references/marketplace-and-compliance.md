# Marketplace, Regulatory, IP & Operability Reference (`specs-gtm`)

## 1. Marketplace Submission & Rejection-Trap Matrix

Verify every applicable row before locking mobile, desktop, extension, or B2B
marketplace architecture:

| Channel | Hard Architectural & Binary Mandates | Metadata, Disclosure & Asset Mandates |
| --- | --- | --- |
| **Apple App Store (iOS / iPadOS / macOS)** | • **Guideline 5.1.1(v):** Full in-app account & personal-data deletion (not deactivation) + Sign in with Apple token revocation.<br>• **Guideline 4.8:** Sign in with Apple required if any third-party social login is offered (unless pure enterprise/education/client-specific login).<br>• **Guideline 3.1.1:** Digital goods/unlocks use StoreKit 2 + "Restore Purchases" button (unless reader/multi-platform/B2B rule applies).<br>• **Privacy Manifest:** Bundled `PrivacyInfo.xcprivacy` declaring Required-Reason APIs, collected data, and tracking domains across app + all third-party SDKs.<br>• **ATT:** `ATTrackingManager` prompt before cross-app tracking; full functionality if user declines. | • **Name:** `<= 30` chars<br>• **Subtitle:** `<= 30` chars<br>• **Promotional Text:** `<= 170` chars<br>• **Keywords:** `<= 100` chars (comma-separated, no spaces, no competitor brands, don't repeat Name/Subtitle words)<br>• **Description:** `<= 4000` chars (plain text; no unverified rankings or prices that vary by region)<br>• **Screenshots:** Up to `10` per locale; mandatory `6.9"` (or `6.5"`) iPhone + `13"` iPad if universal; must depict real in-app UI (`2.3.3`).<br>• **URLs & Review:** Live Privacy Policy URL, Support URL, non-expiring demo credentials + instructions in App Review Information. |
| **Google Play Store (Android)** | • **Dual-path Account Deletion:** In-app account + data deletion **AND** a public web link allowing deletion requests without reinstalling.<br>• **16 KB Native Page Size:** Every bundled `.so` native library (including transitive NDK/engine SDKs) aligned to `16 KB` (`-Wl,-z,max-page-size=16384`, NDK r28+).<br>• **Target API & Scoped Permissions:** Meets Play `targetSdk` floor; uses Android Photo Picker / narrow permissions instead of broad storage/background location unless core to app and justified.<br>• **Play Billing:** Required for in-app digital features unless exempt. | • **Title:** `<= 30` chars<br>• **Short Description:** `<= 80` chars<br>• **Full Description:** `<= 4000` chars (no keyword stuffing or misleading testimonial/award claims)<br>• **Release Notes:** `<= 500` chars per locale<br>• **Graphics:** App icon `512x512` PNG, Feature Graphic `1024x500` (mandatory for featuring/store), `2–8` phone screenshots (`16:9` or `9:16`, `>= 1080px` short side recommended), plus `7"` and `10"` tablet screenshots if targeting tablets.<br>• **Disclosures:** Play Data Safety form matching runtime SDK telemetry + IARC Content Rating + Web Account Deletion URL. |
| **Browser Extension Stores (Chrome Web Store / AMO)** | • **Manifest V3** service-worker lifecycle; zero remotely hosted code.<br>• **Minimum Permissions:** Prefer `activeTab` / optional runtime permissions over broad `<all_urls>` host grants. | • **Summary:** `<= 132` chars (`manifest.json` `description`).<br>• **Screenshots:** `1280x800` or `640x400` (`1–5` frames).<br>• **Single-Purpose & Permission Justifications:** Explicit reviewer rationale for every requested permission and remote host + Privacy tab data-use certification. |
| **B2B Cloud & SaaS Marketplaces (AWS/GCP/Azure, Slack, GitHub, Shopify)** | • **Least-privilege OAuth scopes**, webhook HMAC signature + replay verification, tenant uninstall/deprovision webhook handling, and marketplace entitlement/metering API integration.<br>• **Enterprise readiness:** Customer-managed secrets, audit-log events, zero hardcoded single-region assumptions. | • Scope-by-scope reviewer justification table, architecture/data-flow diagram, customer support SLA & escalation contact, live Privacy Policy + Terms/DPA URLs, and isolated reviewer test workspace. |

---

## 2. Deterministic Screenshot & Store-Metadata-as-Code Layout

Manual screenshots rot as soon as UI changes and block multi-locale launches.
Keep store metadata in a version-controlled layout (default `store/`, or adapt to
an existing store-upload directory if the repo already uses one, e.g.,
`fastlane/metadata/`) and pair it with a **deterministic screenshot pipeline**:

```text
store/
  listing/
    en-US/
      title.txt                 # verified against target store char cap
      subtitle.txt              # e.g., App Store <= 30 chars
      short_description.txt     # e.g., Play Store <= 80 chars
      keywords.txt              # e.g., App Store <= 100 chars
      description.md            # <= 4000 chars
      release_notes.txt         # e.g., Play Store <= 500 chars
  disclosures/
    privacy-disclosures.md      # mapped 1:1 to runtime code/SDKs (Nutrition Labels, Data Safety)
    permission-justifications.md
  screenshots-plan.md           # frame-by-frame route, seed state & caption
  review-notes.md               # reviewer demo login, MFA bypass & test steps
```

### Architectural Hooks Required for Automated Screenshots (Tool-Agnostic)

1. **Seeded Demo Fixture Adapter (`DEMO_SEED=store`):** Populates realistic,
   synthetic, copyright-clean domain records (zero real user PII, zero third-party
   brand logos) through the same seam adapter used by integration tests.
2. **Pinned Clock & Clean System Chrome:** Freezes UI timestamps/charts to a
   fixed instant and normalizes OS/window chrome (e.g., clean status bar via
   iOS simulator `simctl status_bar`, Android demo-mode broadcast, or fixed
   desktop/browser viewport).
3. **Automated UI-Capture Harness:** Drives each screen in `screenshots-plan.md`
   across required viewports and locales to emit reproducible raw captures +
   localized captions (using whatever UI test tool matches the stack — e.g.,
   XCUITest, Espresso/Compose tests, Flutter integration tests, Playwright,
   desktop offscreen rendering, or wrappers such as Fastlane `snapshot` /
   `screengrab`).

---

## 3. Inbound License & Asset Policy by Distribution Mode

Select the license policy matching how code and assets reach users:

| Distribution Mode | Safe Without Counsel (`ALLOW`) | Needs Dynamic-Link / Attribution Care (`REVIEW`) | Default Block (`DENY` in CI Gate) |
| --- | --- | --- | --- |
| **Proprietary Networked SaaS** | `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`, `ISC`, `MPL-2.0` (unmodified files), `LGPL-*` | `GPL-2.0` / `GPL-3.0` (safe server-side *only* if never distributed to client/on-prem; dangerous if BYOC/CLI ships later) | `AGPL-3.0*`, `SSPL-1.0`, `BUSL-1.1` (competing use), `CC-BY-NC*`, `Commons Clause`, non-commercial ML weights, unlicensed repos |
| **Proprietary Shipped App / Binary / SDK / Extension** *(iOS, Android, Desktop, CLI, On-Prem)* | `MIT`, `Apache-2.0`, `BSD-*`, `ISC`, `Zlib`, `0BSD` (bundle `NOTICE` / attribution screen in app settings!) | `MPL-2.0` (file-level modifications must stay open), `LGPL-*` (**blocked on iOS static linking** unless relinkable object files provided!) | `AGPL-*`, `GPL-*`, `SSPL-1.0`, static `LGPL-*` on iOS/WASM, `CC-BY-NC*`, `CC-BY-SA*` on proprietary UI assets, non-commercial ML weights |
| **Permissive Open-Source Project (`MIT` / `Apache-2.0`)** | Inbound licenses compatible with outbound license (`MIT`, `BSD-*`, `ISC`, `Apache-2.0` into `Apache-2.0`) | `Apache-2.0` into `MIT`-only (patent-clause asymmetry) | All copyleft (`MPL`, `LGPL`, `GPL`, `AGPL`) and non-commercial licenses |

---

## 4. Certification & Operational Readiness Cross-Walk

When scoping `SOC 2 Type II`, `ISO 27001`, `GDPR`, `HIPAA`, or enterprise SLAs,
ensure these **architectural seams** exist early:

1. **Data Classification & Crypto-Shredding:** Tag every persisted model (`PUBLIC`,
   `INTERNAL`, `CONFIDENTIAL_TENANT`, `PII`, `REGULATED_PHI_PCI`). Never write
   raw `PII` into immutable event payloads or unredacted structured logs; store
   an erasable subject key or encrypt subject payloads with a destroyable key.
2. **Audit Log vs. Application Log Separation:** Security/compliance audit events
   (`auth.*`, `permission.*`, `billing.*`, `data.export`, `account.delete`,
   `support.impersonate`) write to an append-only, retention-governed sink with
   `actor_id`, `acting_as_id`, `tenant_id`, `ip`, `reason`, and `request_id`.
3. **SLI / Error-Budget Seams:** Define availability and latency SLIs per
   critical user journey (e.g., `checkout`, `sync`, `login`), distinguishing
   client `4xx` errors (excluded from availability failure) from server `5xx`/
   timeout breaches, paired with expand-contract zero-downtime DB migrations.
4. **Support Break-Glass & Offboarding:** Support tools read masked/redacted
   metadata by default; viewing raw tenant payloads or acting as a user requires
   an explicit ticket reason, short TTL (`<= 1 h`), and emits a tenant-visible
   audit event. Provide deterministic tenant export + purge jobs from Day 1.
