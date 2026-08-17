---
name: speckit-code-review
description: |
  Line-by-line code review against a feature spec, producing strict JSON pass/fail
  with business coverage, code/security/architecture issues, and test coverage.
  Triggers: "speckit code review", "review with spec", "spec coverage audit".
compatibility: Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, and a spec at specs/<feature-folder>/spec.md.
license: MIT
allowed-tools: bash glob grep view create edit
metadata:
  specification: agentskills.io/specification
  output_contract: strict-json
  author: Alex Nguyen
  version: "0.0.3"
---

# Speckit Code Review

Compare implementation code to `specs/<feature-folder>/spec.md` and return a strict JSON verdict.
The spec may come from `speckit.specify` (usually already has `FR-*`/`NFR-*` IDs) or from
`superpowers:brainstorming` (narrative design doc, usually no IDs) — both are reviewed identically.

**Always run inline.** Never dispatch as a background task or sub-agent; the caller needs the JSON in-band.

Portability note: `allowed-tools` uses GitHub Copilot-style names (`bash glob grep view create edit`).
Claude Code and OpenCode expose the same capabilities under their own names (`Bash`, `Read`, `Edit`,
`Write`, `Glob`, `Grep`). The review procedure below is identical on all three hosts.

## Inputs

- `spec.md` for the target feature. If no path is given, resolve from `specs/*/spec.md` using the
  current branch name or changed files; ask the user only if still ambiguous.
- Review scope = current git change set (staged + unstaged, incl. renames/deletes). This is
  evaluated in the current working directory — when invoked from `speckit-auto`, the caller must
  run this skill inline from inside the Stage 01 linked worktree, never from the base checkout.
- **Incremental scope (optional)**: the caller may pass `scope` as either a newline-separated file
  list (`--files <paths>`) or a compact map `file → {lines, blob}` — the hunk ranges changed since
  the last review of the same feature. When both `scope` and `state_file` are present, only the
  scoped hunks are re-read; all other files/hunks/areas carry their prior verdicts forward from
  `state_file`. When `scope` is absent, scope = the full git change set (backward-compatible).
- **Invalidate (optional)**: a list of tokens marking which cached review state is stale because a
  Stage 02 artifact changed since the last pass: `spec` (re-derive the checklist + re-run all five
  areas), `plan` (re-run architecture + business-gap), or `tasks` (re-run business-gap +
  code-quality + unit-tests for the scoped files). Categories/tokens not listed carry their prior
  verdicts forward. `invalidate: ["spec"]` is equivalent to a full pass.
- **Retry runs**: the `state_file` path from the previous failed review of the same feature
  (supplied by the caller, e.g. speckit-auto Stage 03 re-entry, or the newest existing
  `.speckit/review-<spec-id>-*/state.json`). Its presence switches area loading to the selective
  mode below.

## Spec ID

`<spec-id>` drives all output paths. Derive it from the feature folder name — never invent one, so
reruns resolve to the same paths:

| Folder | `<spec-id>` | Rule |
|---|---|---|
| `010-user-login` | `010` | leading numeric prefix |
| `ddm-6157-user-login` | `ddm-6157` | leading issue key (`<letters>-<digits>`) |
| `some-feature` | `some-feature` | whole folder name |

Lowercase; strip any character outside `[a-z0-9-]`.

## Requirement Checklist

Step 1 must always yield a numbered checklist.

- **IDs present** → use verbatim; set `requirements_source: "declared"`.
- **No IDs** → synthesize; set `requirements_source: "synthesized"`:
  1. Extract one testable statement per requirement, in priority order: acceptance criteria,
     requirements/behaviour sections, user stories, explicit constraints, any must/should sentence.
  2. Classify `FR-` (functional) vs `NFR-` (performance, reliability, security posture, scalability,
     maintainability, compliance, UX).
  3. Number in document order so IDs stay stable across reruns.
  4. Record each as `{id, statement, spec_anchor}` under `synthesized_requirements` in the
     `business-gap` detail file, so findings trace back to the spec.

If zero requirements are extractable, return `failed` with one `FR-000` fix telling the user to add
testable requirements to the spec. Never return `pass` against an empty checklist.

On a **retry run** (prior `state_file` present), do **not** re-derive the checklist — load it
verbatim from `state_file.checklist` and reuse its `requirements_source`. Re-read `spec.md` only if
`state_file.checklist` is absent, `spec.md` has a newer mtime than the state file, or the caller's
`invalidate` includes `spec`.

## Procedure

1. Build the requirement checklist (see above). On retry, load it from `state_file.checklist`
   instead of re-reading `spec.md`; re-derive only if `state_file.checklist` is absent, `spec.md`
   is newer than the state file, or `invalidate` includes `spec`.
2. Resolve the review scope: use the explicit `scope` input if supplied, else compute the full
   git change set (staged + unstaged, incl. renames/deletes). When `scope` carries line ranges,
   read only those hunks (plus ~5 lines of surrounding context) instead of whole files. On retry
   with `state_file` + `scope`, restrict re-reading to the scoped hunks; files/hunks outside
   `scope` carry forward as verified.
3. **Project guidelines (conditional)** — if `docs/guidelines/architecture.md` exists, load
   [references/project-guidelines-review.md](references/project-guidelines-review.md) and follow its
   Steps 1–4 to load only the guideline files matching the changed-file categories. Skip silently
   if that file is absent.
4. Run each standard area — load its reference file, run the review, then **discard it from context**
   before loading the next:

   | Area | Reference | Issue IDs |
   |---|---|---|
   | Business Gap | [business-gap.md](references/business-gap.md) | `FR-*`, `NFR-*` |
   | Code Quality (incl. conditional SonarQube MCP scan) | [code-quality.md](references/code-quality.md) | `CODE-*` |
   | Security | [security.md](references/security.md) | `SEC-*` |
   | Architecture | [architecture.md](references/architecture.md) | `ARCH-*` |
   | Unit Test Coverage (last) | [unit-test-coverage.md](references/unit-test-coverage.md) | `TEST-*` |

   **Area loading modes:**
   - **First review** (no prior `state_file`): full pass over all five areas, serial load/discard.
   - **Retry** (prior `state_file` exists): load **only** the area refs whose categories have
     open (unresolved) findings in `state_file`; categories with no open findings carry their
     prior verdicts forward from `state_file` — do not reload their refs. Recompute
     `Business cover` from the checklist in `state_file`, re-checking only open `FR-*`/`NFR-*`
     items now. When a `scope` is supplied, additionally restrict each loaded area to the scoped
     files: findings on files outside `scope` carry forward and are not re-read or re-scanned.
     Any category named by `invalidate` is treated as having open findings this pass: its prior
     verdicts are dropped and its area ref is loaded and run again. `invalidate` expands as
     `spec` → all five areas, `plan` → `architecture` + `business-gap`, `tasks` → `business-gap`
     + `code-quality` + `unit-tests`.
   - **Test-runner skip**: before loading `unit-test-coverage.md`, probe for a test runner
     (package.json `scripts.test`, `*.spec.*`/`*.test.*` files, `tests/`, `pytest.ini`/
     `pyproject.toml [tool.pytest]`, `go.mod` + `*_test.go`, surefire in `pom.xml`, a `test`
     target in `Makefile`). If none exists, report `unit-test-coverage: "N/A (no test runner
     detected)"` without loading the ref.

5. If guideline files were loaded in step 3, run the advanced pass (Step 5 of
   project-guidelines-review.md) and merge its findings into the standard results, tagging each with
   `guideline_source`.
6. `Business cover = round(covered / total * 100)`.
7. Write `state_file` (each finding carries `status: open|resolved` so retry runs can carry
   verified verdicts forward), plus one detail file **per category that has issues**. Skip empty
   categories; on `pass` write only `state_file`. Persist a `scope` digest inside `state_file` —
   the `last_reviewed_sha` and the `file → {lines, blob}` map actually reviewed this pass — so the
   next iteration diffs against what was already reviewed, never re-reading unchanged hunks.
8. Build `fixes` from all findings ordered high → medium → low severity, then keep only the **top 3**
   inline. The rest live in `state_file` and the category detail files.
9. `status` = `pass` only if `fixes` is empty **and** coverage ≥ 80% (or `N/A`) **and** the checklist
   is non-empty; otherwise `failed`.

## Output Contract

Return **exactly one compact JSON object**, ≤ 400 tokens, no markdown, no prose outside the JSON.
Field names are literal (keep spaces and capitalization). Never mirror verbose findings inline —
they already live in the files.

| Field | Value |
|---|---|
| `status` | `"pass"` or `"failed"` |
| `Business cover` | percent string, `"0%"`–`"100%"` |
| `unit-test-coverage` | percent string, or `"N/A (no test runner detected)"` — `N/A` counts as passing |
| `state_file` | `.speckit/review-<spec-id>-<ts>/state.json` — ordered issue inventory + next fix queue + pinned `checklist` + `scope` digest, so speckit-auto can resume without re-deriving the checklist or re-reading unchanged hunks |
| `detail_files` | map of category → path; `{}` on pass. Keys: `business-gap`, `architecture`, `security`, `code-quality`, `unit-tests`, each at `.speckit/review-<spec-id>-<ts>/<key>.json` |
| `fixes` | `[]` on pass; else ≤ 3 objects with exactly `id`, `file`, `method`, `lines`, `action` |

`fixes` entry fields:

- `id` — prefix selects the detail file: `FR-*`/`NFR-*` → business-gap, `ARCH-*` → architecture,
  `SEC-*` → security, `CODE-*` → code-quality, `TEST-*` → unit-tests
- `file` — relative path · `method` — `Class::method` or function name
- `lines` — range like `"88-140"`, or `"new"` when the file/method must be created
- `action` — one imperative sentence, no sub-bullets, specific enough to act on **without** opening
  the detail file

```json
{
  "status": "failed",
  "Business cover": "70%",
  "unit-test-coverage": "61.2%",
  "state_file": ".speckit/review-010-1722348000/state.json",
  "detail_files": {
    "business-gap": ".speckit/review-010-1722348000/business-gap.json",
    "security": ".speckit/review-010-1722348000/security.json",
    "unit-tests": ".speckit/review-010-1722348000/unit-tests.json"
  },
  "fixes": [
    {"id": "FR-004", "file": "src/account/service.ts", "method": "AccountService::createAccount", "lines": "88-140", "action": "Add password minimum-length validation (>=8 chars) before calling hashPassword"},
    {"id": "SEC-001", "file": "src/auth/password.ts", "method": "validatePassword", "lines": "5-20", "action": "Enforce min 12 chars, 1 uppercase, 1 digit, 1 symbol in password policy"},
    {"id": "TEST-001", "file": "src/account/service.spec.ts", "method": "AccountService::createAccount", "lines": "new", "action": "Add test: password shorter than 8 chars throws ValidationException"}
  ]
}
```

A passing result is the same shape with `"status": "pass"`, `detail_files: {}`, `fixes: []`.

## Quality Bar

- Never report `pass` while `fixes` is non-empty, coverage < 80%, or the checklist is empty.
- Keep verbose analysis in the category files; the inline object stays under 400 tokens.
- Severity scale for every area: `high` = exploitable or breaks a requirement/invariant;
  `medium` = degrades correctness, security posture, or maintainability; `low` = cosmetic or
  non-exploitable.
