# Shai-Hulud Supply-Chain Detector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `--scanner shai-hulud` (repo mode) and `--host` (laptop mode) to job-security-scan, giving a two-tier verdict — *affected* (known indicator) or *suspicious* (worm-like behavior) — in JSON, console, and the HTML report.

**Architecture:** A stdlib-only Python package `scripts/lib/shaihulud/` (indicators, package inventory, heuristics, host walk, finding model) behind a thin CLI `scripts/shai-hulud-scan.py`. Indicators live in committed, versioned `assets/ioc/shai-hulud.json`, refreshable by `scripts/fetch-iocs.py`. `run-scan.sh` and `generate-report.py` get one function each, following the existing per-scanner pattern.

**Tech Stack:** Python 3.8+ stdlib (`json`, `re`, `pathlib`, `unittest`, `csv`, `urllib`), bash.

**Spec:** `docs/superpowers/specs/2026-11-02-shai-hulud-scanner-design.md`

## Global Constraints

- Stdlib only; every Python entry point runs with `python3 -I`; Python 3.8 syntax (no `match`, no `X | Y` types).
- A scan never executes what it inspects (no `npm`, `node`, `pip`, lifecycle scripts) and makes no network call. Only `fetch-iocs.py` touches the network.
- No secret value may appear in any output (JSON, text, HTML, stderr). Evidence snippets ≤ 120 chars, token-shaped substrings masked.
- Exit codes of `shai-hulud-scan.py`: `0` clean, `1` suspicious, `2` affected, `3` usage/IO error.
- Text-scan limit 25 MB per file (`MAX_SCAN_BYTES = 25 * 1024 * 1024`); host walk default `--max-depth 8`; symlinks never followed.
- Severities: tier-1 `CRITICAL`; tier-2 `HIGH`/`MEDIUM`; unscanned large hook target `LOW`; credential inventory `INFO`, world/group-readable credential file `MEDIUM`.
- Fixtures are inert: matching names/strings only, no working payload code.
- Skill self-containment: relative links stay inside `job-security-scan/`. `python3 tools/validate_skills.py` and `python3 tools/test_validate_skills.py` exit 0.
- `metadata.version` in `job-security-scan/SKILL.md` bumps `2.0` → `2.1`; root `README.md` badge matches.

## Review Focus

1. **Scoped and aliased packages** (`@scope/name`, npm `alias@npm:real@1.0.0`, yarn berry `name@npm:1.0.0`) — must match on the *real* name and version. Test in Task 2.
2. **Benign hooks in big trees** (`node-gyp rebuild`, `prebuild-install`, `husky`, `esbuild`'s `node install.js`, `patch-package`) — must produce zero findings. Test in Task 5 (`native-build`, `husky-prepare` fixtures).
3. **A real token in a hook target or `.npmrc`** — evidence must be masked, value absent from every output. Test in Task 3 and Task 6.
4. **Unreadable / huge / binary files and broken JSON lockfiles** — skipped with a LOW note or ignored, never a crash. Test in Task 2 and Task 5.
5. **File-name collisions** (a project's own `bundle.js`, `setup_bun.js` in a non-package folder) — no tier-1 hit unless inside a package dir or referenced by a hook. Test in Task 4.

---

### Task 1: Indicator data, schema, loader

**Files:**
- Create: `job-security-scan/assets/ioc/shai-hulud.json`, `job-security-scan/assets/ioc/shai-hulud.schema.json`, `job-security-scan/assets/ioc/hook-allowlist.json`, `job-security-scan/assets/ioc/sources.json`
- Create: `job-security-scan/scripts/lib/shaihulud/__init__.py`, `job-security-scan/scripts/lib/shaihulud/iocs.py`
- Create: `job-security-scan/references/ioc-data.md` (format, provenance, Datadog Apache-2.0 attribution)
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- Produces: `iocs.load(path: Optional[str] = None) -> Iocs`; default path order: `$SHAI_HULUD_IOCS` env → `<output-dir>/.ioc-cache/shai-hulud.json` if passed via `--iocs` → committed file.
- `Iocs` attributes: `version: str`, `packages: Dict[Tuple[str, str], Dict[str, str]]` (`(ecosystem, lower_name) -> {version: wave_id}`), `files: Dict[str, str]` (`file_name -> wave_id`), `workflows: List[dict]` (`pattern`, optional `requires_marker`, `wave`), `markers: List[dict]` (`text`, `wave`), `waves: Dict[str, dict]`.
- `iocs.validate(data: dict) -> List[str]` (empty list = valid); `iocs.load_allowlist(path=None) -> List[re.Pattern]`.

- [ ] **Step 1: Write failing tests** `IocTests.test_committed_file_is_valid` (`validate(json.load(...)) == []`), `test_package_index_lowercases_and_keeps_scope` (`("npm", "@accordproject/concerto-linter") in ioc.packages`), `test_validate_rejects_unknown_wave` (package with `wave: "nope"` → one error containing `"unknown wave"`), `test_env_override_wins`.
- [ ] **Step 2: Run** `python3 -I job-security-scan/scripts/test-shai-hulud.py IocTests -v` → FAIL (`ModuleNotFoundError: shaihulud`).
- [ ] **Step 3: Seed data.** Convert the Datadog `shai-hulud-2.0/consolidated_iocs.csv` (git clone `https://github.com/DataDog/indicators-of-compromise`, Apache-2.0) into `packages` with `wave: "sh-2.0"`, `sources` from its column. Add waves `sh-1` (2025-09), `sh-2.0` (2025-11-24), `mini-2026`. Add file/workflow/marker indicators **only with a cited reference URL in the wave's `references`**: `bundle.js` (sh-1, payload), `.github/workflows/shai-hulud-workflow.yml` (sh-1), `setup_bun.js` + `bun_environment.js` (sh-2.0, payload), `.github/workflows/discussion.yaml` with `requires_marker: "SHA1HULUD"` (sh-2.0), `.github/workflows/formatter_*.yml` (sh-2.0, verify pattern in sources), marker `Sha1-Hulud: The Second Coming` (sh-2.0). For `mini-2026`, read the Akamai, Mend, Sonatype and CSA AD-2026-009 write-ups with WebFetch and add only indicators they state; drop any you cannot cite. Allowlist regexes: `^node-gyp rebuild`, `^prebuild-install`, `^node-gyp-build`, `^husky( install)?$`, `^patch-package`, `^node install\.js$` (only for package names `esbuild`, `@swc/core`, `sharp`, `cypress` — store as `{"command": ..., "packages": [...]}`).
- [ ] **Step 4: Implement** `load`, `validate`, `load_allowlist` in `iocs.py`; schema file mirrors `validate`'s rules.
- [ ] **Step 5: Run tests** → PASS.
- [ ] **Step 6: Commit** `feat(shai-hulud): indicator data and loader (#50)`.

### Task 2: Package inventory

**Files:**
- Create: `job-security-scan/scripts/lib/shaihulud/inventory.py`
- Create fixtures: `job-security-scan/tests/fixtures/shai-hulud/{infected-lockfile,infected-node-modules,pypi-pin,clean}/` (lockfiles reference one real `sh-2.0` package@version and, for `pypi-pin`, a fake indicator injected by the test via `SHAI_HULUD_IOCS`)
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- Produces: `Pkg = namedtuple("Pkg", "ecosystem name version location")`; `inventory.iter_packages(root: Path, installed: bool = True) -> Iterator[Pkg]`; `inventory.iter_manifests(root: Path) -> Iterator[Tuple[Path, dict]]` (each installed `node_modules/**/package.json` and the root `package.json`, parsed; unparsable skipped).
- Formats: `package-lock.json` / `npm-shrinkwrap.json` v1 (`dependencies`) and v2/v3 (`packages`, key `node_modules/<name>`), `yarn.lock` v1 and berry (`"name@npm:range"` + `version:`), `pnpm-lock.yaml` (`/name@ver`, `/name/ver`, `name@ver` keys — line regex, no YAML lib), installed `node_modules`, PyPI `requirements*.txt` (`==` pins), `poetry.lock` and `uv.lock` (`name = "..."` / `version = "..."` pairs).

- [ ] **Step 1: Write failing tests** `InventoryTests`: one per format asserting the exact `Pkg` (e.g. `Pkg("npm", "@accordproject/concerto-linter", "3.24.1", "package-lock.json")`), `test_npm_alias_resolves_real_name`, `test_yarn_berry_npm_protocol`, `test_broken_lockfile_is_skipped` (invalid JSON → no exception, zero pkgs from it), `test_nested_node_modules_found`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** `iter_packages` / `iter_manifests`; walk with `os.walk(followlinks=False)`, skip `.git`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): lockfile and installed-package inventory`.

### Task 3: Finding model, redaction, output

**Files:**
- Create: `job-security-scan/scripts/lib/shaihulud/findings.py`
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- Produces: `make_finding(tier: str, severity: str, category: str, location: str, title: str, *, package: str = "", version: str = "", wave: str = "", evidence: str = "", remediation_key: str) -> dict` with keys `id` (stable sha1 of tier+category+location+package+version, 12 hex), `tier` (`affected|suspicious|exposure`), `severity`, `category`, `location`, `title`, `package`, `version`, `wave`, `evidence`, `remediation`.
- `redact(text: str) -> str`: masks GitHub (`gh[pousr]_…`, `github_pat_…`), npm (`npm_…`), AWS (`AKIA…`, 40-char secret after `aws_secret_access_key`), `_authToken=…`, PEM private-key bodies, generic `[A-Za-z0-9+/=_-]{32,}` after `=`/`:`; truncates to 120 chars.
- `verdict(findings) -> str` (`affected` > `suspicious` > `clean`; `exposure` never changes it); `exit_code(verdict) -> int`; `to_document(mode: str, target: str, ioc_version: str, findings: List[dict]) -> dict` with keys `scanner: "shai-hulud"`, `mode`, `target`, `ioc_version`, `verdict`, `counts` (per severity), `findings`; `to_text(document) -> str`.
- Remediation texts keyed by category: `known-package`, `payload-file`, `planted-workflow`, `marker`, `hook-exfil`, `hook-pipe-shell`, `hook-obfuscated`, `hook-runtime-download`, `large-hook-target`, `cached-package`, `credential-store`, `credential-permissions`.

- [ ] **Step 1: Write failing tests** `FindingTests`: `test_redact_masks_each_token_family` (each sample's raw token absent from output), `test_evidence_truncated_to_120`, `test_verdict_precedence`, `test_exposure_does_not_change_verdict`, `test_id_is_stable`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): finding model with redaction`.

### Task 4: Repo-mode tier-1 checks and CLI

**Files:**
- Create: `job-security-scan/scripts/lib/shaihulud/scanner.py`, `job-security-scan/scripts/shai-hulud-scan.py`
- Create fixtures: `tests/fixtures/shai-hulud/planted-workflow/.github/workflows/discussion.yaml` (contains `runs-on: [self-hosted, SHA1HULUD]`), `tests/fixtures/shai-hulud/infected-node-modules/node_modules/<listed pkg>/{package.json,bun_environment.js}` (one inert comment line), `tests/fixtures/shai-hulud/clean/` incl. a project-own `bundle.js` at repo root
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: `scanner.scan_repo(root: Path, ioc: Iocs, allowlist) -> List[dict]` (tier-1 only in this task; Task 5 adds the heuristics call).
- CLI: `shai-hulud-scan.py (--repo PATH | --host) [--root PATH ...] [--max-depth N] [--iocs FILE] [--output FILE] [--format json|text]`; prints `to_text` to stdout, writes `to_document` JSON to `--output`; exits per Global Constraints.

- [ ] **Step 1: Write failing tests** `RepoTier1Tests`: `infected-lockfile` → verdict `affected`, one `known-package` CRITICAL with wave `sh-2.0`; `infected-node-modules` → `known-package` + `payload-file`; `planted-workflow` → `planted-workflow` CRITICAL; `clean` → verdict `clean`, zero findings (root `bundle.js` ignored); `CliTests.test_exit_codes` (subprocess on each fixture: 2, 2, 2, 0) and `test_output_json_shape`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): repo-mode known-indicator checks and CLI`.

### Task 5: Tier-2 behavior heuristics

**Files:**
- Create: `job-security-scan/scripts/lib/shaihulud/heuristics.py`
- Modify: `job-security-scan/scripts/lib/shaihulud/scanner.py` (call it per manifest)
- Create fixtures: `tests/fixtures/shai-hulud/suspicious-hook/node_modules/evil-helper/{package.json,setup.js}` (postinstall `node setup.js`; file text contains `process.env.NPM_TOKEN` and `https.request(`, as strings in an inert, never-called function), `tests/fixtures/shai-hulud/native-build/node_modules/{fsevents,esbuild}/package.json`, `tests/fixtures/shai-hulud/husky-prepare/package.json` (`"prepare": "husky install"`)
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- Produces: `heuristics.analyze_manifest(pkg_dir: Path, manifest: dict, allowlist, repo_root: Path) -> List[dict]`.
- Hooks inspected: `preinstall install postinstall prepare prepublishOnly prepack`. Hook target = first `*.js|*.cjs|*.mjs|*.sh` token in the command, resolved inside `pkg_dir` only.
- Rules (exact): `hook-pipe-shell` HIGH — command matches `(curl|wget)\b[^|]*\|\s*(ba|z)?sh`; `hook-exfil` HIGH — target text has ≥1 secret source **and** ≥1 sink (lists in the spec); `hook-obfuscated` MEDIUM — a base64/hex run ≥ 2,000 chars **and** `eval(`/`new Function(`; `hook-runtime-download` MEDIUM — downloads `bun`/`trufflehog` (`bun.sh/install`, `trufflehog` + `releases/download`); `large-hook-target` LOW — target > `MAX_SCAN_BYTES`. Exactly one weak signal → no finding. A target that is itself a listed payload is left to tier 1 (no duplicate).

- [ ] **Step 1: Write failing tests** `HeuristicTests`: `suspicious-hook` → exactly one `hook-exfil` HIGH, verdict `suspicious`, exit 1; `native-build` and `husky-prepare` → zero findings; `test_pipe_shell_in_command`; `test_single_signal_not_reported` (env read only); `test_large_target_low` (sparse 26 MB temp file); `test_binary_target_no_crash`; `test_hook_target_outside_pkg_dir_ignored` (`node ../../x.js`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): install-hook behavior heuristics`.

### Task 6: Host ("laptop") mode

**Files:**
- Create: `job-security-scan/scripts/lib/shaihulud/host.py`
- Modify: `job-security-scan/scripts/shai-hulud-scan.py` (wire `--host`)
- Test: `job-security-scan/scripts/test-shai-hulud.py` (builds a fake home in `tempfile.mkdtemp()`)

**Interfaces:**
- Consumes: `scanner.scan_repo`, `inventory`, `findings`.
- Produces: `host.scan_host(roots: List[Path], home: Path, ioc, allowlist, max_depth: int = 8) -> List[dict]`.
- Project discovery: any dir under a root containing a lockfile or `node_modules`, scanned with `scan_repo` (location prefixed with the project path relative to home, `~/...`). Skip `.git`, `Library`, `.Trash`, `.cache` (except npm cache below), `AppData/Local/Temp`, `/proc`.
- Global installs: npm prefix from `NPM_CONFIG_PREFIX`, `prefix=` in `~/.npmrc`, else `~/.npm-global`, `/usr/local/lib/node_modules`, `/opt/homebrew/lib/node_modules`, `~/.nvm/versions/node/*/lib/node_modules`; plus `~/.bun/install/global`, `~/.local/lib/python3*/site-packages` (`*.dist-info/METADATA` Name/Version).
- npm cache: lines in `~/.npm/_cacache/index-v5/**` whose key contains `registry.npmjs.org/<name>/-/<basename>-<version>.tgz` for a listed package → `cached-package` CRITICAL.
- Credential inventory (`exposure`, INFO): paths listed in the spec; for `~/.npmrc` evidence is exactly `has auth token: yes|no`; others `present`; mode `& 0o077` non-zero on a private credential file → `credential-permissions` MEDIUM. File contents other than `.npmrc` are never opened.
- Text output ends with a fixed line pointing to the GitHub account check in `references/remediation.md`.

- [ ] **Step 1: Write failing tests** `HostTests`: fake home with an infected project, a global install of a listed package, a cache index entry, `.npmrc` with `//registry.npmjs.org/:_authToken=npm_FAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKEFAKE`, `~/.ssh/id_ed25519` chmod 0644 → verdict `affected`; findings include `known-package`, `cached-package`, `credential-store` (evidence `has auth token: yes`), `credential-permissions` MEDIUM; `test_token_never_in_output` (scan JSON + text contain no `npm_FAKE`); `test_max_depth_respected`; `test_clean_home_is_clean` (exposure only, verdict `clean`, exit 0).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): host (laptop) mode`.

### Task 7: Indicator refresh

**Files:**
- Create: `job-security-scan/scripts/fetch-iocs.py`
- Modify: `job-security-scan/assets/ioc/sources.json` (Datadog consolidated + 2.0 CSV raw URLs, format `csv-name-versions`)
- Test: `job-security-scan/scripts/test-shai-hulud.py` (uses `file://` URLs to local CSV fixtures — no network)

**Interfaces:**
- CLI: `fetch-iocs.py --out DIR [--sources FILE]` → writes `DIR/shai-hulud.json` = committed file merged with fetched packages (union of versions; existing wave kept, new ones get the source's `wave`); validated with `iocs.validate` before writing; exit 0 ok, 3 if any source failed (partial result still written), 1 if the merge is invalid.

- [ ] **Step 1: Write failing tests** `FetchTests.test_merge_adds_new_version`, `test_failed_source_exit_3_still_writes`, `test_output_validates`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** with `urllib.request` (honours `HTTPS_PROXY`). **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(shai-hulud): indicator refresh script`.

### Task 8: run-scan.sh and HTML report integration

**Files:**
- Modify: `job-security-scan/scripts/run-scan.sh` (usage header, `--host` flag, `run_shai_hulud`, dispatch + `all` + valid list, host run before the per-repo loop when `--host` is set)
- Modify: `job-security-scan/scripts/generate-report.py` (`parse_shai_hulud`, add to `parsers`; display name `this machine` for `_host`)
- Modify: `job-security-scan/scripts/test-ecosystems.py` (existing scanner-wiring tests: add `shai-hulud` to the expected scanner list if it asserts one)
- Test: `job-security-scan/scripts/test-shai-hulud.py`

**Interfaces:**
- `run_shai_hulud <repo> <path>` → `python3 -I "$SKILL_DIR/scripts/shai-hulud-scan.py" --repo "$path" --output "$OUTPUT_BASE/$repo/shai-hulud.json" --format text > "$OUTPUT_BASE/$repo/shai-hulud.txt"`; exit 2 → `_fail ... "AFFECTED - see ..."`, 1 → `_warn`, 0 → `_pass`, other → `_warn "scan error"`. Uses `$OUTPUT_BASE/.ioc-cache/shai-hulud.json` via `--iocs` when present.
- `--host` → same script with `--host --output "$OUTPUT_BASE/_host/shai-hulud.json"`; works with `--scanner shai-hulud` or alone.
- `parse_shai_hulud(repo, results_dir, workspace) -> List[dict]` mapping to the report's finding keys: `scanner: "shai-hulud"`, `type: "supply-chain"`, `severity` (INFO → `LOW` for the report), `file: location`, `package`, `installed_version: version`, `rule_id: category`, `title`, `description: wave + evidence + remediation` (≤300), `url: ""`.

- [ ] **Step 1: Write failing tests** `IntegrationTests`: run `run-scan.sh --config <temp config> --scanner shai-hulud` over the fixture dir; assert exit 2, `infected-lockfile/shai-hulud.json` verdict `affected`, `clean/shai-hulud.json` verdict `clean`; `security-report.html` contains `shai-hulud` and the listed package name; `test_unknown_scanner_message_lists_shai_hulud`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS, and `bash -n job-security-scan/scripts/run-scan.sh`.
- [ ] **Step 5: Commit** `feat(shai-hulud): wire into run-scan.sh and HTML report`.

### Task 9: Docs, version, CI, end-to-end script

**Files:**
- Modify: `job-security-scan/SKILL.md` (new phase "Supply-chain worm check (Shai-Hulud)", usage, `metadata.version: "2.1"`), `job-security-scan/README.md` (usage, CI snippet, host mode), `job-security-scan/references/remediation.md` ("If affected" runbook: isolate machine/runner, rotate npm → GitHub → cloud → SSH, check GitHub for repos with the worm's description and unknown workflows/self-hosted runners), root `README.md` badge `v2.1`
- Create: `job-security-scan/tests/e2e/run-shai-hulud-e2e.sh`
- Modify: `.github/workflows/job-security-scan-e2e.yml` (offline job: `python3 -I job-security-scan/scripts/test-shai-hulud.py`, IOC validation, `bash job-security-scan/tests/e2e/run-shai-hulud-e2e.sh`)

**Interfaces:**
- `run-shai-hulud-e2e.sh`: builds a temp `repository.md` over `tests/fixtures/shai-hulud/*`, runs the real `run-scan.sh --scanner shai-hulud` and `run-scan.sh --host` with `HOME` pointed at a generated fake home, then checks per fixture: verdicts (`affected` ×4, `suspicious` ×1, `clean` ×3), report HTML rows, `_host/shai-hulud.json` verdict `affected`, and `grep -r` proves the fake token string is absent from the whole output dir. Same `check`/`annotate` style as `run-e2e.sh`; no external tools required.

- [ ] **Step 1: Write** `run-shai-hulud-e2e.sh`; **Step 2: Run** it → all checks pass.
- [ ] **Step 3: Update docs/version/CI.**
- [ ] **Step 4: Run** `python3 tools/validate_skills.py && python3 tools/test_validate_skills.py && python3 -m compileall -q tools */scripts && for f in $(git ls-files '*.sh'); do bash -n "$f"; done` → all exit 0.
- [ ] **Step 5: Commit** `docs(shai-hulud): usage, runbook, CI and e2e`.

### Task 10: Full verification and hand-back

- [ ] **Step 1:** Run every offline suite: `test-advisory-lib.py`, `test-ecosystems.py`, `test-engine.py`, `test-shai-hulud.py`, `validate-advisories.py --strict`, `detect-ecosystems.py --validate` → all pass (no regressions).
- [ ] **Step 2:** Run `bash job-security-scan/tests/e2e/run-shai-hulud-e2e.sh` → `e2e: all checks passed`; open `security-report.html` and check the shai-hulud rows render with severity colours and no secret text.
- [ ] **Step 3:** Run host mode on this real workspace (`--host --root /home/claude`) as a smoke test; expect no crash and a verdict line.
- [ ] **Step 4:** Report results to Alex; on any failure loop back to the plan. On pass, push and open a PR closing #50 using the repo's PR template if present.
