---
name: speckit-qa-auto
description: |
  Runs an end-to-end QA test design and automation pipeline from a Jira issue or requirement using a
  pluggable provider: github-speckit (repo-installed GitHub Spec Kit agents) or superpowers
  (obra/superpowers skills library). Handles provider setup, interactive QA brainstorming, reviewed
  deduped BDD scenarios, resumable run state, BDD automation, and PR generation.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, Python 3, Jira credentials, and optional Xray credentials."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.4.0"
---

# Speckit QA Auto

Spec-driven QA test design and BDD automation pipeline with pluggable provider support (`github-speckit` and `superpowers`).

## Entry Dispatch (Do This First, Every Invocation)

1. Load [references/shared/host-adaptation.md](references/shared/host-adaptation.md) once per run to detect host (Copilot / Claude Code / OpenCode).
2. Parse invocation text:
   - `--integration <value>` → setup intent (provider setup ONLY, no pipeline)
   - `--issue <url>` → Jira QA pipeline intent
   - `--automation` → request automation execution
   - `--pr` → request PR creation
3. **Setup intent** (`--integration` present): load [references/shared/integration-setup.md](references/shared/integration-setup.md) and execute setup. END TURN after.
4. **Pipeline intent** (no `--integration`): resolve provider from `<repo-root>/.speckit/integration.json` (`integration` field). Missing file → stop and direct user to `/speckit-qa-auto --integration <github-speckit|superpowers>`.
5. Load [references/shared/operating-rules.md](references/shared/operating-rules.md), provider adapter (`references/providers/github-speckit.md` or `references/providers/superpowers.md`), and enter pipeline.

## Pipeline Router

Load only the reference needed for the active stage:

| Stage | Reference File | Produces |
|---|---|---|
| Resume | [references/pipeline/resume.md](references/pipeline/resume.md) | Resolved stage routing |
| Protocol | [references/pipeline/protocol.md](references/pipeline/protocol.md) | Artifact contract & schema |
| 01 — Preflight + Intake | [references/pipeline/stage-01-intake.md](references/pipeline/stage-01-intake.md) | `ticket.md`, existing test exports, initial `run.json` |
| 02 — QA Design & Dedup | [references/pipeline/stage-02-qa-design.md](references/pipeline/stage-02-qa-design.md) | `test-design.md`, dedup labels, source `.feature` files |
| 03 — Automation & Review | [references/pipeline/stage-03-automation-review.md](references/pipeline/stage-03-automation-review.md) | `automation-result.json` & verified test code |
| 04 — Finish & PR | [references/pipeline/stage-04-finish.md](references/pipeline/stage-04-finish.md) | Final QA report, commit, optional PR |

## On-Demand Capability Modules

Load these module references **only when triggered** by active scenario requirements or execution events:

| Capability | Module File | Trigger Condition |
|---|---|---|
| Failure & Flaky Diagnosis | [references/modules/flaky-diagnosis.md](references/modules/flaky-diagnosis.md) | Stage 03 test failure during verification |
| Accessibility (A11y) | [references/modules/a11y-testing.md](references/modules/a11y-testing.md) | Accessibility scanning scenarios |
| Visual Regression | [references/modules/visual-regression.md](references/modules/visual-regression.md) | Screenshot comparison scenarios |
| Dynamic Test Data | [references/modules/test-data-factory.md](references/modules/test-data-factory.md) | Generating isolated step fixture data |
| API Contract Validation | [references/modules/api-contract-testing.md](references/modules/api-contract-testing.md) | API response payload contract steps |
| CI Matrix Sharding | [references/modules/ci-matrix-sharding.md](references/modules/ci-matrix-sharding.md) | Stage 04 finish CI workflow setup |

## Core Invariants

- `specs/qa/<issue>/` is the source of truth. Test-tree files are derived automation output.
- `run.json` is the resume authority. Validate it with `scripts/validate-run-state.py`.
- **Stage 02 Brainstorming Gate:** Conduct clarification interview; present full output summary for explicit human approval before drafting design artifacts.
- **Stage 03 NO-STOP ZONE:** Automation implementation and verification loops continue autonomously until verified.
- Provider is resolved from `.speckit/integration.json` and fixed for the run.

## Inputs

- `--issue <jira-url-or-key>` — required for Jira intake.
- `--integration <github-speckit|superpowers>` — configure provider.
- `--automation` — request test code automation.
- `--pr` — prepare/open Pull Request after completion.

## Sub-Skill Dependencies

- `jira-to-speckit` — Jira fetch + ticket snapshot write.
- `xray-to-speckit` — Xray test export (optional).
- `playwright-bdd-automation` — Playwright BDD test generator & runner integration (optional).
- `playwright-cli` / `playwright-trace` — Official Playwright agent skills for live browser verification & trace analysis (optional).
