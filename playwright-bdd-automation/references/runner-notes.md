# Runner Notes

Generate BDD bindings and run the narrowest useful Playwright command after automation files change.

## Command Selection

Use the repo profile:

1. Confirm the command runs from the Playwright-BDD repository root.
2. Run the BDD generation command first when one exists. Common names are `npm run bddgen`,
   `pnpm bddgen`, `yarn bddgen`, or a repo-specific script.
3. Run the smallest command that proves the changed scenarios:
   - tag filter when source scenarios have stable Jira/suite tags;
   - file path when only one feature file changed;
   - grep when the repo maps scenario titles reliably;
   - project filter such as `--project chromium` when the repo requires it.

If the repo has no known command, infer from `package.json` scripts before falling back to direct
Playwright CLI. Do not invent scripts that are not present.

## Result Classification

Classify each changed scenario:

| Status | Meaning |
|---|---|
| `passed` | BDD generation and scoped Playwright execution passed for the scenario. |
| `failed` | The scenario ran and exposed a product, automation, or assertion failure. |
| `blocked` | Required environment, credentials, data, app state, or source design is missing. |
| `not-run` | The scenario was implemented but intentionally not executed, with a concrete reason. |

Do not convert failures to `passed` because the broad suite has unrelated noise. Keep the scoped
command and failure output in the result artifact.

## Evidence To Record

In `automation-result.json`, record:

- every command run, cwd, exit code, and short outcome;
- generated and changed file paths;
- scenario-level statuses;
- blocked/not-run reasons;
- links or paths to traces, screenshots, videos, Allure output, HTML reports, or logs when present;
- whether source QA artifacts were preserved.

When a command cannot run, still record the command that would have been used if enough information
was discovered.

## Common Defaults

Use these only when they match the repository's package manager and scripts:

```bash
npm run bddgen
npm run test:headed -- --grep "<tag-or-scenario>" --project chromium
```

For non-headed CI-style repos, prefer the repo's existing non-headed command. Avoid running the full
suite unless the changed scenarios cannot be isolated.
