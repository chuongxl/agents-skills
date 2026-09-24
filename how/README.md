# how: Architecture and Runtime-Flow Explanations

## Overview

**how** answers "how does X work?" questions about a codebase: subsystem architecture, runtime
flow, onboarding mental models, and placement/ownership questions ("where should this live",
"which package owns this", "is this the right layer"). It explores the codebase itself (never
takes the answer on faith from docs) and can optionally critique the architecture it just
explained.

## When to Use

- "How does the rate limiter work?"
- "Walk me through what happens when a user submits a form"
- "Which package owns this logic?" / "Is this the right layer for this code?"
- Before changing a subsystem you don't yet understand
- Add "critique it" / "what's wrong with this design" to switch into Critique Mode after the
  explanation

For "why does X work this way" (design rationale, historical decisions), use a `why`-style skill
instead — `how` explains runtime behavior, not motivation.

## How It Works

1. **Assess complexity.** A narrow question (single module/utility) explores directly in one pass.
   A broad question (a subsystem spanning multiple files/services) is decomposed into 2-4
   independent exploration angles, explored in parallel via the host's subagent-dispatch
   capability, then synthesized into one coherent explanation.
2. **Explain.** Output follows a fixed structure: Overview, Key Concepts, How It Works, Where
   Things Live, Gotchas — adapted to the question, not every section needed every time.
3. **Critique (optional).** When asked for architectural issues, `how` explains first, then
   dispatches independent critics against a shared rubric, and presents a lead-judgment verdict
   (Act on / Consider / Noted / Dismissed) below the explanation.

## Compatibility

Runs on GitHub Copilot, Claude Code, and OpenCode. Uses each host's subagent-dispatch capability
for parallel exploration and critique; on a host without one, falls back to direct single-pass
exploration.

## Installation Paths

- GitHub Copilot: `.github/skills/` or `~/.agents/skills/`
- Claude Code: `~/.claude/skills/`
- OpenCode: `~/.config/opencode/skills/` or `.opencode/skills/`

## References

- [Explorer prompt](references/explorer-prompt.md) — base prompt for parallel exploration angles
- [Explainer prompt](references/explainer-prompt.md) — communication style and output format
- [Critic prompt](references/critic-prompt.md) — architectural critique prompt template
- [Critique rubric](references/critique-rubric.md) — the shared rubric critics are judged against

This skill is self-contained: it has no dependency on any other skill in this repository and
works when installed on its own.
