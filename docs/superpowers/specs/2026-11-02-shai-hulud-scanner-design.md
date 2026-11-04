# Shai-Hulud supply-chain detector for job-security-scan — Design

Issue: [#50](https://github.com/chuongxl/agents-skills/issues/50) · Date: 2026-11-02 · Status: draft for approval

## Intent

Give a fast, trustworthy answer to **"has this repo, or this computer, been hit by Shai-Hulud?"**,
the npm/PyPI worm family that runs from install hooks, steals tokens (GitHub, npm, cloud, SSH, CI)
and republishes itself. This is an incident-response check first and a CI gate second.

The family keeps changing: wave 1 (Sep 2025, `bundle.js` postinstall), "2.0 / The Second Coming"
(Nov 2025, `setup_bun.js` + `bun_environment.js` preinstall, self-hosted runner `SHA1HULUD`), and the
2026 "Mini Shai-Hulud" waves (npm **and** PyPI; source reportedly public, so copycats are expected).
A known-indicator list alone ages quickly; heuristics alone are noisy. Hence two tiers.

## Goals

- `run-scan.sh --scanner shai-hulud` scans one repo (`--repo`) or all active repos, offline, in seconds.
- A host ("laptop") mode scans the current machine.
- **Tier 1 — Affected (CRITICAL):** a match on a known indicator. Definite, near-zero false positives.
- **Tier 2 — Suspicious (HIGH/MEDIUM):** behavior that matches the worm's pattern but no known indicator.
- Host mode lists credential stores as "rotate these if affected" without ever reading out a value.
- Per-repo JSON, a console verdict line, and findings in the existing HTML report.
- Clear remediation text per finding category.
- Tests with malicious and benign samples; a real end-to-end run in CI.

## Non-goals

- Generic malware signatures or AV-style scanning.
- Deleting, quarantining, or "cleaning" anything. Report only.
- Network calls during a scan (the indicator refresh is a separate, explicit command).
- Auditing the GitHub account for worm-created repos/workflow runs (needs a token; v1 prints a pointer).
- Re-detecting plain secrets in files — Gitleaks/TruffleHog already do that.

## Anti-goals (a failure even if it "works")

- Printing, logging, or writing any secret value anywhere (JSON, HTML, console).
- Flagging every `postinstall` / `node-gyp` / `husky` hook — alert fatigue kills an IR tool.
- Executing anything it inspects (no `npm`, no `node`, no lifecycle scripts) during a scan.

## Constraints (from the repo)

- Stdlib-only Python 3.8+, run with `python3 -I`; no third-party deps.
- Skill stays self-contained; relative links stay inside `job-security-scan/`.
- `python3 tools/validate_skills.py` and `tools/test_validate_skills.py` must pass; CI also runs
  `bash -n` and `compileall`.
- Fixtures must be **inert**: they contain matching strings/file names, never a working payload.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| 1 | Known indicators only | Fast, precise; blind to new variants; needs list upkeep |
| 2 | Behavior heuristics only | Catches variants; noisier and slower on big `node_modules` |
| 3 | **Both, two tiers** — chosen by Alex | Definite yes/no today + early warning for the next variant |

## Design

### Components

| File | Responsibility |
|---|---|
| `scripts/shai-hulud-scan.py` | CLI: `--repo PATH` or `--host [--root PATH ...]`, `--output`, `--iocs`, `--format json|text`; exit 0 clean / 1 suspicious / 2 affected |
| `scripts/lib/shaihulud/iocs.py` | Load + validate the indicator file |
| `scripts/lib/shaihulud/lockfiles.py` | Extract `(ecosystem, name, version, location)` from npm/yarn(v1+berry)/pnpm lockfiles, installed `node_modules/**/package.json`, and PyPI pins (`requirements*.txt`, `poetry.lock`, `uv.lock`) |
| `scripts/lib/shaihulud/heuristics.py` | Lifecycle-hook and payload-file analysis (tier 2) |
| `scripts/lib/shaihulud/host.py` | Host roots, global installs, package caches, credential inventory |
| `scripts/lib/shaihulud/report.py` | Finding model, redaction, verdict, JSON/text output |
| `scripts/fetch-iocs.py` | Explicit refresh: pull indicator CSVs from URLs in `assets/ioc/sources.json`, merge, write a cache file used in preference to the committed one |
| `assets/ioc/shai-hulud.json` | Committed, versioned indicator data (+ `shai-hulud.schema.json`) |
| `assets/ioc/hook-allowlist.json` | Known-benign hook commands (`node-gyp rebuild`, `prebuild-install`, `husky`, `patch-package`, `node install.js` of named native packages…) |

### Indicator data (`assets/ioc/shai-hulud.json`)

```json
{
  "version": "2026-11-02",
  "waves": [{"id": "sh-2.0", "name": "Shai-Hulud 2.0", "first_seen": "2025-11-24",
             "references": ["https://..."]}],
  "packages": [{"ecosystem": "npm", "name": "@scope/pkg", "versions": ["1.2.3"], "wave": "sh-2.0",
                "sources": ["datadog", "wiz"]}],
  "files":    [{"name": "bun_environment.js", "kind": "payload", "wave": "sh-2.0"}],
  "workflows":[{"pattern": ".github/workflows/shai-hulud-workflow.yml", "wave": "sh-1"},
               {"pattern": ".github/workflows/discussion.yaml", "requires_marker": "SHA1HULUD", "wave": "sh-2.0"}],
  "markers":  [{"text": "Sha1-Hulud: The Second Coming", "wave": "sh-2.0"}]
}
```

Seed content: the Datadog consolidated 2.0 list (Apache-2.0, attributed in `references/`), plus
wave-1 and Mini-wave file names, workflow names and marker strings taken from cited vendor write-ups.
File-name indicators fire only **inside a package directory or a hook target**, never on an
arbitrary file that happens to share the name. Hash indicators are supported by the schema but only
added when a cited source publishes them.

### Repo mode checks

Tier 1 (CRITICAL, verdict `affected`):
1. Lockfile / installed package / PyPI pin equals a listed `name@version`.
2. A listed payload file inside any package directory, or referenced by a lifecycle hook.
3. A listed workflow file present, or any workflow containing a listed marker (e.g. runner `SHA1HULUD`).

Tier 2 (verdict `suspicious`) — evaluated on the repo's own `package.json` and every installed
dependency's `package.json` (`preinstall`, `install`, `postinstall`, `prepare`, `prepublishOnly`,
`prepack`), skipping commands matching the allowlist:
- **HIGH:** hook pipes a download into a shell (`curl|sh`, `wget|bash`), **or** the hook's target
  script combines a *secret source* (`GITHUB_TOKEN`, `NPM_TOKEN`, `AWS_*`, `AZURE_*`, `GCP_*`/
  `GOOGLE_APPLICATION_CREDENTIALS`, `CI_JOB_TOKEN`, `.npmrc`, `.ssh/id_`, `process.env` enumeration)
  with an *exfil sink* (`fetch`, `axios`, `http(s).request/get`, `child_process` running `curl`/`gh`/
  `trufflehog`, GitHub API repo/workflow creation).
- **MEDIUM:** hook target that is heavily obfuscated (long base64/hex blobs + `eval`/`Function`) or
  downloads a runtime/binary (`bun`, `trufflehog`) at install time.
- A hook with only one weak signal is **not** reported.

Scan limits: hook targets and payload candidates up to 25 MB read as text (2.0's payload is ~10 MB);
bigger files reported as "unscanned large hook target" (LOW). Symlinks not followed. Each finding
carries a ≤120-char evidence snippet with anything token-shaped masked.

### Host ("laptop") mode

- Roots: `$HOME` by default, or `--root` (repeatable). Walk finds lockfiles and `node_modules`,
  skipping `.git`, OS/library dirs, and depth > 8 by default (`--max-depth`).
- Global installs: npm global prefix (from `~/.npmrc`/`NPM_CONFIG_PREFIX`/common paths — `npm` is
  never executed), `~/.bun`, pnpm/yarn global dirs, user `site-packages`.
- Caches: npm `_cacache/index-v5` entries matched against listed `name@version` (tier 1, "was
  downloaded on this machine"); listed payload/tool drop locations from sources.
- Credential inventory (INFO, "rotate if affected"): `~/.npmrc` (reports *has auth token: yes/no*),
  `~/.git-credentials`, `~/.config/gh/hosts.yml`, `~/.aws/credentials`, `~/.azure/`, gcloud ADC,
  `~/.ssh` private keys, `~/.docker/config.json`, `~/.kube/config`, `.env*` under roots.
  World/group-readable permissions → MEDIUM. **Values are never read into findings.**
- Output goes to `<output-dir>/_host/shai-hulud.json`; the report shows it as repo "this machine".

### Integration

- `run-scan.sh`: `run_shai_hulud` per repo → `<out>/<repo>/shai-hulud.json`; `_fail` on affected,
  `_warn` on suspicious; included in `all` (offline, fast). New flag `--host` runs host mode once.
- `generate-report.py`: `parse_shai_hulud` + a `_host` pseudo-repo; scanner label `shai-hulud`.
- `SKILL.md`: new phase, usage lines; bump `metadata.version` minor + root README badge.
- `README.md` + `references/remediation.md`: usage, CI snippet, and an "if affected" runbook
  (isolate, rotate in order: npm → GitHub → cloud → SSH; check GitHub for worm repos/workflows).

### Tests

- `scripts/test-shai-hulud.py` (unittest, offline): one test per tier-1 rule and per tier-2 rule,
  lockfile parsers per format, allowlist, redaction (no secret value can appear in output), large-file
  limit, host mode against a temp fake `$HOME`, exit codes, JSON shape.
- Fixtures under `tests/fixtures/shai-hulud/`: `infected-lockfile`, `infected-node-modules`,
  `planted-workflow`, `suspicious-hook`, `pypi-pin`, and benign `native-build`, `husky-prepare`,
  `clean`. All inert.
- E2E: extend `tests/e2e/run-e2e.sh` to run the real `run-scan.sh --scanner shai-hulud` on the
  fixtures plus `--host` on a fake home, then assert per-fixture verdicts and the HTML report rows.
- CI: add the new unit test + an IOC-file validation step to the existing workflow.

## Calls I made (check these)

- Script name follows the issue (`shai-hulud-scan.py`); logic in `scripts/lib/shaihulud/`.
- Included in `--scanner all`.
- Tier thresholds above (one weak signal is never reported).
- 25 MB text-scan limit; depth 8 for host walks.
- Host mode never runs `npm`/`node`; reads config files instead.
- Seed indicators: Datadog 2.0 list + cited names/markers for other waves; refresh via `fetch-iocs.py`.

## Left to the builder

Exact regexes, allowlist entries, report styling, and fixture contents within the rules above.
