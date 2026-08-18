---
name: speckit-auto
description: |
  Runs an end-to-end spec-driven delivery pipeline from a requirement or Jira issue using a
  pluggable provider: github-speckit (repo-installed GitHub Spec Kit agents) or superpowers
  (obra/superpowers skills library). Handles provider setup and auto-install, Jira intake via
  jira-to-speckit, spec/design, implementation, a speckit-code-review remediation loop until
  pass, then human review (default) or YOLO commit and push. Use when a feature must go from
  requirement to committed implementation in one run.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git and bash; network access for Jira intake via --issue."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.3.1"
---

# Speckit Auto

Small entry point: parse the invocation, resolve the provider, then run the shared pipeline
stages. Load only what the current step needs — stage files say at the top which other files they
load.

## Entry Dispatch (Do This First, Every Invocation)

1. Load [references/shared/host-adaptation.md](references/shared/host-adaptation.md) once per
   run; detect the host (Copilot / Claude Code / OpenCode) from the discovery directory + tool
   surface. The host is fixed for the whole run.

2. Parse the invocation text (slash-command body on Copilot/Claude Code; the natural-language
   trigger message on OpenCode — flags may be embedded anywhere):
   - `--integration <value>` → setup intent (provider setup ONLY, no pipeline)
   - `--issue <url>` → Jira pipeline intent
   - `--yolo` → mode = yolo (else default)
   - free text → requirement pipeline intent

3. **Setup intent** (`--integration` present): perform setup only, then END TURN (the one
   legitimate no-pipeline turn end):
   a. Normalize the value: trim, lowercase, map aliases (`github`, `speckit`, `spec-kit`,
      `github-spec-kit` → `github-speckit`; `superpower`, `obra-superpowers` → `superpowers`).
   b. Unsupported value → report the two valid providers and stop, writing nothing. No value →
      ask once, then perform setup in the same turn.
   c. Persist `{"integration": "<value>", "updated_at": "<ISO-8601>", "set_by": "speckit-auto"}`
      to `<repo-root>/.speckit/integration.json` by default (`mkdir -p` first; root from
      `git rev-parse --show-toplevel`); write the global path `<skill-dir>/.state/integration.json`
      instead when `--global` is passed or the cwd is not in a git repo. Overwrite silently;
      report the previous value. Add `.speckit/` to `.gitignore` only if `.gitignore` exists and
      doesn't already ignore it. Never stop over a persistence failure — fall back and report.
   d. Report: resolved provider, file path written, scope, and the next command to run
      (`--issue <jira-url>` or a requirement). Other arguments alongside `--integration` are
      ignored — echo them so the user can re-run.

4. **Pipeline intent** (no `--integration`): resolve the provider once — first match wins:
   a. Repo-local `<repo-root>/.speckit/integration.json` → `integration` field.
   b. Global `<skill-dir>/.state/integration.json` → `integration` field.
   c. Nothing stored → **First-Run Selection**: ask the user once, exactly two choices with no
      recommendation (`github-speckit`, `superpowers`); persist the answer as in 3c (repo-local,
      falling back to global); then continue the pipeline immediately in the same turn — this is a
      required-input ask, never a stop.
   An unparseable or unsupported stored value → warn, ignore, fall through to the next level.
   Record the result as `integration` in run state; never re-read or change it mid-run.
   Never infer the provider from repo contents — a missing framework installation is handled by
   its provider's install recovery, never by switching provider.

5. **Startup Recovery Gate (mandatory, runs at skill start).** Immediately after provider
   resolution, run the Stage 01 framework source check + install recovery flow for the resolved
   provider before any Stage 02/03/04 action:
   - `github-speckit`: if repo `speckit.*` agents are incomplete/missing for the host layout, run
     install recovery to initialize the provider and re-check.
   - `superpowers`: if required provider skills are incomplete/missing, run install recovery and
     re-check.
   This gate is mandatory on every pipeline invocation. A complete provider check continues
   without install; an incomplete check must run recovery now (user may choose `Install` / `Stop`
   per the provider adapter).

6. Load [references/shared/operating-rules.md](references/shared/operating-rules.md), the
   provider adapter [references/providers/github-speckit.md](references/providers/github-speckit.md)
   or [references/providers/superpowers.md](references/providers/superpowers.md) for the resolved
   provider, then enter Stage 01 **immediately, in this same turn**.

Never return an acknowledgement-only response. If the skill is already loaded mid-run (resume
marker: `<skill-context name="speckit-auto">` on Claude Code, `<available_skills>` on OpenCode,
the skill tool list on Copilot), resume from the current stage using available run context — never
block asking the user to re-run the skill.

## Stage Router (Load On Demand)

Load only the stage file for the current stage; never load a file from the provider that was not
selected.

| Stage | File |
|-------|------|
| 01 — Preflight + Intake | [references/pipeline/stage-01-intake.md](references/pipeline/stage-01-intake.md) |
| 02 — Spec / Design | [references/pipeline/stage-02-spec-design.md](references/pipeline/stage-02-spec-design.md) |
| 03 — Implement + Code Review Loop | [references/pipeline/stage-03-implement-review.md](references/pipeline/stage-03-implement-review.md) |
| 04 — Human Review / Commit / Completion | [references/pipeline/stage-04-finish.md](references/pipeline/stage-04-finish.md) |
| Provider adapter | `references/providers/<provider>.md` |
| Shared operating rules | [references/shared/operating-rules.md](references/shared/operating-rules.md) |
| Host detection / tool names | [references/shared/host-adaptation.md](references/shared/host-adaptation.md) |
| Commit + push procedure | [references/shared/commit.md](references/shared/commit.md) |

Shared references are loaded by both providers; provider-specific behavior (install layout,
stage agents/skills, artifact paths, fix routing) lives in the provider adapter and is the ONLY
provider-specific file a stage reads. There is no per-provider pipeline tree — both providers run
the same four stage files.

## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, and Stage 04.
- **YOLO** (`--yolo`): no human checkpoints; all Stage 02 interactions and Stage 04 human review
  are skipped, with an auto-generated commit message.

Stage 03 is a NO-STOP ZONE in both modes (operating rule 7).

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |

Both are provider-independent and used by every provider.

## Portability Note

`allowed-tools` uses Copilot-style tool names; Claude Code and OpenCode expose the same
capabilities under their own names (`Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `skill`).
Never refuse to act because a tool is named differently — see host-adaptation.md.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- Jira credentials in the project root `.env` (gitignored) when using `--issue`:
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — consumed by `jira-to-speckit`; never printed.

## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion, report: resolved provider, `speckit-code-review` final status (`pass`),
implementation commit status/hash, and the spec completion commit hash. For a setup invocation
(`--integration`), report: resolved provider, file written, scope, and the next command.