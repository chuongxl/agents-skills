# Integration Setup (`--integration`)

Loaded **only** when `--integration` is present in the invocation. Perform setup only, then END
TURN (the one legitimate no-pipeline turn end in the whole skill). Never enter the pipeline.

## Steps

1. **Normalize** the value: trim, lowercase, map aliases:
   - `github`, `speckit`, `spec-kit`, `github-spec-kit` → `github-speckit`
   - `superpower`, `obra-superpowers` → `superpowers`

   Unsupported value → report the two valid providers (`github-speckit`, `superpowers`) and stop,
   writing nothing. No value → ask the user once, then continue in the same turn.

2. **Persist** `{"integration": "<value>", "verification": <bool>, "updated_at": "<ISO-8601>",
   "set_by": "speckit-auto"}` to `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root
   from `git rev-parse --show-toplevel`). This repo-local file is the **only** provider and
   verification-opt-in source — there is no global state. If the cwd is not inside a git repo,
   stop and tell the user to re-run from the target repository. Overwrite silently; report the
   previous value if one existed. Never ignore `--global`: if passed, reject it — global state is
   no longer supported.

   `<bool>` comes from a new question asked right after the provider is normalized, before
   persisting: **"Enable implementation verification for this project?"** (Yes/No), via the host
   ask tool ([host-adaptation.md](host-adaptation.md)). No answer → default `false` and say so;
   never block setup waiting on this answer the way step 1's provider value can.

2a. **If verification = true, generate the project's verification skill now:**
   1. Invoke the `skill` tool with name `create-verification-skill`, in **create mode** (no
      `.cursor/skills/verify-<app>/` exists yet for this repo). It runs its own repo interview
      (surface, run, drive, observe, isolate) directly — no separate analysis step is needed
      first.
   2. It writes `.cursor/skills/verify-<app>/SKILL.md` plus a feature map covering the repo's
      existing top 3-5 features, and proves itself once per its own Step 4.
   3. Commit the generated skill: `git add .cursor/skills/verify-<app>/` then
      `git commit -m "chore(verify-<app>): scaffold project verification skill"` (on whatever
      branch setup mode is running on — setup mode does not create its own dedicated branch
      unless installing a provider framework, per step 3 below).
   4. Any failure in this sub-step (skill unavailable, generation fails, self-proof fails) is
      reported but does **not** abort the rest of setup — the provider is still persisted and
      usable; report `verification: false` was effectively left in place for this run and tell the
      user they can retry by re-running `/speckit-auto --integration <value>` and opt in.

   **If verification = false:** skip this sub-step entirely; nothing is generated.

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
      4. Run the install commands **inline from here** — do NOT load the pipeline install-recovery
         files (`../providers/*-install.md`); those are scoped to a pipeline run and assume a
         worktree and a live Stage 01, neither of which exists in setup mode:
         - **github-speckit:** install the Spec Kit CLI (`uv tool install specify-cli`, or
           `--from git+https://github.com/github/spec-kit.git@vX.Y.Z`; fallbacks `pipx install
           specify-cli` / `pip install specify-cli`) → `specify version` sanity check →
           `specify init . --integration <host-key> --integration-options="--skills" --force` in
           `<repo-root>` only → verify all nine skill files exist.
         - **superpowers:** run the host's plugin/clone+copy command (Copilot:
           `copilot plugin marketplace add obra/superpowers-marketplace` then
           `copilot plugin install superpowers@superpowers-marketplace`; Claude Code: the
           equivalent `/plugin` commands; OpenCode: clone `obra/superpowers` and copy
           `skills/*` into the host skill dir) → verify on-disk skills.

         Never invoke `speckit-constitution` or any other provider skill here — the host session
         has not been restarted yet, so an unresolvable skill in setup mode is expected, not a
         failure. Step 4 below tells the user to restart and run it.
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
     >
     > Verification is **enabled** for this project (a `.cursor/skills/verify-<app>/` skill was
     > generated and committed) — Stage 05 will run it after every implementation. / Verification is
     > **disabled** — Stage 05 will be skipped on every run until you re-run
     > `/speckit-auto --integration <value>` and opt in.

   - **superpowers:**
     > ✅ Superpowers is configured. **Please restart your host session (Copilot / Claude Code /
     > OpenCode) now** so the new skills are discovered, then re-run your pipeline command.
     >
     > Verification is **enabled** for this project (a `.cursor/skills/verify-<app>/` skill was
     > generated and committed) — Stage 05 will run it after every implementation. / Verification is
     > **disabled** — Stage 05 will be skipped on every run until you re-run
     > `/speckit-auto --integration <value>` and opt in.

5. Report: resolved provider, verification opt-in result (enabled/disabled, and the generated
   skill's commit hash if enabled), and file path written. **END TURN.**
