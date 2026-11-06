# Scanner sources

This page explains each scanner the skill runs: what it looks for, why it is in the set, how `scripts/run-scan.sh` calls it, and how its findings land in the report.

No single tool covers the whole job. A secret scanner can't read a lockfile, and a CVE database knows nothing about a missing authorization check. So the skill runs several narrow tools and merges their output into one report. Some of them overlap on purpose:

- Gitleaks and TruffleHog both look for secrets. Gitleaks is fast and pattern-based. TruffleHog is slower but calls the provider's API to check whether a credential still works. A verified TruffleHog hit is the strongest secret signal in the report.
- Trivy and OSV-Scanner both find vulnerable dependencies. Trivy also covers Dockerfiles, IaC misconfigurations and secrets. OSV-Scanner reads lockfiles directly against OSV.dev and is better at transitive dependencies.
- Vendor advisories cover what the package databases miss: the runtime itself (Node.js, Go, Next.js), base images, CI `setup-*` actions and end-of-life versions.

## Summary

| Scanner | Finds | Reads | Raw output | Profiles | Network |
|---|---|---|---|---|---|
| Gitleaks | Hardcoded secrets | Full git history (`quick`: working tree) | `gitleaks.json` | all | no |
| Trivy | CVEs, IaC/Dockerfile misconfig, secrets | Repo filesystem | `trivy.json`, `trivy.txt`, `trivy.sarif` | standard, deep | DB download |
| Semgrep | Code flaws (SAST) | Source code | `semgrep.json` | standard, deep | rule download |
| Hadolint | Dockerfile bad practice | `<repo>/Dockerfile` | `hadolint.txt` | standard, deep | no |
| OSV-Scanner | Known-vulnerable dependencies | Lockfiles | `osv.json` | all | OSV.dev API |
| SBOM fallback | Same as OSV, for unknown ecosystems | CycloneDX SBOM from Trivy | `sbom.cdx.json`, `osv-sbom.json` | standard, deep | OSV.dev API |
| TruffleHog | Secrets that still work | Full git history | `trufflehog.json` | standard, deep | provider APIs |
| Vendor advisories | Runtime, image and EOL issues | Version files, images, CI, SBOM | `advisories.json` | standard, deep | advisory feeds (cached) |
| Shai-Hulud | npm/PyPI worm infection | Repo, or the host with `--host` | `shai-hulud.json` | all | no |
| Deep audit | Logic flaws scanners can't see | Source code, read by the agent | `audit/` | opt-in `--audit` | no |

Profiles are set in `run-scan.sh`. `quick` runs Gitleaks, OSV-Scanner and Shai-Hulud. `standard` and `deep` run everything except the deep audit. `deep` also lowers the Trivy threshold to LOW.

Tool versions are pinned in `scripts/install-tools.sh`. On Linux each download is checked against a SHA-256 hash. Trivy is pinned to 0.69.3 because 0.69.4 and the 0.69.4 to 0.69.6 images were published with malicious code.

A scanner that errors or writes no output is reported as "NOT scanned". The report never shows a failed scanner as clean.

## Gitleaks

Phase 1. Finds API keys, tokens, passwords and private keys committed to git.

Gitleaks matches regex rules and entropy checks against every commit (`--log-opts --all`), so a secret deleted last year still shows up. That is the point: a secret that ever reached the remote must be rotated, and deleting the file does not do that. The `quick` profile uses `--no-git` and only reads the working tree, which is faster but misses history.

- Config: `assets/gitleaks.toml`. Runs with `--redact`, so the raw JSON does not hold the secret value.
- Severity: every finding is CRITICAL, type `secret`.
- Limits: pattern matching only. It can't tell a live key from a revoked one or a test fixture. Phase 9 verification and TruffleHog help with that.

## Trivy

Phase 2. A general-purpose scanner from Aqua Security. The skill runs `trivy fs` with three scanners turned on:

- `vuln`: known CVEs in OS packages and language dependencies.
- `misconfig`: Dockerfile, Kubernetes, Terraform and other IaC checks.
- `secret`: a second secret pass with Trivy's own rules.

The severity threshold comes from `FAIL_ON_SEVERITY` (default HIGH). CRITICAL and MEDIUM are always included. `deep` adds LOW. Ignores live in `assets/.trivyignore`.

- Severity: vulnerabilities and misconfigurations keep Trivy's severity. Secrets are CRITICAL.
- Output: `trivy.json` for the report, `trivy.txt` for reading, `trivy.sarif` for the GitHub Security tab in CI.
- Trivy also writes the CycloneDX SBOM used by the SBOM fallback and the advisory matcher.
- Limits: it needs a vulnerability DB download on first run. Dependency results depend on what Trivy can parse. OSV-Scanner is the second opinion.

## Semgrep

Phase 3. Static analysis (SAST) of your own code: injection, unsafe deserialization, weak crypto, missing checks that match a known pattern.

The skill builds the ruleset per repo. It starts from the base set in config, adds language packs for the ecosystems it detects (`ecosystems/*.json`, see [ecosystems.md](ecosystems.md)), and always includes `p/owasp-top-ten` and `p/secrets`. A repo can add more with `semgrep-extra` in `repository.md`.

- Severity: ERROR becomes HIGH, WARNING becomes MEDIUM, INFO becomes LOW. Findings from secret rules get type `secret`.
- Limits: rules match code shape, not intent. Expect false positives, which is why Phase 9 asks the agent to read the code before reporting. Semgrep can't find a flaw no rule describes. The deep audit exists for that.

## Hadolint

Phase 4. Lints `<repo>/Dockerfile` against Docker best practice: running as root, unpinned base images, `apt-get` without `--no-install-recommends`, `ADD` where `COPY` would do. It also runs ShellCheck on `RUN` lines.

- Config: `assets/hadolint.yaml`. Output is the plain-text `hadolint.txt`. The tool is only installed when a repo sets `has-dockerfile: true`, and the phase is skipped when the repo has no root `Dockerfile`.
- Severity: error becomes HIGH, warning becomes MEDIUM, info and style become LOW. Type `misconfig`.
- Limits: only the root `Dockerfile`. Other Dockerfiles still get Trivy's misconfig checks.

## OSV-Scanner

Phase 5. Google's scanner for the OSV.dev database, which merges GitHub Security Advisories, PyPA, RustSec, Go and other ecosystem feeds.

It reads lockfiles (npm, Yarn, pnpm, Maven, Gradle, pip, Poetry, Go, Composer, Bundler, Cargo, NuGet). A lockfile lists the exact resolved version of every transitive dependency, so OSV-Scanner catches the vulnerable package three levels down that `package.json` never mentions.

- Severity: the group's max CVSS score when present (9.0 and up is CRITICAL, and so on down). Otherwise the GHSA label, with MODERATE mapped to MEDIUM. Otherwise MEDIUM.
- Exit code 1 means "vulnerabilities found". Anything above 1 is a scanner error and is reported as a warning.
- Limits: no lockfile, no result. That gap is what the SBOM fallback covers.

## SBOM fallback

Not a separate tool. When a repo has an ecosystem the skill doesn't recognise, or has no lockfile, Trivy writes a CycloneDX SBOM (`sbom.cdx.json`) from what it can see on disk, and OSV-Scanner matches that SBOM against OSV.dev (`osv-sbom.json`). Coverage is weaker than a real lockfile, but it beats an empty result.

## TruffleHog

Phase 6. Scans git history for secrets like Gitleaks does, then calls the provider's API to check whether each credential still works. Runs with `--no-update`.

That verification step is why TruffleHog is in the set. A verified AWS key is an incident. An unverified match may be a revoked key or a fixture.

- Severity: verified is CRITICAL and marked "VERIFIED ACTIVE". Unverified is HIGH.
- `lib/sanitize.py` strips secret values from the output before the report reads it.
- Limits: verification sends the credential to the provider. Only run it where that is allowed. It is slower than Gitleaks and covers fewer secret types.

## Vendor advisories

Phase 7. Package databases track libraries. They often miss the runtime and platform a service runs on. This phase covers that gap for any language.

`scripts/fetch-advisories.py` pulls feeds into `~/.cache/job-security-scan/advisories`: Node.js and Next.js security releases, the Go vulnerability DB, GHSA, CISA KEV and endoflife.date. `match.py` then compares them with what the repo pins: runtime versions in version files, base images in Dockerfiles and compose files, CI `setup-*` actions, and the SBOM.

- Trust order on conflict: vendor bulletin, then OSV/GHSA. CISA KEV only sets the `exploited` flag. endoflife.date only reports end of life.
- Match states: `affected`, `possibly-affected`, `affected-end-of-life`, `affected-if-condition-holds`, `end-of-life`, `unpinned`, `pending` (LOW), `unknown-version`. Unknown severity becomes MEDIUM.
- `ADVISORY_OFFLINE=1` skips the fetch and uses the cache. `JOB_SECURITY_SCAN_PROBE_IMAGES=1` probes base images in a sandbox to read the real runtime version.
- Details: [advisory-data.md](advisory-data.md).

## Shai-Hulud

Phase 8. An offline check for the Shai-Hulud worm family, which spread through hijacked npm and PyPI packages and installed hooks that steal tokens.

It looks for known bad package versions, payload files, planted paths and marker strings from the IOC list in `assets/ioc/shai-hulud.json`. It also flags install hooks that behave like the worm, for example piping a download into a shell or sending data out. Known-safe hooks are listed in `assets/ioc/hook-allowlist.json`. `scripts/fetch-iocs.py` writes a refreshed IOC list to the cache, and the scan uses that copy when it exists. With `--host` it also checks the developer's machine and writes results under `_host/`.

- Verdicts: AFFECTED (CRITICAL, exit 2), SUSPICIOUS (HIGH or MEDIUM, exit 1), clean (exit 0). Type `supply-chain`.
- Limits: it only knows the IOCs in the list. A new variant needs an IOC refresh.
- Details: [ioc-data.md](ioc-data.md), cleanup steps in [remediation.md](remediation.md).

## Deep audit

Phase 10, opt-in with `--audit` or `--scanner audit`. This is not a tool. `scripts/audit-prepare.py` builds a coverage plan, then the agent reads the code following `references/audit/WORKFLOW.md`. It looks for what no rule describes: broken authorization, tenant isolation gaps, CI trust issues, injection through unusual paths.

A second agent re-checks every finding independently. Confirmed findings join the report with scanner `audit`. `--budget N` caps the number of agent calls.

## Change tracking

The report compares each run with the previous one and marks findings as new or fixed. A finding can only count as fixed when both runs scanned the same way. `scanner_modes` in the report records the mode that matters: Gitleaks history versus working tree, and Trivy with or without LOW. A `quick` run after a `standard` run won't mark history secrets as fixed just because it didn't look at history.
