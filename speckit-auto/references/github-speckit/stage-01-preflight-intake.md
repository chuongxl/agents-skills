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
abandon the run. Load [install-recovery.md](install-recovery.md) and follow it.

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

## Scratch Path Hygiene (Required, Before Any Implementation)

Load [../shared/scratch-hygiene.md](../shared/scratch-hygiene.md) and apply it. Only `.speckit/`
applies in this provider.

## Artifact Path (Spec Kit Layout)

Using `issue_id` and `short_title` from [../shared/intake.md](../shared/intake.md):

| Mode | Path |
|------|------|
| `--issue` | `specs/<issue_id>-<short_title>/` (example: `specs/ddm-6157-user-login/`) |
| manual | `specs/<nnn>-<requirement-slug>/` following the repo's existing numbering |

The folder must stay stable across reruns of the same issue.

As soon as this path is resolved, apply the branch rename step from
[../shared/branching.md](../shared/branching.md) (`git branch -m` to the same
`<issue_id>-<short_title>`/`<NNN>-<slug>` string) if the checked-out branch is still on its
provisional name.

| Artifact | Path | Written by |
|----------|------|------------|
| Ticket snapshot (`--issue` only) | `specs/<issue_id>-<short_title>/ticket.md` | `jira-to-speckit` (staged), relocated here by this stage |
| Spec / plan / tasks / checklist | `specs/<issue_id>-<short_title>/` | the `speckit.*` stages |
| Execution report (`--issue` only) | `specs/<issue_id>-<short_title>/execution-report.md` | this pipeline |

## Ticket Snapshot Relocation (Required, `--issue` Mode)

Right after the artifact folder is created, **move** `.speckit/intake/<issue_id>-ticket.md` →
`specs/<issue_id>-<short_title>/ticket.md` and record `ticket_path` in run state. Full rules
(rerun overwrite, never gitignore, never commit separately, never read back):
[../shared/intake.md](../shared/intake.md) → "Ticket Snapshot".
Pass only the compact brief into `/speckit.specify`, never the snapshot's contents.

## Stage 02 Entry Step

After intake completes, invoke `/speckit.specify` with the compact brief (or requirement text) in
the same turn, then continue to [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).

## Execution Report (Jira-Sourced Runs)

In `--issue` mode, load [../shared/execution-report.md](../shared/execution-report.md) and
initialize the report at `specs/<issue_id>-<short_title>/execution-report.md`.
