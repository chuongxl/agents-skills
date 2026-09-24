# Stage 05: Verification (Provider-Agnostic, Conditional)

Load right after Stage 04's implementation commit succeeds (or was skipped because nothing needed
committing). Runs only when this repo opted in to verification at `--integration` setup time.

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
previously-mapped feature, inside the already-generated `.cursor/skills/verify-<app>/features/`
map. It never touches other features' files, and only touches `SKILL.md` itself if this feature
changed Launch/Doctor/Drive/Evidence/Cleanup. **Explicitly tell it to skip its own Step 4
(Prove) proof-and-cleanup for this call** — Stage 05 §3 below is the real proof, driven against
the full running app, and Stage 05/06 own the cleanup timing; a second launch/drive/cleanup cycle
inside `create-verification-skill` itself would double-drive the app and risk tearing down an
instance Stage 06 still expects to clean up.

**Hard failure** (skill unavailable, or it reports it could not complete the update) → stop and
report the exact error. Verification was explicitly opted into; a silent skip here would be
misleading. Tell the user the implementation is already committed and pushed (per Stage
04), and that they can re-run Stage 05 manually or disable verification via
`/speckit-auto --integration <value>` and re-run.

## 3. Execute the verification skill for this feature

Run the (now current) `verify-<app>` skill's own instructions, scoped to only this run's feature:
launch, doctor, drive using the harness recipe from `features/<feature-slug>.md`, capture
evidence, per its own Evidence section — but do **not** run cleanup yet; that happens once, in
Stage 06, after the human confirms verification passed (a failed confirmation may mean rerunning
the drive against the same still-launched instance).

**Hard failure** (launch fails, doctor fails, the drive step cannot complete) → stop and report
the exact error, same failure philosophy as step 2.

## 4. Present evidence and confirm

Present the captured evidence (screenshots, transcripts, response bodies — whatever
`features/<feature-slug>.md` named) as a concise summary.

### Default Mode

Ask via the host ask tool: `Verification passed, proceed to finish` / `Investigate further`.

### YOLO Path

Skip the ask-tool confirmation entirely — the verification itself already ran in step 3; only the
human confirmation is skipped. Auto-record `verification: passed` and note in the final report
that this result was auto-approved (not skipped).

### If Investigate Further

Route back exactly like Stage 04's "Request changes" path: collect the feedback, restart through
the earliest affected step (requirement/architecture/task/code-level), re-run every downstream
Stage 02 step and its self-review gate if regenerated, re-enter the full Stage 03 flow if code
changed, re-enter Stage 04's approval gate, then re-enter this stage (Stage 05) from the top —
including a fresh `create-verification-skill` update-mode call, since the feature's behavior may
have changed.

### If Approved

Continue to Stage 06 with `verification: passed`.

## 5. Handoff

Load [stage-06-finish.md](stage-06-finish.md) and enter Stage 06 in the same turn, carrying
forward whether this stage ran (`skipped` or `passed`) and, if it ran, a reference to what
`verify-<app>` launched so Stage 06 can run its Cleanup step.
