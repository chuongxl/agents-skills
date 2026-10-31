# Advisory data and trusted sources

The advisory engine (built up over phases P0-P3) matches your project's components
against advisories read from **trusted vendor bulletins first**, then aggregators.
This page covers the data format and the trust rules. P0 ships the format, the
validator and a seed dataset; scanning is wired in later phases.

## Files

| File | Purpose |
| --- | --- |
| `assets/advisory.schema.json` | Format of an advisory bundle |
| `assets/sources.json` | Trusted-source registry: allowed hosts, vendors, aggregators |
| `assets/advisories/**/*.json` | Committed advisory bundles (used for scanning) |
| `assets/advisory-examples/` | Format examples, validated but never used for scanning |
| `scripts/validate-advisories.py` | Validates bundles and `sources.json` |
| `scripts/test-advisory-lib.py` | Self-tests (`python3 -I scripts/test-advisory-lib.py`) |

## Resolution order

1. Vendor bulletin (tier `vendor`) - authoritative for affected and fixed versions.
2. Ecosystem database (OSV, GitHub Advisory Database) - fills gaps; can lag vendors.
3. CISA KEV - only sets `exploited`.
4. endoflife.date - only reports end-of-life.

When two sources disagree, the vendor range wins and the conflict is flagged for review.

## Add an advisory

1. Copy a bundle from `assets/advisory-examples/` and edit it.
2. Set `source.url` to the vendor page; its host must be in `allowed_hosts` of `sources.json`.
3. Use `method: "manual"` if you typed it from the bulletin, `"llm-assisted"` if a model parsed it.
   LLM-assisted data stays a warning until a human sets `source.approved_by`;
   `--strict` turns that into an error.
4. Run `python3 -I scripts/validate-advisories.py`.

Rules the validator enforces beyond the schema: published advisories need `fixed` or
`last_affected`; `fixed` must come after `introduced`; aliases never repeat the id; ids are
unique across all bundles; every source host is allowlisted and HTTPS.

Use `status: "pending"` for a vendor pre-announcement with no details yet, and
`conditions` for advisories that only apply in some setups (for example glibc).

## Add a vendor

Add an entry to `vendors` in `sources.json` with `id`, `name`, `tier`, `components`
(`runtime:<name>` or `pkg:<type>/<name>` patterns, `*` allowed) and `sources`
(`url` + `format`: html, rss, json, osv, ghsa, text). Add its host to `allowed_hosts`.

## Check that sources are reachable

    python3 -I scripts/validate-advisories.py --check-sources

Exit code 3 means validation passed but some URLs were unreachable. Redirects are followed
only to allowlisted HTTPS hosts. Entries whose `note` says "to verify" have not yet been
confirmed against the live site.

## Exit codes

0 ok, 1 validation errors, 2 usage or unreadable input, 3 unreachable sources.
