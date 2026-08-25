---
name: playwright-bdd-automation
description: |
  Use when implementing, running, or reviewing Playwright-BDD automation from reviewed Gherkin, speckit-qa-auto artifacts, Jira QA scenarios, or existing feature files in a repository that already uses playwright-bdd.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, .github/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires an existing Playwright-BDD repository."
license: MIT
allowed-tools: bash glob grep view create edit
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# Playwright BDD Automation

## Entry Point

Use this skill only when the target repository already uses Playwright with `playwright-bdd`, or
when the user explicitly asks to add automation to such a repository. Do not bootstrap
Playwright-BDD into a project that has no existing Playwright-BDD setup.

The target project does not need a project-specific automation skill. This skill carries the default
Playwright-BDD conventions itself. Project docs, local AGENTS instructions, and domain skills may add
domain context, but they are supporting evidence rather than a prerequisite.

If this skill is used with `speckit-qa-auto`, read that run's artifact contract first:

- `docs/qa/<issue>/run.json`;
- `test-design.md`;
- reviewed source `.feature` files;
- `automation-result.json` if automation is being resumed.

## Reference Notes

Load only the note needed for the current task. These are not pipeline stages; `speckit-qa-auto`
owns orchestration, resume, gates, and finish.

| Need | Read | Purpose |
|---|---|---|
| Understand repo shape | [references/repo-profile.md](references/repo-profile.md) | file targets, command candidates, and blocked gaps |
| Author automation code | [references/automation-playbook.md](references/automation-playbook.md) | Playwright-BDD feature copies, steps, fixtures, page helpers, and result artifact |
| Run generated automation | [references/runner-notes.md](references/runner-notes.md) | command evidence and scenario status |
| Check automation quality | [references/quality-check.md](references/quality-check.md) | pass/change findings for generated or changed automation |

## Core Rules

- Start by building a repo profile. Let the repository's observed Playwright-BDD patterns decide exact paths,
  imports, naming, commands, and helper APIs.
- If the repo is sparse, use this skill's default Playwright-BDD playbook instead of stopping just
  because a project-specific automation skill is absent.
- Preserve source QA artifacts under `docs/qa/<issue>/`; never edit them just to make automation
  pass.
- Materialized test-tree `.feature` files may be copied, split, tagged, or located according to the
  repository's existing Playwright-BDD conventions.
- Keep step definitions thin. Put UI behavior in page objects/helpers and data setup in fixtures,
  builders, API clients, or mocks that match the repository.
- Prefer stable semantic selectors such as `data-testid`, role, label, or accessible text. Avoid
  brittle CSS/XPath unless the existing project requires it and no better selector exists.
- Do not hide product defects with broad waits, excessive retries, over-mocking, or weakened
  assertions.
- Generate BDD bindings before running tests when the repo has a generation step.
- Run the smallest meaningful Playwright command that proves the changed scenarios.
- When automation code is created or changed, complete the automation quality check before reporting
  finish.

## Speckit Handoff

When writing back to a `speckit-qa-auto` run, update `docs/qa/<issue>/automation-result.json` and
the `automation` object in `run.json`:

- `automation.status`: `implemented`, `review-passed`, `blocked`, or `not-run`;
- `automation.tool`: the actual Playwright-BDD command/tool used;
- `automation.skill`: `playwright-bdd-automation`;
- `automation.result`: path to `automation-result.json` when present;
- `automation.review.status`: `pending` until the automation quality check passes.

If reviewed Gherkin must change, stop automation and report `resume_target: design` to the
orchestrator. Do not patch the source scenario inside automation.
