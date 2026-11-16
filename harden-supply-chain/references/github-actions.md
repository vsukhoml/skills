# GitHub Actions hardening (principles carry over to GitLab CI, Forgejo, Buildkite)

CI holds the keys to production: cloud credentials, registry and package-publish
tokens, signing identities, deploy SSH keys. Recent incidents show the pattern.

- **tj-actions/changed-files (Mar 2025)**: a mutable version tag was rewritten to
  malicious code that dumped secrets into logs.
- **Trivy (Mar 2026)**: attackers with a stolen credential force-pushed most
  version tags of `aquasecurity/trivy-action` and `setup-trivy` and shipped a
  trojanized Trivy release binary. Stolen tokens then cascaded into npm (a worm
  across 50+ packages) and PyPI (LiteLLM 1.82.7/1.82.8). Security tools are
  prime targets because they run with broad access.
- **Shai-Hulud (Sep and Nov 2025)**: a self-replicating npm worm via install
  scripts and stolen tokens. npm then revoked classic tokens and pushed trusted
  publishing.

## Hardened workflow template

```yaml
name: build-and-release
on:
  push:
    branches: [main]
    tags: ['v*']
  pull_request:            # NOT pull_request_target for building untrusted code

permissions: {}            # nothing by default; each job asks for exactly what it needs

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-24.04
    permissions:
      contents: read
    steps:
      # Pin EVERY action to a full 40-char commit SHA; keep the version as a comment for humans/bots.
      - uses: actions/checkout@<full-commit-sha> # vX.Y.Z
        with:
          persist-credentials: false      # don't leave GITHUB_TOKEN in .git/config for later steps
      - name: Safe use of event data
        env:
          # Untrusted input goes through env, then is quoted in the shell; NEVER ${{ }} inside run:
          PR_TITLE: ${{ github.event.pull_request.title }}
        run: printf 'Building PR: %s\n' "$PR_TITLE"
      - name: Install deps (lockfile only, no install scripts)
        run: npm ci --ignore-scripts
      - name: Test, coverage, and fuzz regression corpus (see harden-build)
        run: npm test
      # For compiled binaries (C/C++/Rust/Go/native wheels), also run ASan/UBSan + race tests
      # in a matrix job and verify production ELFs with: bash check-elf.sh --strict dist/

  release:
    if: startsWith(github.ref, 'refs/tags/v')
    needs: build
    runs-on: ubuntu-24.04
    environment: release          # protected: required reviewers, tag-pattern restriction
    permissions:
      contents: write             # create the GitHub release
      id-token: write             # OIDC: keyless signing + cloud/registry auth without stored secrets
      attestations: write         # build provenance
      packages: write             # push to GHCR
    steps:
      - uses: actions/checkout@<full-commit-sha> # vX.Y.Z
        with:
          persist-credentials: false
      - name: Build
        run: make dist
      - uses: actions/attest-build-provenance@<full-commit-sha> # vX.Y.Z
        with:
          subject-path: 'dist/*'
      # Publish to npm/PyPI with trusted publishing (OIDC) — no long-lived NPM_TOKEN/PYPI_TOKEN secrets.
```

Resolve a tag to its commit SHA, and let bots keep the pins fresh:

```sh
gh api repos/actions/checkout/commits/v5 --jq .sha     # tag → commit (works for annotated tags)
# Renovate: "extends": ["helpers:pinGitHubActionDigests"] + "minimumReleaseAge": "7 days"
# Dependabot: package-ecosystem github-actions, with a cooldown, updates SHA pins + comments
# Tools: pinact / ratchet rewrite tags to SHAs in bulk
```

## Rules and the attack each one stops

| Rule | Stops |
| --- | --- |
| Pin actions by full SHA. Org policy can **require** SHA pinning (GitHub, Aug 2025), so unpinned workflows fail. | Tag rewriting (tj-actions, Trivy). Note that SHA pinning does *not* stop a compromised action you then update to, which is why cooldowns and review of bumps matter. |
| `permissions: {}` at the top, minimal per job | A compromised step using a write-scoped `GITHUB_TOKEN` to push code, tags or releases |
| `persist-credentials: false` | Later steps (or a compromised action) reading the token from `.git/config` |
| No `pull_request_target` / `workflow_run` that checks out and runs PR code | "Pwn requests": a fork PR running with secrets and a write token |
| No `${{ github.event.* }}` inside `run:`; pass through `env:` | Script injection via PR titles, branch names, issue bodies |
| Secrets only in protected `environment:`s, with required reviewers and tag rules | Any branch or PR workflow exfiltrating deploy secrets |
| OIDC (`id-token: write`) to cloud providers, registries and npm/PyPI trusted publishing | Long-lived tokens to steal. A token theft yields minutes of access, not months. |
| Separate build and release jobs; release runs only on protected tags | Untrusted build steps touching signing or publishing credentials |
| Self-hosted runners: ephemeral, single-use, never for public repos | Persistence on runners; fork PRs executing on your infrastructure |
| Treat caches as untrusted across trust boundaries | Cache poisoning from PR workflows into release builds |
| Static analysis of workflows: `zizmor .github/workflows` (and in CI) | Catches all of the above before merge |
| Runtime egress monitoring or blocking on runners (e.g. a pinned harden-runner-style step) | Exfiltration from a compromised step |
| Secret scanning + push protection; gitleaks/trufflehog in pre-commit | Secrets committed to the repo |

## When an action or dependency you use is reported compromised

1. **Scope.** Which workflows referenced it, and which runs executed during the
   compromise window? Use `gh run list`, and the audit log if you have
   Enterprise.
2. **Revoke first, then rotate.** Everything those runs could read: repo, org
   and environment secrets, cloud roles reachable via OIDC (review what they did
   in CloudTrail or equivalent), npm/PyPI/registry tokens, deploy keys. Workers
   like Shai-Hulud steal the *new* token if you rotate while they still run.
3. **Look for persistence.** New workflows or branches, modified workflow
   files, new deploy keys or webhooks, new collaborators, unexpected releases
   or package versions published from your accounts.
4. **Rebuild artifacts** produced in the window from a clean state. Re-sign
   and re-publish. Deprecate or yank bad versions.
5. **Re-pin** to a known-good SHA, add a cooldown, and record the incident.
