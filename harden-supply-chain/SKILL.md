---
name: harden-supply-chain
description: >-
  Software supply-chain security for servers, container images, and CI/CD:
  APT/RPM repo trust, verified downloads instead of curl|sh, dependency
  locking and hash verification (npm, pnpm, uv, pip, Go, Cargo), digest
  pinning, SBOMs and signing, GitHub Actions hardening, secrets, and response
  to compromised dependencies. Use when the user installs third-party
  software, writes a Dockerfile or CI workflow, asks about pinning, lockfiles,
  SBOMs, signing, Renovate/Dependabot, or npm/PyPI security, or reacts to a
  supply-chain incident.
last_updated: 2026-11-15
---

# Supply-Chain Hardening

Everything a server runs was built by someone else, fetched from somewhere,
and executed with some privilege. For every artifact, answer five questions:

1. **Who built it, and from what source?** (provenance)
2. **Is it the same bytes they built?** (integrity: signatures and hashes,
   checked against an identity you pinned)
3. **How fast can a poisoned new version reach production?** (pinning,
   cooldowns, review)
4. **What can it touch when it runs?** (install hooks, root maintainer
   scripts, CI secrets)
5. **How would you know, and how would you recover?** (inventory/SBOM,
   advisories, rotation playbook)

Lessons from recent incidents (details in `references/github-actions.md`):

| Incident | Lesson |
| --- | --- |
| xz-utils (2024): a multi-year maintainer takeover, backdooring sshd via liblzma | Trust in a single maintainer is a dependency too |
| tj-actions/changed-files (Mar 2025) and Trivy/trivy-action (Mar 2026): **mutable tags rewritten** | Pin immutable references, and treat security tools as high-value targets |
| Shai-Hulud npm worm (Sep and Nov 2025) | **Install scripts execute code**; stolen publish tokens self-propagate |
| Trivy → npm → PyPI (Mar 2026): a CI credential theft cascaded across ecosystems | **CI secrets are the prize.** Short-lived OIDC credentials limit the blast radius. |

**Reference files:**

- `references/packages-and-binaries.md`: APT/RPM, verifying binaries, the
  language-dependency matrix.
- `references/github-actions.md`: hardened workflow template, rules table,
  compromise response.

## 1. On the server: what gets installed and how

- **Fewer sources.** Every repo is a root-level trust relationship: its
  maintainer scripts run as root. Prefer the distro archive, then the
  vendor's official signed repo, then a verified release binary. Avoid
  personal PPAs and `curl | sh`.
- **Per-repo trust.** deb822 `.sources` with `Signed-By:` and an origin pin,
  so the Docker repo can't replace `openssh-server`. Never `trusted=yes`,
  never a global `trusted.gpg`. `harden-audit` flags all of these.
- **Verified binaries.** Download, verify (`gh attestation verify`, `cosign
  verify-blob` with **identity pinning**, minisign/GPG with an out-of-band
  fingerprint), read install scripts, install root-owned, and record the
  version and hash in the infra repo.
- **Auto-update policy:** automatic *security* updates from the distro (yes,
  `harden-host` §2). Automatic updates from third-party channels
  (snap/flatpak, vendor repos, `:latest` image auto-pullers) are a decision
  with a reviewer, not a default.
- **Inventory.** Packages (`dpkg -l`, `rpm -qa`), unmanaged binaries
  (`harden-audit`), and images (`docker image ls --digests`). Optionally run
  `syft dir:/ -o cyclonedx-json` for a host SBOM, scanned with
  `grype sbom:...` or `osv-scanner`.

## 2. Application dependencies

Follow the matrix in `references/packages-and-binaries.md`. In short:

- **Lockfile plus hash-verified, frozen installs everywhere:** `npm ci`,
  `pnpm --frozen-lockfile`, `uv sync --locked`, `pip --require-hashes`,
  `cargo --locked`, `-mod=readonly`.
- **No install-time code by default:** npm `ignore-scripts=true`, pnpm 10's
  default deny with an allow-list, pip `--only-binary=:all:`. Build steps
  that must run code run in a sandboxed CI job, not on production.
- **Release-age cooldown of about 7 days** for both humans and bots. Use the
  npm/pnpm/uv/Poetry settings, Renovate `minimumReleaseAge`, or Dependabot
  `cooldown`. Most malicious releases are caught and yanked within days.
  Exempt your own scope.
- **Dependency confusion:** scoped private packages with per-scope registries,
  and a single proxying index for Python.
- **Scan what is reachable or exploited,** not raw counts: osv-scanner,
  govulncheck, cargo-audit, pip-audit.

## 3. Container images

- **Base selection.** Distroless or scratch for static binaries; Docker
  Hardened Images (free and Apache-2.0 since Dec 2025; the paid tier adds a
  CVE-fix SLA); Chainguard/Wolfi; Debian slim; Alpine. Prefer a publisher
  with signed images, SBOMs and a patch cadence you can observe.
- **Pin by digest** in `FROM` and in compose/k8s manifests. Bump digests by
  PR (Renovate/Dependabot with a cooldown), rebuild, test, deploy. Rebuild on
  a schedule even without app changes, so base fixes land.
- **Build attestations:** `docker buildx build --provenance=mode=max
  --sbom=true --push`. Inspect with `docker buildx imagetools inspect <ref>
  --format '{{json .Provenance}}'`.
- **Sign** in CI with keyless cosign: `cosign sign --yes <image>@<digest>`
  with `id-token: write`. `--yes` skips the interactive confirmation, which
  would otherwise hang a CI job.
- **Verify at deploy,** even on a single VPS:
  ```sh
  cosign verify ghcr.io/org/app@sha256:<digest> \
    --certificate-identity-regexp '^https://github.com/org/app/\.github/workflows/release\.ya?ml@refs/tags/v' \
    --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  && docker compose up -d
  ```
  Kubernetes uses an admission policy instead (sigstore policy-controller,
  Kyverno).
- Docker Content Trust (Notary v1) is legacy. Use Sigstore/cosign or Notation.
- **Pin and verify the scanners themselves.** Trivy's binary and actions were
  trojanized in March 2026. Grype, Trivy and syft run with access to your
  images and CI secrets.

## 4. CI/CD

Use the template and rules in `references/github-actions.md`. The non-negotiables:

- Actions pinned by full commit SHA, enforced by org policy.
- `permissions: {}` by default.
- `persist-credentials: false`.
- No `pull_request_target` running PR code.
- No `${{ }}` of event data inside `run:`.
- Secrets only in protected environments.
- **OIDC** instead of stored cloud and registry credentials.
- **Trusted publishing** to npm and PyPI.
- Ephemeral runners.
- `zizmor` in CI.
- **Pre-release binary & assurance gates (`harden-build`):** Before the
  protected `release` job signs an artifact, gate `build` on:
  1. Reproducible build flags (`SOURCE_DATE_EPOCH`, `-ffile-prefix-map` /
     `-trimpath` / `--remap-path-prefix`) so provenance attestations can be
     independently verified from source.
  2. `harden-build/scripts/check-elf.sh --strict` on every compiled binary and
     bundled `.so` (rejects `NO-PIE`, partial/missing `RELRO`, executable
     stacks, and leaked `ASan`/`TSan` runtimes).
  3. Sanitizer (`ASan+UBSan`, `TSan`/`-race`, `Miri`), fuzz corpus /
     ClusterFuzzLite, Tier-1 branch/mutation coverage, and `Kani`/`CBMC` proof
     checks where applicable.

**Deploying to a VPS from CI:**

- Prefer **pull-based** deploys. The server pulls a signed digest, verifies
  it, and restarts. CI never holds SSH to production.
- If you push, use a dedicated `deploy` user whose key is restricted in
  `authorized_keys`:
  `restrict,from="<runner egress or bastion>",command="/usr/local/bin/deploy" ssh-ed25519 ...`.
  The deploy script validates its argument (a digest) and runs `docker compose
  pull && up -d` with a pinned compose file.
- **Never give CI root or the docker group on production.** The deploy script
  runs the few privileged steps via a narrowly scoped `sudo` rule.

## 5. Secrets

- Not in git, images, compose `environment:`, CI logs or command lines.
- For versioned secrets, use **sops + age** (encrypted in git, decrypted at
  deploy), or a secret store (Vault/OpenBao, a cloud secret manager,
  1Password/Bitwarden Secrets Manager) with short-lived credentials where
  possible.
- Files at mode 600, owned by the consuming service user, delivered as
  compose secrets or systemd `LoadCredential=`. The latter avoids env vars
  and is readable only by the unit.
- Scanning: GitHub secret scanning with push protection, plus
  gitleaks/trufflehog in pre-commit and CI, including **history**. A secret
  that was ever committed is compromised: rotate it, don't just delete it.
- Keep a rotation runbook per secret: where it lives, who consumes it, how
  to rotate without downtime.

## 6. When something upstream is compromised

Follow `references/github-actions.md` → "When an action or dependency you use
is reported compromised":

1. Scope the exposure window.
2. **Revoke, then rotate.**
3. Hunt for persistence.
4. Rebuild artifacts.
5. Re-pin to known-good versions with a cooldown.

For server-side packages, add a step: check whether the bad version was ever
installed. Search `/var/log/apt/history.log`, `dnf history`, and lockfile git
history. If it ran as root (maintainer scripts), treat the host as compromised
(`harden-audit` §4).

## Verification checklist

- `harden-audit` PACKAGES section: no `trusted=yes`, no legacy keyring, every
  third-party source has `Signed-By` and a pin. Every unmanaged binary has a
  record of source, version and hash.
- Every Dockerfile `FROM` and every compose `image:` uses `@sha256:`, and
  Renovate/Dependabot opens digest PRs with a cooldown.
- `zizmor .github/workflows` is clean. Org policy requires SHA pinning. No
  long-lived cloud or publish tokens remain in repository secrets.
- `cosign verify` (or `gh attestation verify`) runs in the deploy path and
  fails closed.
- Lockfiles are committed, CI uses frozen installs, install scripts are off,
  and cooldowns are configured.
