# github-speckit: Install Recovery

Load this **only** when the Stage 01 Speckit source check failed. A normal run never loads it.

1. Fetch the install guide: `https://github.com/github/spec-kit/blob/main/docs/installation.md`
2. Resolve the host-specific `--integration` key from
   [../shared/host-adaptation.md](../shared/host-adaptation.md): `copilot` (Copilot),
   `claude` (Claude Code), or `opencode` (OpenCode).
3. Ask the user once: `Install GitHub Speckit` or `Stop`.
4. If `Stop`, halt and report that installation is required.
5. If `Install`, follow the guide exactly to install the Spec Kit CLI.
6. Initialize in this repo: `specify init . --integration <host-key>` (for a Copilot repo that
   already uses the commands layout, pass `--integration-options="--commands"`).
7. Run the `speckit.constitution` step via the host's invocation channel:
   - **Copilot**: invoke the repository **agent/slash command** (`/speckit.constitution` or the
     equivalent repo-agent invocation path). Do **not** use the `skill` tool for this step.
   - **Claude Code**: invoke `/speckit.constitution` (or `Skill` tool by resolved name).
   - **OpenCode**: invoke via `skill` tool by resolved name.
8. Re-run the source check.
9. If it passes, continue the pipeline in the same turn.
10. Only if install or init fails, stop and report the exact failing step with quoted error output.

Never fall back to a global or external Speckit variant, and never switch provider — the provider
is fixed for the run (see [../integration-mode.md](../integration-mode.md)).
