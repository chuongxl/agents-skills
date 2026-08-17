# AGENTS.md

Collection of self-contained, installable skills for coding agents (a folder with `SKILL.md` = one skill), plus validation tooling. No application code, no build/dev server. Skills are installed by copying a folder into an agent's skill directory, so each skill must stay fully self-contained.

## Must pass before commit / PR

```bash
python3 tools/validate_skills.py        # validates every skill against SKILL_SPEC.md (exit 0 required)
python3 tools/test_validate_skills.py   # self-tests for the validator
```

CI (`.github/workflows/validate-skills.yml`) runs both, plus `bash -n` on `*.sh` and `python3 -m compileall -q tools */scripts`. Stdlib-only tooling — never add a third-party dependency to `tools/`.

Local-only (not CI): `python3 tools/test_speckit_auto.py` **executes** the `speckit-auto` skill through a real agent (OpenCode/Claude/Copilot) on the build-a-to-do-app scenario and prints a coverage report. It needs an agent CLI with credentials, so it cannot run in CI.

## Skills

- `speckit-auto` — orchestrator; depends on `jira-to-speckit` + `speckit-code-review` being installed
- `speckit-code-review`, `jira-to-speckit`, `job-security-scan`

Not skills: `tools/`, `docs/`, `test-case/`, `speckit-companion-extension/`. Do not add a `SKILL.md` to `speckit-companion-extension/` — the validator would then treat it as a skill.

## Frontmatter contract (SKILL_SPEC.md, machine-enforced)

- `SKILL.md` must open with `---` YAML frontmatter. Allowed top-level keys only: `name`, `description`, `compatibility`, `metadata`, `license`, `allowed-tools`. Unknown keys fail.
- `name` must equal the folder name (lowercase kebab-case); `description` 40–1024 chars; `metadata.author` required; `metadata.version` must be `MAJOR.MINOR[.PATCH]`.
- The validator ships its own minimal YAML parser (no PyYAML). Keep frontmatter to scalars, quoted scalars, block scalars (`|` / `>`), inline lists, and one level of nested maps. Exotic YAML may silently mis-parse.
- Root `README.md` skills-table badge `vX.Y.Z` must equal `metadata.version` in the matching `SKILL.md` (mismatch = error; unlisted new skill = warning only).

## Links

Every relative markdown link in `SKILL.md`, `README.md`, and `references/**` must resolve and must stay inside its own skill folder (self-containment — a skill is copied out on install). `../` is allowed while still inside the folder. Links in fenced code blocks and inline backticks are ignored. Refer to other skills by name in prose, never by link.

## Gotchas

- `jira-to-speckit` reads Jira credentials from the project root `.env` (gitignored): `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN`. Never print them; stop and ask the user if missing.
- `speckit-code-review` is invoked as a **skill** (its strict JSON verdict must come back in-band), never as a background task agent.
- `speckit-auto` resolves its provider from repo-local `.speckit/integration.json` first, then global `~/.agents/skills/speckit-auto/.state/integration.json`. Provider is fixed for the whole run — never infer it from repo contents.
- Gitignored runtime state/scratch: `speckit-auto/.state/`, `.superpowers/`, `.speckit/`, `.security-scan-results/`.
- Manual test cases for `speckit-auto` live in `test-case/speckit-auto/test-cases.md`; there is no automated test framework for skill behavior.
