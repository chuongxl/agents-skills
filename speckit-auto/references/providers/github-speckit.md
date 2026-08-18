# Provider Adapter: github-speckit

Repository-installed GitHub Spec Kit skills. Loaded by every pipeline stage whose provider is
`github-speckit`. Adds to [../shared/operating-rules.md](../shared/operating-rules.md) and the
host table in [../shared/host-adaptation.md](../shared/host-adaptation.md) — never weakens them.

## Stage Skill Map

`speckit.*` steps are installed as **skills** under `.github/skills/speckit-<command>/SKILL.md`
and invoked via the `skill` tool on all hosts, exactly like any other skill.

`<command>` → skill name mapping: `constitution` → `speckit-constitution`, `specify` →
`speckit-specify`, `clarify` → `speckit-clarify`, `plan` → `speckit-plan`, `checklist` →
`speckit-checklist`, `tasks` → `speckit-tasks`, `analyze` → `speckit-analyze`, `implement` →
`speckit-implement`, `converge` → `speckit-converge`.

| Pipeline step | Skill name | Stage order |
|---------------|------------|-------------|
| Stage 02 spec/design | `speckit-specify` → `speckit-clarify` → `speckit-plan` → `speckit-checklist` → `speckit-tasks` → `speckit-analyze` | Fixed, never skip/reorder/optionalize in either mode |
| Stage 02 design-spec approval | covered by the review interview + Stage 03 entry confirmation | — |
| Stage 03 implement | `speckit-implement` (user wording `speckit.implementation` maps here) | — |
| Stage 03 convergence | `speckit-converge` | run after implement until it reports no gaps |

Constitution: invoke `speckit-constitution` via the `skill` tool when the artifact is missing or
outdated (see Stage 01 Section 3 for the freshness check). It must succeed before Stage 02
(mandatory gate). In install recovery it is also mandatory (always runs). The skill writes its
output to `.specify/memory/constitution.md` in the worktree.

All artifacts (spec/plan/tasks/checklist/implementation) are produced ONLY by these skills.
`speckit-auto` never synthesizes spec/plan/tasks content or writes implementation code itself.

## Install / Layout Per Host

Skills are installed under `.github/skills/speckit-<command>/SKILL.md` on all hosts.

| Host | `specify init` key | Layout to probe | Invocation |
|------|--------------------|-----------------|------------|
| GitHub Copilot | `copilot` | `.github/skills/speckit-<command>/SKILL.md` | `skill` tool, name `speckit-<command>` |
| Claude Code | `claude` | `.github/skills/speckit-<command>/SKILL.md` | `skill` tool (`Skill` tool on Claude Code), name `speckit-<command>` |
| OpenCode | `opencode` | `.github/skills/speckit-<command>/SKILL.md` | `skill` tool, name `speckit-<command>` |

Never fall back to a global or external Speckit variant — the repo-installed skills are the only
valid source.

## Invocation Rules (all stages)

Invoke every `speckit-*` step via the `skill` tool using the skill name from the Stage Skill Map.
This is identical on all three hosts — no agent calls, no slash commands.

```
skill speckit-constitution "constitution project to understand the project architecture"
skill speckit-specify
skill speckit-clarify
...
```

- NEVER use the `task` tool with a `speckit-*` or `speckit.*` name.
- NEVER shell out to a nested `copilot`/`claude`/`opencode` CLI subprocess from bash.
- NEVER emit `@speckit.*` or `/speckit.*` — skills are not invoked that way.
- The `skill` tool is **synchronous** — it blocks until the skill finishes and returns the result
  inline in the same turn. speckit-auto does not continue to the next step until the `skill` call
  returns.

## Step Execution and Completion Protocol (mandatory for every speckit-* call)

After every `skill speckit-<command>` call, before proceeding to the next step:

1. **Read the return value.** If the return value is empty, contains an error, or the skill tool
   itself reports a failure, treat it as a skill failure — do NOT proceed.
2. **Verify the expected artifact on disk.** Each skill writes a specific output file. Check that
   the file exists and is non-empty in the worktree:

   | Skill | Expected artifact |
   |-------|------------------|
   | `speckit-constitution` | `.specify/memory/constitution.md` (non-empty, ≥100 words) |
   | `speckit-specify` | `specs/<feature_folder>/spec.md` |
   | `speckit-clarify` | `specs/<feature_folder>/spec.md` (updated) |
   | `speckit-plan` | `specs/<feature_folder>/plan.md` |
   | `speckit-checklist` | `specs/<feature_folder>/checklist.md` |
   | `speckit-tasks` | `specs/<feature_folder>/tasks.md` |
   | `speckit-analyze` | `specs/<feature_folder>/analyze.md` or updated tasks |
   | `speckit-implement` | source/test files written in the worktree |
   | `speckit-converge` | return value reports convergence status |

3. **On missing or empty artifact:** the skill did not complete its work — treat as failure. Do
   not proceed to the next step. Retry the same skill once; if it fails again, stop and report the
   exact return value and file check result. Ask the user to inspect the skill output or restart
   the host session.
4. **On pass:** proceed to the next step immediately in the same turn.
- If the `skill` tool cannot resolve `speckit-<command>`, treat it as a provider validation
  failure: trigger install recovery, re-validate. If still failing, **stop and ask the user to
  restart the host session (Copilot / Claude Code / OpenCode), then re-run `speckit-auto`.**

## Install Recovery (only when the source check fails)

Run from the Stage 01 linked worktree. A normal run never loads this. This flow installs the Spec
Kit CLI, initializes it into THIS repo for the resolved host as **skills**, verifies the layout,
proves executability, and continues the pipeline in the same turn. It never switches provider.

1. **Install the CLI** (official channels — source install is recommended, PyPI is the fallback):
   - Source (pinned, requires `uv`): fetch the install guide
     `https://github.com/github/spec-kit/blob/main/docs/installation.md`, read the current
     release tag `vX.Y.Z` from the Releases page, then
     `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z`.
   - PyPI (simpler, no tag needed): `uv tool install specify-cli`, or `pipx install specify-cli`,
     or `pip install specify-cli`.
   - if not found release tag : using `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v0.16.4`
2. **Sanity check**: `specify version` must print a version. If the command is not found after a
   successful-looking install, PATH may not include the tool dir — report the exact output and
   stop; do not proceed with a broken install.
3. **Resolve the host key** from host detection (`copilot` / `claude` / `opencode`) — never guess,
   never ask.
4. **Ask the user once**: `Install GitHub Speckit` / `Stop` (the install commands above run only
   after this confirm). `Stop` → halt and report that installation is required. (Steps 1–2 may run
   before or after the ask; the gate below never runs before the ask.)
5. **Initialize into this repo as skills (mandatory success gate)**:
   ```
   specify init . --integration <host-key> --integration-options="--skills"
   ```
   Examples: `specify init . --integration copilot --integration-options="--skills"`
            `specify init . --integration claude --integration-options="--skills"`
            `specify init . --integration opencode --integration-options="--skills"`
   This installs `speckit-<command>` skills under `.github/skills/`. This command must succeed or
   the run stops with the exact failing output quoted.
6. **Post-install validation (hard gate)**:
   a. Re-run the Stage 01 source check: verify all nine `speckit-<command>` skills exist at
      `.github/skills/speckit-<command>/SKILL.md` in the worktree.
   b. Invoke `speckit-constitution` via the `skill` tool with prompt
      `"constitution project to understand the project architecture"` and confirm it returns
      successfully (inline, same turn — no turn boundary, no user ask needed).
   c. If either check fails: **stop and ask the user to restart the host session (Copilot /
      Claude Code / OpenCode), then re-run `speckit-auto`.**
7. **On pass**: continue the pipeline in the same turn.

## Runtime Validation Failure Handling (any step)

If any `skill speckit-<command>` call fails (skill not found, skill tool error), treat it as
provider validation failure: trigger this Install Recovery flow, re-run post-install validation.
If validation still fails, **stop and ask the user to restart the host session (Copilot /
Claude Code / OpenCode), then re-run `speckit-auto`.** Never continue to later pipeline steps
while validation remains failed.

## Artifacts

Spec Kit layout: `specs/<issue_id>-<short_title>/` in `--issue` mode, `specs/<nnn>-<slug>/` in
manual mode (Stage 01 resolves the exact path).

## Stage 03 Fix Routing

- PHASE 1: run `speckit-implement` → `speckit-converge` repeatedly until converge reports no gaps.
- PHASE 2 fix application (R6): re-invoke `speckit-implement` with a focused correction prompt
  built from the review `fixes[]`. Never edit files directly as a substitute for the skill.
- Fix classification routing: all FR-*/NFR-*/ARCH-* → re-run `speckit-plan` then `speckit-checklist`
  then `speckit-tasks` then `speckit-analyze`; mix of FR/ARCH + code/test → `speckit-checklist`
  then `speckit-tasks` then `speckit-analyze`; only SEC-*/CODE-*/TEST-* → implement directly.
  After any artifact regeneration, re-run the Stage 02 self-review gate before the next fix
  iteration.