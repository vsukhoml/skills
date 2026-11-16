# Server-side supply chain: repositories, binaries, language packages

## APT (Debian/Ubuntu): third-party repos without global trust

Legacy `apt-key add` and `/etc/apt/trusted.gpg(.d)` make a key trusted for
**every** repository. A vendor key could then sign a fake `openssh-server` for
the Ubuntu archive. Use per-repo `Signed-By` in deb822 format, and pin the
origin so it can only supply the packages you want from it.

```sh
# 1. Key: fetch over HTTPS, then VERIFY the fingerprint against the vendor's docs (out of band)
install -d -m 0755 /etc/apt/keyrings
curl -fsSLo /etc/apt/keyrings/docker.asc https://download.docker.com/linux/ubuntu/gpg
gpg --show-keys --with-fingerprint /etc/apt/keyrings/docker.asc   # compare with the published fingerprint
```

`/etc/apt/sources.list.d/docker.sources`:

```
# Suites = your release codename (lsb_release -cs), e.g. noble (24.04) or resolute (26.04)
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: resolute
Components: stable
Architectures: amd64
Signed-By: /etc/apt/keyrings/docker.asc
```

`/etc/apt/preferences.d/docker.pref` lets this origin supply only its own
packages:

```
Package: *
Pin: origin "download.docker.com"
Pin-Priority: 100

Package: docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin docker-ce-rootless-extras
Pin: origin "download.docker.com"
Pin-Priority: 500
```

Verify with `apt-cache policy openssl docker-ce`. Distro packages must come
from the distro archive. The vendor's maintainer scripts still run as root on
install, so a pin limits *which* packages a compromised repo can replace, not
what its own packages can do. Fewer third-party repos is the real control.

Other APT rules:

- No `trusted=yes` and no `[allow-insecure=yes]`.
- `Acquire::AllowInsecureRepositories "false";` (the default).
- Plain HTTP mirrors are integrity-safe thanks to signatures but leak what you
  install. Prefer HTTPS.
- Personal PPAs are a single maintainer's laptop with root on your server.
  Prefer official vendor repos or distro packages.
- Check packaged files with `dpkg --verify` (`harden-audit --deep`) and
  `debsums -c`.

RPM: keep `gpgcheck=1` and `repo_gpgcheck=1` where supported. Import vendor keys
with `rpm --import` only after checking the fingerprint. Use
`dnf config-manager --save --setopt=<repo>.includepkgs=...` to limit what a
third-party repo supplies.

## Binaries and install scripts

`curl https://get.example.sh | sh` executes whatever the server sends at that
moment. A server can even tell a pipe apart from a browser view. Instead:

1. **Prefer a signed package repo** over a release binary, and a release binary
   over an install script.
2. **Download, verify, read, then run.**
   ```sh
   curl -fsSLO https://github.com/OWNER/REPO/releases/download/v1.2.3/tool_linux_amd64.tar.gz
   # (a) GitHub artifact attestation (SLSA provenance built by GitHub Actions). --repo alone accepts
   #     ANY workflow in that repo; pin the release workflow too:
   gh attestation verify tool_linux_amd64.tar.gz --repo OWNER/REPO \
     --signer-workflow OWNER/REPO/.github/workflows/release.yml
   # (b) Sigstore keyless signature, pinned to the release workflow identity
   cosign verify-blob tool_linux_amd64.tar.gz --bundle tool_linux_amd64.tar.gz.sigstore.json \
     --certificate-identity-regexp '^https://github.com/OWNER/REPO/\.github/workflows/release\.ya?ml@refs/tags/v' \
     --certificate-oidc-issuer https://token.actions.githubusercontent.com
   # (c) minisign / GPG with a key fingerprint obtained out of band
   minisign -Vm tool_linux_amd64.tar.gz -P '<publisher public key>'
   # (d) at minimum: checksum from a DIFFERENT channel than the artifact (e.g. the project's signed tag/website)
   sha256sum -c tool.sha256
   ```
3. Install root-owned into `/usr/local/bin` (`install -o root -g root -m 0755`).
   Record name, version, source URL and SHA-256 in the infra repo.
   `harden-audit` lists unmanaged binaries; every one should have a record.

What verification proves, and what it doesn't:

- A signature or attestation proves **which identity or pipeline produced**
  the file. It does not prove the file is benign.
- Pinning the *exact* workflow path and tag ref stops a stolen maintainer
  token from publishing a validly signed artifact from somewhere else.
- It cannot stop a compromise *of the release pipeline itself*, as in the
  Trivy case. That is what **cooldowns** are for (below).
- A checksum published next to the binary only proves the download wasn't
  corrupted.

## Language dependencies

Two principles: **lock and verify hashes**, and **don't let fresh releases or
install scripts run automatically.**

| Ecosystem | Frozen, hash-verified install | Stop install-time code | Cooldown (min release age) |
| --- | --- | --- | --- |
| npm | `npm ci` (lockfile `integrity` hashes) | `.npmrc`: `ignore-scripts=true` (allow-list builds explicitly) | npm ≥ 11.10: `min-release-age=7` (days) |
| pnpm | `pnpm install --frozen-lockfile` | pnpm ≥ 10 skips dependency lifecycle scripts by default; allow-list via `onlyBuiltDependencies` | pnpm ≥ 10.16: `minimumReleaseAge: 10080` (minutes), with `minimumReleaseAgeExclude` |
| Bun | `bun install --frozen-lockfile` | Scripts only for `trustedDependencies` | Supported, in seconds (see Bun docs) |
| Python (pip) | `pip install --require-hashes -r requirements.txt` (generate with `pip-compile --generate-hashes` / `uv pip compile --generate-hashes`) | `--only-binary=:all:`: no sdist means no `setup.py` executed | — (use the uv or Poetry options) |
| Python (uv) | `uv sync --locked` | Prefer wheels: `--no-build` where possible | `exclude-newer = "7 days"` (relative durations since uv 0.9.17; older versions take an RFC 3339 timestamp) |
| Poetry | `poetry sync` (Poetry ≥ 2; lockfile-exact) | — | Poetry ≥ 2.4: `solver.min-release-age` |
| Go | `go.sum` + `GOFLAGS=-mod=readonly`; `GOSUMDB` (sum.golang.org) left ON; `go mod verify` | No install scripts. `go generate` only from your own code. | Renovate `minimumReleaseAge` |
| Rust | `cargo build --locked`; `cargo vet` / `cargo deny` | `build.rs` and proc-macros run at build: build in a sandbox | Renovate `minimumReleaseAge` |

The cooldown options are new and their names and units differ per tool. Check
your tool version's docs before relying on one.

More rules:

- **Bots:** Renovate `minimumReleaseAge: "7 days"`, or Dependabot `cooldown`,
  for every ecosystem, GitHub Actions included. Most malicious releases are
  detected and pulled within days, so a cooldown turns zero-day package
  attacks into non-events.
- **Dependency confusion and typosquatting:**
  - Scope private packages (`@org/`), with a per-scope registry in `.npmrc`
    (`@org:registry=https://npm.internal/`).
  - For Python, use a **single** index that proxies PyPI, never
    `--extra-index-url` (pip picks the highest version across indexes). uv's
    default `index-strategy` (first index wins) mitigates this.
  - Review new dependencies by name before the first install.
- **A private proxy or mirror** (Artifactory, Nexus, Verdaccio, devpi, Athens)
  gives one choke point for cooldown, quarantine, audit logs and offline
  builds.
- **Vulnerability scanning:** `osv-scanner` (multi-ecosystem lockfiles),
  `govulncheck` (reachability-aware), `cargo audit`, `pip-audit`, `npm audit`.
  Gate on Critical/High that are reachable or known-exploited (CISA KEV),
  not on raw counts.
