# speckit-qa-auto Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `speckit-qa-auto` skill that takes a Jira issue to reviewed, passing Playwright-BDD tests in four stages, plus the `jira-to-speckit` Xray read mode it depends on.

**Architecture:** A router `SKILL.md` under 500 words dispatches to one of four pipeline stage files. Stages hand off through run state on disk, never through each other's prose; shared reference files are leaves that load nothing. Gherkin authored in `docs/qa/<key>/` is the source of truth, materialized into the repo's test tree as a scenario-level subset.

**Tech Stack:** Markdown skill definitions; Python 3.9+ stdlib for the validators; git; `curl` for Jira and Xray REST.

**Spec:** [`docs/superpowers/specs/2026-08-19-speckit-qa-auto-design.md`](../specs/2026-08-19-speckit-qa-auto-design.md)

## Global Constraints

Exact values, copied from the spec. Every task's requirements implicitly include this section.

- **Folder name equals frontmatter `name`**, lowercase kebab-case (`SKILL_SPEC.md`).
- **Required frontmatter keys:** `name`, `description` (40–1024 chars, says what *and* when), `compatibility`, `metadata.author`, `metadata.version`. Optional: `license`, `allowed-tools`. No other top-level key is permitted.
- **`metadata.author`: `Alex Nguyen`** — matches every existing skill in this repo.
- **Versions:** `speckit-qa-auto` starts at `0.1.0`; `jira-to-speckit` moves `0.2.0 → 0.3.0`.
- **No relative Markdown link may resolve outside its own skill folder.** Sibling skills are named in prose and invoked by name through the `skill` tool.
- **Every relative Markdown link must resolve to a file that exists.**
- **Root `README.md` skills-table version badge must match each `SKILL.md`.**
- **Coupling (spec §11.2):** files under `references/shared/` link to no other file in the skill; no file under `references/pipeline/` links to another file under `references/pipeline/`.
- **Authoring style (spec §11.1):** `SKILL.md` is a router under ~500 words. Graphviz only at decision points and bounded loops — exactly three diagrams across the whole skill. Diagram shapes follow `graphviz-conventions.dot`: diamond = question, box = action, plaintext = literal command, ellipse = state, octagon = warning, doublecircle = entry/exit.
- **`allowed-tools` for `speckit-qa-auto`:** `bash glob grep view create edit skill` (Copilot-style names; portability note required in the skill body).

---

## File Structure

| Path | Responsibility |
|---|---|
| `tools/validate_coupling.py` | Enforces spec §11.2 as a runnable check. Opt-in per skill via explicit argument |
| `tools/test_validate_coupling.py` | Self-test for the above, mirroring `test_validate_skills.py` |
| `jira-to-speckit/SKILL.md` | Gains the `xray_tests` input and the three output paths |
| `jira-to-speckit/references/XRAY_API.md` | Xray auth, the fixed JQL, the type split, the endpoints |
| `jira-to-speckit/README.md` | Documents the new mode |
| `speckit-qa-auto/SKILL.md` | Router: entry dispatch, stage table, required inputs |
| `speckit-qa-auto/README.md` | Human documentation, 500–1000 words |
| `speckit-qa-auto/references/shared/run-state.md` | **The data contract between stages.** Leaf |
| `speckit-qa-auto/references/shared/operating-rules.md` | Turn-ending conditions, fix-loop rules, circuit breaker. Leaf |
| `speckit-qa-auto/references/shared/workspace-guard.md` | Both content-addressed baselines. Leaf |
| `speckit-qa-auto/references/shared/repo-profile.md` | Discovery order, field list, `answers` + `provenance`. Leaf |
| `speckit-qa-auto/references/shared/selector-verification.md` | Evidence sources, the resolution diagram, Red Flags. Leaf |
| `speckit-qa-auto/references/shared/gherkin-conventions.md` | Tags, surface, scenario granularity, anti-drift. Leaf |
| `speckit-qa-auto/references/shared/host-adaptation.md` | Host detection, tool-name mapping. Leaf |
| `speckit-qa-auto/references/shared/commit.md` | Conditional commit, fast-forward-only push. Leaf |
| `speckit-qa-auto/references/pipeline/stage-01-intake.md` | Profile → baselines → worktree → intake |
| `speckit-qa-auto/references/pipeline/stage-02-test-design.md` | Analysis → dedup → design → selector gate → human gate |
| `speckit-qa-auto/references/pipeline/stage-03-automate.md` | Materialize → generate → verify → fix loop |
| `speckit-qa-auto/references/pipeline/stage-04-finish.md` | Report → baselines → commit → push |
| `test-case/speckit-qa-auto/test-cases.md` | Scenario coverage for the skill itself |
| `README.md` | Two rows in the skills table |

Twelve tasks. Each ends with a runnable check and a commit.

---

### Task 1: Coupling validator

The rest of the plan depends on this: it is how every later task proves it respected spec §11.2. Build it first, against fixtures, before any skill file exists.

**Files:**
- Create: `tools/validate_coupling.py`
- Test: `tools/test_validate_coupling.py`

**Interfaces:**
- Consumes: `relative_links(text) -> list[str]` from `tools/validate_skills.py` (already exists, strips fenced code and inline backticks).
- Produces:
  - `check_skill(skill_dir: Path) -> list[str]` — returns error strings, empty list when clean.
  - CLI `python3 tools/validate_coupling.py <skill-dir> [<skill-dir>...] [--json]`, exit `0` clean / `1` on any error.

- [ ] **Step 1: Write the failing test**

Create `tools/test_validate_coupling.py`:

```python
#!/usr/bin/env python3
"""Self-test for tools/validate_coupling.py.

Builds throwaway skill folders in a temp directory and asserts the checker
reports exactly the expected errors. Stdlib only; run with:

    python3 tools/test_validate_coupling.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_coupling import check_skill  # noqa: E402

FAILURES: list[str] = []


def expect(label: str, condition: bool) -> None:
    if condition:
        print(f"ok   - {label}")
    else:
        print(f"FAIL - {label}")
        FAILURES.append(label)


def build(root: Path, files: dict[str, str]) -> Path:
    skill = root / "sample-skill"
    for rel, body in files.items():
        path = skill / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    return skill


def test_clean_skill_has_no_errors(tmp: Path) -> None:
    skill = build(tmp / "clean", {
        "SKILL.md": "Router. See [stage 1](references/pipeline/stage-01.md).\n",
        "references/pipeline/stage-01.md": "Load [run state](../shared/run-state.md).\n",
        "references/shared/run-state.md": "The data contract. Links to nothing.\n",
    })
    expect("clean skill reports no errors", check_skill(skill) == [])


def test_shared_file_linking_out_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "shared-links", {
        "SKILL.md": "Router.\n",
        "references/shared/run-state.md": "See [commit](commit.md).\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("shared leaf linking to a sibling is one error", len(errors) == 1)
    expect("error names the offending file",
           "references/shared/run-state.md" in errors[0])


def test_stage_linking_to_stage_is_an_error(tmp: Path) -> None:
    skill = build(tmp / "stage-links", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md": "Then [stage 2](stage-02.md).\n",
        "references/pipeline/stage-02.md": "Leaf.\n",
    })
    errors = check_skill(skill)
    expect("stage linking to another stage is one error", len(errors) == 1)
    expect("error names both stage files",
           "stage-01.md" in errors[0] and "stage-02.md" in errors[0])


def test_links_inside_code_fences_are_ignored(tmp: Path) -> None:
    skill = build(tmp / "fenced", {
        "SKILL.md": "Router.\n",
        "references/shared/run-state.md": "```\n[commit](commit.md)\n```\n",
        "references/shared/commit.md": "Leaf.\n",
    })
    expect("a link inside a code fence is illustrative, not navigational",
           check_skill(skill) == [])


def test_stage_may_link_to_a_shared_leaf(tmp: Path) -> None:
    skill = build(tmp / "two-hop", {
        "SKILL.md": "Router.\n",
        "references/pipeline/stage-01.md": "Load [run state](../shared/run-state.md).\n",
        "references/shared/run-state.md": "Leaf.\n",
    })
    expect("a stage may load a shared leaf", check_skill(skill) == [])


def main() -> int:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_clean_skill_has_no_errors(tmp)
        test_shared_file_linking_out_is_an_error(tmp)
        test_stage_linking_to_stage_is_an_error(tmp)
        test_links_inside_code_fences_are_ignored(tmp)
        test_stage_may_link_to_a_shared_leaf(tmp)
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 tools/test_validate_coupling.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'validate_coupling'`

- [ ] **Step 3: Write the implementation**

Create `tools/validate_coupling.py`:

```python
#!/usr/bin/env python3
"""Enforce the reference-file coupling rules from the speckit-qa-auto design.

Two rules, both from spec section 11.2:

  C1  A file under references/shared/ links to no other file in the skill.
      Shared files are leaves: they may be loaded, they load nothing.
  C2  A file under references/pipeline/ does not link to another file under
      references/pipeline/. Ordering belongs to the router, not to the stages.

Opt-in per skill by explicit argument, so skills that were never designed
against these rules are left alone. Stdlib only; run with:

    python3 tools/validate_coupling.py speckit-qa-auto
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_skills import relative_links  # noqa: E402

SHARED = "references/shared"
PIPELINE = "references/pipeline"


def _markdown_files(skill_dir: Path) -> list[Path]:
    return sorted(p for p in skill_dir.rglob("*.md") if p.is_file())


def check_skill(skill_dir: Path) -> list[str]:
    """Return a list of coupling errors; empty means the skill is clean."""
    errors: list[str] = []
    for path in _markdown_files(skill_dir):
        rel = path.relative_to(skill_dir).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{rel}: unreadable ({exc})")
            continue

        for link in relative_links(text):
            target = link.split("#", 1)[0].strip()
            if not target or not target.endswith(".md"):
                continue
            resolved = (path.parent / target).resolve()
            try:
                target_rel = resolved.relative_to(skill_dir.resolve()).as_posix()
            except ValueError:
                continue  # outside the skill: validate_skills.py owns that error

            if rel.startswith(SHARED + "/"):
                errors.append(
                    f"{rel}: shared files are leaves and must link to nothing "
                    f"inside the skill, but links to {target_rel}"
                )
            elif rel.startswith(PIPELINE + "/") and target_rel.startswith(PIPELINE + "/"):
                errors.append(
                    f"{rel}: stage files must not reference each other, "
                    f"but links to {target_rel}"
                )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check reference-file coupling rules for the named skills"
    )
    parser.add_argument("skills", nargs="+", help="skill folder paths or names")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    report: dict[str, list[str]] = {}
    for name in args.skills:
        skill_dir = Path(name)
        if not skill_dir.is_dir():
            skill_dir = repo_root / name
        if not skill_dir.is_dir():
            report[name] = [f"no such skill folder: {name}"]
            continue
        report[skill_dir.name] = check_skill(skill_dir)

    failed = any(errors for errors in report.values())
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for skill, errors in report.items():
            if errors:
                print(f"{skill}: {len(errors)} coupling error(s)")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"{skill}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 tools/test_validate_coupling.py`
Expected: PASS — `all checks passed`, 7 `ok` lines, exit `0`

- [ ] **Step 5: Confirm it does not disturb existing skills**

Run: `python3 tools/validate_skills.py`
Expected: exit `0`. The new files live in `tools/`, which `discover_skills` excludes.

- [ ] **Step 6: Commit**

```bash
git add tools/validate_coupling.py tools/test_validate_coupling.py
git commit -m "test: add coupling validator for skill reference files"
```

---

### Task 2: `jira-to-speckit` Xray read mode

**Files:**
- Create: `jira-to-speckit/references/XRAY_API.md`
- Modify: `jira-to-speckit/SKILL.md` (frontmatter `description` and `metadata.version`; Optional Inputs; Guardrails; Workflow; output template)
- Modify: `jira-to-speckit/README.md`
- Modify: `README.md` (root skills table, `jira-to-speckit` row → `v0.3.0`)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces, for Task 9 (`stage-01-intake.md`) to call:
  - Optional input `xray_tests: true | false` (default `false`)
  - Optional input `xray_output_path: <path>` — Cucumber tests as one concatenated `.feature`
  - Optional input `xray_manual_output_path: <path>` — Manual/Generic tests as a markdown table
  - Output lines added to the existing template: `Xray tests:`, `Xray query:`, `Xray manual tests:`

- [ ] **Step 1: Write `references/XRAY_API.md`**

Create the file with exactly these sections, values copied verbatim from spec Constraint 2 and §1.1:

1. **Credentials** — `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET` from `.env`. Never printed. Absent → the caller is told `xray: unavailable` and the run continues; this is a warning, never a stop.
2. **Authenticate** —
   `POST https://xray.cloud.getxray.app/api/v2/authenticate`, body `{"client_id": "...", "client_secret": "..."}`, returns a bare quoted bearer token; strip the quotes.
3. **Discovery, one fixed query** — primary `issue in testRequirement("<STORY-KEY>") ORDER BY key ASC`; fallback `issuetype = Test AND issue in linkedIssues("<STORY-KEY>") ORDER BY key ASC` used only when the Xray JQL functions are unavailable. **Never merge the two result sets. Never add label or summary heuristics.** Report which one ran.
4. **Split by test type** — Cucumber tests via `GET https://xray.cloud.getxray.app/api/v1/export/cucumber?keys=A;B` (returns a zip); every other type via the Jira REST API, because **`export/cucumber` returns nothing for Manual and Generic tests**.
5. **Tag conventions** — `@REQ_<STORY-KEY>` at Feature level, `@TEST_<TEST-KEY>` at Scenario level; `@TEST_` makes an import update in place instead of creating a duplicate.
6. **Not this skill's job** — importing, creating test executions, uploading results. Reading only.

- [ ] **Step 2: Verify the reference file resolves and the skill still validates**

Run: `python3 tools/validate_skills.py --skill jira-to-speckit`
Expected: exit `0`. The new file is not yet linked, so this only proves nothing broke.

- [ ] **Step 3: Modify `SKILL.md`**

Four edits:

1. **Frontmatter `metadata.version`**: `"0.2.0"` → `"0.3.0"`.
2. **Frontmatter `description`**: append one sentence — that it can additionally export the Xray tests covering the issue, as Cucumber `.feature` plus a table of non-Cucumber tests, when `xray_tests` is requested. Keep the whole field within 40–1024 characters.
3. **Optional Inputs section**: add `xray_tests`, `xray_output_path`, `xray_manual_output_path`, each with its default and the statement that omitting `xray_tests` leaves `0.2.0` behaviour exactly unchanged. Link to `references/XRAY_API.md` here.
4. **Workflow**: add step `5c. Export Xray tests (only when xray_tests is true)` after the existing snapshot step, following `references/XRAY_API.md`. Add the three output lines to the fixed output template.

Update the two contract sentences that a reader would otherwise find false:
- "Does not write any file other than the single `ticket_output_path` snapshot" → **"writes at most three files, all named by the caller: `ticket_output_path`, `xray_output_path`, `xray_manual_output_path`"**.
- Keep, and do not weaken: no write to any remote system, no Speckit stage, no git operation, no execution report.

- [ ] **Step 4: Modify `jira-to-speckit/README.md` and the root `README.md`**

- `jira-to-speckit/README.md`: document the three optional inputs, the two queries and when each runs, and — stated plainly — that **Manual and Generic tests never appear in the Cucumber export**, so a caller receiving Cucumber tests but no manual tests is looking at partial coverage.
- Root `README.md`: change the `jira-to-speckit` row's badge to `v0.3.0` and extend its description to mention the Xray read mode.

- [ ] **Step 5: Run the validators**

Run: `python3 tools/validate_skills.py --skill jira-to-speckit`
Expected: exit `0`, no warning about the README table version.

Run: `python3 tools/validate_skills.py`
Expected: exit `0`.

- [ ] **Step 6: Commit**

```bash
git add jira-to-speckit README.md
git commit -m "feat(jira-to-speckit): add Xray read mode, v0.3.0"
```

---

### Task 3: `speckit-qa-auto` router and run-state contract

The router and the data contract ship together: the router is meaningless without knowing what stages exchange, and `run-state.md` is the file every later task writes against.

**Files:**
- Create: `speckit-qa-auto/SKILL.md`
- Create: `speckit-qa-auto/README.md`
- Create: `speckit-qa-auto/references/shared/run-state.md`
- Modify: `README.md` (root skills table — new row)

**Interfaces:**
- Consumes: nothing.
- Produces, relied on by every later task:
  - The run-state field names below. Later tasks must use these exact spellings.
  - The stage-router table, which fixes the four stage file paths.

- [ ] **Step 1: Write `references/shared/run-state.md`**

This is the contract of spec §11.2 rule 3. It is a **leaf**: it links to nothing. It defines the on-disk state each stage leaves for the next, so no stage ever reads another stage's prose.

Required content — exact field names, because later tasks reference them:

```yaml
# docs/qa/<jira-key>-<slug>/execution-report.md carries this as a fenced yaml block
run:
  jira_key:            MOM-1234
  slug:                agreement-reset-button
  artifact_dir:        docs/qa/mom-1234-agreement-reset-button
  branch:              test/mom-1234-agreement-reset-button
  worktree_path:       .worktrees/test-mom-1234-agreement-reset-button
  mode:                default | yolo
  full_suite:          false
  stage:               01 | 02 | 03 | 04 | completed
  resume_from:         02

profile:
  # every field re-derived each run from the playbook; see repo-profile.md
  source_paths:        [".github/skills/mom-auto-testing/SKILL.md", "package.json"]

baselines:
  workspace_baseline:  {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_baseline:   {path, head_sha, worktree_diff_sha256, index_diff_sha256, untracked}
  frontend_edits_approved: false

xray:
  query:               testRequirement | linkedIssues | not-run
  cucumber_tests:      12
  manual_tests:        7
  dedup:               ran | not-run

design:
  selector_evidence:   source | live-dom | fallback
  scenarios:
    - name:            Verify the Reset button is renamed
      surface:         ui | api | manual
      dedup:           NEW | UPDATE MOM-5678 | SKIP MOM-5678 | REVIEW MOM-5678
      status:          pending | green | blocked
      blocked_reason:  needs-design-change
      attempts:        0
      commit:          <sha the result was produced on>
```

Plus three rules in prose:

1. A stage reads only this file and the artifact folder. **It never reads another stage's reference file.**
2. A field absent from this contract does not travel between stages. Adding one means editing this file first.
3. `status: green` is only ever written next to the commit sha the run was produced on. A result with no sha is not a result.

- [ ] **Step 2: Write `SKILL.md`**

Frontmatter, exactly:

```yaml
---
name: speckit-qa-auto
description: |
  Runs an end-to-end QA delivery pipeline from a Jira issue: requirement analysis, BDD test
  design, selector verification, Playwright-BDD automation, a bounded run-and-fix loop, then
  human review and a pushed branch. The Gherkin feature file is the single artifact, serving
  manual testers and automation alike. Use when a Jira story needs test cases and automated
  tests produced together, from one command.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, and a Playwright-BDD + TypeScript test repository; network access for Jira and Xray."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---
```

Body sections, in this order, **under 500 words total**:

1. **Entry Dispatch (Do This First, Every Invocation)** — load `references/shared/host-adaptation.md` once; parse `--issue` (required), `--yolo`, `--full-suite`, `--pr`; **a missing `--issue` stops with the reason** (the Jira key is the artifact identity, the `@REQ_` tag, and the dedup key); then load `references/shared/operating-rules.md` and enter Stage 01 in the same turn.
2. **Stage Router** — a table mapping stage 01/02/03/04 to `references/pipeline/stage-0N-*.md`, plus the shared leaves. Load only the current stage's file.
3. **Modes** — default has human gates at Stage 02 and Stage 04; `--yolo` skips both but never the selector gate or the self-review gate. Stage 03 is a no-stop zone in both.
4. **Sub-Skill Dependencies** — a one-row table: `jira-to-speckit`, invoked by name through the `skill` tool, for Jira intake and Xray read.
5. **Required Inputs** — `--issue <jira-url-or-key>`; `.env` with `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`, and optionally `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET`. Never printed.
6. **Portability Note** — `allowed-tools` uses Copilot-style names; Claude Code and OpenCode expose the same capabilities under `Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `skill`. Never refuse because a tool is named differently.

**No stage detail in this file.** No diagrams in this file — all three live in the reference files that own their decision.

- [ ] **Step 3: Write `README.md` (500–1000 words)**

Sections: Overview, Quick Start, Features, Installation, Compatibility, Examples, Configuration, Troubleshooting — matching the shape of `speckit-auto/README.md`. Include the pipeline diagram from spec §Pipeline Flow, and state the four properties a reader most needs: Gherkin is the single artifact; `docs/qa/` is the source of truth; the fix loop may not edit Gherkin; Xray import happens in CI on merge, not here.

- [ ] **Step 4: Add the root README row**

Add to the skills table, matching the existing column order:

```
| [speckit-qa-auto](./speckit-qa-auto/README.md) | Jira-to-tests QA pipeline. Analyses the story, designs BDD scenarios, verifies selectors against evidence, generates Playwright-BDD tests, runs them with a bounded fix loop, then reports for human review. Gherkin is the single artifact for manual and automated testing alike. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | `--issue <jira-url>`, `--yolo`, `--full-suite`, `--pr` | v0.1.0 / Alex Nguyen |
```

- [ ] **Step 5: Run the validators**

Run: `python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: exit `0`.

Run: `python3 tools/validate_coupling.py speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

Run: `wc -w speckit-qa-auto/SKILL.md`
Expected: under 600 words including frontmatter — the router budget of spec §11.1 with margin.

- [ ] **Step 6: Commit**

```bash
git add speckit-qa-auto README.md
git commit -m "feat(speckit-qa-auto): add router and the stage run-state contract"
```

---

### Task 4: `operating-rules.md` and `workspace-guard.md`

**Files:**
- Create: `speckit-qa-auto/references/shared/operating-rules.md`
- Create: `speckit-qa-auto/references/shared/workspace-guard.md`

**Interfaces:**
- Consumes: the run-state field names from Task 3.
- Produces: the ten turn-ending conditions and the two baseline schemas, referenced by Tasks 9–12.

- [ ] **Step 1: Write `operating-rules.md`**

A leaf. Links to nothing. Content, from spec §8, §6.2, §6.4, §6.5:

1. **Operating premise** — a real invocation channel exists in this turn; loading this file is proof. Never claim execution is impossible or channel-less.
2. **The ten turn-ending conditions, verbatim from spec §8**, stated as exhaustive. Any other reason to stop is invalid.
3. **Fix-loop rules** — the permitted-edit list and the forbidden list, both verbatim from spec §6.2. Copy the `fix_loop_boundary` digraph from spec §6.2 **verbatim**, fences included.
4. **The fix-loop Red Flags table**, all six rows, verbatim from spec §6.2.
5. **Infrastructure failure is not test failure** — spec §6.4. Browser binaries, env vars, unreachable app, repo-caused `bddgen` errors: stop immediately, quote the error, **consume no fix attempt**.
6. **Circuit breaker** — spec §6.5. Identical failure 5 consecutive iterations with no file change, or a git/filesystem write error. A differing failure, or one followed by any file edit, does not count.

- [ ] **Step 2: Write `workspace-guard.md`**

A leaf. Links to nothing. Content from spec §7.1 and §4 step 5:

1. **Prevention is primary** — every git command carries `git -C <worktree_path>`; every path resolves against `worktree_path`. A bare `git` invocation is a defect, not a style preference.
2. **Why `git status --porcelain` is not sufficient** — reproduce the four-row table from spec §7.1 showing that an already-dirty path keeps the same status letter through any amount of further editing.
3. **The two baseline schemas** — `workspace_baseline` over the source checkout and `frontend_baseline` over the frontend working tree, both with `head_sha`, `worktree_diff_sha256`, `index_diff_sha256`, `untracked`.
4. **Why two and not one** — a parent repository's `git diff HEAD` sees a submodule as a commit pointer, so it cannot see file edits inside it; and the frontend is initialized inside the worktree, not the source checkout.
5. **Capture commands**, as literal shell:

```bash
git -C "$P" rev-parse HEAD
git -C "$P" diff --binary HEAD | shasum -a 256
git -C "$P" diff --cached --binary HEAD | shasum -a 256
git -C "$P" ls-files --others --exclude-standard
```

6. **Untracked cap** — above 2000 files or 50 MB, fingerprint path and size only and record `untracked_fingerprint: degraded`.
7. **On violation** — stop before committing, report the differing paths with both hashes. **Never revert the source checkout.** A `frontend_baseline` difference is a violation unless `frontend_edits_approved: true`, in which case it is reported for review.
8. **Known limits, stated not hidden** — gitignored files (`.env` above all) appear in neither diff nor `ls-files --others --exclude-standard`; and detection runs at Stage 04, so it reports rather than prevents.

- [ ] **Step 3: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto`
Expected: `speckit-qa-auto: ok` — proves both files are leaves.

Run: `python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: exit `0`.

Run: `grep -c '^```dot' speckit-qa-auto/references/shared/operating-rules.md`
Expected: `1` — the fix-loop diagram, and only it.

- [ ] **Step 4: Commit**

```bash
git add speckit-qa-auto/references/shared/operating-rules.md speckit-qa-auto/references/shared/workspace-guard.md
git commit -m "docs(speckit-qa-auto): add operating rules and the workspace guard"
```

---

### Task 5: `repo-profile.md`

**Files:**
- Create: `speckit-qa-auto/references/shared/repo-profile.md`

**Interfaces:**
- Consumes: the `profile.source_paths` field from Task 3's run-state contract.
- Produces: the fourteen profile field names, used verbatim by Tasks 9–12 (`test_root`, `feature_path`, `steps_path`, `page_path`, `selectors_path`, `testdata_path`, `generate_cmd`, `scoped_run_cmd`, `frontend_source_root`, `selector_attribute`, `existing_tags`, `xray_project_key`, `branch_prefix`, `artifact_root`).

- [ ] **Step 1: Write the file**

A leaf. Links to nothing. Content from spec §2 and §2.1:

1. **Discovery order**, stopping at the first source that answers: repo-local automation skill (`.github/skills/*auto-testing*/SKILL.md`, `.claude/skills/*/SKILL.md`) → `AGENTS.md` / `CLAUDE.md` → `docs/` guideline files → inference from `package.json` scripts, `playwright.config.ts`, and one existing `.feature` / `.steps.ts` pair read as a worked example.
2. **The field table**, all fourteen fields, with the reference-repo example values from spec §2 kept as examples.
3. **What is cached and what is not** — reproduce the `docs/qa/.repo-profile.json` shape from spec §2.1 with its `answers` and `provenance` keys.
4. **The three rules that keep it a cache and not config:**
   - `answers` holds only what no file can answer.
   - Every other field is **re-derived every run**; it is never stored.
   - `provenance` records each source file with its sha256. Any mismatch means re-derive, and **report which source changed**.
5. **A stale answer is re-asked, not reused** — a `frontend_source_root` that is not a directory, an `xray_project_key` Xray rejects.
6. **Why a path-exists check is not enough** — the paths still exist when a playbook changes its conventions. That is the failure this design refuses.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/shared/repo-profile.md
git commit -m "docs(speckit-qa-auto): add repo profile discovery"
```

---

### Task 6: `selector-verification.md`

**Files:**
- Create: `speckit-qa-auto/references/shared/selector-verification.md`

**Interfaces:**
- Consumes: `frontend_source_root`, `selector_attribute` from Task 5; `design.selector_evidence` and `baselines.frontend_edits_approved` from Task 3.
- Produces: the selector map shape consumed by Task 10 (Stage 02) and Task 11 (Stage 03).

- [ ] **Step 1: Write the file**

A leaf. Links to nothing. Content from spec Constraint 3:

1. **The gate binds to evidence, not to a technique.** Every element of every `surface: ui` scenario resolves against something real before Gherkin is approved.
2. **The three evidence sources table** — repository source / live DOM / semantic fallback, with the availability condition and what each produces.
3. **The `selector_resolution` digraph, copied verbatim from spec Constraint 3**, fences included.
4. **The choice is asked, never assumed** — with frontend source present the user still picks report-only, propose-testids, or live DOM, because a stale checkout makes source the wrong evidence and only the user knows that.
5. **Live DOM runs in a subagent** — the subagent receives the element list and the application URL, drives the host's browser automation, and returns **only the selector map**. It reads; it never submits forms, mutates data, or triggers modal dialogs. Prerequisites: base URL, and credentials when the app needs them. Missing either → **the option is not offered**, because a login wall returns a selector map for the login page and nothing else.
6. **Semantic fallback is a recorded risk** — writes `selector_evidence: fallback` plus the user's acknowledgement into `test-design.md`; the Stage 04 report repeats it.
7. **`--yolo` order** — repository source if readable, else live DOM if available, else **stop**. It never chooses fallback on the user's behalf.
8. **Frontend edits** — report-only by default. Approval sets `frontend_edits_approved: true` and the edits land on a **separate frontend branch inside the submodule**, never on the test branch.
9. **The selector map shape** — one table per scenario: `| Element | Evidence | Strategy |`, every row resolved to existing selector, proposed selector with file and line, or semantic fallback.
10. **A Red Flags table** — at minimum: "the testid probably exists, I'll assume the usual name" → that is a guess, and guesses are what this gate exists to stop; "I'll write a CSS path from the screenshot" → not evidence, it is a snapshot of one render; "no frontend checkout, so I'll skip the gate" → offer the browser instead, the gate does not skip.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

Run: `grep -c '^```dot' speckit-qa-auto/references/shared/selector-verification.md`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/shared/selector-verification.md
git commit -m "docs(speckit-qa-auto): add evidence-based selector verification"
```

---

### Task 7: `gherkin-conventions.md`, `host-adaptation.md`, `commit.md`

Three leaves, each small, none meaningful to reject without the others — they ship together.

**Files:**
- Create: `speckit-qa-auto/references/shared/gherkin-conventions.md`
- Create: `speckit-qa-auto/references/shared/host-adaptation.md`
- Create: `speckit-qa-auto/references/shared/commit.md`

**Interfaces:**
- Consumes: `existing_tags`, `xray_project_key` from Task 5; `design.scenarios[].surface` from Task 3.
- Produces: the tag rules used by Task 10, the anti-drift rules used by Task 11, and the push procedure used by Task 12.

- [ ] **Step 1: Write `gherkin-conventions.md`**

From spec Constraint 1, Constraint 2, Constraint 3's surface table, and §3.1:

1. **One file, three consumers** — manual tester, `playwright-bdd`, and Xray via CI on merge. Nothing is authored twice.
2. **Tags** — `@REQ_<STORY-KEY>` at Feature level; `@TEST_<TEST-KEY>` at Scenario level **only** for `UPDATE` rows; plus the profile's `existing_tags`. These are **additive**: existing repo tags stay so `--grep` filtering and the current CI keep working.
3. **The surface table** — `ui` / `api` / `manual`, with what each requires. A `surface: ui` scenario with zero UI elements is a design error, not a pass. A `surface: manual` scenario needs a one-line reason, because otherwise `manual` is an easy way to make the selector gate disappear.
4. **Scenario granularity** — one behaviour per scenario; negative and boundary cases included.
5. **The anti-drift rule**, as the four-row table from spec §3.1 (Feature name / feature tags / Background identical; each scenario matching exactly or absent-because-blocked; order preserved; nothing authored in the test tree).
6. **The two degenerate cases** — every scenario in a file blocked → the file is **not materialized at all** and any previous copy is deleted; a `Scenario Outline` with some rows blocked → **the whole outline is blocked**, example rows are never individually omitted.

- [ ] **Step 2: Write `host-adaptation.md`**

A leaf. Detect the host once per run from the discovery directory and tool surface; the host is fixed for the whole run. Table mapping the capability to each host's tool name: bash / read / write / edit / glob / grep / skill across GitHub Copilot, Claude Code, OpenCode. One rule: **never refuse to act because a tool is named differently.** Note which hosts expose browser automation, since the live-DOM evidence option depends on it.

- [ ] **Step 3: Write `commit.md`**

From spec §7 steps 3–5:

1. **Conditional commit** — check `git status --porcelain` in the worktree first; empty output is a **success path**, not a failure. Report the existing commits instead.
2. **Fast-forward-only push**, as literal commands:

```bash
git -C "$W" fetch origin "$BRANCH"
# remote absent      -> git -C "$W" push -u origin "$BRANCH"
# remote is ancestor -> git -C "$W" push origin "$BRANCH"
# diverged           -> STOP and report; do not rebase
```

3. **Why no `pull --rebase` here** — a rebase pulls in commits the suite was never run against, and the stage would then report a green result for a tree that never existed when the tests ran. The branch belongs to this pipeline; divergence means something outside it wrote to the branch, which is a human decision.
4. **Every reported test result names the commit it was produced on.**
5. **Scratch must already be ignored** — `.worktrees/` is git-ignored at Stage 01, so `git add -A` cannot sweep it into the feature commit.

- [ ] **Step 4: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

- [ ] **Step 5: Commit**

```bash
git add speckit-qa-auto/references/shared/gherkin-conventions.md speckit-qa-auto/references/shared/host-adaptation.md speckit-qa-auto/references/shared/commit.md
git commit -m "docs(speckit-qa-auto): add gherkin, host, and commit conventions"
```

---

### Task 8: `stage-01-intake.md`

**Files:**
- Create: `speckit-qa-auto/references/pipeline/stage-01-intake.md`

**Interfaces:**
- Consumes: `repo-profile.md`, `workspace-guard.md`, `operating-rules.md` (shared leaves); `jira-to-speckit` inputs `ticket_output_path`, `xray_tests`, `xray_output_path`, `xray_manual_output_path` from Task 2.
- Produces, in run state: `run.jira_key`, `run.slug`, `run.artifact_dir`, `run.branch`, `run.worktree_path`, `baselines.workspace_baseline`, `baselines.frontend_baseline`, `xray.query`, `xray.cucumber_tests`, `xray.manual_tests`, and the artifact folder with `ticket.md`, `existing-tests.feature`, `existing-tests-manual.md`.

- [ ] **Step 1: Write the file**

Header line names exactly what it loads: `repo-profile.md`, `workspace-guard.md`, `operating-rules.md`. **It links to no other stage file.**

The eight numbered steps, in the order spec §4 fixes — and the file must say **why** the order is what it is, because the obvious order is wrong:

1. **Repo profile** (read-only, against the source checkout; may ask its one round of questions here). *Runs first because step 4 is conditioned on `frontend_source_root`, which this step produces.*
2. **Capture `workspace_baseline`** — before the run touches anything. Capturing it later would bake in changes the run itself caused.
3. **Worktree gate** — base priority `develop → main → master`, local then remote-tracking; best-effort sync; worktree at `<repo-root>/.worktrees/<branch>`; ensure `.worktrees/` is git-ignored; branch `<branch_prefix><jira-key>-<slug>`, renamed in place with `git branch -m` when a provisional name was used.
4. **Frontend source init** — `git submodule update --init -- <frontend_source_root>` **inside the worktree**. A **stop**, not a warning: Stage 02's selector gate reads this tree.
5. **Capture `frontend_baseline`** — immediately after step 4.
6. **Jira intake** — `jira-to-speckit` by name through the `skill` tool, `ticket_output_path` = `<artifact_dir>/ticket.md`.
7. **Xray read** — `jira-to-speckit` with `xray_tests: true`, writing `existing-tests.feature` and `existing-tests-manual.md`. Unavailable credentials → warning; record `xray.dedup: not-run`.
8. **Resume** — an existing `<jira-key>-*` artifact folder is **reused, never duplicated with a new slug**; `execution-report.md` names the stage to resume from.

Ends by entering Stage 02 **in the same turn**. No human gate in this stage.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto`
Expected: `speckit-qa-auto: ok` — proves this stage links to no other stage.

Run: `python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: exit `0`.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-01-intake.md
git commit -m "docs(speckit-qa-auto): add stage 01 intake"
```

---

### Task 9: `stage-02-test-design.md`

**Files:**
- Create: `speckit-qa-auto/references/pipeline/stage-02-test-design.md`

**Interfaces:**
- Consumes: `selector-verification.md`, `gherkin-conventions.md` (shared leaves); everything Task 8 wrote to run state.
- Produces: `<artifact_dir>/<domain>-<aspect>.feature`, `<artifact_dir>/test-design.md`, and run-state `design.selector_evidence`, `design.scenarios[]` with `surface`, `dedup`, `status: pending`.

- [ ] **Step 1: Write the file**

Header names what it loads: `selector-verification.md`, `gherkin-conventions.md`. **No link to another stage file.**

The eight steps of spec §5:

- **2.1 Requirement analysis** — acceptance criteria to testable behaviours. A blocking ambiguity is asked **once**; a non-blocking one goes to Open Questions and the run continues.
- **2.2 Dedup** — the four labels and the matching rule, reproduced from spec §5.1: **normalized scenario key** (lowercase; strip tags, the `Scenario:` / `Scenario Outline:` prefix, punctuation, collapsed whitespace, quoted literals and numbers), then key match + step-sequence identity decides `SKIP` / `UPDATE`; no key match → `NEW`; an existing test matching nothing new → `REVIEW`, **never deleted or modified by the pipeline**.
- **Non-Cucumber tests are advisory** — `existing-tests-manual.md` is a table, so no key match is possible. Presented at the 2.8 gate as *possible overlap, decide yourself*. **They never produce an automatic `SKIP`.** Treating a Manual test as uncovered creates duplicates; treating it as covered drops coverage; a human decides.
- **When Xray was unavailable** — every behaviour is `NEW` and `test-design.md` records `dedup: not-run` with the reason. An unrun dedup must never look like one that ran and found nothing.
- **2.3 Scenario design** — Gherkin, one behaviour per scenario, negative and boundary cases, **a `surface` on every scenario**, and the coverage matrix acceptance criterion → scenarios.
- **2.4 Selector gate** — applies to `surface: ui` only; evidence source is **asked**, per `selector-verification.md`.
- **2.5 Write `.feature`** into `<artifact_dir>` — never into the test tree at this stage.
- **2.6 Write `test-design.md`** — scenarios, coverage matrix, selector map, page objects to create or modify, test data and mock plan, dedup decisions, open questions.
- **2.7 Self-review gate** — every acceptance criterion covered · no `TODO`/`TBD`/placeholder · every element of every `ui` scenario resolved · every `api` scenario naming endpoint and fixture · every `manual` scenario carrying a reason · every behaviour carrying a dedup label. Fix at source and re-verify. **The same check failing 3 consecutive times stops the run.**
- **2.8 Human gate** — present the summary, take approval or revisions, commit the artifacts, take the single start-automation confirmation, enter Stage 03 **in the same turn**.

State plainly: `--yolo` skips 2.8 but **not** 2.4 and **not** 2.7.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-02-test-design.md
git commit -m "docs(speckit-qa-auto): add stage 02 test design"
```

---

### Task 10: `stage-03-automate.md`

**Files:**
- Create: `speckit-qa-auto/references/pipeline/stage-03-automate.md`

**Interfaces:**
- Consumes: `operating-rules.md`, `gherkin-conventions.md` (shared leaves); run-state `design.scenarios[]`, `profile.*`.
- Produces: generated `*.steps.ts`, `*Page.ts`, `*Selectors.ts`, fixtures and mocks; the materialized `.feature` subset in `feature_path`; run-state `design.scenarios[].status`, `.attempts`, `.blocked_reason`, `.commit`.

- [ ] **Step 1: Write the file**

Header names what it loads: `operating-rules.md`, `gherkin-conventions.md`. **No link to another stage file.**

The six steps of spec §6, plus its five sub-rules:

- **3.0 Materialize** — copy `.feature` from `<artifact_dir>` to `feature_path`. On any difference **the artifact wins**; overwrite and log it. Apply the anti-drift and degenerate-case rules from `gherkin-conventions.md`.
- **3.1 Partition** — one scenario package at a time, dependency order, minimum slices, never whole prior-stage prose.
- **3.2 Generate** — following the repo profile paths. **Only selectors present in the approved selector map may be used.**
- **3.3 Verify** — `generate_cmd`, then `scoped_run_cmd` filtered to the scenario's tag; capture the output.
- **3.4 Fix loop** — at most **3 attempts per scenario**, bounded by the rules and the diagram in `operating-rules.md`.
- **3.5 Coverage review loop** — every acceptance criterion has a passing scenario · every selector map entry is used · repo conventions hold (page objects via the base page, selectors centralized, no hardcoded test data in steps, no `waitForTimeout`). A failure feeds the next fix iteration, **never a stop**.
- **Run scope** — default is the affected domain plus the new scenarios; whole suite only under `--full-suite`.
- **Blocked scenarios** — marked `blocked: needs-design-change`, **omitted from the materialized copy**, run continues. `surface: manual` scenarios follow the same path by construction. **Stage 03 does not tag them**, because it may not edit `.feature`; Stage 04 does that after approval.
- Restate the no-stop-zone property: the only exits are a scenario verdict, an infrastructure stop, or the circuit breaker.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

Run: `grep -c '^```dot' speckit-qa-auto/references/pipeline/stage-03-automate.md`
Expected: `0` — the fix-loop diagram lives in `operating-rules.md`; duplicating it would drift.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-03-automate.md
git commit -m "docs(speckit-qa-auto): add stage 03 automate"
```

---

### Task 11: `stage-04-finish.md`

**Files:**
- Create: `speckit-qa-auto/references/pipeline/stage-04-finish.md`

**Interfaces:**
- Consumes: `workspace-guard.md`, `commit.md` (shared leaves); run-state `baselines.*`, `design.scenarios[]`.
- Produces: the final `execution-report.md`, the `@not-automated` tags on blocked scenarios, the pushed branch, and run-state `run.stage: completed`.

- [ ] **Step 1: Write the file**

Header names what it loads: `workspace-guard.md`, `commit.md`. **No link to another stage file.**

The six steps of spec §7:

1. **Update `execution-report.md`** — scenarios passing, scenarios blocked with reasons, run output summary, coverage matrix status, and the commit sha each result was produced on.
2. **Human review** — files created and changed, test results, blocked scenarios with reasons, **proposed `data-testid` additions with file and line**, `selector_evidence` including a fallback acknowledgement when one was taken, open questions.
3. **Verify both baselines** — `workspace_baseline` and `frontend_baseline`. A violation stops the run **before any commit**.
4. **Tag blocked scenarios** — on approval, write `@not-automated` into the **artifact** version. This is a human-gated edit, explicitly not a fix-loop edit.
5. **Commit and fast-forward push**, per `commit.md`.
6. **Print a ready-to-use PR title and body. Do not open the PR unless `--pr` is passed.** Then mark the artifact `completed` and make the follow-up commit for that status change.

Add the handoff note from spec §10: this skill **never writes to Xray**. CI imports from `docs/qa/` on merge — never from the test tree, which omits blocked and manual scenarios. Include the `curl` block from spec §10 verbatim, as reference for whoever writes the CI job.

- [ ] **Step 2: Verify**

Run: `python3 tools/validate_coupling.py speckit-qa-auto && python3 tools/validate_skills.py --skill speckit-qa-auto`
Expected: `speckit-qa-auto: ok`, exit `0`.

- [ ] **Step 3: Commit**

```bash
git add speckit-qa-auto/references/pipeline/stage-04-finish.md
git commit -m "docs(speckit-qa-auto): add stage 04 finish"
```

---

### Task 12: Test cases and full-repository validation

**Files:**
- Create: `test-case/speckit-qa-auto/test-cases.md`
- Modify: `.github/workflows/validate-skills.yml` (add the coupling check)

**Interfaces:**
- Consumes: every acceptance criterion in spec §12.
- Produces: nothing later tasks rely on. This is the closing gate.

- [ ] **Step 1: Write `test-case/speckit-qa-auto/test-cases.md`**

Follow the shape of `test-case/speckit-auto/test-cases.md`. One case per acceptance criterion in spec §12, each with preconditions, steps, and expected result. The four that carry the design's real risk, written as executable scenarios rather than prose:

| Case | What it proves |
|---|---|
| Workspace baseline regression | Source checkout holds one already-modified tracked file and one already-present untracked file; append to each; Stage 04 verification reports **both** as violations. This is precisely what a `git status` string comparison misses |
| Frontend baseline regression | Edit one file inside the frontend working tree without committing; Stage 04 reports a violation. A parent-repo diff alone does not catch this |
| Dedup determinism | Run Stage 02 twice over the same story with Xray unchanged; the `NEW` / `UPDATE` / `SKIP` / `REVIEW` label set is identical |
| Blocked-scenario round trip | With one scenario blocked: the test tree omits it, `docs/qa/` keeps it, and the §10 import command picks it up |
| Selector evidence branch | With `frontend_source_root` absent, the run **offers live DOM inspection rather than stopping**; declining with fallback accepted records `selector_evidence: fallback`; declining both stops the run |

- [ ] **Step 2: Add the coupling check to CI**

In `.github/workflows/validate-skills.yml`, immediately after the existing `Self-test the validator` step and before `Shell script syntax check`, add two steps:

```yaml
      - name: Validate reference-file coupling
        run: python3 tools/validate_coupling.py speckit-qa-auto

      - name: Self-test the coupling validator
        run: python3 tools/test_validate_coupling.py
```

Named skills only — skills that were never designed against these rules are deliberately not checked. The existing `python3 -m compileall -q tools */scripts` step already covers the two new files for syntax.

- [ ] **Step 3: Run every check the repository has**

Run: `python3 tools/validate_skills.py`
Expected: exit `0`, no errors, no version-table warnings.

Run: `python3 tools/test_validate_skills.py`
Expected: `all checks passed`.

Run: `python3 tools/test_validate_coupling.py`
Expected: `all checks passed`.

Run: `python3 tools/validate_coupling.py speckit-qa-auto`
Expected: `speckit-qa-auto: ok`.

Run: `wc -w speckit-qa-auto/SKILL.md`
Expected: under 600.

Run: `grep -rc '^```dot' speckit-qa-auto --include=*.md | grep -v ':0'`
Expected: exactly three files with one diagram each — `README.md` (pipeline), `references/shared/operating-rules.md` (fix loop), `references/shared/selector-verification.md` (selector resolution).

Run: `grep -rn 'TODO\|TBD\|FIXME' speckit-qa-auto jira-to-speckit/references/XRAY_API.md`
Expected: no output other than the self-review gate's own literal mention of `TODO`/`TBD` as things to scan for.

- [ ] **Step 4: Commit**

```bash
git add test-case/speckit-qa-auto .github/workflows/validate-skills.yml
git commit -m "test(speckit-qa-auto): add test cases and wire the coupling check into CI"
```

---

## Self-Review Notes

**Spec coverage.** Every numbered spec section maps to a task: Constraint 1 → Task 7; Constraint 2 → Task 2; Constraint 3 → Task 6; §1.1 → Task 2; §2 / §2.1 → Task 5; §3 / §3.1 → Task 7; §4 → Task 8; §5 / §5.1 → Task 9; §6 and §6.1–6.5 → Tasks 4 and 10; §7 / §7.1 → Tasks 4 and 11; §8 → Task 4; §9 → Task 3; §10 → Task 11; §11 → Tasks 3–11; §11.1 / §11.2 → Tasks 1 and 3; §12 → Task 12; §13 needs no task by definition.

**Deliberate omissions.** D4 (Playwright-BDD assumed, no framework abstraction) and D3 (no provider layer) are satisfied by *not* building something, so neither has a task. D6 and D15 (Xray write in CI on merge) are out of the skill's scope by decision; Task 11 documents the handoff and does not implement it.

**Type consistency.** The run-state field names defined in Task 3 are used unchanged in Tasks 4, 8, 9, 10, and 11. The fourteen profile field names defined in Task 5 are used unchanged in Tasks 8 through 11. The `jira-to-speckit` input names defined in Task 2 (`xray_tests`, `xray_output_path`, `xray_manual_output_path`) are consumed unchanged in Task 8.

**One diagram, one home.** The three diagrams live in `README.md`, `operating-rules.md`, and `selector-verification.md`. Task 10 explicitly asserts zero diagrams in `stage-03-automate.md` so the fix-loop diagram is not duplicated into the stage that uses it — duplicated instructions drift, and the drift is silent.
