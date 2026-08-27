# Integration Setup (`--integration`)

Loaded **only** when `--integration` is present in the invocation. Perform setup only, then END
TURN (the one legitimate no-pipeline turn end in the whole skill). Never enter the pipeline.

## Steps

1. **Normalize** the value: trim, lowercase, map aliases:
   - `github`, `speckit`, `spec-kit`, `github-spec-kit` → `github-speckit`
   - `superpower`, `obra-superpowers` → `superpowers`

   Unsupported value → report the two valid providers (`github-speckit`, `superpowers`) and stop,
   writing nothing. No value → ask the user once, then continue in the same turn.

2. **Persist** `{"integration": "<value>", "updated_at": "<ISO-8601>", "set_by": "speckit-qa-auto"}`
   to `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root from
   `git rev-parse --show-toplevel`). This repo-local file is the **only** provider source — there
   is no global state. If the cwd is not inside a git repo, stop and tell the user to re-run from
   the target repository. Overwrite silently; report the previous value if one existed.

3. **Provider install check + setup** (runs immediately after persist):

   a. Check whether the provider's skills are already installed on the **main repo checkout**
      (`<repo-root>`):
      - **github-speckit:** verify skill files exist under `<repo-root>/.github/skills/`.
      - **superpowers:** check the host on-disk skill dirs for required superpowers skills.
      - **Playwright Agent Skills (Optional):** check if `playwright-cli` / `playwright-trace` exist for UI automation; if requested, run `npx playwright init-skills --loop agents`.

   b. **Already installed** → skip install; go straight to step 4.

   c. **Not installed** → install on a dedicated setup branch:
      1. Resolve base branch priority: `develop → main → master` (local first).
      2. `git checkout <base>` + `git pull origin <base>` (best-effort; failure → log, continue).
      3. `git checkout -b init-speckit-qa-auto-<integration>`
      4. Run the adapter's install commands (load provider reference from `references/providers/<provider>.md`).

4. **Post-setup message** (always shown):

   - **github-speckit:**
     > ✅ GitHub Speckit is configured for Speckit QA Auto. **Please restart your host session (Copilot / Claude Code / OpenCode) now.** After restarting, you can run your QA pipeline command.

   - **superpowers:**
     > ✅ Superpowers is configured for Speckit QA Auto. **Please restart your host session (Copilot / Claude Code / OpenCode) now** so the skills are discovered, then re-run your QA pipeline command.

5. Report: resolved provider and file path written. **END TURN.**
