# Shared: Execution Report (Jira-Sourced Runs Only)

Load during Stage 01 in `--issue` mode. Skip entirely for manual runs — there is no Jira metadata
to track.

`jira-to-speckit` only fetches and compacts the Jira issue (workflow steps 1–5); it does not run or
track any downstream stage. `speckit-auto` owns the running execution report for the whole pipeline.

- Initialize once, right after Jira intake returns, from
  [../../assets/execution-report-template.md](../../assets/execution-report-template.md).
- Path: `<artifact_folder>/execution-report.md` — the same folder as the provider's spec/plan
  artifacts (see that provider's Stage 01).
- Populate metadata from the `jira-to-speckit` output: Jira issue key, Jira title, resolved feature
  name, repository.
- Update the report in place after **every** stage in this run — Jira intake, each Stage 02 step,
  the Stage 03 implement/review loop, the Stage 04/05 commit, and Stage 06 completion — recording
  progress, current blocker/issue, cumulative Copilot requests, and input/response token estimates.
  Label token counts as estimates when exact counts are unavailable from the active tools.
- Keep the report current until the pipeline ends; do not skip updates because a stage "handed
  back" — a finished stage is not a stop condition (see [global-rules.md](global-rules.md)).
