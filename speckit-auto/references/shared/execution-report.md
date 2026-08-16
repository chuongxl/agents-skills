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

## Per-Stage Token Accounting

After each stage completes, append a row to a `## Token Accounting` section in the report
(create the section on first write). This makes post-run cost analysis measurable:

```markdown
## Token Accounting

| Stage | Static instructions (chars) | Dynamic content (chars) | Tool calls | Est. input tokens | Est. output tokens | Notes |
|-------|---------------------------|------------------------|------------|-------------------|-------------------|-------|
| Entry + Stage 01 | 28,000 | 4,000 | 8 | ~8,000 | ~1,500 | worktree bootstrap + intake |
| Stage 02 | 15,000 | 12,000 | 6 | ~7,000 | ~3,000 | specify → plan → tasks |
| Stage 03 iter 1 | 12,000 | 25,000 | 15 | ~10,000 | ~6,000 | implement + review (1 iteration) |
| Stage 03 iter 2 | 12,000 | 20,000 | 10 | ~8,000 | ~4,000 | fix + re-review |
| Stage 04 | 8,000 | 3,000 | 3 | ~3,000 | ~500 | human review + commit |
| Stage 06 | 5,000 | 1,000 | 2 | ~1,500 | ~200 | spec completion |
| **Total** | | | **44** | **~37,500** | **~15,200** | |
```

Rules for accounting:
- **Static instructions**: sum of all `.md` files loaded for that stage (use `wc -c` or estimate).
- **Dynamic content**: Jira payload, spec/plan re-reads, diff output, review results.
- **Tool calls**: count every bash/edit/create/skill call made during the stage.
- **Est. input/output tokens**: estimate from chars (tokens ≈ chars ÷ 4); label as estimates.
- **Notes**: one-line summary of what happened (e.g. "2 review iterations", "FR-* fix triggered
  plan regeneration").
- The `Total` row sums tool calls and token estimates; cost can be computed from the totals using
  the Claude Sonnet 4.6 pricing in the token optimization plan.
