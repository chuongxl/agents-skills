# Install Recovery: github-speckit

Load **only** when the Stage 01 provider gate or a later `skill speckit-*` call fails. A normal
run (provider already installed) must never load this file.

This flow installs the Spec Kit CLI into the **main repo checkout** (base branch), initializes the
skills into both the main checkout and the worktree, verifies the layout, proves executability,
and continues the pipeline in the same turn. It never switches provider and never runs
`specify init` only inside the worktree.

1. **Ask the user once**: `Install GitHub Speckit` / `Stop`, naming the pinned release from
   [pins.md](pins.md) (`v1.4.0`, commit `0019fa14d12f45edabc2cc3176c9168a68bd0f97`). `Stop` → halt and report that installation is
   required. Nothing below runs before this answer.
2. **Install the CLI** from the official GitHub source **at the pinned commit** — never from PyPI
   (`specify-cli` on PyPI is not published from the Spec Kit repository), never from a branch, and never
   from "the newest tag" resolved at run time:
   `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@0019fa14d12f45edabc2cc3176c9168a68bd0f97`.
   `uv` missing → stop and ask the user to install `uv`; do not fall back to another index.
3. **Sanity check**: `specify version` must print `1.4.0` (the pinned release). Command not found →
   PATH likely missing the tool dir; a different version → report both and stop. Never proceed with a
   broken or unexpected install.
4. **Resolve the host key** (`copilot` / `claude` / `opencode` / `hermes`) from the run's fixed
   host — see [../shared/host-adaptation.md](../shared/host-adaptation.md). Never guess, never ask.
5. **Initialize into BOTH locations (mandatory success gate)** — run in the main checkout
   (`<repo-root>`) and then in `<worktree-path>`:
   ```
   specify init . --integration <host-key> --integration-options="--skills"
   ```
   Both must succeed, installing `speckit-<command>` skills under `.github/skills/` in each
   location. If either fails, stop and quote the exact failing output.
6. **Post-install validation (hard gate)**:
   a. Verify all nine `speckit-<command>/SKILL.md` files exist under
      `<repo-root>/.github/skills/`.
   b. Invoke `speckit-constitution` via the `skill` tool with prompt
      `"constitution project to understand the project architecture"` and confirm it returns
      successfully (inline, same turn).
   c. Either check failing → **stop and ask the user to restart the host session, then re-run
      `speckit-auto`.**
7. **On pass**: continue the pipeline in the same turn.

If a later `skill speckit-<command>` call fails mid-run, re-enter this flow, then re-run step 6.
If validation still fails, stop with the restart-session message. Never continue to later
pipeline steps while validation remains failed.
