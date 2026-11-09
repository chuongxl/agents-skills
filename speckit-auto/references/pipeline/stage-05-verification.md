# Stage 05: Verification (Provider-Agnostic, Conditional)

Load right after Stage 04's implementation commit succeeds (or was skipped because nothing needed
committing). Runs only when this repo opted in to verification at `--integration` setup time.

At actual entry or re-entry emit `{type: "stage_started", stage: "05-verification"}` using the
shared JSON stdin invocation, not on context-only resume. Emit
`{type: "stage_finished", stage: "05-verification"}` at the handoff (step 5), including when the
stage is skipped.

## 1. Read the opt-in

Read `verification` from the mirrored `<worktree>/.speckit/integration.json` (the same file Stage
01 §1.4 already copies into the worktree on every entry). Missing file, or the field absent
entirely (a repo that ran `--integration` before this field existed) → treat as `false`. Never
default a pre-existing repo into unexpected new behavior.

- `false` → skip this stage entirely. Load [stage-06-finish.md](stage-06-finish.md) and enter
  Stage 06 in the same turn, noting `verification: skipped` for the final report.
- `true` → continue with steps 2-5 below.

## 2. Update the project verification skill for this feature

Invoke the `skill` tool with name `create-verification-skill`, in **update mode**: name the one
feature this run just implemented (from the spec title / Jira summary) and pass the spec, plan,
and the list of files changed in the implementation commit as context. It adds a new
`features/<feature-slug>.md` file, or updates the existing one if this run modified a
previously-mapped feature, inside the already-generated `.agents/skills/verify-<app>/features/`
map. It never touches other features' files, and only touches `SKILL.md` itself if this feature
changed Launch/Doctor/Drive/Evidence/Cleanup. **Explicitly tell it to skip its own Step 4
(Prove) proof-and-cleanup for this call** — Stage 05 §3 below is the real proof, driven against
the full running app, and Stage 05/06 own the cleanup timing; a second launch/drive/cleanup cycle
inside `create-verification-skill` itself would double-drive the app and risk tearing down an
instance Stage 06 still expects to clean up.

**Failure** (skill unavailable, or it reports it could not complete the update) → follow
"Verification Unavailable" below. Verification was explicitly opted into; it is never skipped
silently.

## 3. Execute the verification skill for this feature

Run the (now current) `verify-<app>` skill's own instructions, scoped to only this run's feature:
launch, doctor, drive using the harness recipe from `features/<feature-slug>.md`, capture
evidence, per its own Evidence section — but do **not** run cleanup yet; that happens once, in
Stage 06, after the human confirms verification passed (a failed confirmation may mean rerunning
the drive against the same still-launched instance).

**Failure** (launch fails, doctor fails, the drive step cannot complete) → run Cleanup, retry
steps 2-3 **once**, then follow "Verification Unavailable" below if it fails again.

## 4. Assess evidence against the spec, then confirm

### 4a. Assess (both modes)

Capturing evidence is not proof. Before anything is presented or approved, compare the evidence
from step 3 with the feature's acceptance criteria — the spec's acceptance scenarios and `FR-*`
requirements that this feature's `features/<feature-slug>.md` exercises. For each criterion record
one verdict with a pointer to the evidence (file path, transcript line, response field):

- `met` — the evidence shows the expected behavior.
- `not met` — the evidence shows different behavior, an error, or the expected effect absent.
- `unverifiable` — the drive did not exercise it (say why). This never fails the stage by itself,
  but it is listed in the report and the evidence summary, never counted as `met`.

Judge only what the evidence shows; never infer `met` from "the drive completed". Any `not met`
makes the assessment a **mismatch**. No `not met` → **clean**.

### 4b. Default Mode

Present the criteria table (criterion, verdict, evidence pointer) with the captured evidence as a
concise summary; a mismatch is flagged at the top and `Investigate further` is recommended.
The human still decides: ask via the host ask tool `Verification passed, proceed to finish` /
`Investigate further`. Immediately before asking emit `gate_waiting` with
`stage: "05-verification"` and `gate: "verification-confirm"`; immediately after either response
emit `gate_answered` with the same stage/gate and no answer text.

### 4c. YOLO Path

No ask-tool confirmation (no `gate_waiting`/`gate_answered`) — the assessment itself is the gate:

- **Clean** → auto-record `verification: passed`; the final report says it was auto-assessed
  (not human-confirmed), lists any `unverifiable` criteria, and continues to Stage 06.
- **Mismatch** → do not continue. Run `verify-<app>`'s Cleanup step (the code is about to
  change), then route back like "Investigate Further" below, using the `not met` criteria and
  their evidence as the feedback (no human to collect it from). Each pass increments
  `investigate_loops`. After **3** mismatching passes with no `not met` criterion newly fixed,
  stop: emit `run_failed` with `reason.code: "review_loop_stuck"` (composed one-line message, no
  raw output), report the remaining `not met` criteria, and do not mark the spec completed or open
  a PR. The implementation is already pushed (Stage 04).

### If Investigate Further

"Investigate further" (default mode) and a YOLO mismatch are not a `run_failed` by themselves.
Run `verify-<app>`'s Cleanup first if you will change code. Route back exactly like Stage 04's
"Request changes" path: collect the feedback (YOLO: use the `not met` findings), restart through
the earliest affected step (requirement/architecture/task/code-level), re-run every downstream
Stage 02 step and its self-review gate if regenerated, re-enter the full Stage 03 flow if code
changed (this is the fix step: implementation plus the `speckit-code-review` loop until `pass`),
re-enter Stage 04 (human approval gate in default mode; auto-commit in YOLO), then re-enter this
stage (Stage 05) from the top — including a fresh `create-verification-skill` update-mode call,
since the feature's behavior may have changed.

### If Approved (or YOLO clean)

Continue to Stage 06 with `verification: passed`.

## Verification Unavailable

The environment cannot run the app (no display, missing service, launch crash) after the retry.
This is not a defect in the implementation, which already passed review and project checks, so it
must not strand a finished feature without a PR. Clean up first (run `verify-<app>`'s Cleanup for
anything launched; trouble is a warning), then:

- **YOLO** → record `verification: unavailable` with a one-line composed reason, emit no waiting
  events, and continue to Stage 06. Stage 06 states "UNVERIFIED" prominently in the PR body.
- **Default mode** → ask via the host ask tool `Continue without verification` / `Stop`, bracketed
  with `gate_waiting`/`gate_answered` using `stage: "05-verification"`,
  `gate: "verification-unavailable"`. `Continue` → same as YOLO above. `Stop` → "Hard stop" below.

### Hard stop

1. Cleanup already ran above; confirm nothing launched is still running.
2. Emit `run_failed` with `reason.code: "crashed"` (a one-line, composed message — never raw tool
   output) before reporting. On an event write error, stop and never emit `run_completed`.
3. Report the exact error, and tell the user: the implementation is already committed and pushed
   (Stage 04), but the spec is not marked completed and no PR was opened. They can fix the
   problem and re-run, or disable verification via `/speckit-auto --integration <value>` and
   re-run.

## 5. Handoff

Emit `stage_finished` for `05-verification`, then load [stage-06-finish.md](stage-06-finish.md)
and enter Stage 06 in the same turn, carrying
forward whether this stage ran (`skipped`, `passed` or `unavailable`) and, if it ran, a reference to what
`verify-<app>` launched so Stage 06 can run its Cleanup step.
