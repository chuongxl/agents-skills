# superpowers: Install Recovery

Load this **only** when the Stage 01 availability check failed. A normal run never loads it.

1. Fetch the install guide: `https://github.com/obra/superpowers`.
2. Ask the user once: `Install superpowers` or `Stop`.
3. If `Stop`, halt and report that installation is required.
4. If `Install`, run both Copilot CLI commands in order:
   `copilot plugin marketplace add obra/superpowers-marketplace`, then
   `copilot plugin install superpowers@superpowers-marketplace`.
   If those commands are unavailable, stop and report it as a concrete install failure — do not
   improvise another harness's install path.

5. Confirm the install landed by re-running availability check 2 (on-disk paths) from Stage 01.
6. Re-run the full availability check. Newly installed skills may not be surfaced in the current
   session's skill list — if so, use the file-read fallback for this run rather than stopping.
7. If it passes, continue the pipeline in the same turn.
8. Only if install fails, stop and report the exact failing step with quoted error output.

Never fall back to the `github-speckit` provider because superpowers is missing — the provider is
fixed for the run (see [../integration-mode.md](../integration-mode.md)).
