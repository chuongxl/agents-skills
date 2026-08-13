# github-speckit: Install Recovery

Load this **only** when the Stage 01 Speckit source check failed. A normal run never loads it.

1. Fetch the install guide: `https://github.com/github/spec-kit/blob/main/docs/installation.md`
2. Ask the user once: `Install GitHub Speckit` or `Stop`.
3. If `Stop`, halt and report that installation is required.
4. If `Install`, follow the guide exactly to install the Spec Kit CLI.
5. Initialize in this repo: `specify init . --integration copilot`
6. Run `/speckit.constitution` as an agent.
7. Re-run the source check.
8. If it passes, continue the pipeline in the same turn.
9. Only if install or init fails, stop and report the exact failing step with quoted error output.

Never fall back to a global or external Speckit variant, and never switch provider — the provider
is fixed for the run (see [../integration-mode.md](../integration-mode.md)).
