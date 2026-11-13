# Install Recovery: superpowers

Load **only** when the Stage 01 availability check fails or a later superpowers skill cannot be
resolved in-session. A normal run must never load this file.

Run from the Stage 01 linked worktree. This flow installs the superpowers skills for the resolved
host, re-checks availability, and continues the pipeline in the same turn. It never switches
provider (run contract, rule 2).

1. **Ask the user once**: `Install superpowers` / `Stop`. `Stop` → halt and report that
   installation is required.
2. **Run the exact install command for the resolved host** — never improvise another host's path:
   - **GitHub Copilot** — `copilot plugin marketplace add obra/superpowers-marketplace`, then
     `copilot plugin install superpowers@superpowers-marketplace`.
   - **Claude Code** — `/plugin marketplace add obra/superpowers-marketplace`, then
     `/plugin install superpowers@superpowers-marketplace` (fallback: the same two as
     `claude plugin ...` commands).
   - **OpenCode** / **Hermes Agent** — clone the newest release tag (never the default branch)
     into a fresh private temp directory (never a fixed `/tmp` path another local user could
     pre-create), in one shell invocation:
     ```bash
     tag="$(git ls-remote --tags --refs --sort=-v:refname https://github.com/obra/superpowers.git 'v*' | head -n1 | sed 's#.*refs/tags/##')"
     [ -n "$tag" ] || { echo "no superpowers release tag resolvable"; exit 1; }
     src="$(mktemp -d)" && git clone --depth 1 --branch "$tag" https://github.com/obra/superpowers.git "$src"
     mkdir -p <skills dir> && cp -R "$src"/skills/* <skills dir>/ && rm -rf "$src"
     ```
     `<skills dir>` is `~/.config/opencode/skills/` or `.opencode/skills/` on OpenCode, and
     `~/.hermes/skills/` (`/opt/data/skills/` inside the Docker container) on Hermes Agent. Report
     the installed tag. No tag resolvable → stop; do not install an unpinned copy.

   Host-specific command unavailable → stop and report it as a concrete install failure.
3. **Confirm the install landed on disk**: re-run the on-disk probe from the current linked
   worktree — the minimum skill set's `SKILL.md` files must exist at the host paths (for
   project-local installs, verify from the worktree checkout, not another checkout).
4. **Post-install validation (hard gate)**: re-run the full Stage 01 availability check and
   require runtime executability (`using-superpowers` invocable in this session). On pass,
   continue the pipeline in the same turn.
5. **Validation failure (stop, no continuation).** Skills still missing, skill tool cannot invoke
   them, or the host session was not refreshed → do not continue and do not use the file-read
   fallback. **Stop and ask the user to restart the host session, then re-run `speckit-auto`.**

If a later superpowers stage invocation fails because required skills are missing/unresolvable,
re-enter this flow and re-run step 4. If validation still fails, stop with the restart-session
message. Never continue to later pipeline steps while validation remains failed.
