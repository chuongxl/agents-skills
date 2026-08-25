# Playwright BDD Automation

**Version**: 0.1.0
**Author**: Alex Nguyen

## Overview

`playwright-bdd-automation` discovers, implements, runs, and reviews automation in repositories that
already use Playwright with `playwright-bdd`. It can consume reviewed `speckit-qa-auto` artifacts or
existing Gherkin requirements, then generate or update repository test-tree files.

The skill is framework-specific but not domain-specific. It replaces project-specific Playwright-BDD
automation playbooks by carrying default conventions for repo profiling, feature materialization, thin
steps, page objects, selectors, fixture data, mocks, execution, and review. Local project docs or
domain skills can still refine business/API details when they are present.

## Inputs

- Reviewed source `.feature` files, often under `docs/qa/<issue>/`.
- Optional `test-design.md` and `run.json` from `speckit-qa-auto`.
- Existing Playwright-BDD repo layout, scripts, fixtures, page objects, mocks, selectors, and local
  project instructions when present.

## Invocation Shape

When invoked by `speckit-qa-auto`, this skill acts only inside the automation capability boundary.
It profiles the Playwright-BDD repo, authors test-tree files, runs the narrow command, and performs
an automation quality check. `speckit-qa-auto` remains responsible for the QA workflow, stage gates,
resume behavior, and finish/report/PR decisions.

## Boundaries

- Does not install or bootstrap Playwright-BDD.
- Does not edit source QA artifacts to make automation pass.
- Does not hardcode domain data when the repository has fixture or builder conventions.
- Does not require `mom-auto-testing` or any other project-specific automation skill.

## References

- [references/repo-profile.md](references/repo-profile.md)
- [references/automation-playbook.md](references/automation-playbook.md)
- [references/runner-notes.md](references/runner-notes.md)
- [references/quality-check.md](references/quality-check.md)
