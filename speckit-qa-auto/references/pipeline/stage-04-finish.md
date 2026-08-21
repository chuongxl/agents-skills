# Stage 04: Finish

Loads: [run-state.md](../shared/run-state.md), [operating-rules.md](../shared/operating-rules.md),
[workspace-guard.md](../shared/workspace-guard.md), [commit.md](../shared/commit.md),
[selector-verification.md](../shared/selector-verification.md),
[gherkin-conventions.md](../shared/gherkin-conventions.md). Six leaves,
so the reader knows the cost before paying it (design spec §11.2 rule 1) — every leaf cited below
by rule or turn-ending-condition number is declared here, since a cited file that goes undeclared
is read from memory instead of from the file. That sentence stood here while two of the leaves it
promised went undeclared: the report quotes `selector-verification.md`'s "Semantic Fallback Is A
Recorded Risk" requirement and classifies manual and blocked scenarios by `gherkin-conventions.md`'s
Surface table. A claim a file makes about itself is not a check, which is why C3 now is one. It links to no other file under
`references/pipeline/` — its predecessor is not linked back to, and it has no successor: this is
the last stage the skill runs. After the steps below the pipeline ends — with the pull request
opened at 4.6 when `--pr` was passed, and otherwise left for a human to open from the text 4.6
printed.

This is the pipeline's second and final human gate (design spec §7, marked ◀ HUMAN GATE). Stage 03
left every scenario in run scope with a verdict — `green` or `blocked` — and this stage turns that
into a report a human can act on, then commits and pushes only after both integrity checks pass.
What those checks are entitled to conclude depends on `run.isolation`: under `worktree`, that the
developer's checkout came out of the run untouched; under `branch` — the default — that the run
wrote only inside the paths it owns and left every already-dirty path exactly as it found it. 4.3
is where that difference is spelled out.

## What This Stage Receives

Per `run-state.md` rule 2, read only from `execution-report.md` and the artifact folder — never
from `stage-03-automate.md`: `run.jira_key`, `run.artifact_dir`, `run.branch`, `run.isolation`,
`run.workspace_path`, `baselines.workspace_baseline`, `baselines.frontend_baseline`,
`baselines.preexisting_dirty[]`, `baselines.owned_paths[]`,
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

- Files created and changed, across the workspace and the artifact folder
- Test results — pass/blocked per scenario, each naming its commit
- Blocked scenarios with reasons
- Proposed `data-testid` additions for the frontend, each with file and line (the report-only
  proposals `selector-verification.md`'s selector gate produced at the head of Stage 03, carried
  forward unapplied unless `baselines.frontend_edits_approved` is true)
- `design.selector_evidence` — `source | live-dom | fallback | n/a` — including the fallback
  acknowledgement recorded at Stage 02 when the evidence source was `fallback`
  (`selector-verification.md`, "Semantic Fallback Is A Recorded Risk": "The Stage 04 report
  repeats it"). It is a roll-up over `surface: ui` scenarios by the precedence in `run-state.md`
  rule 16, and the per-scenario values are the authority, so report a mixed run by its scenarios
  rather than by the summary alone. `n/a` means the scope held no `ui` scenario and there was
  nothing to resolve. Never `deferred` — that value means the gate never ran, and a run carrying it
  cannot have reached this stage
- **Impact scenarios approved at the Stage 02 gate**, each with the flow and evidence path it came
  from
- **`design.adversarial_review` and `design.review_mode`.** A run that shipped with an inline review,
  or with `issues-open`, says so in the artifact a human reads last — not only in a gate they saw
  once and scrolled past
- **Recommended regression**: the existing tests the impact sweep's test-inventory branch found, per
  flow. A list to run or schedule, **not a run** — Stage 03 deliberately did not execute them, for
  the reason its Run Scope section gives.

  A flow is **approved** when at least one of its scenarios is in `impact.approved_scenarios[]`.
  That list names scenarios and never flows (`run-state.md` rule 10), so "approved flow" is derived
  here rather than stored. A flow whose scenarios were **all dropped** still has its tests reported,
  marked as such: the human dropped a scenario, not the observation that tests exist on that surface
- Open questions carried from `test-design.md`

This approval always runs — no flag skips it. Neither does 4.3's baseline verification, which is
unconditional (`operating-rules.md`, Turn-Ending Condition 8) and would remain so even if this
review were ever made optional: the two answer different questions, and a human saying "the tests
look right" is not a human saying "this run stayed inside what it was entitled to touch."

### 4.3 Verify both baselines

Before any commit, re-verify the source checkout and the frontend working tree per
`workspace-guard.md`'s capture commands and comparison. Both must be checked; neither substitutes
for the other, and `workspace-guard.md`, "Why Two And Not One" is why: a parent-repo diff cannot
see inside a submodule, so the checkout-level check cannot speak for the frontend in either
isolation mode.

**Which comparison the source checkout gets depends on `run.isolation`**, per
`workspace-guard.md`, "What `workspace_baseline` Checks, Per Mode". Read that section rather than
assuming the whole-tree form: applied under `isolation: branch` it flags the run's own deliverable
as a leak, and every run in the default mode would stop here.

- Under `isolation: worktree`: re-capture `workspace_baseline` over the source checkout and compare
  whole-tree. **Any** difference is a violation.
- Under `isolation: branch`: run the scoped pair, and **both** halves must pass — every entry of
  `baselines.preexisting_dirty[]` still hashes to its recorded `sha256` (an entry recorded `null`
  is still absent from disk), and every path changed since intake falls inside
  `baselines.owned_paths[]`.
- Either form's failure is a violation. Stop the run **before any commit**, report the differing
  paths with both the baseline and current hashes, and go no further. **Never revert the source
  checkout** — undoing a developer's working tree without asking is worse than the leak it would
  undo, and in the default mode that checkout is the one the developer is standing in.
- A `frontend_baseline` difference is a violation **unless** `baselines.frontend_edits_approved` is
  `true`, in which case it is not a stop — report the diff for review alongside the rest of 4.2's
  output instead.

This is Turn-Ending Condition 8 (`operating-rules.md`). A run that stops here has produced a
report but made no commit; the workspace and the source checkout are left exactly as they were
found.

### 4.4 Tag blocked scenarios

On approval at 4.2, write `@not-automated` into the **artifact** version of every scenario at `status: blocked`: the
`.feature` file(s) in `run.artifact_dir`, never the materialized copy at `feature_path`, since a
blocked scenario was never materialized into it (Stage 03, 3.0 and the Two Degenerate Cases in
`gherkin-conventions.md`).

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

Follow `commit.md` in full: conditional commit on the status check its table names for this run's
`run.isolation` — scoped to `baselines.owned_paths[]` under `branch`, whole-tree under
`worktree` — where an already-clean tree (for example, every change already committed incrementally
during Stage 03) is a success path, so report the existing commits on the branch rather than
treating it as an error. Stage per the same table, and under `isolation: branch` verify the staged
set before committing; `git add -A` is forbidden in that mode (`run-state.md` rule 17). Then
fast-forward-only push. Fetch `origin/<branch>`; remote absent pushes with `-u`; remote an ancestor
of local pushes plainly; **remote diverged stops and reports, and this stage does not rebase**
(Turn-Ending Condition 9). Every command carries an explicit `-C <workspace_path>`.

Report the resulting commit(s) — hash and subject — and the branch pushed, per `commit.md`,
"Reporting."

### 4.6 Print the PR text, then mark the artifact completed

Print a ready-to-use PR title and body: the story key and slug, the coverage summary, the blocked
and manual scenarios called out by name, and a link back to `run.artifact_dir`.

**When `--pr` was passed, open the pull request here**, after 4.5's push, from exactly the title and
body just printed — through whatever PR mechanism the host has: the `gh` CLI where it is installed
and authenticated (`gh pr create --base <base branch> --head <run.branch> --title … --body …`),
otherwise the host's own equivalent. Report the resulting PR URL alongside 4.5's commit and branch.
If no mechanism is available, say so in the report and leave the printed text as the handoff — a
stated limitation, not a silent skip.

**When `--pr` was not passed, the stage prints the text and stops there.** The flag is what decides;
opening a PR nobody asked for is not a default.

Then set `run.stage: completed` in `execution-report.md` and make the follow-up commit for that
status change, pushed the same way 4.5 pushed — `commit.md`'s procedure governs every commit this
stage makes, not only the first. A second divergence here is unlikely immediately after 4.5's push
succeeded, but the check is not skipped on that assumption; a diverged remote at this point stops
and reports exactly as it would have at 4.5.

## What This Stage Produces

Written into run state:

- `run.stage` — `04` on entering this stage, then `completed` at 4.6, the one terminal value
- `design.scenarios[]` unchanged in shape — 4.1 reads these fields, it does not add new ones

And, on disk: the updated `execution-report.md`, `@not-automated` tags written into the blocked
scenarios' artifact `.feature` file(s), the pushed branch, the printed PR title and body, and — when
`--pr` was passed — the pull request 4.6 opened from that text.

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

Scenarios tagged `@TEST_<TEST-KEY>` update in place; untagged scenarios create new Test issues.
Writing the resulting keys back into the `.feature` files closes the loop and is a v2 concern
(design spec §10, §13) — nothing this stage does.

## Red Flags — thoughts that mean a gate or the push discipline is being bent

| Thought | Reality |
|---|---|
| "The baseline diff is tiny, probably just whitespace, I'll clean it up and continue" | A failed baseline check — whole-tree under `worktree`, either half of the scoped pair under `branch` — stops the run before committing. Report it; do not touch the source checkout to make it go away |
| "This is branch mode, so the whole-tree baseline check obviously fails — I'll skip 4.3" | 4.3 is not skipped, it is the *other* comparison. Run the scoped pair; skipping it means nothing checked whether the run wrote outside `owned_paths[]` |
| "I already reverted the stray edit, so the run can proceed clean" | Never revert the source checkout, even to fix what the run itself would report as a violation. Undoing a developer's working tree without asking is the worse outcome |
| "The frontend diff is expected, the human will obviously approve it" | Report it and wait for `baselines.frontend_edits_approved: true`. An expected diff is still a violation until the approval is on record |
| "Stage 03 already knows this scenario is blocked, I'll tag it during the fix loop to save a step" | Stage 03 may not edit `.feature` files, period. The tag is a human-gated edit and belongs here, after 4.2's approval, not inside the fix loop |
| "The remote only has a trivial commit ahead, I'll rebase past it" | Diverged means diverged. Stop and report regardless of how small the remote's commit looks — `commit.md` only ever pushes fast-forward or stops |
| "`--pr` wasn't passed, but opening it saves the human a step" | Opening the PR is `--pr`'s effect alone. Print the title and body; let the flag decide whether it opens |
| "CI can just read whichever `.feature` copy is easiest to zip" | `src/tests` omits blocked and manual scenarios by construction. CI must read `docs/qa/`, never the test tree — that is the whole reason D15 exists |
