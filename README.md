# agents-skills

This repository contains the necessary agent skills used to support the development workstream.

It is intended to be a central place to define, organize, and maintain reusable skill instructions that help coding agents perform software engineering tasks consistently and efficiently.

## Purpose

- Provide essential, reusable skills for day-to-day development activities.
- Standardize how agents approach coding, debugging, refactoring, testing, and documentation.
- Reduce repeated prompt engineering by capturing proven workflows as versioned skill assets.
- Improve delivery quality by making agent behavior more predictable across projects.

## What This Repository Is For

- Building and curating skill definitions for engineering workflows.
- Supporting implementation tasks such as feature development and bug fixing.
- Supporting quality workflows such as review, testing, and validation.
- Supporting knowledge workflows such as architecture exploration and documentation generation.

## Typical Development Workstream Coverage

- Codebase exploration and architecture understanding.
- Debugging and root cause analysis.
- Safe refactoring and impact analysis.
- Pull request review guidance.
- Documentation and onboarding content generation.

## Why It Matters

By keeping necessary agent skills in one repository, teams can:

- Reuse high-quality development patterns.
- Onboard contributors faster.
- Evolve agent capabilities with clear version history.
- Align development practices across multiple repositories and teams.

## Install Skills Locally

Copy the skill folder you need from this repository's `skills/` directory into one of the following locations:

- GitHub Copilot skill location: `.github/skills/` (inside your target repository)
- Claude skill location: `~/.claude/skills/`

Example:

```bash
# From the root of this repository
cp -R skills/<skill-name> /path/to/your-target-repo/.github/skills/

# Or install for Claude local usage
cp -R skills/<skill-name> ~/.claude/skills/
```

After copying, restart your IDE/agent session so the new skill is discovered.

## Skills Summary

| Skill | Description | Guide |
|-------|-------------|-------|
| `job-security-scan` | Comprehensive multi-tool security scanning workflow for development repositories. | [job-security-scan.md](job-security-scan.md) |

## Contributing

When adding or updating skills, aim for:

- Clear scope and trigger conditions.
- Practical, testable instructions.
- Minimal ambiguity in expected outcomes.
- Backward-compatible changes when possible.