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

## Skills Overview

### Security & Compliance
- **job-security-scan** — Scan repositories for vulnerabilities, secrets, and misconfigurations using industry-standard tools (Gitleaks, Trivy, Semgrep, Hadolint, OSV-Scanner, TruffleHog)

### Spec-Driven Delivery
- **speckit-auto** — End-to-end delivery pipeline from requirements to implementation with automatic code review
- **speckit-code-review** — Deep code review comparing implementation against specifications
- **jira-to-speckit** — Convert Jira tickets into Speckit-ready feature specifications

## Comprehensive Skills Table

| Skill | Description | Install Path | Compatibility | Triggers | Status |
|-------|-------------|---------------|----------------|----------|--------|
| [job-security-scan](./job-security-scan/README.md) | Comprehensive multi-tool security scanner. Combines Gitleaks, Trivy, Semgrep, Hadolint, OSV-Scanner, TruffleHog. Produces structured HTML reports with severity filtering and VS Code deep-links. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "scan for vulnerabilities", "check for secrets", "security pipeline" | v2.0 / one-om-ddm-team |
| [speckit-auto](./speckit-auto/README.md) | End-to-end spec-driven delivery orchestrator. Runs intake, spec creation, design, implementation, code review loop, and commit—all in one turn. Supports `--yolo` mode for zero-human automation. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Requirement text, `--issue <jira-url>`, `--yolo`, `--integration` | v0.0.2 / Alex Nguyen |
| [speckit-code-review](./speckit-code-review/README.md) | Spec-to-code validation gate. Extracts requirements from specification and validates implementation against each requirement. Produces JSON with coverage %, business gaps, security issues, architecture issues, and unit test coverage. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "speckit code review", "review with spec", "spec coverage audit" | v0.0.2 / Alex Nguyen |
| [jira-to-speckit](./jira-to-speckit/README.md) | Jira-to-spec orchestrator. Fetches Jira issues, compacts content, runs clarification loops for spec/plan/test/tasks phases, then hands off to implementation. Maintains execution reports with token usage and cost estimates. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Jira key (e.g., `DDM-1234`), Jira URL, `--issue <url>` | v0.0.1 / Alex Nguyen |

## Contributing

When adding or updating skills:

1. **Create a `SKILL.md` file** in the skill directory with frontmatter (name, description, compatibility, metadata)
2. **Create a `README.md` file** alongside SKILL.md with comprehensive documentation (500-1000 words)
3. **Structure your README** with: Overview, Quick Start, Features, Installation, Compatibility, Examples, Configuration, Troubleshooting
4. **Test the skill** across intended platforms (GitHub Copilot, Claude, local)
5. **Document all triggers and use cases** for discoverability
6. **Keep SKILL.md as the source of truth** — README expands on it

For new security skills, add test configurations to prevent false positives.
For new spec-delivery skills, ensure compatibility with all supported integration providers.
