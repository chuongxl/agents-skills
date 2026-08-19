# Integration Setup (`--integration`)

Loaded **only** when `--integration` is present in the invocation. Perform setup only, then END
TURN (the one legitimate no-pipeline turn end in the whole skill). Never enter the pipeline.

## Steps

1. **Normalize** the value: trim, lowercase, map aliases:
   - `github`, `speckit`, `spec-kit`, `github-spec-kit` → `github-speckit`
   - `superpower`, `obra-superpowers` → `superpowers`

   Unsupported value → report the two valid providers (`github-speckit`, `superpowers`) and stop,
   writing nothing. No value → ask the user once, then continue in the same turn.

2. **Persist** `{"integration": "<value>", "updated_at": "<ISO-8601>", "set_by": "speckit-auto"}`
   to `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root from
   `git rev-parse --show-toplevel`). This repo-local file is the **only** provider source — there
   is no global state. If the cwd is not inside a git repo, stop and tell the user to re-run from
   the target repository. Overwrite silently; report the previous value if one existed. Never
   ignore `--global`: if passed, reject it — global state is no longer supported.

3. **Provider install check + setup** (runs immediately after persist):

   a. Check whether the provider's skills are already installed on the **main repo checkout**
      (`<repo-root>`) — do **not** use any worktree for this:
      - **github-speckit:** verify all nine `speckit-<command>/SKILL.md` files exist under
        `<repo-root>/.github/skills/` for `<command>` in `constitution`, `specify`, `clarify`,
        `plan`, `checklist`, `tasks`, `analyze`, `implement`, `converge`.
      - **superpowers:** check the host on-disk skill dirs for the required superpowers skills.

   b. **Already installed** → skip install; go straight to step 4.

   c. **Not installed** → install on a dedicated setup branch (never on the base branch directly,
      never in a worktree):
      1. Resolve base branch priority: `develop → main → master` (local first).
      2. `git checkout <base>` + `git pull origin <base>` (best-effort; failure → log, continue).
      3. `git checkout -b init-speckit-auto-<integration>`
         (e.g. `init-speckit-auto-github-speckit`).
      4. Run the adapter's install commands (load
         [../providers/github-speckit.md](../providers/github-speckit.md) or
         [../providers/superpowers.md](../providers/superpowers.md)):
         - **github-speckit:** install CLI → `specify version` sanity →
           `specify init . --integration <host-key> --integration-options="--skills" --force` →
           verify all nine skill files exist.
         - **superpowers:** run the host's plugin/clone+copy command → verify on-disk skills.
      5. If any install step fails → stop, report the exact error, and tell the user to fix it
         manually before re-running `/speckit-auto --integration <value>`.

4. **Post-setup message** (always shown — whether install ran or was skipped):

   - **github-speckit:**
     > ✅ GitHub Speckit is configured. **Please restart your host session (Copilot / Claude
     > Code / OpenCode) now.** After restarting, run:
     > ```
     > skill speckit-constitution "constitution project to understand the project architecture"
     > ```
     > to initialise the project constitution, then you can run your pipeline command.

   - **superpowers:**
     > ✅ Superpowers is configured. **Please restart your host session (Copilot / Claude Code /
     > OpenCode) now** so the new skills are discovered, then re-run your pipeline command.

5. Report: resolved provider and file path written. **END TURN.**
