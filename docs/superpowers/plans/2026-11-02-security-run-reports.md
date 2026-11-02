# Per-Run Security Report Folder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every `run-scan.sh` run writes `security-run-YYYYMMDD-HHMMSS/` in the workspace folder with `security-report.{md,json,html}` plus raw tool output, every finding located to file + line + code excerpt (no excerpt for secrets), and the skill is explicitly report-only.

**Architecture:** A locate step (`scripts/lib/report_locate.py`) and report writers (`scripts/lib/report_formats.py`) used by `generate-report.py --out-dir`; `run-scan.sh` creates the run folder, points raw output at it and keeps caches in `output-dir`.

**Tech Stack:** bash, Python 3.8+ stdlib.

**Spec:** `docs/superpowers/specs/2026-11-02-security-run-reports-design.md`

## Global Constraints

- Stdlib only, `python3 -I`, Python 3.8 syntax; CI runs 3.8 and 3.12.
- Folder name `security-run-%Y%m%d-%H%M%S` (local time), collision suffix `-2`, `-3`…; parent `${SECURITY_RUN_ROOT:-$PWD}`.
- Excerpt ≤ 160 chars, passed through `shaihulud.findings.redact`; **none** for `type == "secret"` and for Shai-Hulud `credential-store` / `credential-permissions`.
- Report-only: no code path modifies a scanned repo; SKILL.md says never offer or attempt fixes.
- `job-security-scan` `metadata.version` `2.2` → `2.3`; root README badge matches. `tools/validate_skills.py` exit 0.

## Review Focus

1. **A secret in an excerpt** — gitleaks/trufflehog/trivy-secret rows and credential files must never carry code text. Test in Task 1 and Task 4 e2e (`grep` the whole run folder for planted values; raw gitleaks JSON redacted).
2. **Package name that appears many times in a lockfile** (as a dependency of others before its own entry) — line must be the package's own entry with the matching version. Test in Task 1.
3. **Finding paths of every shape** — repo-relative, `node_modules/...`, `~/...` (host), absolute, image paths with no file — locate or return `null`, never crash. Test in Task 1.
4. **Two runs in the same second** — second folder gets `-2`, first untouched. Test in Task 3.
5. **Clean run / single scanner / `--host` only** — all three report files still written. Test in Task 3.

---

### Task 1: Locate step

**Files:** Create `job-security-scan/scripts/lib/report_locate.py`; Test `job-security-scan/scripts/test-reports.py` (new, unittest).

**Interfaces:**
- Produces: `locate(finding: dict, repo_root: Optional[Path], home: Path) -> Tuple[Optional[int], str]` → `(line, code)`; `apply(findings: List[dict], repos_root: Path, home: Path) -> None` (sets `f["line"]`, `f["code"]` in place; repo root = `repos_root / f["repo"]`, host rows (`repo == "this machine"`) resolve `~/` against `home`).
- `NO_EXCERPT_TYPES = {"secret"}`, `NO_EXCERPT_RULES = {"credential-store", "credential-permissions"}`.
- Path resolution: absolute → as is; `~/x` → `home/x`; else `repo_root/x`. Missing/unreadable/binary/>25 MB → `(existing line or None, "")`.
- Line rules (in order): keep a given line; for findings with `package` + `installed_version` find the line containing the quoted name (or `node_modules/<name>`, `name==`, `name = "`) whose entry holds the version within the next 6 lines, else first line containing the name; else line containing the evidence text extracted from `description` after `evidence: `; else line 1 for a file finding with no other anchor.

- [ ] **Step 1: Write failing tests** `LocateTests`: `test_keeps_given_line_and_reads_excerpt`, `test_npm_lock_v3_package_entry_line` (package also listed earlier as a dependency → returns its own entry line), `test_yarn_lock_line`, `test_requirements_line`, `test_marker_evidence_line` (workflow with `SHA1HULUD` on line 7), `test_secret_row_gets_line_but_no_code`, `test_credential_rows_never_opened` (file mode 000 / nonexistent still fine, code empty), `test_home_relative_path`, `test_missing_file_returns_null`, `test_excerpt_redacted_and_capped` (a line holding an `npm_` token → masked, ≤160 chars).
- [ ] **Step 2: Run** `python3 -I job-security-scan/scripts/test-reports.py LocateTests` → FAIL (module missing).
- [ ] **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(job-security-scan): locate every finding to file, line and code`.

### Task 2: Report writers and generate-report.py

**Files:** Create `job-security-scan/scripts/lib/report_formats.py`; Modify `job-security-scan/scripts/generate-report.py` (`--out-dir`, `--repos-root`, `--home`, `code` in HTML File : Line cell, call `report_locate.apply`), `job-security-scan/assets/report-template.html` (excerpt style); Test `scripts/test-reports.py`.

**Interfaces:**
- Consumes: Task 1 `apply`.
- Produces: `report_formats.build_json(findings, meta) -> dict`, `report_formats.build_markdown(findings, meta) -> str` where `meta = {team, org, config, run_dir, scanners, repos, skipped, generated_at}`; repo status 🔴 if any CRITICAL/HIGH, 🟡 if any MEDIUM/LOW, 🟢 none.
- CLI: `generate-report.py --results-dir D --config C [--out-dir D] [--output F] [--workspace W] [--repos-root R] [--home H]`; `--out-dir` writes `security-report.html`, `.json`, `.md`; exit non-zero on failure.
- Markdown: title `# Security Scan Report — {team} / {org}`, Date, Config, Run folder, Repos, Scanners; Summary table; sections `## 🔴 Critical Findings`, `## 🟠 High Findings`, `## 🟡 Medium Findings`, `## 🔵 Low / Info`, `## 🔑 Secrets (values never shown)`, `## ⏭️ Skipped`, `## 📋 Remediation guidance` (link text to `references/remediation.md`, no fix offer). Each finding: `- **{title}** — \`{file}:{line}\` · {scanner} · {rule_id}{ · package@version → fix}` then an indented code span with the excerpt when present. Pipes and backticks in values escaped.

- [ ] **Step 1: Write failing tests** `FormatTests`: `test_json_shape_and_counts`, `test_markdown_sections_and_file_line`, `test_markdown_secret_has_no_code`, `test_markdown_escapes_pipes_backticks`, `test_clean_run_reports`; `GenerateTests.test_out_dir_writes_three_files` (subprocess on a temp results dir with a semgrep + osv + shai-hulud raw file; asserts `file:line` and excerpt appear in all three).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(job-security-scan): markdown and json reports alongside html`.

### Task 3: run-scan.sh run folder

**Files:** Modify `job-security-scan/scripts/run-scan.sh`; Modify tests that read raw output from `output-dir`: `scripts/test-ecosystems.py`, `scripts/test-engine.py`, `scripts/test-shai-hulud.py`; Test `scripts/test-reports.py` (`RunFolderTests`).

**Interfaces:**
- `RUN_DIR` created before any scanner; all per-repo raw outputs `"$RUN_DIR/$repo/..."`, host `"$RUN_DIR/_host/..."`; caches and fetch logs stay under `"$OUTPUT_BASE"`. `RUN_DIR/.gitignore` = `*`. Gitleaks gets `--redact`.
- Report step: `generate-report.py --results-dir "$RUN_DIR" --out-dir "$RUN_DIR" --config … --workspace "$PWD" --repos-root "$WORKSPACE" --home "$HOME"`; stderr kept in `$RUN_DIR/report.log`; failure → `🟡 report generation failed - see …` and exit ≥ 1.
- Final line: `📁 Run folder: $RUN_DIR`.
- Test helper (in each affected test): find the newest `security-run-*` under the test's `SECURITY_RUN_ROOT`.

- [ ] **Step 1: Write failing tests** `RunFolderTests` (stub tools on PATH as in test-ecosystems): `test_run_folder_with_three_reports_and_raw` (`--scanner shai-hulud` over two fixtures → `security-run-*/{security-report.md,json,html,.gitignore,<repo>/shai-hulud.json}`), `test_caches_stay_in_output_dir`, `test_same_second_gets_suffix` (pre-create the folder name for the frozen `date` via a stub `date` on PATH → new run uses `-2`), `test_host_only_and_clean_run_still_write_reports`, `test_gitleaks_called_with_redact`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement**; update the three existing test files to read raw output from the run folder.
- [ ] **Step 4: Run** all suites → PASS; `bash -n` run-scan.sh.
- [ ] **Step 5: Commit** `feat(job-security-scan): self-contained security-run folder per run`.

### Task 4: Docs, report-only rule, e2e scripts, version

**Files:** Modify `job-security-scan/SKILL.md` (report-only rule, Output Format, paths), `job-security-scan/README.md`, `job-security-scan/references/ci-workflow.md` (artifact path `security-run-*/`), `job-security-scan/references/ioc-data.md` (cache path unchanged — verify), `job-security-scan/tests/e2e/run-e2e.sh`, `job-security-scan/tests/e2e/run-shai-hulud-e2e.sh` (read from run folder; add checks: three reports exist, every finding in JSON has `line`, no secret excerpt, no planted value in the folder), root `README.md` badge `v2.3`, root `.gitignore` `security-run-*/`, `AGENTS.md` gitignored-state line.

- [ ] **Step 1: Update e2e scripts; Step 2: run** `run-shai-hulud-e2e.sh` → all pass; `run-e2e.sh` if osv-scanner + trivy can be installed in this session, else rely on CI.
- [ ] **Step 3: Update docs/version.** **Step 4: Run** `python3 tools/validate_skills.py && python3 tools/test_validate_skills.py && python3 -m compileall -q tools */scripts` and `bash -n` on all `*.sh` → exit 0.
- [ ] **Step 5: Commit** `docs(job-security-scan): report-only rule and security-run folder`.

### Task 5: End-to-end verification and PR

- [ ] **Step 1:** All offline suites on Python 3.8 and 3.12.
- [ ] **Step 2:** Real run on the sample workspace from the earlier test (infected / suspicious / clean repos + fake home), skill installed in `.github/skills/` from this branch: open the three reports, check every finding has file + line, excerpts present except secrets, no planted token anywhere in the run folder, second run creates a second folder.
- [ ] **Step 3:** Report results to Alex; on any issue loop back to the plan; on pass push and open the PR.
