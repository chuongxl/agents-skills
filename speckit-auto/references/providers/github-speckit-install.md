# Install Recovery: github-speckit

Load **only** when the Stage 01 provider gate or a later `skill speckit-*` call fails. A normal
run (provider already installed) must never load this file.

This flow installs the Spec Kit CLI into the **main repo checkout** (base branch), initializes the
skills into both the main checkout and the worktree, verifies the layout, proves executability,
and continues the pipeline in the same turn. It never switches provider and never runs
`specify init` only inside the worktree.

1. **Install the CLI** (source install recommended, PyPI is the fallback):
   - Source (pinned, requires `uv`): read the current release tag `vX.Y.Z` from
     `https://github.com/github/spec-kit` Releases, then
     `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z`.
     No tag resolvable → use `@v0.16.4`.
   - PyPI: `uv tool install specify-cli`, or `pipx install specify-cli`, or
     `pip install specify-cli`.
2. **Sanity check**: `specify version` must print a version. Command not found after a
   successful-looking install → PATH likely missing the tool dir; report the exact output and
   stop. Never proceed with a broken install.
3. **Resolve the host key** (`copilot` / `claude` / `opencode`) from the run's fixed host — see
   [../shared/host-adaptation.md](../shared/host-adaptation.md). Never guess, never ask.
4. **Ask the user once**: `Install GitHub Speckit` / `Stop`. `Stop` → halt and report that
   installation is required. Steps 1–2 may run before or after the ask; step 5 never runs before
   it.
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
