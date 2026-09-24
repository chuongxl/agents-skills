---
name: speckit-auto
description: |
  Runs an end-to-end spec-driven delivery pipeline from a requirement or Jira issue using a
  pluggable provider: github-speckit (repo-installed GitHub Spec Kit agents) or superpowers
  (obra/superpowers skills library). Handles provider setup and auto-install, Jira intake via
  jira-to-speckit, spec/design, implementation, a speckit-code-review remediation loop until
  pass, human review (default) or YOLO commit, optional Stage 05 verification, and Stage 06
  PR creation. Use when a feature must go from requirement to committed, PR-ready implementation
  in one run.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git and bash; network access for Jira intake via --issue."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.4.0"
---

# Speckit Auto

Entry point only: parse the invocation, resolve the provider, then run the stages.

**Progressive loading is a hard rule.** Load a reference file at the moment its step runs, never
ahead of time. Never load a stage you are not in, a provider you did not resolve, an install-
recovery file on a healthy run, or a file already in context. See the loading map below.

## Entry Dispatch (every invocation)

1. **Parse the invocation text** (slash-command body on Copilot/Claude Code; the natural-language
   trigger message on OpenCode — flags may be embedded anywhere):
   - `--integration <value>` → setup intent (setup ONLY, no pipeline)
   - `--issue <url>` → Jira pipeline intent
   - `--yolo` → mode = yolo (else default)
   - free text → requirement pipeline intent

2. **Note the host** from the directory this file was loaded from: `~/.copilot/skills/`,
   `.github/skills/`, `~/.agents/skills/` → Copilot; `~/.claude/skills/` → Claude Code;
   `~/.config/opencode/skills/`, `.opencode/skills/` → OpenCode. Directories that overlap
   (`.claude/skills/`, `.agents/skills/`) or any other ambiguity → resolve via the tie-break in
   [references/shared/host-adaptation.md](references/shared/host-adaptation.md). The host is fixed
   for the run; look up host-specific values (ask tool, skill dirs, install host key) from that
   same file when a step needs one.

3. **Setup intent** (`--integration` present): load
   [references/shared/integration-setup.md](references/shared/integration-setup.md) and follow it.
   END TURN after — do not enter the pipeline, and do not load any pipeline file.

4. **Pipeline intent**: resolve the provider from **exactly one source** —
   `<repo-root>/.speckit/integration.json` → `integration` field. No global fallback, no first-run
   prompt. Missing file, unparseable content, or an unsupported value → stop immediately and tell
   the user to run `/speckit-auto --integration github-speckit` (or `superpowers`) first. On
   success, record it as `integration` in run state; never re-read or change it mid-run, and never
   infer the provider from repo contents.

5. Load **exactly three files**, then enter Stage 01 in this same turn:
   [references/shared/operating-rules.md](references/shared/operating-rules.md), the adapter for
   the resolved provider, and
   [references/pipeline/stage-01-intake.md](references/pipeline/stage-01-intake.md).

Never return an acknowledgement-only response. If the skill is already loaded mid-run (resume
marker: `<skill-context name="speckit-auto">` on Claude Code, `<available_skills>` on OpenCode,
the skill tool list on Copilot), resume from the current stage using available run context and
load only that stage's file — never block asking the user to re-run the skill.

## Loading Map

| File | Load when |
|------|-----------|
| `references/shared/operating-rules.md` | every pipeline run, at entry (the only eager load) |
| `references/providers/<provider>.md` | every pipeline run, at entry — resolved provider only |
| `references/pipeline/stage-01-intake.md` | entering Stage 01 |
| `references/pipeline/stage-02-spec-design.md` | entering Stage 02 |
| `references/pipeline/stage-03-implement-review.md` | entering Stage 03 |
| `references/pipeline/stage-04-finish.md` | `speckit-code-review` returns `pass` |
| `references/pipeline/stage-05-verification.md` | Stage 04 implementation commit succeeds (or is skipped as already-clean) |
| `references/pipeline/stage-06-finish.md` | Stage 05 hands off (whether it ran or was skipped) |
| `references/shared/commit.md` | first commit gate reached (Stage 02 → 03) |
| `references/shared/host-adaptation.md` | a step needs an ask-tool name, skill dir, or install host key |
| `references/shared/integration-setup.md` | `--integration` present (setup runs; no stage file loads) |
| `references/providers/<provider>-install.md` | provider validation fails — never on a healthy run |
| `references/pipeline/jira-fallback.md` | `--issue` run and `jira-to-speckit` is unavailable |
| `assets/execution-report-template.md` | `--issue` run, at execution-report init |

Once loaded, a reference file from the table above stays in context for the run — never re-read
it. That rule covers `references/**` pipeline files only. Stage-local context (interviews, failed
review bodies) is dropped when leaving a stage; project **guideline** files are cached in
`loaded_guidelines` and may be dropped from context and re-read on demand later — when you drop
one, also drop its `loaded_guidelines` cache entry so a later stage knows to re-read it.

## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, Stage 04's human review, and (when
  verification is enabled) Stage 05's verification confirmation.
- **YOLO** (`--yolo`): no human checkpoints; Stage 02 interactions, Stage 04 human review, and (when
  verification is enabled) Stage 05's confirmation are all skipped, with an auto-generated commit
  message and an auto-approved verification result.

Both Stage 04 and Stage 06 always run in both modes — Stage 06 (commit verification artifacts,
mark spec completed, push, open PRs) is never optional. Stage 05 itself is conditional on the
`--integration`-time verification opt-in, independent of default/YOLO mode. Stage 03 is a NO-STOP
ZONE in both modes.

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |
| `create-verification-skill` | Generate/update the project's `.cursor/skills/verify-<app>/` verification skill | `skill` tool, name `create-verification-skill`; only invoked when `--integration` setup enabled verification |

All three are provider-independent and used by every provider. `create-verification-skill` is
conditional on the `verification` opt-in persisted at `--integration` setup time
([shared/integration-setup.md](references/shared/integration-setup.md)); the other two run on
every pipeline invocation.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- Jira credentials in the project root `.env` (gitignored) when using `--issue`:
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — consumed by `jira-to-speckit`; never printed.

## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion (Stage 06), report: resolved provider, `speckit-code-review` final status
(`pass`), verification outcome (`skipped` or `passed`, plus investigate-loop count if any),
implementation commit status/hash, the verification-artifact commit (if any), the spec completion
commit hash, pushed branches, and per-repo PR outcomes. For a setup invocation (`--integration`),
report: resolved provider, verification opt-in result, file written, scope, and the next command.

## Portability Note

`allowed-tools` uses Copilot-style tool names; Claude Code and OpenCode expose the same
capabilities under their own names (`Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Skill`).
Never refuse to act because a tool is named differently.
