# Stage 01 (github-speckit): Preflight + Intake

Provider: **github-speckit** — repo-installed GitHub Spec Kit agents.

Load with this file:
- [provider-rules.md](provider-rules.md) — provider-specific rules and invocation
- [../shared/branching.md](../shared/branching.md) — branch gate (runs first)
- [../shared/intake.md](../shared/intake.md) — issue resolution, run state, Jira intake
- [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md) — project context

Execution order for this stage:
**branch setup (shared) → Speckit source check → install recovery if missing → guidelines load →
intake (shared) → artifact path → `/speckit.specify` (Stage 02 entry, also the executability proof).**

Only the Speckit-specific steps are described below; everything else lives in the shared files.

## Preflight Speckit Source Check (Required)

Verify these repo-installed files exist for each of the eight stages
(`specify`, `clarify`, `plan`, `checklist`, `tasks`, `analyze`, `implement`, `converge`):

- `.github/agents/speckit.<stage>.agent.md`
- `.github/prompts/speckit.<stage>.prompt.md`

If any file is missing, run install recovery below. Never fall back to a global or external Speckit
variant — the repo-installed agents are the only valid source.

## Missing Speckit Auto-Recovery (Required)

When any required repo Speckit file is missing, run recovery — do not silently skip and do not
abandon the run:

1. Fetch the install guide: `https://github.com/github/spec-kit/blob/main/docs/installation.md`
2. Ask the user once: `Install GitHub Speckit` or `Stop`.
3. If `Stop`, halt and report that installation is required.
4. If `Install`, follow the guide exactly to install the Spec Kit CLI.
5. Initialize in this repo: `specify init . --integration copilot`
6. Run `/speckit.constitution` as an agent.
7. Re-run the source check.
8. If it passes, continue the pipeline in the same turn.
9. Only if install or init fails, stop and report the exact failing step with quoted error output.

## Runtime Executability (No Separate Probe)

Do **not** invoke `/speckit.specify` as a standalone probe before intake — it is a mutating call
and would start Stage 02 without the resolved artifact path. Executability is proven by the real
post-intake `/speckit.specify` invocation at the end of this stage.

`stage_invocation_mode` is always `slash-agent` — never attempt the `task` tool with a `speckit.*`
agent_type, it always fails with `Unknown agent_type`. Only a concrete error from the real
invocation is reportable as a runtime failure (quote it), and only after the source check passed.

## Preflight Guidelines Context Load (Required)

Load [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md).
If `docs/guidelines/` or `architecture.md` is missing, skip and continue — never a stop.

## Artifact Path (Spec Kit Layout)

Using `issue_id` and `short_title` from [../shared/intake.md](../shared/intake.md):

| Mode | Path |
|------|------|
| `--issue` | `specs/<issue_id>-<short_title>/` (example: `specs/ddm-6157-user-login/`) |
| manual | `specs/<nnn>-<requirement-slug>/` following the repo's existing numbering |

The folder must stay stable across reruns of the same issue.

| Artifact | Path | Written by |
|----------|------|------------|
| Ticket snapshot (`--issue` only) | `specs/<issue_id>-<short_title>/ticket.md` | `jira-to-speckit` (staged), relocated here by this stage |
| Spec / plan / tasks / checklist | `specs/<issue_id>-<short_title>/` | the `speckit.*` stages |
| Execution report (`--issue` only) | `specs/<issue_id>-<short_title>/execution-report.md` | this pipeline |

## Ticket Snapshot Relocation (Required, `--issue` Mode)

Right after the artifact folder is created, **move** the staged snapshot
`.speckit/intake/<issue_id>-ticket.md` → `specs/<issue_id>-<short_title>/ticket.md` and record
`ticket_path` in run state. Overwrite an existing `ticket.md` on a rerun. Full rules:
[../shared/intake.md](../shared/intake.md) → "Ticket Snapshot".

`ticket.md` is the traceback record of the original request; the Spec Kit artifacts remain the
source of truth for what gets built. It is committed alongside them by Stage 04/05 (`git add -A`) —
do not add it to `.gitignore` and do not commit it separately. Pass only the compact brief into
`/speckit.specify`, never the snapshot's contents.

## Stage 02 Entry Step

After intake completes, invoke `/speckit.specify` with the compact brief (or requirement text) in
the same turn, then continue to [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).

## Execution Report (Jira-Sourced Runs)

`jira-to-speckit` only fetches and compacts the Jira issue (workflow steps 1–5) — it does not run
or track any downstream stage. `speckit-auto` owns the running execution report for the whole
pipeline whenever the run started from `--issue` mode.

- Initialize once, right after Jira intake returns, from
  [../../assets/execution-report-template.md](../../assets/execution-report-template.md).
- Recommended path: `specs/<issue_id>-<short_title>/execution-report.md` (same folder as the
  Spec Kit artifact path above).
- Populate metadata from the `jira-to-speckit` output: Jira issue key, Jira title, resolved
  Speckit/artifact name, repository.
- Update the report in place after every stage in this run (Jira intake, `specify`, `clarify`,
  `plan`, `checklist`, `tasks`, `analyze`, Stage 03 implement/review loop, Stage 04/05 commit,
  Stage 06 completion): progress, current blocker/issue, cumulative Copilot requests, and
  input/response token estimates. Label token counts as estimates when exact counts are
  unavailable from the active tools.
- Keep the report current until the pipeline ends; do not skip updates because a stage "handed
  back" — a finished stage is not a stop condition (see
  [../shared/global-rules.md](../shared/global-rules.md)).
- Skip this section entirely for manual (non-`--issue`) runs — there is no Jira metadata to track.
