# Stage 03: Automate

Loads: [run-state.md](../shared/run-state.md), [operating-rules.md](../shared/operating-rules.md),
[gherkin-conventions.md](../shared/gherkin-conventions.md),
[selector-verification.md](../shared/selector-verification.md),
[repo-profile.md](../shared/repo-profile.md), [commit.md](../shared/commit.md),
[gate-presentation.md](../shared/gate-presentation.md). Seven leaves, so the
reader knows the cost before paying it (design spec §11.2 rule 1). `gate-presentation.md` is
declared because the selector gate at the head of this stage asks a human to choose an evidence
source, and everything a human reads is presented under that file — it is a leaf, so
`selector-verification.md` cannot declare it on this stage's behalf. `commit.md` is declared because
3.4 commits after every scenario verdict, and which paths it may stage depends on `run.isolation` —
a staging rule read from memory is how `git add -A` reappears in the mode that forbids it. `repo-profile.md` is declared because this stage
resolves `generate_cmd`, `scoped_run_cmd`, and `testdata_path` against that file's field table —
it was cited here and left undeclared until the coupling check C3 started reading citations rather
than links. `selector-verification.md` is declared because the
selector gate opens this stage; it is no longer a design-stage concern, and reading it from memory
is exactly how a moved gate goes on being applied where it used to live. `run-state.md` is declared
because this stage reads and updates `design.scenarios[]` by field name — `attempts` above all, which is what bounds
the fix loop across turns. It links to no other file under `references/pipeline/` — Stage 02 is
not linked back to, and its successor is named, never linked: **enter Stage 04** at the end of this
stage, same turn.

◀ NO-STOP ZONE. Stage 03 opens once Stage 02's human gate has passed and the design artifacts are
committed. From that point until every scenario in scope carries a
verdict, nothing in this stage asks a question, waits for approval, or pauses for confirmation.
Once the no-stop zone is open there are exactly three ways this stage ends: a verdict recorded
against every scenario in scope, an infrastructure stop (`operating-rules.md`, "Infrastructure
Failure Is Not Test Failure"), or the circuit breaker (`operating-rules.md`, "Circuit Breaker"). No
fourth exit exists inside the zone. The entry gate below can end the stage before the zone opens —
that is a fourth exit from the *stage*, and deliberately not one from the *zone*.

## Entry Gate: Resolve The Intent Map

Runs first, before any step below, and before the no-stop zone opens. Follow
`selector-verification.md` in full.

1. **Refuse `code_state: pending`.** A run whose code has not landed must not have reached this
   stage; Stage 02 ends such runs at `resume_from: 02.4`. Reaching here with
   `selector_evidence: deferred` means that exit was missed — stop and report, rather than generate
   against selectors nobody could verify.
2. **Ask the evidence source and resolve.** Repository source, live DOM via subagent, or a recorded
   semantic fallback, per `selector-verification.md`, "The Choice Is Asked, Never Assumed". Asked
   under `gate-presentation.md`: each source is one choice carrying its own trade-off, and the
   question names no step and no field — a reader picking an evidence source does not need to know
   which run-state value their answer lands in. Write
   `design.selector_evidence`. This is the one question this stage asks, and asking it here — rather
   than after three scenarios have been generated against the wrong source — is what keeps it
   answerable.
3. **Turn the element intent map into a selector map.** One row per element, each resolving to an
   existing selector, a proposed one with file and line, or a named semantic fallback. Each
   scenario's own value is written to `design.scenarios[].selector_evidence`, and the run-level
   field is the roll-up over the `surface: ui` ones (`run-state.md` rule 16). A run whose scope
   holds no `ui` scenario at all has nothing to resolve: every scenario carries `n/a`, the roll-up
   is `n/a`, and step 2's question is not asked. `n/a` is not `deferred` — nothing was skipped,
   there was nothing to seek — and Turn-Ending Condition 11 does not fire on it.
4. **Block, do not stop, on an element that is not there.** Per `selector-verification.md`, "An
   Element That Does Not Exist Is A Design Verdict, Not A Stop": mark that scenario
   `blocked: needs-design-change` and continue with the rest. It costs no fix-loop attempt — the
   verdict is known before the first attempt could be spent.

Frontend edits proposed here are report-only unless the human explicitly approves them; an approval
sets `baselines.frontend_edits_approved: true`, is recorded for the Stage 04 frontend baseline
re-verification, and lands on a separate frontend branch inside the submodule — never mixed into the
test branch or the same commit as test artifacts.

The no-stop zone opens once every `surface: ui` scenario in scope either carries a complete selector
map or carries a `blocked` verdict.

## What This Stage Receives

Per `run-state.md` rule 2, read only from `execution-report.md` and the artifact folder — never
from `stage-02-test-design.md`: `run.artifact_dir`, `run.branch`, `run.isolation`,
`run.workspace_path`, `baselines.owned_paths[]`, `run.full_suite`, every field of `profile.*` (`repo-profile.md`'s fourteen-field
table — `feature_path`, `steps_path`, `page_path`, `selectors_path`, `testdata_path`,
`generate_cmd`, `scoped_run_cmd`, `selector_attribute`, `existing_tags`, and the rest), and
`design.scenarios[]` as Stage 02 left them — every scenario at `status: pending` — and
`run.code_state`, which the entry gate checks before anything else. On disk, inside `run.artifact_dir`: the `.feature` file(s) from Stage 02's step
2.5, and `test-design.md` for its coverage matrix, element intent map, and test data/mock plan.

## Execution Order

The six steps below run in the order design spec §6 fixes. 3.1–3.4 repeat once per scenario
package, in the dependency order 3.1 establishes. 3.0 runs first, ahead of any package, and again
whenever a scenario's fix loop resolves to `blocked`. 3.5 runs once, after every scenario in the
current run scope carries a verdict.

### 3.0 Materialize

Copy `.feature` file(s) from `run.artifact_dir` into `feature_path`. On any difference between the
two, the artifact version wins: overwrite the copy and log the overwrite in
`execution-report.md`. This step never edits the artifact version, only the copy, and it follows
`gherkin-conventions.md`'s Anti-Drift Rule and Two Degenerate Cases in full — the copy is a
scenario-level subset checked Gherkin-aware, never a text diff, and a file with every scenario
blocked is not materialized at all.

`surface: manual` scenarios are never candidates for the copy — they are excluded from the very
first materialization, by construction, per `gherkin-conventions.md`'s Surface table. A scenario
whose fix loop concludes `blocked: needs-design-change` (3.4) triggers a re-materialization that
drops it from the copy the same way, so the committed test tree only ever holds scenarios with a
passing verdict.

### 3.1 Partition

Work one scenario package at a time, in dependency order — a scenario sharing `Background:` setup
or a page object with another goes after whichever it depends on. Pass each package only the
slices of `test-design.md` it needs: its own rows of the coverage matrix and of the selector map the
entry gate produced, never the whole document, and never the whole of Stage 02's prose.

### 3.2 Generate

Produce `*.steps.ts` at `steps_path`, page objects at `page_path`, selectors at `selectors_path`,
and test data or mocks at `testdata_path` — all per `repo-profile.md`'s field table. Only selectors already present in the selector map the entry gate
produced may be used; a missing selector is a gate defect surfaced here, not something to resolve by
inventing one.

### 3.3 Verify

Run `generate_cmd`, then `scoped_run_cmd` filtered to the scenario's tag. Capture the full output —
it is both the input to 3.4's fix loop and the evidence quoted at an infrastructure stop.

### 3.4 Fix loop

At most 3 attempts per scenario, bounded by the rules and the diagram in `operating-rules.md`.
`design.scenarios[].attempts` counts edit-and-rerun cycles, not the initial verify in 3.3 — the
first red result costs nothing; each subsequent edit that gets re-verified spends one of the three.
A scenario still red after the third spent attempt is marked `blocked: needs-design-change`
(`design.scenarios[].blocked_reason`), never given a fourth.

Every edit in this loop stays inside the permitted set `operating-rules.md` names — selectors,
waits and synchronization, page objects, step definitions, test data, mocks — and never touches the
forbidden set, `.feature` files included. A failure that would only be fixed by changing Gherkin is
not a failure to keep retrying; it is `blocked: needs-design-change` on the first attempt that
reveals it, whether or not attempts remain. An environmental failure is not a fix-loop failure at
all: it stops the run immediately with the error quoted, per `operating-rules.md`'s
infrastructure-failure rule, and consumes no attempt.

When a scenario resolves — `green` or `blocked` — commit locally, no push, so
`design.scenarios[].commit` names a real sha. Stage the way `commit.md`'s "Conditional Commit"
table requires for this run's `run.isolation`: `git add -A` under `worktree`, and `git add --
<owned_paths>` under `branch`, where `add -A` is forbidden because it would sweep the developer's
in-flight edits into a test commit (`run-state.md` rule 17). Every command carries an explicit
`-C <workspace_path>`. Pushing the branch is Stage 04's job alone. A result with no sha attached is
not a result (`run-state.md` rule 4).

### 3.5 Coverage review loop

Once every scenario in the current run scope carries a verdict, check three things across the whole
batch: every acceptance criterion in `test-design.md`'s coverage matrix **whose covering scenarios
are in automation scope** — `surface: ui` or `surface: api`, and not marked
`blocked: needs-design-change` — has at least one passing scenario; every row of the entry gate's selector map
was used by generated code; and repo conventions hold —
page objects go through the base page, selectors stay centralized, no test data is hardcoded in
step definitions, and no `waitForTimeout` appears anywhere. A failure here is not a stop. It feeds
the next fix-loop iteration for whichever scenario or file the failure traces to, under the same
3-attempt budget 3.4 already spends.

The scope qualifier on the first check is what keeps this loop from being unexitable. A criterion
covered only by a `surface: manual` scenario has no passing scenario by construction — nothing ever
automates it — and the same is true of a criterion covered only by a scenario the fix loop marked
`blocked: needs-design-change`. Counting either as a coverage failure would feed a fix loop that
cannot succeed, forever, against a check whose failure is explicitly not a stop. Such a criterion is
**reported** in Stage 04's coverage-matrix status as covered by a manual or a blocked scenario,
not retried here.

## Run Scope

Default scope is the affected domain's tests plus the new scenarios — not the whole suite. A
full-suite run only happens under the explicit `--full-suite` flag (`run.full_suite`), because
running everything is slow and rarely what a single ticket needs. `scoped_run_cmd`'s tag filter is
what enforces this scope at 3.3; narrowing that filter to dodge a red scenario is itself a forbidden
fix-loop edit (`operating-rules.md`).

The impact `.feature` file is a second input to **materialization** and generation, and its
scenarios get `design.scenarios[]` entries like any other. The scoped run command covers exactly the
scenarios that have such entries — both files' — and is **not** widened to sweep in the pre-existing
tests of the flows those scenarios touch.

That restraint is arithmetic, not caution. This stage's exit condition is a verdict recorded against
every scenario in scope, and its fix loop budgets attempts per entry in `design.scenarios[]`. A
pre-existing test pulled in by a broadened tag filter has no entry, so no attempts budget and no
path to a verdict — inside a no-stop zone that cannot end until every in-scope scenario has one.
Widening the command would manufacture in-scope work this stage has no mechanism to discharge. Those
tests are reported by Stage 04 as recommended regression instead, where a human can run them.

`@IMPACT` is not part of the tag filter either, for the same reason (`gherkin-conventions.md`).

## Blocked And Manual Scenarios

A scenario enters the fix loop only if it is `surface: ui` or `surface: api`. `surface: manual`
scenarios never enter 3.2–3.4 at all — they stay out of the materialized copy and are reported
as-is at Stage 04.

A scenario the fix loop marks `blocked: needs-design-change` is omitted from the materialized copy
so the committed test tree stays green, and the run continues with the remaining scenarios in the
package. Stage 03 does not tag a blocked or manual scenario inside the `.feature` file — it cannot,
since editing `.feature` is forbidden without exception (`operating-rules.md`). The tag that marks a
scenario's automation status in the file itself is written later, after a human approves it — that
is Stage 04's job, not this stage's.

## What This Stage Produces

Written into run state:

- `run.stage: 03`, written on entering this stage, so a run interrupted inside it resumes here
- `design.selector_evidence` — `source | live-dom | fallback`, written by the entry gate. Never
  `deferred`: that value means the gate has not run, and this stage does not open until it has
- `design.scenarios[].status` — `green` or `blocked`; never left `pending` for a scenario the run
  scope included
- `design.scenarios[].attempts` — the number of fix-loop edit-and-rerun cycles spent
- `design.scenarios[].blocked_reason` — `needs-design-change`, set only when `status: blocked`
- `design.scenarios[].commit` — the sha each result was produced on

And, on disk: the materialized `.feature` subset at `feature_path`, and the generated
`*.steps.ts`, `*Page.ts`, `*Selectors.ts`, fixtures, and mocks that the repo profile's paths name.

## Enter Stage 04

Once every scenario in scope carries a verdict — `green` or `blocked` — enter Stage 04 in the same
turn. That verdict on every scenario is the entire exit condition. 3.5 is a review loop that feeds
3.4, not a gate on this exit: a coverage-review failure is explicitly not a stop, so making the exit
conditional on 3.5 passing would invent a fourth way for the stage to end — hanging — for exactly
the runs that carry a manual or blocked scenario. There is no human gate in this stage, and nothing
here waits for one.
