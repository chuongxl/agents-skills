# Import reports into DefectDojo

`scripts/import-defectdojo.py` reads a run folder or its `security-report.json`
file and converts it to DefectDojo's Generic Findings Import format. It accepts
legacy v2 reports with inline findings and current v3 reports with an index and
integrity-checked finding shards. The shared report reader validates and
reassembles both formats before scanner metadata enrichment.
Python 3.8+ and its standard library are sufficient. It does not run scanners,
change the source report, or read repository source files. By default it also
reads adjacent run metadata and Trivy, Semgrep, OSV and advisory JSON to recover
information omitted or shortened by report generation.

## Usage

Run after verification and any deep audit have finished. You can import an
unfinished run, but pending findings remain unverified and incomplete audit
leads are not imported. The command prints warnings for these cases.

Preview without credentials or network requests:

```bash
python3 -I job-security-scan/scripts/import-defectdojo.py \
  /path/to/security-run-YYYYMMDD-HHMMSS --branch main
```

In DefectDojo, get an API v2 token from the user menu. Set
`DEFECTDOJO_API_TOKEN` through your secret manager, or save the token in a
private file outside any repository, readable only by you. Never commit it.
For uploads, pass the HTTPS URL of the authorized production DefectDojo instance
explicitly. The importer has no localhost URL default. Dry runs do not need a URL.

```bash
python3 -I job-security-scan/scripts/import-defectdojo.py \
  /path/to/security-run-YYYYMMDD-HHMMSS \
  --branch main --url https://defectdojo.example.com \
  --token-file ~/.config/job-security-scan/defectdojo.token --upload
```

Replace `https://defectdojo.example.com` with the production URL approved for
your organization.
Use the same branch label on subsequent runs. If the report has source-reference
branches, `--branch` is optional and each repository uses its recorded branch.
For older reports with no branch, supply a label describing the actual scope,
such as `workspace`, rather than assuming it was `main`.

Optional arguments:

| Argument | Behavior |
|---|---|
| `--repo NAME` | Import only that repository |
| `--output-dir PATH` | Create a new directory with private JSON payloads, per-request receipts and `summary.json`; refuses an existing directory |
| `--batch-size N` | Findings per request, 1-1000; default 500 |
| `--timeout N` | HTTP timeout in seconds; default 300 |
| `--url URL` | DefectDojo base URL; required with `--upload`, with no default |
| `--include-code` | Include redacted non-secret excerpts already in the report; never opens source files |
| `--no-enrich` | Use only the normalized report; skip adjacent metadata and scanner JSON |
| `--update-existing` | Refresh matched findings' scanner-owned descriptions and native detail fields; preserve lifecycle and review state |

HTTPS is required for remote instances. Loopback HTTP is supported only for an
explicitly supplied local test URL; the importer never selects localhost by
default. Redirects and environment HTTP
proxies are disabled so credentials cannot be forwarded elsewhere. TLS
certificate verification stays enabled. The importer does not retry failed
uploads automatically. After an ambiguous timeout, check DefectDojo before
rerunning. Earlier successful requests remain imported; receipts identify them.

## Mapping and lifecycle

- Product Type: `<org> / <team>`.
- Product: repository name. Existing products must have unique, unambiguous names
  in your instance; do not reuse a repository name for unrelated organizations.
- Engagement: `job-security-scan / <branch>`, with engagement-only deduplication
  for newly created engagements.
- Test: `job-security-scan / <scanner> / <coverage mode>`, reused across batches
  and runs. Test Type: `Job Security Scan Scan (Generic Findings Import)`.
  Covered scanners with no findings also get an empty Test, not a placeholder
  finding. Test descriptions retain run and coverage context, commit references,
  verification counts, audit completeness and excluded-result summaries.
- Confirmed findings use their verified severity and `verified=true`.
  Pending and needs-validation findings use scanner severity and `verified=false`.
  Needs-validation blockers and plans are retained for non-secret findings.
- Rejected, locally accepted baseline findings, fixed-history entries and host
  findings are not uploaded. Existing server records for these are not changed.
  Local acceptance is not automatically DefectDojo risk acceptance.
- Source excerpts are excluded unless `--include-code` is supplied. Secret and
  credential-store findings always omit code, free-text evidence, scanner
  descriptions and URLs, even with that option. Raw secret findings are never
  enriched or attached.
- `close_old_findings=false` and `do_not_reactivate=true` are always sent.
  Partial scans, missing scanners, filtered findings and incomplete audits cannot
  automatically close or reopen existing findings. No automatic mitigation is
  supported, including on an empty scan.

Native finding fields include available fix versions, publication dates,
CVSS v3/v4, CWEs, vulnerability aliases, component versions, references,
verification evidence and remediation. Full descriptions and scanner metadata
are retained in finding descriptions; original titles, paths and package/fix
values are retained there even when native columns require truncation.
Ambiguous scanner matches are not enriched. Adjacent files must be regular
JSON files under 50 MiB, without symlink or traversal paths.

Raw scanner files and audit scratch files are not attached. Secret masks reduce
exposure, but are not a guarantee of anonymization: non-secret descriptions,
metadata and optional excerpts still contain project information. Upload only
to a DefectDojo instance authorized to hold it. Missing scanner files and source
text already truncated upstream cannot be reconstructed.

## Updating findings already imported

DefectDojo reimport does not reliably update matched descriptions, CVSS, CWE
associations and other details. Use `--update-existing` to refresh these through
the Finding API after each successful batch:

```bash
python3 -I job-security-scan/scripts/import-defectdojo.py \
  /path/to/security-run-YYYYMMDD-HHMMSS \
  --branch workspace \
  --token-file ~/.config/job-security-scan/defectdojo.token \
  --include-code --update-existing --upload \
  --output-dir /path/to/new-private-import-receipts
```

This explicitly overwrites scanner-owned descriptive fields, including manual
edits to those fields. It never PATCHes severity, verification, active/mitigated
status or risk acceptance. Native CWEs and aliases are merged without deleting
manually added entries. Refresh refuses missing or ambiguous identities and is
scoped to the exact imported Test. Normal reimport alone is insufficient to
repair older records.

## Stable matching

Each finding gets a namespaced `unique_id_from_tool` derived from organization,
team, repository and the report fingerprint. The default Generic Findings
matching algorithm is hash-based, so this field alone does not guarantee identity
across line moves or verdict changes. For stable identity, configure the dedicated
Test Type on your instance before importing, without changing other generic tools:

```python
DEDUPLICATION_ALGORITHM_PER_PARSER = {
    **DEDUPLICATION_ALGORITHM_PER_PARSER,
    "Job Security Scan Scan (Generic Findings Import)": "unique_id_from_tool",
}
HASHCODE_FIELDS_PER_SCANNER = {
    **HASHCODE_FIELDS_PER_SCANNER,
    "Job Security Scan Scan (Generic Findings Import)": ["unique_id_from_tool"],
}
```

These settings belong in your deployment's settings overrides and require its
normal restart procedure. Verify matching against your DefectDojo version before
relying on it. Do not mix native scanner imports and these normalized reports in
the same Tests. Trivy and OSV findings remain separate tool observations, not a
cross-scanner vulnerability count.

Exit codes: 0 means dry-run completed or every upload and requested detail refresh
succeeded; 1 means validation, authentication, transport or output failure. A successful response
means the import was accepted; background deduplication may still be running.

## Validation

```bash
python3 -I job-security-scan/scripts/test-defectdojo.py
```

For an instance test, import a fixture twice and check it reuses Tests without
adding findings. With fingerprint matching configured, also test moved lines,
changed verdicts and a partial scan that must leave absent findings open.
Also check native details after `--update-existing`, human review state, and
that a repeated detail refresh makes no changes.

API references:
[Generic Findings Import](https://docs.defectdojo.com/supported_tools/parsers/file/generic/),
[import and reimport API](https://docs.defectdojo.com/import_data/import_scan_files/api_pipeline_modelling/).
