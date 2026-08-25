# Repo Profile

Build a repository profile before writing automation. The goal is to learn how this specific
Playwright-BDD project already works, then fill gaps with this skill's defaults.

## Required Checks

Inspect:

- `package.json` dependencies for `playwright-bdd`, `@playwright/test`, scripts, and package manager;
- Playwright config, BDD config, generated step output paths, test directory, and project names;
- existing `*.feature` files and their tags, folder layout, language, Background usage, and scenario
  naming;
- existing `*.steps.ts` files and their import pattern, fixture source, parameter syntax, and state
  sharing style;
- fixtures, page objects, selector files, API helpers, mocks, builders, and test data loaders;
- local project instructions such as `AGENTS.md`, README testing notes, or domain skills that are
  already injected in the session.

Do not require a project-specific automation skill. If local instructions are absent, continue with
the default conventions in [automation-playbook.md](automation-playbook.md).

## Repo Profile

Record the useful facts before editing:

```json
{
  "framework": "playwright-bdd",
  "package_manager": "npm|pnpm|yarn|unknown",
  "feature_dir": "path or unknown",
  "steps_pattern": "path or unknown",
  "fixture_import": "path or unknown",
  "page_object_pattern": "path or unknown",
  "selector_pattern": "path or unknown",
  "test_data_pattern": "path or unknown",
  "mocking_pattern": "path or unknown",
  "bddgen_command": "command or none",
  "narrow_test_command": "command template or unknown",
  "risks": []
}
```

When working from `speckit-qa-auto`, include this profile in `automation-result.json` or summarize
it in the result's `notes`/`risks` field.

## Stop Or Block

Stop or mark automation as blocked/not-run when:

- `playwright-bdd` is not installed and no existing BDD structure is present;
- the app-under-test, credentials, service endpoints, required test data, or generated fixtures are
  unavailable;
- the reviewed Gherkin needs business changes before it can be automated;
- the repository's commands cannot be identified and there is no safe narrow fallback.

Do not install frameworks, change source QA artifacts, fake generated bindings, or report coverage
for scenarios that were not actually implemented.
