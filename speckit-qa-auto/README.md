# Speckit QA Auto

**Version**: 0.4.0 — unreleased.
**Author**: Alex Nguyen

## Overview

`speckit-qa-auto` runs a complete spec-driven QA test design and BDD automation pipeline: intake, interactive QA brainstorming (with explicit human review & approval gate), framework-neutral BDD test design & deduplication, automated BDD test implementation, and final PR delivery.

It is a **provider factory**: the same QA pipeline runs on either of two pluggable providers, configured via `--integration <github-speckit|superpowers>`:

| Provider | What runs the stages |
|----------|----------------------|
| `github-speckit` | Repo-installed GitHub Spec Kit skills (`speckit-specify`, `speckit-plan`, `speckit-implement`, `speckit-converge`) |
| `superpowers` | The `obra/superpowers` skills library (`brainstorming`, `writing-plans`, `subagent-driven-development`, `test-driven-development`) |

Both providers follow the same 4-stage pipeline architecture.

## Quick Start

### Provider Setup (One-time)
```bash
skill speckit-qa-auto --integration github-speckit   # or superpowers
```

### Running the QA Pipeline
```bash
# Jira QA pipeline
skill speckit-qa-auto --issue MOM-1234

# Request BDD automation & PR creation
skill speckit-qa-auto --issue MOM-1234 --automation --pr
```

## Architecture & Pipeline Stages

1. **Stage 01 — Preflight + Intake:** Worktree setup, project guidelines parsing, Jira intake (`jira-to-speckit`), Xray export (`xray-to-speckit`).
2. **Stage 02 — QA Design & Dedup:** Interactive clarification interview, output summary presentation & explicit human approval gate, `test-design.md` & `.feature` authoring, Gherkin deduplication (`dedup-gherkin.py`), and QA review gate.
3. **Stage 03 — Automation & Verification (NO-STOP ZONE):** Executes BDD test automation (`playwright-bdd-automation`) in the repository using provider skills, diagnoses test failures with official Playwright skills (`playwright-trace`, `playwright-cli`), performs inline verification review, and generates `automation-result.json`.
4. **Stage 04 — Finish & PR:** Validates state with `scripts/validate-run-state.py`, generates final QA execution report, commits changes, and opens a PR.

## Core Invariants

- `specs/qa/<issue>/` is the source of truth for QA design artifacts.
- `run.json` controls resumable state execution.
- Provider selection is stored in `.speckit/integration.json` and fixed per repository.
- Stage 02 brainstorming output summary requires human approval before design drafting begins.
- Stage 03 automation execution is a NO-STOP ZONE.

## Installation

Copy `speckit-qa-auto` along with `jira-to-speckit`, `xray-to-speckit`, `speckit-code-review` into your host skill directory (`~/.agents/skills/`, `~/.claude/skills/`, `~/.config/opencode/skills/`).
