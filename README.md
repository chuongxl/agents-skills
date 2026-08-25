# agents-skills

A collection of reusable, production-grade skills for software engineering workflows. These skills provide consistent, efficient task execution across development, testing, security, and documentation workflows.

## Purpose

This repository contains skill definitions for common engineering tasks:
- **Security scanning** — comprehensive vulnerability and secret detection
- **Spec-driven delivery** — end-to-end pipeline from requirements to implementation
- **Code review** — deep line-by-line review against specifications
- **Jira integration** — fetch and convert Jira tickets to Speckit-ready specs

Each skill is designed to work across multiple platforms and coding agents.

## Quick Install

Copy the skill folder you need into your agent's skill location:

| Platform | Location | Example |
|----------|----------|---------|
| GitHub Copilot | `.github/skills/` (in your repo) | `cp -r job-security-scan .github/skills/` |
| Claude Local | `~/.claude/skills/` | `cp -r job-security-scan ~/.claude/skills/` |
| Local | `~/.agents/skills/` | `cp -r job-security-scan ~/.agents/skills/` |

After copying, restart your IDE or agent session to discover the skill.

Full instructions, dependency graph, prerequisites, and troubleshooting:
**[docs/INSTALL.md](docs/INSTALL.md)**.

## Skills Overview

### Security & Compliance
- **job-security-scan** — Scan repositories for vulnerabilities, secrets, and misconfigurations using industry-standard tools (Gitleaks, Trivy, Semgrep, Hadolint, OSV-Scanner, TruffleHog)

### Spec-Driven Delivery
- **speckit-auto** — End-to-end delivery pipeline from requirements to implementation with automatic code review
- **speckit-code-review** — Deep code review comparing implementation against specifications
- **jira-to-speckit** — Convert Jira tickets into Speckit-ready feature specifications
- **xray-to-speckit** — Export the Xray tests that already cover a story, steps verbatim
- **playwright-bdd-automation** — Implement and review Playwright-BDD automation from reviewed QA artifacts

## Comprehensive Skills Table

| Skill | Description | Install Path | Compatibility | Triggers | Status |
|-------|-------------|---------------|----------------|----------|--------|
| [job-security-scan](./job-security-scan/README.md) | Comprehensive multi-tool security scanner. Combines Gitleaks, Trivy, Semgrep, Hadolint, OSV-Scanner, TruffleHog. Produces structured HTML reports with severity filtering and VS Code deep-links. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "scan for vulnerabilities", "check for secrets", "security pipeline" | v2.0 / one-om-ddm-team |
| [speckit-auto](./speckit-auto/README.md) | End-to-end spec-driven delivery orchestrator. Runs intake, spec creation, design, implementation, code review loop, and commit—all in one turn. Supports `--yolo` mode for zero-human automation. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Requirement text, `--issue <jira-url>`, `--yolo`, `--integration` | v0.2.8 / Alex Nguyen |
| [speckit-code-review](./speckit-code-review/README.md) | Spec-to-code validation gate. Extracts requirements from specification and validates implementation against each requirement. Produces JSON with coverage %, business gaps, security issues, architecture issues, and unit test coverage. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "speckit code review", "review with spec", "spec coverage audit" | v0.0.2 / Alex Nguyen |
| [jira-to-speckit](./jira-to-speckit/README.md) | Jira-to-spec reader. Fetches a Jira issue, compacts it into a size-bounded Speckit-ready brief, and optionally writes a full-fidelity ticket snapshot for traceability. Does not read Xray (see `xray-to-speckit`) and does not run Speckit stages itself. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Jira key (e.g., `DDM-1234`), Jira URL, `--issue <url>` | v0.6.0 / Alex Nguyen |
| [xray-to-speckit](./xray-to-speckit/README.md) | Xray coverage reader. Discovers the Xray tests covering a story with one fixed JQL query, splits them by test type, and writes Cucumber tests as a concatenated `.feature` plus a Manual/Generic table carrying each test's steps verbatim from Xray's GraphQL API, each reported with its `description` so a caller can triage before reading steps. Read-only: no import, no test execution, no result upload. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Jira story key (e.g., `MOM-1234`), Jira URL, `xray_output_path`, `xray_manual_output_path` | v0.1.0 / Alex Nguyen |
| [speckit-qa-auto](./speckit-qa-auto/README.md) | Framework-neutral Jira-to-tests QA workflow. Resumes from `run.json`, fetches Jira and Xray evidence, requires QA brainstorming before design, requires QA review before automation or finish, writes `docs/qa/<issue>/` artifacts, designs deduped BDD scenarios, and can automate through repository conventions or injected project skills. Core still works without automation. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | `--issue <story\|epic\|test-key>`, `--impact "<flow>[, <flow>]"`, `--related <KEY>[,<KEY>]`, `--design-only`, `--automation`, `--pr` | v0.4.0 / Alex Nguyen |
| [playwright-bdd-automation](./playwright-bdd-automation/README.md) | Playwright-BDD automation extension. Discovers, implements, runs, and reviews automation from reviewed Gherkin or `speckit-qa-auto` artifacts in repositories that already use `playwright-bdd`, with built-in default conventions that do not require a project-specific automation skill. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Playwright-BDD repo, reviewed `.feature`, `automation-result.json`, `speckit-qa-auto --automation` | v0.1.0 / Alex Nguyen |

### Companion configuration

[speckit-companion-extension](./speckit-companion-extension/README.md) is not a
skill — it holds VS Code settings that point the Spec Kit companion extension at
a `superpowers`-based workflow.

## Repository Layout

```
<skill-name>/                    one folder per skill, each with SKILL.md + README.md
docs/INSTALL.md                  installation, dependencies, troubleshooting
SKILL_SPEC.md                    the contract every skill must satisfy
tools/validate_skills.py         the validator that enforces it
tools/test_validate_skills.py    self-tests for the validator
.github/workflows/               CI that runs the validator on every push and PR
```

## Validation

Every skill is machine-checked against [SKILL_SPEC.md](SKILL_SPEC.md):

```bash
python3 tools/validate_skills.py              # all skills
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/validate_skills.py --json       # machine-readable
python3 tools/test_validate_skills.py         # self-test the validator
```

The validator needs nothing beyond Python 3.9+, and checks that:

- frontmatter parses and carries only the keys the spec allows
- `name` matches the folder name, in lowercase kebab-case
- `description` is 40–1024 characters
- `metadata.author` is present and `metadata.version` is semver-ish
- `README.md` exists in every skill folder
- every relative Markdown link resolves (links inside code blocks are ignored)
- the version in the table above matches each skill's `SKILL.md`

CI runs the same checks on every push and pull request via
[validate-skills](.github/workflows/validate-skills.yml).

## Contributing

When adding or updating skills:

1. **Read [SKILL_SPEC.md](SKILL_SPEC.md)** — it defines the required folder layout and frontmatter
2. **Create a `SKILL.md` file** in the skill directory with the required frontmatter
3. **Create a `README.md` file** alongside SKILL.md with comprehensive documentation (500–1000 words)
4. **Structure your README** with: Overview, Quick Start, Features, Installation, Compatibility, Examples, Configuration, Troubleshooting
5. **Add a row to the skills table above**, with a version matching your `SKILL.md`
6. **Run `python3 tools/validate_skills.py`** and confirm a clean pass before opening a PR
7. **Test the skill** across intended platforms (GitHub Copilot, Claude, local)
8. **Keep SKILL.md as the source of truth** — README expands on it

For new security skills, add test configurations to prevent false positives.
For new spec-delivery skills, ensure compatibility with all supported integration providers.

## License

[MIT](LICENSE)
