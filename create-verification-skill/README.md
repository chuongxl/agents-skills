# create-verification-skill: Generate a Project's Verification Skill

## Overview

**create-verification-skill** generates a project-local, self-contained skill
(`.cursor/skills/verify-<app>/`) that launches the real app, drives it the way a user would, and
captures evidence — Launch, Doctor, Drive, Evidence, Cleanup, Helpers, plus a maintained feature
map. It works for any language, framework, or platform: web UI, CLI/TUI, desktop app, API, mobile
app, or library.

It also supports **update mode**: given an already-generated `verify-<app>` skill and one named
feature, it adds or updates just that feature's file in the map, touching the rest of the
generated skill only if that feature genuinely changed Launch/Doctor/Drive/Evidence/Cleanup. This
is how `speckit-auto`'s Stage 05 keeps a project's verification skill current after every
implemented feature, without regenerating it from scratch each time.

## When to Use

- A project has no scripted way to prove UI/CLI/service behavior — use create mode.
- An existing `verify-<app>` skill needs a feature added or updated after a change — use update
  mode, naming the one feature.
- Triggers: "make a control skill for this repo", "/create-verification-skill".

## How It Works

1. **Interview the repo, not the user.** Surface, run command, drive harness, evidence, and
   isolation are all answered by reading the codebase; the user is only asked what can't be
   observed.
2. **Generate (or update) the skill.** Launch/Doctor/Drive/Evidence/Cleanup/Helpers sections, each
   grounded in what the interview found — no placeholders.
3. **Seed (or extend) the feature map.** One file per user-facing feature, answering what it is,
   how to reach it, how to drive it, and what proves it works.
4. **Prove it once.** Launch, doctor, drive one feature, capture evidence, clean up, and confirm
   the evidence survived cleanup — a generated skill that was never executed is a draft, not a
   deliverable.
5. **Offer the maintenance loop** (create mode only) for keeping the map honest as the app changes.

## Compatibility

Runs on GitHub Copilot, Claude Code, and OpenCode. Requires the target project to be
buildable/runnable locally, plus whatever tooling the chosen harness needs (a browser for
CDP-driven web apps, `tmux`/PTY for CLI/TUI, nothing extra for plain HTTP services).

## Installation Paths

- GitHub Copilot: `.github/skills/` or `~/.agents/skills/`
- Claude Code: `~/.claude/skills/`
- OpenCode: `~/.config/opencode/skills/` or `.opencode/skills/`

## References

- [Feature map example](references/feature-map-example/README.md) — the shape every generated
  feature file follows

This skill is self-contained: it has no dependency on any other skill in this repository (it is
consumed by `speckit-auto` as a sibling install dependency, not the other way around) and works
when installed on its own.
