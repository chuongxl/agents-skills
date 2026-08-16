# Integration Mode (Provider Resolution)

`speckit-auto` is a factory: it selects one delivery provider and delegates every stage to that
provider's reference files. Setup invocations (`--integration <value>`) are handled entirely by
[integration-setup.md](integration-setup.md) — load that file only when the flag is present.

## Providers

| `integration` | Provider | Stage references |
|---|---|---|
| `github-speckit` | Repo-installed GitHub Spec Kit agents | `references/github-speckit/` |
| `superpowers` | `obra/superpowers` skills library | `references/superpowers/` |

No other value is valid.

## Resolution (first match wins)

1. Repo-local `<repo-root>/.speckit/integration.json` → `integration` field
2. Global `<skill-dir>/.state/integration.json` → `integration` field
3. Nothing stored → First-Run Selection below

A stored file that is unparseable or holds an unsupported value: warn, ignore it, fall through to
the next source. Once resolved, record `integration` in run state — never re-read the file mid-run
and never switch provider mid-run. Load stage files from the selected provider's directory only;
shared references under `references/shared/` are loaded by both providers.

## First-Run Selection (nothing stored anywhere)

Provider detection is driven solely by the two `integration.json` files — never infer the provider
from repo contents. A missing provider installation is not a selection signal; it is handled by
that provider's Stage 01 preflight and its auto-install.

1. Ask the user once, exactly two choices, no recommendation: `github-speckit` or `superpowers`.
2. Persist `{"integration": "<value>", "updated_at": "<ISO-8601>", "set_by": "speckit-auto"}` to
   the repo-local path (`mkdir -p` first; repo root from `git rev-parse --show-toplevel`). If that
   write fails or the cwd is not inside a git repo, write the global path instead and report the
   fallback — never stop over a persistence failure.
3. Continue the pipeline immediately, in the same turn, with that provider. Do not ask the user
   to re-run the command — this ask is a required-input ask, not a stop condition. Stage 01
   preflight of the selected provider then verifies the framework and auto-installs it if missing;
   provider selection never depends on that outcome.
