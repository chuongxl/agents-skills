# Stage 01 (github-speckit): Preflight + Intake

Provider: **github-speckit** — repo-installed GitHub Spec Kit agents.

Load with this file:
- [../shared/branching.md](../shared/branching.md) — branch gate (runs first)
- [../shared/intake.md](../shared/intake.md) — issue resolution, run state, Jira intake
- [../shared/preflight-guidelines-context.md](../shared/preflight-guidelines-context.md) — project context

Execution order for this stage:
**branch setup (shared) → Speckit source check → install recovery if missing → runtime executability
check → guidelines load → intake (shared) → artifact path → Stage 02.**

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

## Preflight Runtime Executability Check (Required, After Source Check)

Invoke `/speckit.specify` directly. `stage_invocation_mode` is always `slash-agent` — never attempt
the `task` tool with a `speckit.*` agent_type, it always fails with `Unknown agent_type`.

If it runs, executability is proven. Only a concrete error from that call is reportable as a
runtime failure (quote it), and only after the source check has passed.

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

## Stage 02 Entry Step

After intake completes, invoke `/speckit.specify` with the compact brief (or requirement text) in
the same turn, then continue to [stage-02-spec-design-flow.md](stage-02-spec-design-flow.md).
