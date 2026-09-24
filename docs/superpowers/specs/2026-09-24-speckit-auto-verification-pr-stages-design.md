# speckit-auto: Verification and PR Stages Design

**Date**: 2026-09-24
**Status**: Draft — pending user review

## Summary

Add two new skills to this repo, `how` and `create-verification-skill`, cloned from their
existing plugin-marketplace counterparts and adapted to this repo's self-containment contract.
`how` ships as a standalone, generically-usable skill and is not wired into speckit-auto's
pipeline (its analysis duplicates what `create-verification-skill`'s own interview step already
does). Extend `speckit-auto`'s pipeline from four stages to six: Stage 05 (Verification,
conditional on an integration-time opt-in) runs a generated project-specific verification skill
against the just-implemented feature; Stage 06 (Clean / Commit / Push / PR / Complete) absorbs the
"mark spec completed" and PR-creation responsibilities that Stage 04 owns today, adds teardown of
whatever Stage 05 launched, and replaces today's `superpowers`-only best-effort PR call with a
provider-agnostic, per-repo (parent + each submodule) `gh pr create` step.

## Problem

Today's Stage 04 does three unrelated things in one file: human approval, implementation commit,
and (only in `superpowers` mode, via an optional external skill call) PR creation. There is no
verification step between "code review passed" and "shipped" — a human is asked to approve based
on a summary, with no automated proof the feature actually works end to end. PR creation is also
inconsistent across providers: `github-speckit` mode never opens a PR at all today.

## Non-goals

- This does not change Stage 01–03 behavior (intake, spec/design, implement + code-review loop).
- This does not make `how` or `create-verification-skill` speckit-auto-specific; both ship as
  independently usable, generic skills, consistent with `jira-to-speckit` and
  `speckit-code-review`.
- This does not attempt CI integration; verification and PR creation both run locally, synchronously,
  in the same turn.

## New skills

### `how/` (new, cloned)

Cloned from the existing `how` plugin skill (`SKILL.md` + `references/{explorer,explainer,critic}
-prompt.md`, `critique-rubric.md`). No behavior changes beyond what's needed to satisfy this
repo's `SKILL_SPEC.md` frontmatter contract (`name`, `description`, `compatibility`, `metadata`,
`license`, `allowed-tools` only; `metadata.author`/`version` required). Ships as a standalone
skill for architecture/runtime-flow questions; not invoked by speckit-auto's pipeline, since
`create-verification-skill`'s own interview step already covers the same ground for verification
purposes.

### `create-verification-skill/` (new, cloned)

Cloned from the existing `create-verification-skill` plugin skill (`SKILL.md` +
`references/feature-map-example/`). Behavior addition beyond the original: **incremental update
mode**. The original skill only describes creating a skill from scratch; this repo's version adds
an explicit "if `.cursor/skills/verify-<app>/` already exists, add or update only the named
feature's file in `features/`, and only touch `SKILL.md` itself if Launch/Doctor/Drive/Cleanup
actually changed — never a blind full regeneration." This is required because Stage 05 calls it
once per implemented feature, long after integration setup already created the skill.

`create-verification-skill` is declared as a sibling install dependency of `speckit-auto`, the
same pattern already used for `speckit-code-review` and `jira-to-speckit` (copied in together;
`speckit-auto` invokes it via the `skill` tool and treats a missing/failed invocation as a
stop-and-report condition when verification is enabled, since the user explicitly opted in).
`how` is added to this repo as an independent skill but is not a speckit-auto install dependency.

## Integration-time opt-in

`shared/integration-setup.md` (the `--integration` flow) gains one more question after provider
resolution: **"Enable implementation verification for this project?"** (Yes/No). The answer is
persisted alongside the provider choice, as a new `verification: true|false` field in
`.speckit/integration.json` (repo-local) or the user-home config — same precedence chain the
provider choice already uses (repo-local → user-home → first-run ask).

If **Yes**:
1. Invoke `create-verification-skill` directly (its own "Interview the repo" step observes surface,
   run command, harness, and isolation from the codebase itself) to generate the full skill for
   this project: Launch, Doctor, Drive, Evidence, Cleanup, Helpers, plus a feature map
   (`features/README.md` + one file per identified feature, top 3-5 to start) covering the repo's
   **existing** top features — not yet the feature this speckit-auto run is about to implement,
   which doesn't exist yet at setup time.
2. Prove the generated skill once (per `create-verification-skill`'s own step 4): launch, doctor,
   drive one mapped feature, capture evidence, clean up, confirm evidence survived cleanup.
3. Commit the generated `.cursor/skills/verify-<app>/` skill + feature map as part of integration
   setup.

If **No**: persist `verification: false`; generate nothing; Stage 05 will be skipped on every run
for this repo until re-opted-in.

## Stage 04 (narrowed)

Unchanged: the human-review approval loop (or YOLO auto-approve), and the implementation commit
via `shared/commit.md`, still happen here, immediately after approval — so verification in Stage
05 always runs against **committed** code, never uncommitted working-tree state.

Removed from Stage 04 (moved to Stage 06): "Mark Spec Completed + Follow-up Commit" and the
`finishing-a-development-branch` PR-creation call.

## Stage 05 (new): Verification

1. Read `verification` from the resolved integration config (the same config object Stage 01
   already resolves the provider from).
2. `false`, or the config predates this field (older `.speckit/integration.json` without
   `verification` at all) → treat as `false`, skip this stage entirely, proceed to Stage 06.
   (Never defaults a pre-existing repo into unexpected new behavior.)
3. `true` →
   a. Invoke `create-verification-skill` in **update mode**, with the just-completed spec + plan +
      changed files as context: add a new feature file, or update the existing one if this run
      modified a previously-mapped feature, in the existing `.cursor/skills/verify-<app>/features/`
      map. Never touches other features' files.
   b. Execute the (now current) `verify-<app>` skill, scoped to only this run's feature: launch,
      doctor, drive, capture evidence, per its own instructions.
   c. Present the evidence summary in chat. Ask via the host ask tool: `Verification passed,
      proceed to finish` / `Investigate further`.
   d. **Investigate further** → route back exactly like Stage 04's "Request changes" path: restart
      through the earliest affected step, re-run downstream stages, re-enter Stage 03's full
      no-stop flow if code changed, then re-enter Stage 05 from the top.
4. Any hard failure inside `create-verification-skill` or the generated skill itself (skill
   missing, launch fails, doctor fails) is a stop-and-report condition — verification was
   explicitly opted into, so a silent skip here would be misleading, unlike the historical
   best-effort PR call it replaces.

## Stage 06 (new): Clean, Commit, Push, PR, Complete

1. If Stage 05 ran, run the generated `verify-<app>` skill's own Cleanup step: tear down only what
   it started (kill by tracked PID/handle, never by process name). Evidence artifacts are never
   deleted by this cleanup — they stay wherever `verify-<app>` named them.
2. Commit the `verify-<app>` skill files + feature map changes only (not run evidence/screenshots)
   — reuses `shared/commit.md`'s conditional-commit logic (skip if already clean) and submodule
   commit ordering.
3. Mark the active spec `completed` (moved here from Stage 04) + commit, as today.
4. Push parent + every submodule that has local commits ahead of its pushed base — reuses
   `shared/commit.md`'s branch-sync-and-push section verbatim (already handles submodules).
5. **PR creation (provider-agnostic, replaces the old `finishing-a-development-branch` call)**:
   for the parent repo, then for each submodule that has commits ahead of its base branch:
   a. Detect the remote: `git remote get-url origin`.
   b. If the host is `github.com`, run `gh pr create` for that repo/submodule, with a title/body
      derived from the spec. Treat "a PR already exists for this branch" as success, not an error
      (idempotent).
   c. Any other host, or `gh` not installed/authenticated → report "PR not created for <repo>:
      <reason>" and continue — non-blocking, one repo's failure never stops another repo's PR or
      the overall stage.
   d. Report the outcome (created / already existed / skipped + reason) per repo in the final
      report.

## Final Report (Stage 06, replaces Stage 04's)

Resolved provider, `speckit-code-review` final status, verification outcome (`verification:
skipped|passed`, plus `investigate_loops: N` when it ran), the implementation commit(s), the
verification-artifact commit (if any), the spec completion commit, pushed branches, and per-repo
PR outcomes.

## Failure handling additions

- Stage 05 hard failures (see above) stop the run; the human review approval and implementation
  commit from Stage 04 are not undone — the user is told the implementation is committed and
  pushed-pending, verification failed, and manual verification or a re-run of Stage 05 is needed.
- Stage 06 PR failures are per-repo non-blocking, per the user's explicit instruction; a failed
  commit, failed push, or unresolved rebase inside Stage 06 remains a hard stop (unchanged
  philosophy from `shared/commit.md`).

## Open questions

None outstanding — all prior ambiguities (skill reusability, commit timing, clean semantics,
commit scope, PR mechanism/failure mode, opt-in placement, setup-time map scope) were resolved
during brainstorming and are reflected above.
