# Speckit Auto — Spec-Driven Delivery Pipeline

**Version**: 0.3.0
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

Both providers run the same six shared pipeline stages; only the stage agents/skills, install
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
4. **Stage 04 — Human Review / Implementation Commit**: default mode asks for human approval
   before committing; YOLO mode auto-commits. Both modes hand off to Stage 05.
5. **Stage 05 — Verification** (conditional): only runs when verification was enabled at
   `--integration` setup time. Updates the project's generated `verify-<app>` skill for the
   just-implemented feature, runs it, and asks for a pass/investigate confirmation before
   continuing. Skipped entirely (with a report line saying so) when verification was not opted
   into.
6. **Stage 06 — Clean / Commit / Push / PR / Complete**: tears down anything Stage 05 launched,
   commits verification artifacts (if any), marks the spec completed, pushes every repo/submodule
   with local commits, and opens a pull request per repo (parent + each submodule) via `gh pr
   create` where the remote is GitHub — non-blocking per repo.

## Install

Copy the `speckit-auto` folder (with `speckit-code-review` and `jira-to-speckit`) into the host's
skill directory: `~/.agents/skills/` (Copilot), `~/.claude/skills/` (Claude Code), or
`~/.config/opencode/skills/` (OpenCode). The skill is auto-discovered from those locations. Also
copy `create-verification-skill` if this repo opts into Stage 05 verification — it's a conditional
dependency, only invoked when verification was enabled at `--integration` setup time.

**Key rule**: Stage 03 is a **NO-STOP ZONE** in both default and YOLO modes; code review loops continue automatically until the spec is satisfied.

<img width="754" height="501" alt="image" src="https://github.com/user-attachments/assets/bc5e90df-0523-4951-a195-3b740d1d38c6" />

<img width="2120" height="3775" alt="spec-driven-development-Speckit-Auto-Skill drawio" src="https://github.com/user-attachments/assets/cbe59272-6c75-4f33-bdf9-ad7d0f6aaa22" />

### Provider System

Speckit Auto resolves a **provider** from a single source: `.speckit/integration.json` in the
repository root, written once by `speckit-auto --integration <provider>`. There is no global/
user-home state and no first-run ask mid-pipeline — a missing or unparseable file stops the run
and tells you to run `--integration` first. The same file's `verification` field (also set at
`--integration` setup time) gates Stage 05.

Supported providers:

| Provider | Location | Use Case |
|----------|----------|----------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents | GitHub Actions + Spec Kit environment |
| `superpowers` | Superpowers skills library (obra/superpowers) | Local, Claude Code, flexible environments |

Each provider includes stage-specific reference files that implement the pipeline logic for that environment.

### YOLO vs Default Mode

**Default Mode** (recommended for critical features):
- Runs Stages 01–06, with mandatory human checkpoints at Stage 04 and (when verification is
  enabled) Stage 05
- Requires explicit human approval before code is merged, and — if verification is enabled —
  explicit confirmation that verification passed
- Best for production, regulatory, or high-stakes work

**YOLO Mode** (`--yolo` flag):
- Still routes through every stage, but skips the human checkpoints at Stage 04 and (when
  verification is enabled) Stage 05
- Zero human checkpoints; fully automated merge, verification confirmation, and commit/push/PR
- Ideal for internal tools, experiments, or when continuous delivery is the goal
- All code still passes speckit-code-review before merge; if verification is enabled, it still
  runs — YOLO only skips asking a human to confirm the result

**Verification is independent of mode.** It is enabled or disabled once, per repo, at
`--integration` setup time — not per run, and not tied to `--yolo`.

---

## 3. Quick Start

### Installation

#### GitHub Copilot CLI
Speckit Auto is auto-discovered from `~/.agents/skills/` or the repository's `.github/skills/` path, depending on how the skill is installed. No manual setup is required after copying the skill into one of those locations.

#### Claude Code
Install the skill from the Superpowers skills library, or copy the skill directory to `~/.claude/skills/`.

#### Local Usage (Standalone)
Clone the skill and ensure `.env` credentials are configured if using `--issue` with Jira.

### First Use: Default Mode (With Human Review)

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

Writes `.speckit/integration.json` in the repo — the **only** provider source (no global state).
Without it, the pipeline stops and asks you to run the command above. Missing framework
installations (Spec Kit agents not in the repo, superpowers skills not installed) are also
repaired by this setup command, per provider.

## Project Context

If the repo has `docs/guidelines/architecture.md`, Stage 01 parses it once into an in-memory
project context (repo map, arch pattern, dependency rule, linked guideline files) that every
stage must use for task assignment, naming, and architecture compliance. Guideline files are
lazy-loaded and cached. If `docs/guidelines/` is absent, the pipeline continues with an inferred
repo map.

## Sub-Skill Dependencies

- `jira-to-speckit` — Jira fetch + compaction + ticket snapshot (`--issue` only)
- `speckit-code-review` — authoritative JSON pass/fail gate; the only way Stage 03 exits
- `create-verification-skill` — generates/updates the project's `verify-<app>` skill; conditional
  on the `verification` opt-in persisted at `--integration` setup time; not needed if verification
  was never enabled for this repo

## Progressive Loading (context budget)

`SKILL.md` is an entry point, not a manual. Only three reference files are loaded at the start of
a pipeline run — the run contract, the resolved provider adapter, and the Stage 01 file. Every
other file loads at the exact moment its step runs:

| File | Load trigger |
|------|--------------|
| `references/shared/operating-rules.md` | pipeline entry (run contract) |
| `references/providers/<provider>.md` | pipeline entry — resolved provider only |
| `references/pipeline/stage-0N-*.md` | entering that stage |
| `references/shared/commit.md` | first commit gate (Stage 02 → 03) |
| `references/shared/host-adaptation.md` | a step needs an ask tool, skill dir, or install host key |
| `references/shared/integration-setup.md` | `--integration` runs (no stage file loads at all) |
| `references/providers/<provider>-install.md` | provider validation failed — never on a healthy run |
| `references/pipeline/jira-fallback.md` | `jira-to-speckit` unavailable on an `--issue` run |

Rules enforced by the skill: never load the unselected provider, never load a stage you are not
in, never re-read a file already in context, and drop stage-local context (interviews, failed
review bodies, unused guideline files) when leaving a stage.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "Which provider?" on every run | Run `--integration <provider>` once to persist |
| Jira intake fails | Ensure root `.env` has all three `JIRA_*` keys; test with `jira-to-speckit` directly |
| Stage 03 review loop doesn't converge | Simplify the spec's acceptance criteria; avoid vague language ("elegant", "performant") |
| Missing framework | At startup and any later step, failed provider validation triggers install recovery; if still failing after install, stop and ask the user to restart Copilot / Claude Code / OpenCode, then re-run |

## Notes

- Jira credentials live only in the gitignored root `.env`; never printed, never committed.
- Run state (`.superpowers/`) is git-ignored; the relocated Jira ticket snapshot
  (`<artifact_folder>/ticket.md`) is committed with the artifacts.
- The Jira execution report (`<artifact_folder>/execution-report.md`, `--issue` runs only)
  tracks stage progress and blockers — no token or cost estimates.