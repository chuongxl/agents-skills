# Provider Adapter: github-speckit

Repo-installed GitHub Spec Kit skills under `.github/skills/speckit-<command>/SKILL.md`, invoked
via the `skill` tool on all hosts. Adds to [../shared/operating-rules.md](../shared/operating-rules.md);
never weakens it.

## Stage Skill Map

| Pipeline step | Skill(s) |
|---------------|----------|
| Stage 01 provider gate | `speckit-constitution` → `.specify/memory/constitution.md` |
| Stage 02 spec/design | `speckit-specify` → `speckit-clarify` → `speckit-plan` → `speckit-checklist` → `speckit-tasks` → `speckit-analyze` (fixed order, never skipped/reordered in either mode) |
| Stage 03 implement | `speckit-implement` (user wording `speckit.implementation` maps here) |
| Stage 03 convergence | `speckit-converge` — run after implement until it reports no gaps |

All artifacts are produced ONLY by these skills. `speckit-auto` never synthesizes spec/plan/tasks
content and never writes implementation code itself.

## Step Completion Protocol (after every `skill speckit-*` call)

1. **Read the return value.** Empty, an error, or a skill-tool failure → treat as failure; do not
   proceed.
2. **Verify the expected artifact on disk** (non-empty, in the worktree):

   | Skill | Expected artifact |
   |-------|------------------|
   | `speckit-constitution` | `.specify/memory/constitution.md` (≥100 words) |
   | `speckit-specify` / `speckit-clarify` | `specs/<feature_folder>/spec.md` (created / updated) |
   | `speckit-plan` | `specs/<feature_folder>/plan.md` |
   | `speckit-checklist` | `specs/<feature_folder>/checklist.md` |
   | `speckit-tasks` | `specs/<feature_folder>/tasks.md` |
   | `speckit-analyze` | `specs/<feature_folder>/analyze.md` or updated tasks |
   | `speckit-implement` | source/test files written in the worktree |
   | `speckit-converge` | return value reports convergence status |

3. **Missing/empty artifact** → the skill did not do its work: retry the same skill once, then
   stop and report the exact return value plus the file-check result.
4. **On pass** → next step immediately, same turn.

Unresolvable skill name → provider validation failure: load
[github-speckit-install.md](github-speckit-install.md).

## Artifacts

`specs/<issue_id>-<short_title>/` (`--issue`) or `specs/<nnn>-<slug>/` (manual); Stage 01 resolves
the exact path. Never fall back to a global or external Speckit variant — the repo-installed
skills are the only valid source.

## Stage 03 Fix Routing

- PHASE 1: `speckit-implement` → `speckit-converge`, repeated until converge reports no gaps.
- R6 fix application: re-invoke `speckit-implement` with a focused correction prompt built from
  the review `fixes[]`. Never direct file edits as a substitute for the skill.
- Classification routing: all `FR-*`/`NFR-*`/`ARCH-*` → `speckit-plan` → `speckit-checklist` →
  `speckit-tasks` → `speckit-analyze`; mixed FR/ARCH + code/test → `speckit-checklist` →
  `speckit-tasks` → `speckit-analyze`; only `SEC-*`/`CODE-*`/`TEST-*` → implement directly.
  After any artifact regeneration, re-run the Stage 02 self-review gate before the next fix
  iteration.

## Install Recovery

Not loaded on a healthy run. On any provider validation failure, load
[github-speckit-install.md](github-speckit-install.md) and follow it.
