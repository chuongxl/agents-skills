# Shai-Hulud indicator data

The `shai-hulud` scanner decides "affected" from `assets/ioc/shai-hulud.json`. This page says what
is in it, where each part comes from, and how to update it.

## Layout

| Key | What it holds | How the scanner uses it |
|---|---|---|
| `waves` | One entry per campaign wave, each with at least one reference URL | Every other entry names its wave |
| `packages` | Compromised `name` + exact `versions` per `ecosystem` (`npm`, `pypi`) | Exact match against lockfiles, installed packages, global installs, npm cache |
| `files` | Payload/stager file names; `sha256` list | Name matched inside a package directory or a hook target. When `sha256` is non-empty (generic names such as `bundle.js`) a hash match is required |
| `paths` | Path globs relative to the scanned root; optional `requires_marker` | Planted workflows and persistence files |
| `markers` | Strings unique to the worm (runner labels, repo descriptions, C2 hosts) | Searched only in workflows, path-indicator files and hook targets |

`scripts/lib/shaihulud/iocs.py` (`validate`) is the enforced contract; `assets/ioc/shai-hulud.schema.json`
mirrors it for editors. Package names are compared case-insensitively; PyPI names are PEP 503 normalised.

## Provenance

| Wave | Content | Source |
|---|---|---|
| `sh-1` (Sep 2025) | `bundle.js` SHA-256 hashes (7 variants), `shai-hulud.yaml` / `shai-hulud-workflow.yml` workflows | Socket and Wiz write-ups listed in the wave's `references` |
| `sh-1` | webhook exfil URL marker | Wiz |
| `sh-2.0` (Nov 2025) | 795 npm packages / 1,091 versions | Datadog `indicators-of-compromise`, `shai-hulud-2.0/consolidated_iocs.csv` (Apache-2.0, © Datadog), retrieved 2026-11-02 |
| `sh-2.0` | `setup_bun.js`, `bun_environment.js`, `discussion.yaml` backdoor, `formatter_*.yml`, runner `SHA1HULUD`, repo description marker | mnemonic and Cycode write-ups |
| `mini-2026` (May 2026) | `opensearch_init.js`, `.claude/` and `.vscode/` persistence files, C2 host `git-tanstack.com` | Akamai and Mend write-ups |

No public, licensed version-level package list was available for `sh-1` or `mini-2026` when this
file was seeded. For those waves, tier 1 relies on files, paths and markers. The `osv` scanner adds
OSV.dev malicious-package records (`MAL-` ids) for lockfiles, which covers many of those releases.

An indicator is only added with a reference that states it. Indicators that cannot be cited are left out.

## Updating

- **Refresh from remote lists:** `python3 -I scripts/fetch-iocs.py --out ~/.cache/job-security-scan/ioc`
  merges the CSV lists in `assets/ioc/sources.json` into a cache copy. `run-scan.sh` uses the cache when present.
- **Add a wave or indicator by hand:** edit `shai-hulud.json`, add the reference URL to the wave, then run
  `python3 -I scripts/test-shai-hulud.py IocTests`.
- **Use a different file for one run:** set `SHAI_HULUD_IOCS=/path/to/file.json` or pass `--iocs`.
