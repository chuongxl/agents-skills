# Integration Setup (`--integration`)

Loaded **only** when `--integration` is present in the invocation. Perform setup only, then END
TURN (the one legitimate no-pipeline turn end in the whole skill). Never enter the pipeline.

## Steps

1. **Normalize** the value: trim, lowercase, map aliases:
   - `github`, `speckit`, `spec-kit`, `github-spec-kit` → `github-speckit`
   - `superpower`, `obra-superpowers` → `superpowers`

   Unsupported value → report the two valid providers (`github-speckit`, `superpowers`) and stop,
   writing nothing. No value → ask the user once, then continue in the same turn.
   Optional `--coding-rules <true|false>` overrides the existing flag for this setup run and is
   persisted below; any other
   value → report the valid values and stop, writing nothing.

2. **Persist** `{"integration": "<value>", "verification": <bool>, "verification_yolo": <bool>,
   "commit_ticket": <bool>, "coding_rules": <bool>, "updated_at": "<ISO-8601>", "set_by": "speckit-auto"}` to `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root
   from `git rev-parse --show-toplevel`). This repo-local file is the **only** provider and
   verification-opt-in source — there is no global state. If the cwd is not inside a git repo,
   stop and tell the user to re-run from the target repository. Overwrite silently; report the
   previous value if one existed. Never ignore `--global`: if passed, reject it — global state is
   no longer supported.

   `<bool>` comes from a new question asked right after the provider is normalized, before
   persisting: **"Enable implementation verification for this project?"** (Yes/No), via the host
   ask tool ([host-adaptation.md](host-adaptation.md)). No answer → default `false` and say so;
   never block setup waiting on this answer the way step 1's provider value can.

   `verification_yolo` is `false` unless `verification` is `true` **and** the user answers Yes to a second
   question, asked right after: **"Allow verification to launch the app unattended under `--yolo`? (default: No)"**
   (Stage 05 runs code generated from the ticket on this machine; without this, `--yolo` skips Stage 05). No
   answer → `false`. `commit_ticket` is `true` unless the user already set it to `false` in the existing file — keep
   an existing `false`; it keeps the Jira snapshot (`ticket.md`) out of commits (Stage 01, "Ticket snapshot
   rules"). Preserve both existing values when re-running setup without a new answer.
   `coding_rules` follows the same pattern: `true` unless the existing file already has it `false` — keep
   an existing `false`; it is the project's opt-out from step 3a and is never asked about. An explicit
   `--coding-rules <true|false>` wins over the existing value, so opting back in has a setup path.

2a. **If verification = true, generate the project's verification skill now:**
   1. Invoke the `skill` tool with name `create-verification-skill`, in **create mode** (no
      `.agents/skills/verify-<app>/` exists yet for this repo). It runs its own repo interview
      (surface, run, drive, observe, isolate) directly — no separate analysis step is needed
      first.
   2. It writes `.agents/skills/verify-<app>/SKILL.md` plus a feature map covering the repo's
      existing top 3-5 features, and proves itself once per its own Step 4.
   3. Commit the generated skill: `git add .agents/skills/verify-<app>/` then
      `git commit -m "chore(verify-<app>): scaffold project verification skill"` (on whatever
      branch setup mode is running on — setup mode does not create its own dedicated branch
      unless installing a provider framework, per step 3 below).
   4. Any failure in this sub-step (skill unavailable, generation fails, self-proof fails) is
      reported but does **not** abort the rest of setup — the provider is still persisted and
      usable. On this failure, re-run the same persist logic from step 2 with `verification:
      false` so the JSON never claims a skill exists that wasn't actually generated, and tell the
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
         - **github-speckit:** install the Spec Kit CLI from the official GitHub source at the **pinned
           commit** in [../providers/pins.md](../providers/pins.md) (`uv tool install specify-cli --from
           git+https://github.com/github/spec-kit.git@<pinned-commit>`; never PyPI, never a branch, never a tag
           resolved at run time; `uv` missing → stop and ask the user to install it) → `specify version` must
           print the pinned version → `specify init . --integration <host-key>
           --integration-options="--skills" --force` in `<repo-root>` only → verify all nine skill files exist.
         - **superpowers:** run the host's plugin/clone+copy command (Copilot:
           `copilot plugin marketplace add obra/superpowers-marketplace` then
           `copilot plugin install superpowers@superpowers-marketplace`; Claude Code: the
           equivalent `/plugin` commands — marketplace installs cannot be pinned, say so; OpenCode and Hermes
           Agent: the pinned, commit-verified, non-overwriting clone in
           [../providers/pins.md](../providers/pins.md) "Superpowers clone" — use that snippet, do not
           improvise one) → verify on-disk skills.

         Never invoke `speckit-constitution` or any other provider skill here — the host session
         has not been restarted yet, so an unresolvable skill in setup mode is expected, not a
         failure. Step 4 below tells the user to restart and run it.
      5. If any install step fails → stop, report the exact error, and tell the user to fix it
         manually before re-running `/speckit-auto --integration <value>`.

3a. **Project coding rules (`AGENTS.md`)** — runs after step 3 whether or not an install ran, on
   whatever branch step 3 left checked out, so a provider install that rewrites agent files cannot
   drop the block. Skip entirely when `coding_rules` is `false`.

   1. Record `git -C <repo-root> status --porcelain -- AGENTS.md CLAUDE.md`; any output is a
      pre-existing edit (used in sub-step 4).
   2. Run the bundled helper, resolved relative to this skill's folder and passed as an argument
      vector, never interpolated into a shell string:
      `node <skill-dir>/scripts/agents-rules.mjs apply --repo <repo-root>` — add `--claude-import`
      only when the host is Claude Code, which loads `CLAUDE.md` rather than `AGENTS.md`. It
      inserts or refreshes the block from `assets/coding-rules.md` between its
      `speckit-auto:coding-rules` markers, touches nothing outside them, and prints one JSON line
      with `action` = `created` (no `AGENTS.md` existed) | `appended` | `updated` | `unchanged` |
      `newer` (the repo already carries a later block; left alone). It also prints `status`
      (`none` / `valid` / `legacy` / `unsupported` / `newer` / `malformed`), `supported`,
      `rules` (the validated block body) and `preferred_libraries`, plus `claude_md` when asked.
      Text outside the markers is preserved byte for byte, including mixed line endings and
      trailing whitespace. Never write or repair the block by hand.
   3. Generate or validate the team-owned `## Preferred libraries` table with the same helper —
      never author it from memory:
      `node <skill-dir>/scripts/agents-rules.mjs libraries draft --repo <repo-root> --apply`.
      It reads declared dependencies (excluding dev-only dependencies), maps them through a fixed
      catalog of unambiguous concerns, emits at most 12 `Concern | Library` rows, and appends the
      section after the block only when none exists. `action` is `draft` / `added` / `existing` /
      `none`. An existing section belongs to the team and is never edited.
      Then run `node <skill-dir>/scripts/agents-rules.mjs libraries validate --repo <repo-root>`;
      exit 2 with a JSON error means a hand-edited table has a guessed, undeclared or misclassified
      row — report it and leave the table uncommitted.
   4. Commit only what this step wrote. Sub-step 1 found pre-existing edits → leave the files
      uncommitted and say so. Otherwise, when anything changed:
      `git add -- AGENTS.md` (and `CLAUDE.md` when `claude_md` is `created` or `import_added`), then
      `git commit -m "chore(agents): add speckit-auto coding rules" -- <those paths>`. No push.
      `unchanged` / `newer` with no section added → nothing to commit.
   5. Any failure here (Node.js unavailable, helper exit 2 for malformed markers, an invalid `Preferred libraries`
      table, or a non-regular `AGENTS.md`) is reported with the helper's error quoted and does **not** abort setup.

4. **Post-setup message** (always shown — whether install ran or was skipped):

   - **github-speckit:**
     > ✅ GitHub Speckit is configured. **Please restart your host session (Copilot / Claude
     > Code / OpenCode / Hermes Agent) now.** After restarting, run:
     > ```
     > skill speckit-constitution "constitution project to understand the project architecture"
     > ```
     > to initialise the project constitution, then you can run your pipeline command.

     If verification is enabled for this project:
     > A `.agents/skills/verify-<app>/` skill was generated and committed — Stage 05 will run it
     > after every implementation.

     If verification is disabled for this project:
     > Verification is disabled — Stage 05 will be skipped on every run until you re-run
     > `/speckit-auto --integration <value>` and opt in.

   - **superpowers:**
     > ✅ Superpowers is configured. **Please restart your host session (Copilot / Claude Code /
     > OpenCode / Hermes Agent) now** so the new skills are discovered, then re-run your pipeline command.

     If verification is enabled for this project:
     > A `.agents/skills/verify-<app>/` skill was generated and committed — Stage 05 will run it
     > after every implementation.

     If verification is disabled for this project:
     > Verification is disabled — Stage 05 will be skipped on every run until you re-run
     > `/speckit-auto --integration <value>` and opt in.

   - **Both providers**, when step 3a ran:
     > Coding rules: `AGENTS.md` `<action>` (commit `<hash>`, or "left uncommitted"). Pipeline
     > worktrees are cut from the base branch, so merge this commit there before the next run.
     > Review the `## Preferred libraries` table — it is yours to edit.

     When `coding_rules` is `false`:
     > Coding rules are disabled for this project (`"coding_rules": false`). Re-enable with
     > `/speckit-auto --integration <provider> --coding-rules true`.

5. Report: resolved provider, verification opt-in result (enabled/disabled, and the generated
   skill's commit hash if enabled), the coding-rules result (helper `action`, `claude_md` when
   requested, commit hash or the reason nothing was committed), and file path written. **END TURN.**
