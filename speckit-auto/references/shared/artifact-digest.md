# Shared: Artifact Digest (Prompt Wiring Optimization)

Instead of re-sending the full `spec.md` (3k–15k chars) and `plan.md` (3k–15k chars) to every
`speckit.*` stage invocation, maintain a compact ≤500-token digest. The digest is the
**prompt-wiring shortcut** — it goes into every stage call's input; the full artifacts stay on
disk and are read only when a stage explicitly needs them.

## Digest Format

Write to `<artifact_folder>/artifact-digest.md` after Stage 02 completes (spec + plan finalized).

```markdown
# Artifact Digest — <feature_name>

**Spec path:** specs/<issue_id>-<short_title>/spec.md
**Plan path:** specs/<issue_id>-<short_title>/plan.md
**Tasks path:** specs/<issue_id>-<short_title>/tasks.md
**Status:** in-progress | completed

## Summary (≤150 tokens)
<2–3 sentence business summary of what is being built and why>

## Key Acceptance Criteria (≤100 tokens)
- AC-1: <first critical acceptance criterion>
- AC-2: <second>
- AC-3: <third> (max 5; only the most important)

## Architecture (≤100 tokens)
- Layout: <single-repo|multi-workspace>
- Key paths: <2–3 most important file paths>
- Pattern: <e.g. "NestJS controllers → services → repositories">
- Constraints: <any hard technical constraints from spec/plan>

## Task Summary (≤100 tokens)
- Total tasks: <N>
- Workspaces: <list of workspace names>
- Completed: <M> / <N>
- Current: <description of what is being worked on now>

## Loaded Guidelines (≤50 tokens)
- <guideline-name-1>: <1-line relevance>
- <guideline-name-2>: <1-line relevance>
```

## When to Write

1. **After Stage 02 self-review gate passes** — the digest is built from finalized spec + plan +
   tasks. Write once, update only on major changes.
2. **After Stage 03 code review passes** — update status to "completed", set Completed = N/N.

## When to Use

Every `speckit.*` stage invocation and `speckit-code-review` call receives the digest as part of
its prompt wiring — in place of the full spec.md and plan.md. The digest tells the stage:

- **what** is being built (summary + ACs)
- **where** it lives (paths, layout, workspaces)
- **how far along** it is (task completion, current focus)

Stages that need the full spec (e.g. `speckit.clarify`, `speckit.analyze`) still read the file
directly — the digest is a prompt shortcut, not a replacement for on-disk artifacts.

## Size Budget

Hard cap: **500 tokens** (~2,000 chars). If the digest exceeds this, trim the lowest-priority
sections first (Loaded Guidelines → Task Summary → Architecture → ACs → Summary). The summary
must always be present.
