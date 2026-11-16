# Reproducible Builds & Artifact Footprint Minimization Reference (`release-engineering`)

---

## 1. Cross-Ecosystem Reproducibility & Footprint Recipes

Every ecosystem leaks build-host entropy and ships dead bytes unless explicitly
configured:

| Ecosystem | Reproducibility Flags (`Same Commit => Same Hash`) | Footprint & Split-Symbol Recipe |
| --- | --- | --- |
| **C / C++ / Embedded (`GCC` / `Clang`)** | `SOURCE_DATE_EPOCH`, `-ffile-prefix-map=$PWD=.`, `-fno-ident`, `-Wl,--build-id=sha1`, deterministic `ar D` | Compile `-Os`/`-Oz` (firmware) or `-O2`, `-ffunction-sections -fdata-sections -fvisibility=hidden -flto -Wl,--gc-sections`; split symbols via `objcopy --only-keep-debug app app.debug && strip --strip-unneeded app && objcopy --add-gnu-debuglink=app.debug app`. |
| **Rust (`Cargo`)** | `cargo build --release --locked --offline` with `RUSTFLAGS="--remap-path-prefix=$PWD=. -C link-arg=-Wl,--build-id=sha1"` | In `[profile.release]`: `debug = true` (or `debug = "line-tables-only"`), `lto = "thin"` (or `"fat"`), `codegen-units = 1`, `split-debuginfo = "packed"`, `strip = "symbols"`, `panic = "abort"` (when unwinding is unneeded); audit crate weight via `cargo bloat` & `default-features = false`. |
| **Go** | `CGO_ENABLED=0 go build -mod=readonly -trimpath -buildvcs=false -ldflags="-buildid="` | Add `-ldflags="-s -w"` for smallest runtime binary (`~25–35%` smaller) when external DWARF debuggers aren't needed (Go still retains compact pclntab stack traces!), or archive unstripped binary alongside stripped copy. |
| **Python (`uv` / Wheels)** | `SOURCE_DATE_EPOCH`, `PYTHONHASHSEED=0`, `uv sync --locked --no-dev --no-editable --no-build --offline` | Install only production wheel closure (`--no-dev`), strip native `.so` extensions (`find .venv -name '*.so' -exec strip --strip-unneeded {} +`), exclude `tests/`, `__pycache__` source duplicates, or compile self-contained zipapp/PEX when fitting. |
| **TypeScript / JS / Web / Wasm** | `npm ci --ignore-scripts` / `pnpm install --frozen-lockfile --offline`, deterministic bundler chunk IDs | Tree-shake ESM (`"sideEffects": false`), externalize/prune dev packages, emit **external** `.map` source maps uploaded only to symbol store (never publicly served if IP-sensitive), run `wasm-opt -Oz --strip-debug` after splitting DWARF, and pre-compress assets (`brotli -q 11`, `zstd -19`). |
| **Container / OCI (`BuildKit`)** | Pin `FROM ...@sha256:<digest>`, pass `--build-arg SOURCE_DATE_EPOCH=...` and `rewrite-timestamp=true` in OCI exporter | Multi-stage into `scratch` / `distroless:nonroot` / `chainguard` / `chiseled` (`2–35 MB` total image vs. `900 MB` full distro!). |

---

## 2. Deterministic Archive Packaging (`tar` / `zip`)

Standard `tar czf release.tar.gz build/` produces a **different SHA-256 every second**
because `tar` records directory `readdir()` order, current `gzip` header timestamp,
file `mtime`s, and the CI runner's `uid`/`username`!

**Canonical reproducible tarball command (GNU `tar` >= 1.28 + `zstd`/`gzip -n`):**

```bash
LC_ALL=C tar \
  --sort=name \
  --mtime="@${SOURCE_DATE_EPOCH}" \
  --owner=0 --group=0 --numeric-owner \
  --mode='u+rwX,go+rX,go-w' \
  --pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime \
  -cf - -C dist . \
  | zstd -19 -T1 -o release.tar.zst
  # (Note: single-threaded zstd -T1 or fixed chunking guarantees deterministic compressed framing; for gzip, always pass 'gzip -n'!)
```

---

## 3. Verifying Hermeticity & Reproducibility in CI

```text
[Job 1: Fetch]  (Network ON)  ──► Verifies lockfile hashes, populates vendored/read-only cache
                                         │
               ┌─────────────────────────┴─────────────────────────┐
               ▼                                                   ▼
[Build A: /work/a, umask 022, TZ=UTC]               [Build B: /work/build-longer-path, umask 002, TZ=UTC+14]
  (Network OFF / --offline)                           (Network OFF / --offline)
               │                                                   │
               └──────────────► Assert SHA-256(A) == SHA-256(B) ◄──┘
                                (On mismatch: run 'diffoscope A B' and fail gate!)
```

---

## 4. Artifact Size-Budget Gate Pattern

Silent dependency upgrades routinely double binary or firmware sizes overnight
(e.g., an innocent transitive crate pulling a regex Unicode table + second HTTP
stack + TLS library). Enforce explicit budgets in CI:

| Target Artifact | Typical Metrics to Track & Gate on Every PR | Section / Symbol Attribution Tool |
| --- | --- | --- |
| **Native ELF / Mach-O / PE Binary** | `.text`, `.rodata`, `.data`, `.bss`, stripped total file bytes | `bloaty binary -d compileunits,symbols` (diff against `main`: `bloaty new -- old`!) |
| **Firmware `.elf` / `.bin`** | Flash `%` (`<= 85%` of slot so OTA headroom remains!), static SRAM `.data + .bss`, worst-case stack | `arm-none-eabi-size`, linker `--print-memory-usage`, `puncover` / `bloaty` |
| **WebAssembly (`.wasm`) & Web Bundles** | Raw + Brotli-compressed `.wasm`/`.js` transfer size (`initial route <= 100–170 KiB` compressed) | `twiggy top -n 20 app.wasm`, bundler stat diff |
| **OCI Container Image** | Compressed pull bytes, uncompressed disk bytes, layer count, `0` wasted whiteout files | `docker buildx imagetools inspect`, `dive --ci` |
