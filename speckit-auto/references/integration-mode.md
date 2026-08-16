# Integration Mode (Provider Resolution)

`speckit-auto` is a **factory**: it selects one delivery provider, then delegates every stage to
that provider's reference files. This file defines how the provider is resolved for a pipeline run.

Setup invocations (`--integration <value>`) are handled entirely by
[integration-setup.md](integration-setup.md) — load that file only when the flag is present.

## Supported Providers

| `integration` value | Provider | Stage references |
|---------------------|----------|------------------|
| `github-speckit` | Repo-installed GitHub Spec Kit agents (layout is host-dependent — see [shared/host-adaptation.md](shared/host-adaptation.md)) | `references/github-speckit/` |
| `superpowers` | `obra/superpowers` skills library (`superpowers:*` skills) | `references/superpowers/` |

No other value is valid.

## Pipeline Invocation (`--integration` absent)

```
/speckit-auto --issue https://example.atlassian.net/browse/ABC-123
/speckit-auto "requirement text"
/speckit-auto --issue <url> --yolo
```

On OpenCode, the same flags are passed embedded in the natural-language message that triggers the
skill (`--issue <url>`, `--yolo`); on Claude Code and Copilot they come in the slash-command body.
Parse the invocation text as described in the SKILL.md Entry Dispatch.

Resolve the provider, then run that provider's pipeline immediately in the same turn. Never end the
turn merely because the provider had to be resolved.

## Resolution Precedence

Take the **first** match:

1. Repo-local `<repo-root>/.speckit/integration.json` → `integration` field.
2. Global `<skill-dir>/.state/integration.json` → `integration` field, where `<skill-dir>` is the
   directory this `SKILL.md` was discovered from (e.g. `~/.agents/skills/speckit-auto/` on Copilot,
   `~/.claude/skills/speckit-auto/` on Claude Code, `~/.config/opencode/skills/speckit-auto/` on
   OpenCode).
3. **Nothing stored anywhere** → run First-Run Selection below.

If a stored file exists but is unparseable or holds an unsupported value, warn, ignore it, and fall
through to the next level.

Once resolved, record it in run state as `integration` and reuse it for every stage of the run.
Never re-read the file mid-run and never switch provider mid-run.

## First-Run Selection (No Stored Mode Anywhere)

Provider detection is driven **solely** by `integration.json`. Never infer the provider from repo
contents (do not probe for `.github/agents/speckit.*`, `.claude/skills/speckit-*`,
`.opencode/skills/speckit-*`, superpowers skill files, or any other artifact) — a missing provider
installation is not a selection signal, it is handled by that provider's Stage 01 preflight, which
auto-installs the missing framework.

When neither the repo-local nor the global file exists:

1. Ask the user **once** to choose, with exactly these two choices and no recommendation:
   - `github-speckit`
   - `superpowers`
2. Persist the answer without loading `integration-setup.md` (that file is setup-only):
   write `{"integration": "<value>", "updated_at": "<ISO-8601>", "set_by": "speckit-auto"}` to
   `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root from
   `git rev-parse --show-toplevel`). If that write fails or the cwd is not inside a git repo, write
   the global path instead and report the fallback — never stop over a persistence failure.
3. **Continue the pipeline immediately in the same turn** with that provider. Do not ask the user
   to re-run the command — this ask is a required-input ask, not a stop condition.
4. Stage 01 preflight of the selected provider then verifies that framework is installed and
   auto-installs it if missing. Provider selection never depends on that outcome.

## Dispatch

After the provider is resolved, load stage files from that provider's directory only, using the
templated Stage Router in [../SKILL.md](../SKILL.md). Provider-agnostic references under
`references/shared/` are loaded by both providers. Never load a stage file from the provider that
was not selected.
