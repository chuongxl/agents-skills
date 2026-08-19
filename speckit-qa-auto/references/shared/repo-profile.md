# Shared: Repo Profile Discovery

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

`speckit-qa-auto` carries no knowledge of any particular repository. It owns the *process*; the
target repo owns its *conventions*. This file is how Stage 01 discovers those conventions at
run time, and what of that discovery is allowed to persist.

## Discovery Order

Search, stopping at the first source that answers each field:

1. A repo-local automation skill — `.github/skills/*auto-testing*/SKILL.md`,
   `.claude/skills/*/SKILL.md`
2. `AGENTS.md` / `CLAUDE.md`
3. `docs/` guideline files
4. Inference — `package.json` scripts, `playwright.config.ts`, and one existing
   `.feature` / `.steps.ts` pair read as a worked example

Run-only, read-only, against the source checkout, before any worktree exists — discovery is safe
to run this early precisely because it only reads (design spec §4 step 1). A field that no source
answers is asked of the human, once.

## Field Reference

Fourteen fields, resolved by discovery. These names are a public interface consumed verbatim by
the pipeline stages — never rename, re-case, or reshape one.

| Field | Example (reference repo) |
|---|---|
| `test_root` | `src/tests` |
| `feature_path` | `src/tests/{domain}/{domain}-{aspect}.feature` |
| `steps_path` | `src/tests/{domain}/{domain}-{aspect}.steps.ts` |
| `page_path` | `src/pages/{domain}/{DomainAspect}Page.ts` |
| `selectors_path` | `src/pages/{domain}/{DomainAspect}Selectors.ts` |
| `testdata_path` | `src/support/{domain}/fixtures/{name}.json` |
| `generate_cmd` | `npm run bddgen` |
| `scoped_run_cmd` | `npm run test:headed -- --grep "<tag>" --project chromium` |
| `frontend_source_root` | `om-mom-frontend` (submodule) |
| `selector_attribute` | `data-testid` |
| `existing_tags` | `@Automation`, `@Regression_Test`, `@{Domain}` |
| `xray_project_key` | `MOM` |
| `branch_prefix` | `test/` |
| `artifact_root` | `docs/qa` |

Any example path built from a Jira key follows this rule (design spec §4 step 8): the key is
uppercase where it names the issue — `run.jira_key`, the `@REQ_` / `@TEST_` tags, every Jira or
Xray API call — and **lowercase in every path**: the artifact directory, the branch name, the
resume glob. Paths and globs are case-sensitive on Linux CI even where a developer's macOS
checkout forgives them, so a run that creates `docs/qa/mom-1234-…` and later resumes by globbing
`MOM-1234-*` finds nothing and silently starts a second artifact folder. A story `MOM-1234`
therefore resolves its `artifact_dir` to `docs/qa/mom-1234-<slug>`, never `docs/qa/MOM-1234-<slug>`.
`artifact_root` itself stays `docs/qa` — the shared root every ticket folder hangs under, and the
one place the `.repo-profile.json` cache below lives.

## What Is Cached, And What Is Not

A file that is committed and read *before* discovery stops being a cache and becomes
configuration — and configuration nobody remembers authoring is worse than no configuration at
all. A playbook can change its conventions while the file keeps applying the old ones, and a
"do the paths still exist?" check does not catch that: the paths still exist, they are simply no
longer the convention. That failure is what this design refuses.

The cache is therefore split by *who can answer*, not by which fields are convenient to store:

```json
// docs/qa/.repo-profile.json
{
  "answers": {
    "xray_project_key":     "MOM",
    "frontend_source_root": "om-mom-frontend"
  },
  "provenance": {
    "sources": [
      {"path": ".github/skills/mom-auto-testing/SKILL.md", "sha256": "…"},
      {"path": "package.json",                            "sha256": "…"}
    ]
  }
}
```

Shared by every ticket in the repo — one file at `<artifact_root>/.repo-profile.json`, not one
per artifact folder.

## The Three Rules

1. **`answers` holds only what no file can answer** — the questions a human had to answer because
   discovery found no source for them. Nothing that a file could have supplied belongs here.
2. **Every other field in the table above is re-derived from the playbook on every run.** It is
   never stored. The playbook stays the single source of truth for convention; the cache never
   competes with it.
3. **`provenance` records every file discovery read, with its content hash.** On each run the
   hashes are recomputed. Any mismatch means the playbook changed: re-derive, and report which
   source changed — staleness is made visible, never silent.

## A Stale Answer Is Re-Asked, Not Reused

A field in `answers` whose value no longer resolves is asked again, exactly as if no cache
existed — it is not patched, defaulted, or silently dropped:

- `frontend_source_root` names a path that is not a directory
- `xray_project_key` is a value Xray rejects

## Why A Path-Exists Check Is Not Enough

The temptation is to treat "the cached path still exists on disk" as proof the cache is still
valid. It is not. When a playbook changes its conventions, the old paths frequently keep
existing — they are just no longer where new work goes. A path-exists check passes on exactly the
case it needed to catch. Provenance hashing over the *source files that produced the answer*
catches it instead, because the playbook's content, not the filesystem's shape, is what changed.
