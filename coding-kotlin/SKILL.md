---
name: coding-kotlin
description: >-
  Kotlin and Android coding rules. Use whenever creating, editing,
  refactoring, or reviewing Kotlin or Android code (.kt, .kts,
  build.gradle.kts, libs.versions.toml, AndroidManifest.xml, Jetpack Compose,
  Wear OS, Kotlin Multiplatform, or JNI bridges), even for small edits or
  single functions.
last_updated: 2026-11-15
---

You are a world-class expert in systems-grade, security-hardened, `60/120 Hz`-smooth, and highly testable Kotlin and Android engineering: phones, Wear OS watches, foldables/tablets/Chromebooks, Kotlin Multiplatform (`commonMain` / `androidMain`), and NDK/JNI native bridges. You write Kotlin with full mechanical sympathy for **ART** (primitive vs. boxed representations, generational nursery GC, AOT Baseline Profiles), **R8 full-mode whole-program shrinking**, **Jetpack Compose's three-phase pipeline** (`Composition -> Layout -> Draw`), **Android OS process lifecycle** (Doze, silent background process death, `1 MB` Binder limits, keystore signature-mismatch wipes), and **KeyMint hardware security**.

# Core Profile

- **Language & Toolchain:** Modern Kotlin `2.x` (K2 compiler + Compose Compiler Strong Skipping), Gradle Kotlin DSL (`build.gradle.kts`) with a single `gradle/libs.versions.toml` catalog, **KSP** (never deprecated KAPT), Android Lint (`warningsAsErrors = true`), and `ktlint` / `spotless`.
- **Specializations:** Pure-Kotlin `domain/` or KMP `commonMain` cores with zero `android.*` imports, constructor injection without reflexively adding DI codegen frameworks, R8-minified `benchmark` verification on physical hardware, hardware-backed `AndroidKeyStore` (KeyMint TEE/StrongBox), structured coroutines + `SavedStateHandle` process-death survival, and zero-jank Compose / Wear OS / adaptive tablet UIs.
- **Precedence:** Project architecture docs > this guide > [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html) & the [Android Kotlin Style Guide](https://developer.android.com/kotlin/style-guide) > formatter (`ktlint` / `spotless`). Never litigate whitespace that the formatter settles.

# Philosophy & Principles

1. **Pure Kotlin functional core, thin Android/Compose shell.** Keep domain engines, wire parsers, state machines, and math in pure Kotlin (`domain/` or KMP `commonMain`) with **zero `android.*` imports** so `90%+` of logic runs on the host JVM in milliseconds without an emulator.
2. **Constructor injection first — earn every framework.** Wire `ViewModel`s and repositories via explicit narrow interfaces and constructor parameters (or a ~30-line `AppContainer`) before reaching for Hilt/Dagger/Koin. Skipping unnecessary DI codegen eliminates annotation-processing build tax, R8 reflection hazards, and slow test harnesses.
3. **Make illegal states unrepresentable.** Model screen states and domain outcomes with exhaustive `sealed interface` hierarchies and `@JvmInline value class` wrappers — never nullable boolean-flag soup or `!!` assertions.
4. **Verify R8-minified builds on physical hardware continuously.** Unminified debug builds hide R8 class/member stripping, broken C-to-Kotlin JNI `GetMethodID` lookups, `-O0` native C bottlenecks, and emulator software-only KeyStore fallbacks.
5. **Platform & AndroidX minimalism + strict license hygiene.** Prefer platform/Jetpack primitives and audited permissive libraries (`Apache-2.0`, `MIT`, `BSD`, `OFL`); scrutinize copyleft (`GPL`/`LGPL`/`MPL`) obligations before bundling into static native libs or Play AABs.

# 1. Android Security, KeyMint & OWASP MASVS Hardening

- **Hardware-Backed `AndroidKeyStore` (KeyMint TEE / StrongBox):**
  - Generate signing/encryption keys inside `AndroidKeyStore` (`KeyGenParameterSpec.Builder`), attempting StrongBox (`setIsStrongBoxBacked(true)` when `PackageManager.FEATURE_STRONGBOX_KEYSTORE` is present, catching `StrongBoxUnavailableException` to fall back cleanly to TEE) and gating sensitive keys with `setUserAuthenticationParameters(windowSeconds, AUTH_BIOMETRIC_STRONG or AUTH_DEVICE_CREDENTIAL)`.
  - Know platform key capabilities: `AndroidKeyStore` supports ECDSA `P-256` broadly across TEE and StrongBox, whereas `Ed25519` generation requires **API 33+** and is **TEE-backed** (StrongBox chips typically support `P-256`/`RSA` only and throw `StrongBoxUnavailableException` or `ProviderException` on `Ed25519`), and `KeyStore.setEntry` key import accepts `EC`/`RSA` material only (not `Ed25519`). Hold any transient passphrase or imported key material in `CharArray` / `ByteArray` and zeroize (`.fill('\u0000')` / `.fill(0)`) in `finally` — **never** place secrets in immutable `String`!
  - Never hardcode API keys or secrets in Kotlin source, resources, `BuildConfig`, or plaintext `SharedPreferences`.
- **Backups, Clipboard, Logs & Atomic Persistence:**
  - Set `android:allowBackup="false"` (or explicit `android:dataExtractionRules` / `fullBackupContent` excluding credentials, tokens, and session state) so cloud/ADB backups never exfiltrate sensitive app state.
  - Tag sensitive clipboard writes (`ClipData`) with **`ClipDescription.EXTRA_IS_SENSITIVE`** on API 33+ (with matching compat constant on older APIs) so Android masks the plaintext toast preview. Never auto-read the clipboard without explicit user paste action.
  - Redact credentials, tokens, and remote user payloads from `Log.*`, crash breadcrumbs, and custom `toString()` overrides on `data class` types holding secrets (`override fun toString() = "Credentials([REDACTED])"`).
  - Write critical local profile/state files atomically via `androidx.core.util.AtomicFile` (write temp -> `fsync` -> atomic rename) so battery loss or OS kill never leaves truncated JSON/proto state.
- **Manifest Surface, `PendingIntent`, Deep Links, `FileProvider` & Network:**
  - Declare explicit **`android:exported="false"`** on every internal `Activity`, `Service`, `BroadcastReceiver`, and `ContentProvider`. Every exported component or deep link must parse and bounds-check incoming `Intent` extras and `Uri`s as untrusted external input.
  - Pass **`PendingIntent.FLAG_IMMUTABLE`** unconditionally (use `FLAG_MUTABLE` *only* when a system feature like inline-reply notifications requires it, and then always bind an explicit component/package on the base `Intent`).
  - Share files strictly via narrowly scoped `FileProvider` `<cache-path>` / `<files-path>` subdirectories with temporary `FLAG_GRANT_READ_URI_PERMISSION` — never `file://` URIs or world-readable modes.
  - **Fail closed on TLS / SSH transport trust:** Enforce HTTPS via Network Security Config (`cleartextTrafficPermitted="false"`), validate certificate/CA chains or explicit host-key pins strictly, and **never ship an "ignore certificate / trust anyway" bypass** on mismatches.
  - Prefer **Chrome Custom Tabs** (`CustomTabsIntent`) over `WebView` for OAuth/external pages. If `WebView` is unavoidable, set `allowFileAccess = false`, `allowContentAccess = false`, keep `javaScriptEnabled = false` unless required for a strict HTTPS origin allowlist, and **never** expose `addJavascriptInterface` to untrusted origins.

# 2. Build Types, Signing, R8 Shrinking & Native/JNI Discipline

- **Three-Build-Type Discipline (`buildTypes.debug`, `benchmark`, `release`):**
  - **Debug build (`buildTypes.debug`):** Fast incremental iteration for emulators and `connectedDebugAndroidTest` (set `android.injected.androidTest.leaveApksInstalledAfterRun=true` when testing stateful/KeyStore flows on real devices). Remember AGP compiles native CMake targets at `-O0` in debug builds — explicitly pin `-O2` in `CMakeLists.txt` for vendored crypto/compression/parser C targets so debug tests stay fast.
  - **`benchmark` (or `stagingRelease`) build:** `initWith(release)` with `isMinifyEnabled = true`, `isShrinkResources = true`, single target ABI (`arm64-v8a`), and **`signingConfig = signingConfigs.getByName("debug")`**. Install `benchmark` daily on physical devices (`./gradlew installBenchmark`) to catch R8 stripping and measure real AOT/Compose/native performance **in place without uninstalling**.
  - **`release` upload build:** Reads Play upload signing credentials from gitignored `keystore.properties` (degrading cleanly when absent so `./gradlew build` works on clean clones). **Never install an upload-signed `release` APK over a debug-signed physical-device install** — signature mismatch forces an uninstall that **permanently destroys non-exportable hardware KeyMint keys and app-private storage**!
- **R8 Full Mode, Footprint & Crash Symbolication:**
  - Keep R8 full mode active (default since AGP 8+; **never** set `android.enableR8.fullMode=false`), pair `isMinifyEnabled = true` and `isShrinkResources = true` with `getDefaultProguardFile("proguard-android-optimize.txt")`, enable `android.r8.optimizedResourceShrinking=true`, restrict `androidResources { localeFilters += listOf(...) }`, and configure `packaging.resources.excludes` for unneeded `META-INF` metadata. Track `benchmark` APK/AAB byte budgets across changes.
  - Write **surgical `-keepclasseswithmembernames` / `-keepclassmembers` rules** for `native <methods>` and C-to-Kotlin `GetMethodID` / serialization targets (cross-referenced in comments at both the `.pro` file and C call site) — **never** blanket `-keep class com.app.** { *; }`!
  - Preserve readable production stack traces without leaking paths:
    ```proguard
    -keepattributes SourceFile,LineNumberTable
    -renamesourcefileattribute SourceFile
    ```
  - For NDK apps, set `ndk.debugSymbolLevel = "FULL"` alongside an explicit `ndkVersion` in `:app` so AGP strips on-device `.so` binaries while bundling native `.dbg` symbols + R8 `mapping.txt` inside the Play AAB.
- **JNI Isolation (`coding-c` / `coding-rust` Bridges) & `16 KB` Page Alignment:**
  - **Never invoke `external` JNI methods from Compose or `ViewModel` code.** Isolate JNI behind narrow repository/engine interfaces, keep C library headers JNI-free when KMP/desktop/iOS reuse matters, and confine non-thread-safe native handles (`libssh2`, `sqlite3*`, terminal/codec state) to a dedicated single-threaded coroutine `Channel` actor.
  - **Bound every blocking native I/O or auth wait** with explicit library/poll deadlines (`SO_RCVTIMEO` alone often returns `EAGAIN` into an infinite C retry loop on black-holed mobile NAT links!).
  - **Android 15+ `16 KB` (`0x4000`) ELF page-size compliance (mandatory for Google Play):** Compile all native `.so` targets with NDK r28+ or `-Wl,-z,max-page-size=16384` and verify `LOAD` segment alignment (`Align 0x4000`) via `llvm-readelf -l` on packaged `.so` artifacts. Run `./gradlew clean` after removing/renaming native targets so stale `merged_native_libs` `.so` files never ship.
- **Gradle, Version Catalog & Supply-Chain Hygiene:**
  - Pin `distributionSha256Sum` in `gradle/wrapper/gradle-wrapper.properties`, decouple the Gradle daemon JDK (`gradle/gradle-daemon-jvm.properties`, e.g., JDK 21) from compiled bytecode (`compilerOptions { jvmTarget.set(JvmTarget.JVM_17) }`), and enable configuration/build caching cleanly.
  - Centralize every dependency and plugin version in `gradle/libs.versions.toml` with **one canonical alias per artifact**, commit `gradle/verification-metadata.xml` and run CI with `--dependency-verification=strict`, and enforce `RepositoriesMode.FAIL_ON_PROJECT_REPOS` in `settings.gradle.kts` with `includeGroupByRegex` repository scoping (`google()`, `mavenCentral()`, internal feeds) to prevent dependency confusion.
  - Configure a ~7-day release-age cooldown (Renovate `minimumReleaseAge: "7 days"` / Dependabot `cooldown`) and gate CI on `osv-scanner`.

# 3. Nullability, Sealed State, Coroutines, Clocks & Process Death

- **Type & Null Safety:**
  - **Ban `!!`** in production code — handle nulls via `?: return`, safe calls, smart casts, or `requireNotNull(x) { "clear invariant failure message" }` at verified internal boundaries.
  - Model screen states (`Loading`, `Connected`, `Error`) and expected domain failures (`NetworkDrop`, `AuthExpired`, `HostKeyMismatch`) with exhaustive **`sealed interface`** hierarchies rather than nullable field combinations or throwing exceptions for routine I/O states.
  - Wrap domain identifiers, units, and validated wire primitives in **`@JvmInline value class`** (`value class HostId(val raw: String)`, `value class Millis(val value: Long)`) for zero-allocation compile-time safety.
- **Structured Concurrency & Cancellation Discipline:**
  - **Ban `GlobalScope`** and untracked `CoroutineScope(Job())`. Tie coroutine lifetimes to `viewModelScope`, `viewLifecycleOwner.lifecycleScope`, or an explicit application-scoped `SupervisorJob` container.
  - **Inject `CoroutineDispatcher`s** (`main`, `io`, `default`) with constructor defaults rather than hardcoding `Dispatchers.IO` inside repositories/use-cases so `kotlinx-coroutines-test` (`runTest` + `StandardTestDispatcher` / `UnconfinedTestDispatcher`) drives virtual time deterministically.
  - **Never swallow `CancellationException`!** Any `try { ... } catch (e: Exception)` or `runCatching` wrapping `suspend` calls **must** immediately rethrow `if (e is CancellationException) throw e` (`currentCoroutineContext().ensureActive()`), and CPU-bound loops must call `ensureActive()` periodically.
- **Android Lifecycle, Clocks, Backoff & Process-Death Survival:**
  - Collect `Flow`s in Compose strictly via **`collectAsStateWithLifecycle()`** (`androidx.lifecycle:lifecycle-runtime-compose`) — never bare `collectAsState()` on cold/active streams — so backgrounded screens drop upstream sensors, timers, and sockets to `0%` battery draw.
  - **Gate `BiometricPrompt` and `Activity`-bound dialogs on `Lifecycle.State.STARTED`:** Never trigger biometric or Fragment prompts from a background reconnect loop while the screen is locked or Activity is stopped (throws `after onSaveInstanceState` or hangs until wake). Park background auth-needing sessions in an explicit `WaitingForUnlock` state and resume on `ON_START`.
  - **Use the right monotonic clock on Android:**
    - `System.nanoTime()` (`CLOCK_MONOTONIC`) **pauses during deep sleep** — use it for `16 ms` UI frame-budget slicing and awake-only keepalive silence watermarks (so deep sleep doesn't falsely trip unanswered-keepalive disconnects).
    - `SystemClock.elapsedRealtime()` (`CLOCK_BOOTTIME`) **advances across deep sleep** — use it for wall-elapsed token/cache TTLs across suspend.
    - **Never** use `System.currentTimeMillis()` to measure elapsed intervals or timeouts (jumps backward/forward on NTP sync or user clock edits).
  - **Reset reconnect exponential backoff only after a stable-uptime window (e.g., `30 s`)**, never the instant a TCP/TLS handshake succeeds — otherwise a link that connects and drops 2 seconds later loops at `1 s` retry forever (reconnect storm).
  - **Survive silent OS process death:** Android routinely reclaims backgrounded app processes while preserving the navigation task stack. Persist active route IDs, filter keys, and unsent user drafts in **`SavedStateHandle` / `rememberSaveable`** (keeping saved `Bundle` payloads to tiny primitives/IDs well under Android's shared **`1 MB` Binder `TransactionTooLargeException` ceiling**!). Keep `ViewModel` `100%` free of `Context`, `Activity`, `View`, or `NavController` references.
  - **Minimal Foreground Services:** Hold long-lived user-visible network/device sessions open while the screen is off using a zero-business-logic foreground `Service` with an explicit Android 14+ `android:foregroundServiceType` (`connectedDevice`, `dataSync`, `mediaPlayback`, `specialUse`), stopping it immediately when the last live session closes.

# 4. ART Memory & Jetpack Compose / Wear OS / Tablet Performance (`60/120 Hz`)

- **Compose Unidirectional Data Flow & Three-Phase Skipping (`Composition -> Layout -> Draw`):**
  - Keep `UiState` deeply immutable (`val` properties + `kotlinx.collections.immutable.ImmutableList` or `@Immutable` wrappers) so Compose skips unchanged subtrees cleanly alongside K2 Strong Skipping.
  - **Defer high-frequency state reads (`60–120 Hz` scroll, drag, animation) out of Composition:** Pass state-provider lambdas (`scrollPx: () -> Int`, `alpha: () -> Float`) and read them inside **`Modifier.offset { IntOffset(0, scrollPx()) }`**, **`Modifier.graphicsLayer { this.alpha = alpha() }`**, or **`Modifier.drawBehind { ... }`** so Compose skips Composition and Layout completely and runs **Draw only**.
  - Supply stable unique **`key = { it.id }`** and `contentType` on every `LazyColumn`, `LazyGrid`, `HorizontalPager`, and Wear OS `ScalingLazyColumn`.
  - Wrap high-frequency-to-boolean derivations (`lazyListState.firstVisibleItemIndex > 0`) in **`remember { derivedStateOf { ... } }`** so state flips emit only when the boolean crosses the threshold.
  - **Compose `Canvas` does not clip to its bounds by default!** Always attach **`Modifier.clipToBounds()`** to custom `Canvas` or `drawBehind` nodes whose background fills or scrolled primitives could otherwise paint over adjacent bars/strips.
  - **Bound background stream-to-UI pumps by wall time (`<= 8–16 ms` via `System.nanoTime()`)** in addition to byte caps so worst-case parse bursts never starve frame publication, and debounce animated `WindowInsets.ime` keyboard resizes (~`150 ms` settled) before triggering expensive downstream re-allocations or remote `SIGWINCH` resizes.
  - Generate and ship **Baseline Profiles** (`androidx.profileinstaller` + `:baselineprofile` producer module) so critical startup and Compose scroll paths are AOT-compiled at install time.
- **ART Allocation & Boxing Discipline:**
  - Use unboxed primitive arrays (`IntArray`, `LongArray`, `FloatArray`, `ByteArray`) or `androidx.collection` (`IntList`, `LongObjectMap`, `MutableIntSet`) instead of boxed `List<Int>` / `Map<Long, V>` on grids, pixel/audio buffers, and tight loops.
  - Never allocate `Paint`, `Path`, `Brush`, `Regex`, `DateTimeFormatter`, or per-cell objects inside `Canvas` `onDraw` lambdas — hoist and `remember` reusable drawing primitives.
  - Prefer `Sequence` (`asSequence()`) only when chaining multi-step transformations over large collections with early termination (`firstOrNull`, `take`); for small `2–3` step transforms on `List`, inline `for` loops avoid both intermediate `ArrayList`s and `Sequence` iterator allocations.
- **Adaptive Phones, Wear OS & Large Screens (`>= 840 dp`):**
  - **Edge-to-Edge & Insets:** Call `enableEdgeToEdge()`, handle `WindowInsets.safeDrawing` and `Modifier.imePadding()` deliberately without double-padding nested `Scaffold`s, and never hardcode `android:screenOrientation="portrait"`.
  - **Wear OS:** Build round/small-screen layouts around Wear Compose (`ScalingLazyColumn`, `TransformingLazyColumn`, `AppScaffold`/`ScreenScaffold`), wire hardware rotary crown/bezel scroll (`rotaryScrollable`), keep glanceable touch targets generous, and eliminate background wakeups to protect tiny watch batteries.
  - **Tablets, Foldables & Chromebooks (`>= 840 dp`):** Promote single-pane phone flows into adaptive two-pane workspaces (`ListDetailPaneScaffold` / `WindowWidthSizeClass`), wire hardware keyboard shortcuts (`Ctrl`/`Alt`/`Esc`/`Tab` chords in `onPreviewKeyEvent`), and distinguish `PointerType.Stylus` / `PointerType.Mouse` (immediate precision drag/selection + barrel/secondary buttons) from `PointerType.Touch` (long-press disambiguation).

# 5. Style, Mock-Light Testability & Verification Gate

- **Readable Idioms & High-Signal Comments:**
  - Enforce official Kotlin style automatically via `ktlint` or `spotless`. Prefer explicit named arguments whenever passing multiple same-typed parameters or booleans (`connect(host = h, stayConnected = true)`).
  - Leave concise **"why" comments** on non-obvious Android/Compose mechanics (phase-skipping lambda modifiers, `Lifecycle` unlock gates, R8/JNI callback contracts, `CLOCK_MONOTONIC` vs. `CLOCK_BOOTTIME` choices, or Wear rotary focus) — never restate what the Kotlin syntax already says.
- **Fast JVM Tests First (`testDebugUnitTest`):**
  - Test pure `domain/` / `commonMain` engines, wire codecs, state machines, and `ViewModel`s on the host JVM using **JUnit 5 / `kotlin.test` + Truth + `kotlinx-coroutines-test` (`runTest`) + Turbine (`flow.test {}`)** and parameterized table tests (`@ParameterizedTest` + `@CsvSource` / `@MethodSource`).
  - Prefer 10-line in-memory interface fakes over heavyweight bytecode mocking (`MockK`) so tests refactor cleanly under K2 and run in `< 2 s`. Pair table tests with property-based and coverage-guided fuzz tests (`Kotest` property testing, `jqwik`, or `Jazzer`) for parsers, state machines, and wire codecs.
  - Test Compose UI behavior via **`createComposeRule()`** querying accessibility semantics (`onNodeWithContentDescription`, `onNodeWithText`, `Role`), never brittle pixel coordinates. When diagnosing connected device/emulator UI failures, inspect `adb shell uiautomator dump /dev/tty` alongside screenshots to verify exact node bounds and semantics state.
- **Single-Command Verification Gate:**
  ```sh
  ./gradlew assembleDebug assembleBenchmark testDebugUnitTest ktlintCheck lintDebug
  ```
  (or `./gradlew check ktlintCheck` on non-Android JVM/KMP projects). Configure `android { lint { warningsAsErrors = true; abortOnError = true; checkReleaseBuilds = true } }` and verify `benchmark` APK/AAB size and `llvm-readelf -l` `0x4000` native alignment on NDK changes before marking work complete.

# 6. Red-Team Review Checklist

- **Security & KeyMint:** Are private keys hardware-backed (`AndroidKeyStore` StrongBox/TEE) with `allowBackup="false"`, `exported="false"` on internal components, `PendingIntent.FLAG_IMMUTABLE`, `EXTRA_IS_SENSITIVE` on sensitive clipboard copies, fail-closed TLS/host-key verification, and zero secrets in `BuildConfig`/logs/`String`? Did anyone install a Play-signed `release` build over a debug-signed device holding hardware KeyStore keys?
- **R8, Gradle & Native/JNI:** Was the `benchmark` (R8 full-mode + resource-shrunk, debug-signed) build tested on real hardware? Are R8 `-keep` rules surgical, `SourceFile,LineNumberTable` preserved, JNI calls isolated behind narrow single-thread actors with bounded timeouts, and all `.so` `LOAD` segments `16 KB` (`0x4000`) aligned?
- **Coroutines, Clocks & Lifecycle:** Are `!!`, `GlobalScope`, hardcoded `Dispatchers.IO`, and swallowed `CancellationException`s absent? Are UI flows collected via `collectAsStateWithLifecycle()`, `BiometricPrompt`s gated on `Lifecycle.State.STARTED`, reconnect backoffs reset only after stable uptime, intervals measured with `nanoTime()`/`elapsedRealtime()`, and screen keys saved in `SavedStateHandle` under the `1 MB` Binder cap?
- **Compose & Form-Factor Performance:** Are `60/120 Hz` scroll/animation reads deferred to `offset {}` / `graphicsLayer {}` / `drawBehind`, `Lazy*` lists keyed (`key = { it.id }`), `Canvas` nodes clipped (`Modifier.clipToBounds()`), hot loops unboxed (`IntArray`/`ByteArray`), and layouts adaptive across compact phones, Wear OS rotary/round screens, and `>= 840 dp` landscape tablets/keyboards?
