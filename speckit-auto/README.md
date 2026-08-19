# Speckit Auto — Spec-Driven Delivery Pipeline

**Version**: 0.2.8
**Author**: Alex Nguyen

## Overview

Speckit Auto runs a complete spec-driven delivery pipeline from a requirement or Jira issue:
intake, spec/design, implementation, an automatic `speckit-code-review` remediation loop until
pass, then human review (default mode) or fully automated (YOLO mode) commit and push.

It is a **provider factory**: the same pipeline runs on either of two pluggable providers,
selected once and fixed for the run:

| Provider | What runs the stages |
|----------|----------------------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents (`/speckit.specify`, `/speckit.plan`, `/speckit.implement`, ...) |
| `superpowers` | The `obra/superpowers` skills library (`brainstorming`, `writing-plans`, `subagent-driven-development`, ...) |

Both providers run the same four shared pipeline stages; only the stage agents/skills, install
layout, and fix-application style differ (provider adapters under `references/providers/`).

The pipeline:

1. **Stage 01 — Preflight + Intake**: linked worktree + feature branch, mandatory startup
   framework recovery gate (checks provider skills/agents and auto-installs on user confirmation
   if missing), project context from
   `docs/guidelines/architecture.md`, Jira intake via `jira-to-speckit` when `--issue` is used.
2. **Stage 02 — Spec / Design**: spec, plan, tasks via the provider's stages, with review
   interviews (default mode) or autonomous self-review (YOLO), a mandatory self-review gate, and a
   spec/plan commit before implementation starts.
3. **Stage 03 — Implement + Code Review Loop** (NO-STOP ZONE): implement → converge/verify → run
   `speckit-code-review` → fix → repeat until `pass`. No human gates in either mode.
4. **Stage 04 — Human Review / Commit / Completion**: default mode asks for human approval before
   committing; YOLO mode auto-commits. Both modes then mark the spec `completed` with a follow-up
   commit.

## Install

Copy the `speckit-auto` folder (with `speckit-code-review` and `jira-to-speckit`) into the host's
skill directory: `~/.agents/skills/` (Copilot), `~/.claude/skills/` (Claude Code), or
`~/.config/opencode/skills/` (OpenCode). The skill is auto-discovered from those locations.

## Usage

```bash
# Requirement pipeline (default mode, human review at the end)
skill speckit-auto "Add two-factor authentication to login form"

# Jira pipeline (requires JIRA_URL/JIRA_USERNAME/JIRA_API_TOKEN in the root .env)
skill speckit-auto --issue https://jira.example.com/browse/PROJ-123

# Fully automated: no human checkpoints
skill speckit-auto --yolo --issue https://jira.example.com/browse/PROJ-456
```

On Copilot/Claude Code invoke as `/speckit-auto <flags>`; on OpenCode embed the flags in the
trigger message.

### Provider setup (one-time)

```bash
skill speckit-auto --integration github-speckit   # or superpowers
```

Writes `.speckit/integration.json` in the repo (or `<skill-dir>/.state/integration.json` with
`--global` / outside a git repo). Without a stored provider, the skill asks once on first run and
persists the answer. Missing framework installations (Spec Kit agents not in the repo, superpowers
skills not installed) are also repaired on request, per provider.

## Project Context

If the repo has `docs/guidelines/architecture.md`, Stage 01 parses it once into an in-memory
project context (repo map, arch pattern, dependency rule, linked guideline files) that every
stage must use for task assignment, naming, and architecture compliance. Guideline files are
lazy-loaded and cached. If `docs/guidelines/` is absent, the pipeline continues with an inferred
repo map.

## Sub-Skill Dependencies

- `jira-to-speckit` — Jira fetch + compaction + ticket snapshot (`--issue` only)
- `speckit-code-review` — authoritative JSON pass/fail gate; the only way Stage 03 exits

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Which provider?" on every run | Run `--integration <provider>` once to persist |
| Jira intake fails | Ensure root `.env` has all three `JIRA_*` keys; test with `jira-to-speckit` directly |
| Stage 03 review loop doesn't converge | Simplify the spec's acceptance criteria; avoid vague language ("elegant", "performant") |
| Missing framework | At startup and any later step, failed provider validation triggers install recovery; if still failing after install, stop and ask the user to restart Copilot / Claude Code / OpenCode, then re-run |

## Notes

- Jira credentials live only in the gitignored root `.env`; never printed, never committed.
- The relocated Jira ticket snapshot (`<artifact_folder>/ticket.md`) is committed with the
  artifacts.
- The Jira execution report (`<artifact_folder>/execution-report.md`, `--issue` runs only)
  tracks stage progress and blockers — no token or cost estimates.