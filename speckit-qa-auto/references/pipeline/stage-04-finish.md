# Stage 04: Finish

Loads: [workspace-guard.md](../shared/workspace-guard.md), [commit.md](../shared/commit.md). Two
leaves, so the reader knows the cost before paying it (design spec §11.2 rule 1). It links to no
other file under `references/pipeline/` — its predecessor is not linked back to, and it has no
successor: this is the last stage the skill runs. After the steps below, the pipeline ends; only a
human opening the PR (or re-running with `--pr`) follows.

This is the pipeline's second and final human gate (design spec §7, marked ◀ HUMAN GATE). Stage 03
left every scenario in run scope with a verdict — `green` or `blocked` — and this stage turns that
into a report a human can act on, then commits and pushes only after both integrity baselines
confirm the developer's own checkout came out of the run untouched.

## What This Stage Receives

Per `run-state.md` rule 2, read only from `execution-report.md` and the artifact folder — never
from `stage-03-automate.md`: `run.jira_key`, `run.artifact_dir`, `run.branch`,
`run.worktree_path`, `run.mode`, `baselines.workspace_baseline`, `baselines.frontend_baseline`,
`baselines.frontend_edits_approved`, `design.selector_evidence`, and every entry of
`design.scenarios[]` as Stage 03 left them — each carrying `status: green | blocked`, `attempts`,
`blocked_reason` when blocked, and `commit`. On disk, inside `run.artifact_dir`: the `.feature`
file(s) at their artifact version, `test-design.md`, and the materialized copy at `feature_path`
that Stage 03's step 3.0 last wrote.

## Execution Order

### 4.1 Update `execution-report.md`

Write the run summary: scenarios passing, scenarios blocked with reasons
(`design.scenarios[].blocked_reason`), the run output summary from Stage 03's verify runs, and the
coverage matrix status carried over from `test-design.md`. Every scenario listed here names the
commit it was produced on (`design.scenarios[].commit`, `run-state.md` rule 4) — a result with no
sha attached is not a result, and this is the report a human reviews next, so it is the wrong place
for that rule to go unenforced.

### 4.2 Human review

Present, for approval:

- Files created and changed, across the worktree and the artifact folder
- Test results — pass/blocked per scenario, each naming its commit
- Blocked scenarios with reasons
- Proposed `data-testid` additions for the frontend, each with file and line (the report-only
  proposals `selector-verification.md`'s selector gate produced at Stage 02, carried forward
  unapplied unless `baselines.frontend_edits_approved` is true)
- `design.selector_evidence` — `source | live-dom | fallback` — including the fallback
  acknowledgement recorded at Stage 02 when the evidence source was `fallback`
  (`selector-verification.md`, "Semantic Fallback Is A Recorded Risk": "The Stage 04 report
  repeats it")
- Open questions carried from `test-design.md`

`--yolo` skips this review's approval, the same way it skips the Stage 02 approval — it does not
skip 4.3's baseline verification, which is unconditional regardless of mode (`operating-rules.md`,
Turn-Ending Condition 8).

### 4.3 Verify both baselines

Before any commit, re-verify `baselines.workspace_baseline` against the source checkout and
`baselines.frontend_baseline` against the frontend working tree, per `workspace-guard.md`'s capture
commands and comparison. Both must be checked; neither substitutes for the other, and
`workspace-guard.md`, "Why Two And Not One" is why: a parent-repo diff cannot see inside a
submodule, and the frontend baseline cannot cover the source checkout since it is scoped to a path
inside the worktree.

- A `workspace_baseline` difference is always a violation. Stop the run **before any commit**,
  report the differing paths with both the baseline and current hashes, and go no further. **Never
  revert the source checkout** — undoing a developer's working tree without asking is worse than
  the leak it would undo.
- A `frontend_baseline` difference is a violation **unless** `baselines.frontend_edits_approved` is
  `true`, in which case it is not a stop — report the diff for review alongside the rest of 4.2's
  output instead.

This is Turn-Ending Condition 8 (`operating-rules.md`). A run that stops here has produced a
report but made no commit; the worktree and the source checkout are left exactly as they were
found.

### 4.4 Tag blocked scenarios

On approval at 4.2, write `@not-automated` into the **artifact** version of each scenario
`design.scenarios[].status: blocked` — the `.feature` file(s) in `run.artifact_dir`, never the
materialized copy at `feature_path`, since a blocked scenario was never materialized into it
(Stage 03, 3.0 and the Two Degenerate Cases in `gherkin-conventions.md`).

This happens here, at the human gate, and not inside Stage 03's fix loop, because it is a different
kind of edit. Stage 03 may not edit any `.feature` file, in the artifact or the copy, without
exception — the forbidden set applies regardless of attempts remaining or how obviously a scenario
is stuck. Writing `@not-automated` is still an edit to that same file. Deferring it to the one point
in the pipeline where a human has just reviewed and approved the blocked list is what makes it
permissible: this is a human-gated edit, not a fix-loop edit, and the tag it produces keeps the
automation status visible both in the file itself and in Xray once CI imports it.

`surface: manual` scenarios need no tag here — they were never candidates for automation and carry
their one-line reason in the artifact already (`gherkin-conventions.md`'s Surface table).

### 4.5 Commit and fast-forward push

Follow `commit.md` in full: conditional commit on `git status --porcelain` in the worktree — an
already-clean tree (for example, every change already committed incrementally during Stage 03) is
a success path, report the existing commits on the branch rather than treating it as an error — then
fast-forward-only push. Fetch `origin/<branch>`; remote absent pushes with `-u`; remote an ancestor
of local pushes plainly; **remote diverged stops and reports, and this stage does not rebase**
(Turn-Ending Condition 9). Every command carries an explicit `-C <worktree_path>`.

Report the resulting commit(s) — hash and subject — and the branch pushed, per `commit.md`,
"Reporting."

### 4.6 Print the PR text, then mark the artifact completed

Print a ready-to-use PR title and body: the story key and slug, the coverage summary, the blocked
and manual scenarios called out by name, and a link back to `run.artifact_dir`. **Do not open the
PR** — that only happens when `--pr` was passed to the invocation, and even then it is the one step
in this stage this file does not itself perform; it is the flag's effect, not a default.

Then set `run.stage: completed` in `execution-report.md` and make the follow-up commit for that
status change, pushed the same way 4.5 pushed — `commit.md`'s procedure governs every commit this
stage makes, not only the first. A second divergence here is unlikely immediately after 4.5's push
succeeded, but the check is not skipped on that assumption; a diverged remote at this point stops
and reports exactly as it would have at 4.5.

## What This Stage Produces

Written into run state:

- `run.stage: completed`
- `design.scenarios[]` unchanged in shape — 4.1 reads these fields, it does not add new ones

And, on disk: the updated `execution-report.md`, `@not-automated` tags written into the blocked
scenarios' artifact `.feature` file(s), the pushed branch, and the printed PR title and body (not a
PR — that is `--pr`'s effect, or a human's later action).

## Never Writes To Xray

The skill never writes to Xray. Import happens in CI, on merge, and reads from `docs/qa/` — never
from the test tree at `feature_path`. The test tree is the automated subset Stage 03 materialized;
`docs/qa/` is the whole approved set, automated, blocked, and manual scenarios alike (D15, §10).
Importing from the test tree would silently drop every blocked and every manual scenario from
Xray — exactly the coverage `@not-automated` above was written to keep visible. This is why the
`@TEST_` and `@REQ_` tags on the artifact version matter more than the ones on the copy: the copy
is not what CI reads.

Reference for whoever writes that CI job — the exact command this pipeline hands off to, quoted
verbatim from design spec §10:

```bash
token=$(curl -s -H "Content-Type: application/json" -X POST \
  --data "{\"client_id\":\"$XRAY_CLIENT_ID\",\"client_secret\":\"$XRAY_CLIENT_SECRET\"}" \
  https://xray.cloud.getxray.app/api/v2/authenticate | tr -d '"')

# docs/qa holds the full approved set: automated, blocked, and manual scenarios alike (D15).
# Zipping src/tests instead would silently drop every scenario that is not yet automated.
zip -r features.zip docs/qa -i \*.feature -x \*existing-tests.feature
curl -H "Authorization: Bearer $token" -F "file=@features.zip" \
  "https://xray.cloud.getxray.app/api/v2/import/feature?projectKey=$XRAY_PROJECT_KEY"
```

Scenarios tagged `@TEST_<key>` update in place; untagged scenarios create new Test issues. Writing
the resulting keys back into the `.feature` files closes the loop and is a v2 concern (design spec
§10, §13) — nothing this stage does.

## Red Flags — thoughts that mean a gate or the push discipline is being bent

| Thought | Reality |
|---|---|
| "The baseline diff is tiny, probably just whitespace, I'll clean it up and continue" | Any `workspace_baseline` difference stops the run before committing. Report it; do not touch the source checkout to make it go away |
| "I already reverted the stray edit, so the run can proceed clean" | Never revert the source checkout, even to fix what the run itself would report as a violation. Undoing a developer's working tree without asking is the worse outcome |
| "The frontend diff is expected, the human will obviously approve it" | Report it and wait for `baselines.frontend_edits_approved: true`. An expected diff is still a violation until the approval is on record |
| "Stage 03 already knows this scenario is blocked, I'll tag it during the fix loop to save a step" | Stage 03 may not edit `.feature` files, period. The tag is a human-gated edit and belongs here, after 4.2's approval, not inside the fix loop |
| "The remote only has a trivial commit ahead, I'll rebase past it" | Diverged means diverged. Stop and report regardless of how small the remote's commit looks — `commit.md` only ever pushes fast-forward or stops |
| "`--pr` wasn't passed, but opening it saves the human a step" | Opening the PR is `--pr`'s effect alone. Print the title and body; let the flag decide whether it opens |
| "CI can just read whichever `.feature` copy is easiest to zip" | `src/tests` omits blocked and manual scenarios by construction. CI must read `docs/qa/`, never the test tree — that is the whole reason D15 exists |
