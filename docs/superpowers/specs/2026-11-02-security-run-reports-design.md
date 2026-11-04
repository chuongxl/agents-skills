# job-security-scan: per-run report folder (MD + JSON + HTML) with file and line detail — Design

Date: 2026-11-02 · Status: draft for approval

## Intent

Every `run-scan.sh` run leaves a complete, self-contained record that is never overwritten, and every
finding in it points at the exact file and line. The skill **only reports**: it never changes scanned code
and never offers or asks to fix anything.

## Decisions (from Alex)

- Output per run: `security-run-{datetime}/` in the **workspace folder** (the folder `run-scan.sh` is run from),
  holding `security-report.md`, `security-report.json`, `security-report.html` **plus all raw per-tool output**
  (self-contained).
- Caches leave the workspace (Alex, 15:40): only `security-run-*` folders appear there, so users never confuse a
  cache folder with a report folder. Caches live in `${XDG_CACHE_HOME:-~/.cache}/job-security-scan/`
  (`advisories/`, `ioc/`), shared by every workspace on the machine; `cache-dir:` in `repository.md` or
  `JOB_SECURITY_SCAN_CACHE` overrides it (CI). `output-dir` is deprecated: still honoured as the cache folder,
  with a warning. An existing `.security-scan-results/` folder is left untouched (the skill never deletes).
- Every finding carries **file + line + one line of code** (excerpt). **Secrets get file + line only, never an
  excerpt**, so no secret value lands in a report someone might share.
- Report-only: remove any fix-offer behaviour; `SKILL.md` states it as a hard rule.

## Goals

- All three report files are written on every run (repo mode, `--scanner X`, `--host`), including a clean run.
- A report-generation failure is visible (warning + non-zero exit), never silently swallowed as today.
- Findings that today have no line (Trivy dependency CVEs, OSV, vendor advisories, Shai-Hulud) get one.
- Folder name sorts by time and is safe on every OS: `security-run-YYYYMMDD-HHMMSS` (local time); a second
  run in the same second gets `-2`, `-3`.

## Non-goals

- Fixing, patching, opening PRs, or editing any scanned repo.
- Deleting old run folders (retention is the user's choice).
- Changing what each scanner detects.

## Anti-goals

- A secret value in any report or excerpt.
- A run folder accidentally committed to git.

## Design

### Run folder

- `run-scan.sh` creates `RUN_DIR="${SECURITY_RUN_ROOT:-$PWD}/security-run-$(date +%Y%m%d-%H%M%S)"`.
  `SECURITY_RUN_ROOT` is an override for CI and tests only; default is the workspace folder.
- Raw outputs move from `<output-dir>/<repo>/…` to `RUN_DIR/<repo>/…` (host mode: `RUN_DIR/_host/`);
  run logs (advisory fetch log, report log) go into `RUN_DIR/` too.
- `CACHE_DIR` = `$JOB_SECURITY_SCAN_CACHE` > `cache-dir:` > deprecated `output-dir:` > `${XDG_CACHE_HOME:-$HOME/.cache}/job-security-scan`;
  advisories in `CACHE_DIR/advisories`, refreshed Shai-Hulud indicators in `CACHE_DIR/ioc/shai-hulud.json`.
- `RUN_DIR/.gitignore` containing `*` keeps the folder out of git with no change to the user's own
  `.gitignore`. The repo's root `.gitignore` also gets `security-run-*/`.
- Gitleaks runs with `--redact` so its raw JSON in the run folder holds no secret values.
- The last console line names the run folder.

### Locate step (file + line + code)

New `scripts/lib/report_locate.py`, applied to every finding when the report is built:

| Finding | How the line is found |
|---|---|
| Already has a line (Gitleaks, Semgrep, Hadolint, TruffleHog, Trivy secret/misconfig) | Kept; excerpt read from that line |
| Dependency in a lockfile/manifest (Trivy vuln, OSV, advisories, Shai-Hulud `known-package`) | Line of the package entry (name + version) in that file |
| Shai-Hulud marker / planted path / hook finding | Line containing the evidence text; else line 1 |
| No file on disk (e.g. image layer) or unreadable | `line: null`, excerpt empty |

Excerpt: that one line, trimmed, max 160 chars, passed through the Shai-Hulud `redact()` as a second guard.
**No excerpt at all** for `type == "secret"` findings and Shai-Hulud credential-store / credential-permissions
findings (the locator never opens credential files).

### Reports

- `security-report.json`: `schema_version`, `generated_at`, `team`, `org`, `config`, `run_dir`, `scanners`,
  per-repo summary (`name`, `status` 🔴/🟡/🟢, severity counts), and `findings[]` with `repo, scanner, type,
  severity, file, line, code, package, installed_version, fixed_version, rule_id, title, description, url`.
- `security-report.md`: the structure `SKILL.md` "Output Format" already defines (summary table, sections by
  severity, secrets, skipped repos), each finding as `file:line`, the excerpt in a code span, rule, title,
  package/version. Ends with a pointer to `references/remediation.md` — guidance, not an offer.
- `security-report.html`: existing report; the File : Line cell also shows the excerpt.
- `generate-report.py` gains `--out-dir DIR` (writes all three); the old `--output FILE` still works (HTML only).

### SKILL.md

- New hard rule near the top: report only — never modify scanned files, never offer, ask, or attempt to fix;
  remediation stays as text in the report.
- "Output Format": the agent reads `security-report.md`, gives a short summary and the run-folder path.
- Docs (README, ci-workflow.md artifact path → `security-run-*/`), version `2.2` → `2.3`.

## Approaches considered

| | Approach | Trade-off |
|---|---|---|
| 1 | **Locate at report time, one shared step** — chosen | Covers external tools (Trivy, OSV) we cannot change; one place to test |
| 2 | Each scanner emits lines itself | Impossible for Trivy/OSV; still needs approach 1 |

Run folder content: **self-contained** (reports + raw) chosen over "reports only, raw overwritten".

## Left to the builder

MD layout details, excerpt styling in HTML, exact lockfile line-matching heuristics within the table above.
