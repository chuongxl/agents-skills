# job-security-scan: large reports (> 5 MB) — design

Status: approved in chat (direction C), spec awaiting review
Skill: `job-security-scan` (current report `schema_version` 2)

## Problem

`lib/report_model.py` caps a report at `MAX_REPORT_BYTES = 5 MB`; `load_report()` returns `None` above it.
Big multi-repo runs (Trivy on monorepos, `deep` profile with Trivy LOW, Semgrep) cross 5 MB easily because the
JSON is written with `indent=2` and every finding repeats its full advisory `description`.

Observed and latent failures (all in scope):

| # | Where | Effect |
|---|---|---|
| F1 | `triage.py queue` / `apply` (`load_run`) | Phase 9 aborts: "not a valid v2 report – run run-scan.sh again". A rerun produces the same size: dead end. |
| F2 | `report_model.find_previous()` | Previous report silently skipped: every finding NEW, no "fixed", carried verdicts lost, all re-queued. |
| F3 | `generate-report.py --keep-verdicts` (Phase 10 regenerate, `audit-prepare.py:278`) | Phase 9 verdicts silently dropped. |
| F4 | `validate-report.py` | Report marked INVALID. |
| F5 | Agent: `triage/queue.json` | Whole queue with ±15 context lines per item is one file; agent reads it whole and overflows context. |
| F6 | Agent: `security-report.md` | Multi-MB Markdown the agent is told to read in Output Format step 2. |

## Goals

- No silent loss: every size or integrity problem is a loud, specific error naming the file and the limit.
- Any single file the scripts load or the agent reads stays under a fixed cap, regardless of finding count.
- Phase 9 processes findings one at a time; the agent never needs to load a whole queue or report.
- Previous v2 reports keep working for change tracking and carried verdicts.
- Stdlib only, Python 3.8+, report-only (unchanged security posture).

Non-goals: changing scanners, severity rules, the verdict contract, fingerprints, or the HTML features.

## Design

### 1. Report storage — schema v3 (index + shards)

```
security-run-<dt>/
├── security-report.json        # index, target ≤ 256 KB
├── findings/
│   ├── <repo>-001.json         # ≤ 2,000 findings and ≤ 4 MB each, compact JSON
│   └── _host-001.json
├── SUMMARY.md                  # ≤ 20 KB, what the agent reads
├── security-report.md          # human Markdown (see §3)
├── security-report.html
└── triage/ ...                 # see §2
```

Index (`security-report.json`, `schema_version: 3`) keeps every top-level key of v2 **except** `findings`, and adds:

- `rules`: `{rule_id: {"title", "description", "url"}}` — shared text stored once. Shard rows keep `rule_id`
  and drop `title`/`description`/`url` when they equal the rule entry (rows that differ keep their own).
  `description` in `rules` is truncated to 4,000 chars.
- `shards`: `[{"file": "findings/<repo>-001.json", "repo", "count", "bytes", "sha256"}]`.
- `fixed` is capped at 2,000 rows plus `fixed_total`; the full list goes to `findings/_fixed-NNN.json` shards.

Shard file: `{"schema_version": 3, "repo": "...", "findings": [ ... ]}` written with
`json.dumps(..., separators=(",", ":"))`. Row fields are the v2 `FINDING_KEYS` + verdict keys, unchanged.

Splitting: findings are sorted by (repo, severity rank, file, line) and cut into a new shard when either 2,000
rows or 4 MB of serialized bytes would be exceeded. A single row is capped by existing field limits
(`MAX_LINE`, `MAX_TEXT`); a row over 64 KB is a hard error.

### 2. `lib/report_store.py` — the only loader/saver

| Function | Behaviour |
|---|---|
| `save(doc, run_dir)` | Writes shards then the index (index last, written via temp file + `os.replace`). Removes stale shards from an earlier save of the same run. |
| `load_index(run_dir)` | Reads `security-report.json` (cap 5 MB for v3 index; v2 file cap raised to 64 MB) and validates it. |
| `iter_findings(run_dir, index)` | Yields rows shard by shard; checks each shard's size (≤ 5 MB) and `sha256` against the index; re-expands `title`/`description`/`url` from `rules`. Total cap 200 MB / `MAX_FINDINGS` (20,000 → raised to 200,000). |
| `load_full(run_dir)` | Index + all findings as a v2-shaped in-memory doc (for code that needs the whole list). |
| v2 fallback | `schema_version: 2` → read the single file (≤ 64 MB) and present it through the same API. |

Errors: `ReportTooLarge`, `ReportCorrupt` (sha mismatch, missing shard, invalid schema), `ReportMissing`.
Each message names the file, the size and the limit, and the next action. `load_report()` and `find_previous()`
switch to this module:

- `triage.py` (F1): catches the errors and prints the specific reason (not "run run-scan.sh again").
- `find_previous()` (F2): a previous run that fails to load is **reported** in the new report (`run.previous_error`)
  and the Markdown/HTML summary shows "change tracking unavailable: <reason>" instead of marking all NEW silently.
- `--keep-verdicts` (F3): if the existing report cannot be loaded, `generate-report.py` exits 1 and writes
  nothing, so verdicts are never dropped.
- `validate-report.py` (F4): accepts a run folder or an index path; validates index + every shard streaming.

`report_schema.validate` gains `validate_index(index)` and `validate_rows(rows, seen_fingerprints)` so the
validation runs per shard; counts are cross-checked against the accumulated totals at the end.

### 3. Agent-facing outputs (F6)

- `SUMMARY.md` (hard cap 20 KB): per-repo status table, Shai-Hulud rows, changes since last run (counts + up to
  20 new CRITICAL/HIGH), verification counts, top 50 confirmed/unverified CRITICAL+HIGH as `file:line rule`,
  deep-audit summary, report paths. Truncation is announced ("… N more in security-report.html").
- `security-report.md`: lists every CRITICAL and HIGH finding in full; MEDIUM/LOW/INFO become per-repo, per-rule
  count tables with a pointer to the HTML report and shards. Stays human-readable at any size.
- `SKILL.md` Output Format step 2 changes from "read `security-report.md`" to "read `SUMMARY.md`".

### 4. Triage one item at a time (F5)

| Command | Output |
|---|---|
| `triage.py queue RUN` | `triage/queue-index.json` (fingerprint, repo, severity, batch file, status — no context) and `triage/batch-NNN.json` with 10 items each (context included). Prints the count and the first batch. |
| `triage.py next RUN` | Prints exactly one pending item (most severe first) as JSON on stdout, or `{"done": true}`. Pending = queued and no file in `triage/verdicts/`. |
| `triage.py record RUN FILE_OR_-` | Validates one verdict object (same rules as `parse_verdicts`), writes `triage/verdicts/<fingerprint>.json`. Bad input → exit 1, nothing written. Idempotent; a second verdict for the same fingerprint replaces the first only with `--replace`. |
| `triage.py apply RUN [VERDICTS.json]` | With no file: merges every `triage/verdicts/*.json`. With a file: v2-compatible bulk path (2 MB cap kept). Loads findings shard by shard, applies, saves via `report_store.save`, regenerates reports, `NEEDS-VALIDATION.md`. Still all-or-nothing. |

The 25-items-per-run budget is unchanged. `references/verification.md` steps become: `queue` → loop
`next` → fresh verifier per item → `record` → `apply`. The agent is told never to open `queue-index.json`,
batch files or shards directly.

`audit-prepare.py` and `lib/audit.py` (`input_bytes` 5 MB) only read the report via `report_store`; no other
change in Phase 10.

### 5. Compatibility and versions

- Readers accept v2 and v3; writers emit v3 only. `assets/report.schema.json` documents both index and shard.
- `run-scan.sh` baseline-exit check reads `counts` from the index — unchanged.
- e2e `assert-located.py`, `assert-shai-hulud-section.py`, the inline `d["run"]["previous_run"]` check: switch to
  `report_store.load_full` (or a small `scripts/report-cat.py RUN` that prints the v2-shaped doc).
- Skill version: `metadata.version` `3.0` → `3.1`; root `README.md` badge updated to match.

## Error handling summary

| Situation | Behaviour |
|---|---|
| Shard > 5 MB / index too big | `ReportTooLarge`, exit 1, message with file, size, limit |
| sha256 mismatch / missing shard | `ReportCorrupt`, exit 1 |
| Previous run unreadable | Report written; `run.previous_error` set and shown; nothing marked fixed |
| `--keep-verdicts` source unreadable | Exit 1, no report written |
| `record` invalid verdict | Exit 1, nothing written, errors listed |
| > 200,000 findings | Hard error naming the repos/scanners with the most rows and suggesting `--profile standard` / `--repo` |

## Testing

- `scripts/test-reports.py`: synthetic run with 30,000 findings across 3 repos → every shard ≤ 4 MB / ≤ 2,000
  rows, index ≤ 256 KB, `iter_findings` round-trip equals input, sha mismatch → `ReportCorrupt`, rules
  de-duplication restores the original fields.
- v2 compatibility: a v2 fixture report loads via `report_store`, works as `previous` (change tracking + carried
  verdicts).
- `find_previous` with an unreadable previous run sets `run.previous_error` and marks nothing fixed.
- `--keep-verdicts` with an unreadable report exits 1 (regression for F3).
- `scripts/test-verification.py`: `queue` → `next`/`record` loop over > 10 items (multiple batches) → `apply`
  equals the bulk-file path; invalid `record` writes nothing; `next` returns `{"done": true}` at the end.
- `validate-report.py` on a sharded run folder; `SUMMARY.md` ≤ 20 KB at 30,000 findings.
- Existing e2e scripts updated to the new reader; `python3 tools/validate_skills.py` and
  `python3 tools/test_validate_skills.py` pass.

## Out of scope

Changing scanner configuration to emit fewer findings, HTML pagination/virtualisation (HTML size is a separate
concern; it is not loaded by any script or by the agent).
