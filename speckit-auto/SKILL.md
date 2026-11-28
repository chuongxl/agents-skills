---
name: speckit-auto
description: |
  Runs an end-to-end spec-driven delivery pipeline from a requirement or Jira issue using a
  pluggable provider: github-speckit (repo-installed GitHub Spec Kit agents) or superpowers
  (obra/superpowers skills library). Handles provider setup and auto-install, Jira intake via
  jira-to-speckit, spec/design, implementation, a speckit-code-review remediation loop until
  pass, human review (default) or YOLO commit and push, optional Stage 05 verification, and a
  Stage 06 that completes the spec and opens a draft pull request behind its own approval gate
  (default mode) or authorized by --yolo. Use when a feature must go from requirement to
  committed, PR-ready implementation in one run, or to push a fix to an existing open PR
  (--pr-fix).
compatibility: "Runs on GitHub Copilot, Claude Code, OpenCode, and Hermes Agent. Discovered from ~/.agents/skills/, ~/.claude/skills/, ~/.config/opencode/skills/, or ~/.hermes/skills/ (/opt/data/skills/ in Docker). Requires git, bash, and Node.js >=22.13; network access for Jira intake via --issue. Default mode also needs the host's ask/question tool (Copilot ask_user, Claude AskUser, OpenCode question; Hermes uses a plain chat message) for the Stage 02, 04, 05 and 06 checkpoints; see references/shared/host-adaptation.md."
license: MIT
allowed-tools: bash glob grep view create edit skill ask_user
metadata:
  author: Alex Nguyen
  version: "0.10.0"
---

# Speckit Auto

Entry point only: parse the invocation, resolve the provider, then run the stages.

**Progressive loading is a hard rule.** Load a reference file at the moment its step runs, never
ahead of time. Never load a stage you are not in, a provider you did not resolve, an install-
recovery file on a healthy run, or a file already in context. See the loading map below.

**Event initialization is a hard gate.** After the Stage 01 worktree gate, initialize run
events and confirm the tool call succeeded before provider validation, implementation edits,
tests, commits, pushes, or loading Stage 02 or later. Stage 01 may make only the setup changes
needed for that gate. Failure handling (including YOLO and Stage 03) is in
`references/shared/run-events.md`.

## Entry Dispatch (every invocation)

1. **Parse the invocation text** (slash-command body on Copilot/Claude Code; the natural-language
   trigger message on OpenCode and Hermes Agent — flags may be embedded anywhere):
   - `--integration <value>` → setup intent (setup ONLY, no pipeline)
   - `--issue <url>` → Jira pipeline intent
   - `--pr-fix <absolute GitHub PR URL>` → existing-PR fix intent. Require a non-empty fix
     request as well; reject missing/invalid values and combinations with `--issue` or
     `--integration` before changing anything. Treat the PR URL as identity, not requirement text.
     A worktree and branch come from `--worktree`/`--branch` or, for older callers, from the
     invocation text naming them; capture them as structured run state. If none is supplied,
     use the manual creation path.
   - `--worktree <path> --branch <name>` → optional caller-chosen worktree and branch for any
     pipeline intent. Accept only as a pair. A relative path resolves against the primary
     checkout; the resolved path must sit directly under `<repo-root>/.worktrees/`, and the
     branch must pass `git check-ref-format --branch`. Reject anything else as an invocation
     error before changing anything. Retain both across resumes; never replace them mid-run.
     Stage 01 reuses that worktree when it exists and creates it when it does not.
   - `--yolo` → mode = yolo (else default)
   - `--run-id <uuid>` / `--run-id=<uuid>` → optional attempt identity, not requirement text.
     Missing/invalid UUID → explicit invocation error. Preserve it across resumes; never
     replace it mid-run. Without it, generate once with Node's `crypto.randomUUID()`.
     A fresh retry after a terminal run needs a new UUID, even in a reused worktree.
   - free text → requirement pipeline intent

2. **Note the host** from the directory this file was loaded from: `~/.copilot/skills/`,
   `.github/skills/`, `~/.agents/skills/` → Copilot; `~/.claude/skills/` → Claude Code;
   `~/.config/opencode/skills/`, `.opencode/skills/` → OpenCode; `~/.hermes/skills/`,
   `/opt/data/skills/` → Hermes Agent. Directories that overlap
   (`.claude/skills/`, `.agents/skills/`) or any other ambiguity → resolve via the tie-break in
   [references/shared/host-adaptation.md](references/shared/host-adaptation.md). The host is fixed
   for the run; look up host-specific values (ask tool, skill dirs, install host key) from that
   same file when a step needs one.

3. **Setup intent** (`--integration` present): load
   [references/shared/integration-setup.md](references/shared/integration-setup.md) and follow it.
   END TURN after — do not enter the pipeline, and do not load any pipeline file.

4. **Pipeline intent**: resolve the provider from **exactly one source** —
   `<repo-root>/.speckit/integration.json` → `integration` field. For `--pr-fix`, before provider
   resolution identify the primary checkout from the current Git repository's worktree list and use
   that checkout as `<repo-root>`, including when the invocation starts in a supplied worktree.
   Record it as `source_repo_path` for Stage 01. No global fallback, no first-run
   prompt. Missing file, unparseable content, or an unsupported value → stop immediately and tell
   the user to run `/speckit-auto --integration github-speckit` (or `superpowers`) first. On
   success, record it as `integration` in run state; never re-read or change it mid-run, and never
   infer the provider from repo contents.

   Before a new pipeline begins, check the runtime, not just `node --version`:
   `node -e 'const [a,b]=process.versions.node.split(".").map(Number); if(a<22||(a===22&&b<13)){console.error("speckit-auto requires Node.js >=22.13");process.exit(1)}'`.
   Missing/old Node → stop explicitly before worktree creation. Setup-only invocations do
   not require event initialization.

5. Load **exactly three files**, then enter Stage 01 in this same turn:
   [references/shared/operating-rules.md](references/shared/operating-rules.md), the adapter for
   the resolved provider, and
   [references/pipeline/stage-01-intake.md](references/pipeline/stage-01-intake.md).

Never return an acknowledgement-only response. If the skill is already loaded mid-run (resume
marker: `<skill-context name="speckit-auto">` on Claude Code, `<available_skills>` on OpenCode,
the skill tool list on Copilot; Hermes Agent sessions never rotate, so the running session itself
is the resume marker), resume from the current stage using available run context and
load only that stage's file — never block asking the user to re-run the skill.

## Loading Map

| File | Load when |
|------|-----------|
| `references/shared/operating-rules.md` | every pipeline run, at entry (the only eager load) |
| `references/providers/<provider>.md` | every pipeline run, at entry — resolved provider only |
| `references/pipeline/stage-01-intake.md` | entering Stage 01 |
| `references/shared/run-events.md` | first event initialization after the worktree gate; retain for later emits |
| `references/pipeline/stage-02-spec-design.md` | entering Stage 02 |
| `references/pipeline/stage-03-implement-review.md` | entering Stage 03 |
| `references/pipeline/stage-04-finish.md` | the applicable spec-based or direct review passes and project checks succeed |
| `references/pipeline/stage-05-verification.md` | Stage 04 implementation commit succeeds (or is skipped as already-clean) |
| `references/pipeline/stage-06-finish.md` | Stage 05 hands off (whether it ran or was skipped) |
| `references/pr-fix/stage-0{1,2,3,6}-*.md` | only for `--pr-fix`, when the current stage directs |
| `references/shared/commit.md` | first commit gate reached (Stage 02 → 03) |
| `references/shared/host-adaptation.md` | a step needs an ask-tool name, skill dir, or install host key |
| `references/shared/integration-setup.md` | `--integration` present (setup runs; no stage file loads) |
| `references/providers/<provider>-install.md` | provider validation fails — never on a healthy run |
| `references/providers/pins.md` | an install flow or `--integration` setup installs a provider — the only source of provider versions |
| `references/pipeline/jira-fallback.md` | `--issue` run and `jira-to-speckit` is unavailable |
| `assets/execution-report-template.md` | `--issue` run, at execution-report init |

Once loaded, a reference file from the table above stays in context for the run — never re-read
it. That rule covers `references/**` pipeline files only. Stage-local context (interviews, failed
review bodies) is dropped when leaving a stage; project **guideline** files are cached in
`loaded_guidelines` and may be dropped from context and re-read on demand later — when you drop
one, also drop its `loaded_guidelines` cache entry so a later stage knows to re-read it.

## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, the Stage 04 implementation approval,
  (when verification is enabled) the Stage 05 verification confirmation, and the Stage 06
  `pr-publish` gate — no pull request is opened until that gate is approved. For a PR fix,
  this gate authorizes pushing to the existing PR instead.
- **YOLO** (`--yolo`): no human checkpoints; Stage 02 interactions, Stage 04 human review, the
  Stage 05 confirmation, and the Stage 06 `pr-publish` gate are skipped, with an auto-generated
  commit message and a verification result auto-assessed against the spec (a mismatch loops back
  to Stage 03 instead of continuing). YOLO authorizes opening a draft pull
  request on its own.

Stages 04 and 06 run in both modes — Stage 06 (commit verification artifacts, mark spec completed,
push, offer the PR) is never skipped by mode — unless an earlier stage hard-fails and stops the
run (a Stage 05 environment failure retries once, then YOLO continues as `verification: unavailable` and default mode asks; only a `Stop` answer cleans up, emits `run_failed`, and does not reach
Stage 06). Stage 05 itself is conditional on the
`--integration`-time verification opt-in, independent of default/YOLO mode. Stage 03 is a NO-STOP
ZONE in both modes.
For `--pr-fix`, Stage 06 updates only the existing PR head; it does not create a PR or mark an
unrelated spec completed.

## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |
| `create-verification-skill` | Generate/update the project's `.agents/skills/verify-<app>/` verification skill | `skill` tool, name `create-verification-skill`; only invoked when `--integration` setup enabled verification |

All three are provider-independent and used by every provider. `create-verification-skill` is
conditional on the `verification` opt-in persisted at `--integration` setup time
([shared/integration-setup.md](references/shared/integration-setup.md)); the other two run on
every pipeline invocation except a PR fix without a matching spec, which uses direct review.

## Project Coding Rules

`--integration` setup writes a managed block from `assets/coding-rules.md` into the project's root
`AGENTS.md` with `scripts/agents-rules.mjs` (reuse existing libraries, no unapproved dependency).
When that block is present, Stage 01 caches it as `coding_rules`, Stage 02 requires a
`Reuse & dependencies` section in the plan, Stage 03 passes the rules to the implementer, and
`speckit-code-review` blocks on reinvented code and undeclared dependencies. No block → every one
of those steps is skipped silently.

## Required Inputs

- Requirement text, or a Jira issue link via `--issue <jira link>`
- For an existing PR: `--pr-fix <absolute GitHub PR URL>` and a fix request; GitHub CLI access
  and permission to update the PR's actual head repository are required.
- Jira credentials in the project root `.env` (gitignored) when using `--issue`:
  `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — consumed by `jira-to-speckit`; never printed.

## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion (Stage 06), report: resolved provider, `speckit-code-review` final status
(`pass`), verification outcome (`skipped`, `passed` or `unavailable`, plus investigate-loop count if any),
implementation commit status/hash, the verification-artifact commit (if any), the spec completion
commit hash, pushed branches, and per-repo PR outcomes. For a setup invocation (`--integration`),
report: resolved provider, verification opt-in result, coding-rules result, file written, scope, and
the next command.
For a PR fix with no matching spec, report direct-review evidence instead of a spec review status
or spec completion commit, and report the existing PR URL and verified head SHA.

## Portability Note

`allowed-tools` uses Copilot-style tool names; Claude Code and OpenCode expose the same
capabilities under their own names (`Bash`, `Read`, `Edit`, `Write`, `Glob`, `Grep`, `Skill`).
Hermes Agent exposes the same capabilities as `terminal`, `read_file`, `write_file`, `patch`,
`search_files`, `skill_view` (see references/shared/host-adaptation.md).
Never refuse to act because a tool is named differently.
Resolve `scripts/run-events.mjs` and `scripts/agents-rules.mjs` relative to this loaded skill's
folder, not the project cwd.
Structured events use only Node builtins on every host; invoke the emitter with JSON stdin,
never shell-interpolated JSON.
