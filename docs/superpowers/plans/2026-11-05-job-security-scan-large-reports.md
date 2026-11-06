# job-security-scan Large Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `job-security-scan` work at any finding count: no file the scripts load or the agent reads exceeds a fixed cap, no silent data loss, and Phase 9 triage runs one finding at a time.

**Architecture:** A new `scripts/lib/report_store.py` is the only reader/writer of a run's report. It stores a small `security-report.json` index (schema v3) plus capped `findings/<repo>-NNN.json` shards and reads v2 files for compatibility. In memory, the document keeps today's shape (`doc["findings"]` is a list), so the model, schema, Markdown and HTML code change little. Triage gains `next`/`record` commands backed by per-fingerprint verdict files.

**Tech Stack:** Python 3.8+ stdlib only, `unittest`, bash.

**Spec:** `docs/superpowers/specs/2026-11-05-job-security-scan-large-report-design.md`

## Global Constraints

- Stdlib only, Python 3.8+; every script runs with `python3 -I`. No third-party dependencies.
- Report-only: nothing in a scanned repo is changed, nothing from it runs.
- Shard: ≤ 2,000 findings and ≤ 4 MB (`4 * 1024 * 1024`) serialized, compact JSON `separators=(",", ":")`.
- Loader caps: shard file ≤ 5 MB, v3 index ≤ 5 MB, v2 single file ≤ 64 MB, run total ≤ 200 MB, `MAX_FINDINGS = 200000`, single row ≤ 64 KB.
- Index target ≤ 256 KB; `fixed` inline ≤ 2,000 rows + `fixed_total`; the rest in `findings/_fixed-NNN.json`.
- `rules[rule_id].description` truncated to 4,000 chars.
- `SUMMARY.md` hard cap 20 KB (20 * 1024 bytes).
- Triage batch size 10; verifier budget stays 25 per run; the bulk `verdicts.json` path keeps its 2 MB cap.
- Errors are `ReportTooLarge`, `ReportCorrupt`, `ReportMissing` (all subclass `ReportError(Exception)`); the message names the file, its size, the limit and the next action.
- Writers emit `schema_version: 3`; readers accept 2 and 3.
- Skill `metadata.version` `3.0` → `3.1`; root `README.md` badge `v3.1`.
- Must pass: `python3 tools/validate_skills.py`, `python3 tools/test_validate_skills.py`, `python3 -m compileall -q tools */scripts`.

## Review Focus

1. **Previous run is a v2 report over 5 MB** (exactly today's broken case): it must load through the 64 MB v2 path and give real NEW/fixed/carried results. Test in Task 2.
2. **A shard is deleted or edited by hand between `run-scan.sh` and `triage.py apply`**: `apply` must fail with `ReportCorrupt`, naming the shard, and change nothing. Test in Task 5.
3. **Regenerating a run with fewer findings** (`--keep-verdicts` after the audit, or a rerun into the same folder): stale shards from the earlier save must be removed, or `iter_findings` would double-count. Test in Task 1.
4. **Repo names that differ only in characters unsafe in file names, and the `_host` label** (`this machine`): shard file names must be derived safely and stay inside `findings/`. Test in Task 1.
5. **The agent calls `record` twice for one fingerprint, or `next` after everything is recorded**: the second `record` is refused without `--replace`; `next` prints `{"done": true}`. Test in Task 5.

---

### Task 1: `report_store` — sharded save/load with v2 fallback

**Files:**
- Create: `job-security-scan/scripts/lib/report_store.py`
- Modify: `job-security-scan/scripts/lib/report_model.py:15` (`SCHEMA_VERSION = 3`), `:146` (accept v2 and v3 previous)
- Modify: `job-security-scan/scripts/lib/report_schema.py:14,75-77` (`MAX_FINDINGS = 200000`; accept `schema_version in (2, 3)`; add `validate_index`)
- Test: `job-security-scan/scripts/test-reports.py` (new class `StoreTests`)

**Interfaces:**
- Produces:
  - `class ReportError(Exception)`, `ReportTooLarge(ReportError)`, `ReportCorrupt(ReportError)`, `ReportMissing(ReportError)`
  - `save(doc: dict, run_dir: Path) -> Path` writes shards, then the index via temp file + `os.replace`; deletes `findings/*.json` not listed in the new index; returns the index path. It does not mutate `doc`.
  - `load_full(run_dir: Path) -> dict`: in-memory doc with `findings` (and full `fixed`) restored, `rules`/`shards`/`fixed_total` removed, `schema_version` 3. It validates with `report_schema.validate` and raises `ReportCorrupt` on errors.
  - `load_index(run_dir: Path) -> dict` and `iter_findings(run_dir: Path, index: dict) -> Iterator[dict]` (shard-by-shard, size and sha256 checks, rule fields re-expanded).
  - `shard_name(repo: str, n: int) -> str`: `re.sub(r"[^A-Za-z0-9._-]", "_", repo)` with a leading `.` replaced by `_`, plus `"-%03d.json" % n`.
  - `report_schema.validate_index(index: dict) -> list[str]`.
- For a v2 file, `load_full` returns the parsed doc with `schema_version` set to 3 after validating it as v2.

- [ ] **Step 1: Write failing tests in `StoreTests(TempDirCase)`**

```python
def big_doc(n=30000, repos=("api", "web", "this machine")):
    # build via report_model.build_document from finding(...) rows: n rows across repos,
    # 50 distinct rule_ids each with a 3,000-char description, severities cycling C/H/M/L
    ...

def test_shards_respect_caps_and_round_trip(self):
    doc = big_doc(); report_store.save(doc, self.tmp)
    idx = self.tmp / "security-report.json"
    self.assertLessEqual(idx.stat().st_size, 256 * 1024)
    for p in (self.tmp / "findings").glob("*.json"):
        self.assertLessEqual(p.stat().st_size, 4 * 1024 * 1024)
        self.assertLessEqual(len(json.loads(p.read_text())["findings"]), 2000)
    back = report_store.load_full(self.tmp)
    self.assertEqual(back["findings"], doc["findings"])   # titles/descriptions re-expanded
    self.assertEqual(back["counts"], doc["counts"])

def test_sha_mismatch_is_corrupt(self):            # edit one byte in a shard -> ReportCorrupt naming the file
def test_missing_shard_is_corrupt(self):
def test_oversize_shard_is_too_large(self):        # pad a shard past 5 MB -> ReportTooLarge, message has "5242880"
def test_resave_removes_stale_shards(self):        # save 30k, save 100 -> only listed shards remain, load_full has 100
def test_shard_names_are_safe(self):               # shard_name("this machine",1)=="this_machine-001.json"; "../x" stays in findings/
def test_v2_file_loads(self):                      # write a v2 doc (json indent=2) of ~6 MB -> load_full works, schema_version 3
def test_v2_over_64mb_is_too_large(self):          # sparse file via f.truncate(64*1024*1024+1)
def test_fixed_is_capped_in_index(self):           # doc["fixed"] of 2,500 -> index has 2,000 + fixed_total 2500; load_full restores 2,500
def test_over_max_findings_is_too_large(self):     # 200,001 rows -> save raises ReportTooLarge naming the top repo/scanner and "--profile standard"
def test_row_over_64kb_is_rejected(self):          # one row with a 70 KB description -> ReportTooLarge
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I job-security-scan/scripts/test-reports.py StoreTests -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'report_store'`

- [ ] **Step 3: Implement `report_store.py` and the schema/model version changes**

Sort the rows by `(repo, severity rank, file, line)`. Accumulate each row's compact serialized length and start a new shard when either 2,000 rows or 4 MB would be exceeded. The `rules` table takes `title`/`description`/`url` from the first row of each `rule_id`; drop those fields from a row only when they equal the rule entry. `sha256` is computed over the exact bytes written. `validate_index` checks the `TOP_KEYS` minus `findings`, plus `rules`, `shards` (each with `file`, `repo`, `count`, `bytes`, `sha256`, and `file` matching `^findings/[A-Za-z0-9._-]+\.json$`), and that the sum of `count` equals the sum of `counts`.

- [ ] **Step 4: Run the tests and confirm they pass, plus the existing suites**

Run: `python3 -I job-security-scan/scripts/test-reports.py -v && python3 -I job-security-scan/scripts/test-verification.py ValidatorTests FingerprintTests ChangesTests`
Expected: all OK. Adjust `ValidatorTests.test_generated_document_is_valid` to expect `3`.

- [ ] **Step 5: Commit**

```bash
git add job-security-scan/scripts/lib/report_store.py job-security-scan/scripts/lib/report_model.py job-security-scan/scripts/lib/report_schema.py job-security-scan/scripts/test-reports.py job-security-scan/scripts/test-verification.py
git commit -m "feat(job-security-scan): sharded report store (schema v3) with v2 fallback"
```

### Task 2: Wire the store into the generator and model (fixes F2 and F3)

**Files:**
- Modify: `job-security-scan/scripts/lib/report_model.py:227-262` (`load_report`, `find_previous`)
- Modify: `job-security-scan/scripts/generate-report.py:718-734` (`write_reports`), `:830-865` (`--previous`, `--keep-verdicts`)
- Modify: `job-security-scan/scripts/lib/report_formats.py` (show `run.previous_error`)
- Modify tests that read `security-report.json` directly: `scripts/test-reports.py`, `scripts/test-verification.py`, `scripts/test-audit-report.py`, `scripts/test-shai-hulud-report.py`. Use `report_store.load_full(run_dir)` wherever they read `["findings"]`.
- Test: `job-security-scan/scripts/test-verification.py` (`GenerateChangesTests`)

**Interfaces:**
- Consumes: `report_store.save`, `report_store.load_full`, `ReportError` (Task 1)
- Produces:
  - `report_model.load_report(run_dir: Path) -> dict` raises `ReportError`. It now takes the **run folder**, not the json path; update every caller.
  - `report_model.find_previous(run_dir) -> (doc | None, folder | None, error: str | None)`. A newer previous folder that fails to load returns `(None, folder, "<message>")` and does not fall back to older runs.
  - `doc["run"]["previous_error"]: str | None` (add it to the schema's allowed `run` keys).
  - `write_reports` saves through `report_store.save` (no `json.dumps(doc, indent=2)`).

- [ ] **Step 1: Write failing tests**

```python
def test_previous_v2_over_5mb_is_compared(self):     # previous run folder holds a 6 MB v2 json -> fixed/NEW computed, previous_run set
def test_unreadable_previous_sets_error_and_fixes_nothing(self):
    # previous run's shard deleted -> exit 0, run.previous_error contains "missing", doc["fixed"] == [],
    # every finding change == "new" is NOT asserted; assert "change tracking unavailable" in security-report.md
def test_keep_verdicts_with_unreadable_report_exits_1(self):
    # make run, corrupt a shard, rerun generate-report --keep-verdicts -> returncode 1, index bytes unchanged
def test_explicit_previous_unreadable_is_reported(self):   # --previous <bad dir> -> previous_error set, stderr names the dir
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `python3 -I job-security-scan/scripts/test-verification.py GenerateChangesTests -v`
Expected: FAIL (`previous_error` is missing and the `--keep-verdicts` run exits 0)

- [ ] **Step 3: Implement the changes**

With `--keep-verdicts`, wrap the load and call `sys.exit(1)` with `"generate-report: cannot keep verdicts: <msg>"` **before** any write. The Markdown summary line reads `Change tracking unavailable: <previous_error>`.

- [ ] **Step 4: Run every Python suite and confirm it passes**

Run: `for t in job-security-scan/scripts/test-*.py; do python3 -I "$t" || exit 1; done`
Expected: all OK

- [ ] **Step 5: Commit** — `feat(job-security-scan): loud previous/keep-verdicts failures; reports saved sharded`

### Task 3: Validator CLI and e2e readers (fixes F4)

**Files:**
- Modify: `job-security-scan/scripts/validate-report.py` (accept a run folder or an index path)
- Modify: `job-security-scan/tests/e2e/assert-located.py`, `tests/e2e/assert-shai-hulud-section.py`, `tests/e2e/run-e2e.sh:99-102`, `tests/e2e/run-shai-hulud-e2e.sh:96-97`
- Test: `job-security-scan/scripts/test-reports.py` (`ValidateCliTests`)

**Interfaces:**
- Consumes: `report_store.load_index`, `iter_findings`, `report_schema.validate_index`
- Produces: `validate-report.py PATH`, where PATH is a run folder or `<run>/security-report.json`. It prints `VALID    <path> (<n> findings, <k> shards)` and exits 0, or `INVALID ...` and exits 1. It validates shard by shard and never holds more than one shard plus the index. The e2e asserts take the run folder.

- [ ] **Step 1: Write failing tests** — a sharded 30k-finding run gives `VALID` with `shards` in the output. The same run with a corrupted shard gives exit 1 and output naming the shard. The index path works the same way as the folder path.
- [ ] **Step 2: Run** `python3 -I job-security-scan/scripts/test-reports.py ValidateCliTests -v` and confirm it fails (`larger than` or a missing-findings error).
- [ ] **Step 3: Implement.** In `run-e2e.sh:102`, replace the inline `json.load` with a `python3 -I -c` that does `sys.path.insert(0, "<skill>/scripts/lib"); import report_store; sys.exit(0 if report_store.load_index(Path(sys.argv[1]))["run"]["previous_run"] else 1)` on the run folder.
- [ ] **Step 4: Run the test** and `bash -n job-security-scan/tests/e2e/*.sh` and confirm both pass.
- [ ] **Step 5: Commit** — `feat(job-security-scan): validate sharded reports; e2e reads via report_store`

### Task 4: Bounded Markdown — `SUMMARY.md` and compact `security-report.md` (fixes F6)

**Files:**
- Modify: `job-security-scan/scripts/lib/report_formats.py` (`render_markdown`; new `render_summary`)
- Modify: `job-security-scan/scripts/generate-report.py` (`write_reports` also writes `SUMMARY.md`)
- Test: `job-security-scan/scripts/test-reports.py` (`FormatTests`)

**Interfaces:**
- Produces: `report_formats.render_summary(doc: dict, max_bytes: int = 20 * 1024) -> str`. Sections, in order: per-repo status table, Shai-Hulud rows, changes (counts + up to 20 new CRITICAL/HIGH), verification counts, up to 50 CRITICAL+HIGH as `` `file:line` rule (verdict) ``, deep-audit summary, report paths. If it would exceed `max_bytes`, drop finding lines from the end and append `… N more in security-report.html`. The result is always ≤ `max_bytes` UTF-8 bytes.
- `render_markdown` lists every CRITICAL and HIGH finding as today. MEDIUM/LOW/INFO become a `| repo | rule | severity | count |` table instead of one block per finding. Secrets still show `file:line` only.

- [ ] **Step 1: Write failing tests**

```python
def test_summary_is_bounded(self):              # 30k-finding doc -> len(render_summary(doc).encode()) <= 20480 and "more in security-report.html" in it
def test_summary_never_contains_secret_code(self):  # secret row with code -> code text absent
def test_markdown_lists_all_high_and_tables_low(self):  # 300 HIGH + 20k LOW -> 300 HIGH fingerprints present, LOW as table rows, size < 2 MB
def test_write_reports_writes_summary(self):    # GenerateTests: SUMMARY.md exists after generate-report
```

- [ ] **Step 2: Run** `python3 -I job-security-scan/scripts/test-reports.py FormatTests GenerateTests -v` and confirm it fails.
- [ ] **Step 3: Implement** `render_summary`, the `render_markdown` table change and the `SUMMARY.md` write.
- [ ] **Step 4: Run all suites** (loop from Task 2) and confirm they pass. Update any existing assertion that expected a MEDIUM/LOW finding block in the Markdown.
- [ ] **Step 5: Commit** — `feat(job-security-scan): bounded SUMMARY.md; compact Markdown for MEDIUM and below`

### Task 5: One-by-one triage — `queue` batches, `next`, `record`, directory `apply` (fixes F1 and F5)

**Files:**
- Modify: `job-security-scan/scripts/triage.py`
- Test: `job-security-scan/scripts/test-verification.py` (`TriageTests`)

**Interfaces:**
- Consumes: `report_store.load_full`, `report_store.save`, `ReportError`; `generate-report.write_reports` (Task 2 signature, unchanged)
- Produces (CLI):
  - `triage.py queue RUN` writes `triage/queue-index.json` = `{"schema_version": 2, "profile", "items": [{"fingerprint","repo","severity","batch"}]}` (no context) and `triage/batch-NNN.json` = `{"items": [<v1 queue item>]}` with 10 items each, most severe first. It deletes any old `triage/queue.json` and `batch-*.json`.
  - `triage.py next RUN` prints one JSON object to stdout: the first item in queue-index order with no `triage/verdicts/<fp>.json`, taken from its batch file. It prints `{"done": true}` when none remain. Exit 0.
  - `triage.py record RUN FILE|- [--replace]` validates one object with the existing `parse_verdicts` rules (wrap it as `{"verdicts":[obj]}`), checks that the fingerprint is in `queue-index.json`, and writes `triage/verdicts/<fp>.json`. An existing file without `--replace` gives exit 1 and `already recorded`. Exit 1 on any error, with nothing written.
  - `triage.py apply RUN [VERDICTS.json]`: with no file, it merges every `triage/verdicts/*.json`. With a file, the bulk path runs as today. Both call `report_store.save` and regenerate the reports plus `NEEDS-VALIDATION.md`. A `ReportError` gives exit 1 with its message, never "run run-scan.sh again".
  - `load_run(run_dir)` uses `report_store.load_full`.

- [ ] **Step 1: Write failing tests**

```python
def test_queue_writes_batches_without_context_in_index(self):  # 23 queued -> batch-001..003, index has no "context" key
def test_next_record_loop_equals_bulk_apply(self):
    # run A: next/record each item then apply; run B: same verdicts as one verdicts.json + apply
    # -> load_full(A)["findings"] == load_full(B)["findings"] (ignoring run_dir)
def test_next_prints_done_when_all_recorded(self):
def test_record_twice_refused_without_replace(self):
def test_record_invalid_writes_nothing(self):      # severity on a rejected verdict -> exit 1, verdicts/ empty
def test_apply_with_corrupted_shard_changes_nothing(self):  # exit 1, "ReportCorrupt"/shard name in stderr, index bytes unchanged
def test_queue_on_large_run_works(self):           # 6 MB-equivalent run (5,000 HIGH semgrep rows) -> queue exit 0
```

- [ ] **Step 2: Run** `python3 -I job-security-scan/scripts/test-verification.py TriageTests -v` and confirm it fails.
- [ ] **Step 3: Implement** the commands above. Update the existing `TriageTests` that read `queue.json` to read `queue-index.json` plus the batches.
- [ ] **Step 4: Run all suites** and confirm they pass.
- [ ] **Step 5: Commit** — `feat(job-security-scan): one-by-one triage (next/record) on sharded reports`

### Task 6: Docs, schema file, version bump

**Files:**
- Modify: `job-security-scan/references/verification.md` (Steps 1–4 become `queue` → loop `next` → fresh verifier → `record` → `apply`; tell the agent never to open `queue-index.json`, batch files or shards directly)
- Modify: `job-security-scan/SKILL.md`:
  - Phase 9 steps;
  - Reports tree (`findings/`, `SUMMARY.md`, `triage/verdicts/`);
  - Output Format step 2 changes to "Read `SUMMARY.md`";
  - `validate-report.py <run>`;
  - `metadata.version: "3.1"`.
- Modify: `job-security-scan/assets/report.schema.json` (index v3 + shard definitions; v2 kept under `$defs` for reference)
- Modify: `job-security-scan/README.md` (report layout), root `README.md:45` badge `v3.0` → `v3.1`
- Modify: `job-security-scan/scripts/run-scan.sh:28,682` (also echo `SUMMARY.md`)

- [ ] **Step 1: Make the doc edits above.**
- [ ] **Step 2: Run the repo gates**

Run: `python3 tools/validate_skills.py && python3 tools/test_validate_skills.py && python3 -m compileall -q tools */scripts && for f in $(git ls-files '*.sh'); do bash -n "$f" || exit 1; done && for t in job-security-scan/scripts/test-*.py; do python3 -I "$t" || exit 1; done`
Expected: exit 0, validator reports no errors

- [ ] **Step 3: Commit** — `docs(job-security-scan): v3.1 sharded reports and one-by-one triage`
