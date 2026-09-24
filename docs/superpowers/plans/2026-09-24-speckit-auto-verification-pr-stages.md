# Speckit Auto: Verification and PR Stages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two new self-contained skills (`how`, `create-verification-skill`) to this repo, and
extend `speckit-auto`'s pipeline from four stages to six: a new Stage 05 (conditional, opt-in
verification of the implemented feature using a generated project-local verification skill) and a
new Stage 06 (clean, commit verification artifacts, mark spec completed, push, and open a PR per
repo/submodule).

**Architecture:** `how` and `create-verification-skill` are cloned from their existing
plugin-marketplace equivalents, trimmed of nothing but reshaped to satisfy this repo's
`SKILL_SPEC.md` frontmatter contract. `create-verification-skill` gains one new capability
(incremental update mode) beyond its source, and becomes a declared sibling install dependency of
`speckit-auto`. The verification opt-in itself lives in `speckit-auto`'s `--integration` setup
flow, persisted as a new `verification` field in `.speckit/integration.json`. Stage 04 is narrowed
to only the human-review/YOLO approval loop plus the implementation commit; "mark spec completed"
and PR creation move out of Stage 04 into the new Stage 06, and PR creation itself switches from a
`superpowers`-only best-effort external-skill call to a provider-agnostic `gh pr create` step run
once per repo (parent + each submodule with commits ahead of its base).

**Tech Stack:** Markdown skill definitions (no application code). Validation is
`tools/validate_skills.py` + `tools/test_validate_skills.py` (stdlib-only Python, already in this
repo, never modified by this plan). Git and `gh` CLI for the runtime behavior these skill files
describe.

**Spec:** [docs/superpowers/specs/2026-09-24-speckit-auto-verification-pr-stages-design.md](../specs/2026-09-24-speckit-auto-verification-pr-stages-design.md)

## Global Constraints

- Every `SKILL.md` frontmatter block may only use these top-level keys: `name`, `description`,
  `compatibility`, `metadata`, `license`, `allowed-tools`. `metadata` must contain `author` and
  `version`; `version` must match `^\d+\.\d+(\.\d+)?$`.
- `description` must be 40–1024 characters and state both what the skill does and when to use it.
- `name` must equal the skill's folder name, lowercase kebab-case.
- Every skill folder needs a `README.md` (required) alongside `SKILL.md`.
- No relative link inside a skill's `SKILL.md`/`README.md`/`references/**.md` may resolve outside
  that skill's own folder — refer to sibling skills by name in prose, never by link.
- The root `README.md` skills-table `vX.Y.Z` badge must exactly equal `metadata.version` in that
  skill's `SKILL.md` — every version bump requires a paired README edit.
- `python3 tools/validate_skills.py` (0 errors) and `python3 tools/test_validate_skills.py` (all
  self-tests passed) must both pass before every commit in this plan.
- This repo has no application code and no automated behavioral test framework for skills (per
  `AGENTS.md`); "tests" for this plan are: the schema validator above, targeted `grep` checks for
  stale/dangling references, and (for the two new skills) `create-verification-skill`'s own
  documented self-proof step, which cannot be executed for real inside this repo (no target app to
  drive) — Task 2 notes this explicitly rather than skipping it silently.
- Base every task's starting point on `main` at the versions currently there (do not assume any
  other open, unmerged branch's version bumps): `speckit-auto` is `0.3.0`.

---

### Task 1: Clone the `how` skill into this repo

**Files:**
- Create: `how/SKILL.md`
- Create: `how/README.md`
- Create: `how/references/explorer-prompt.md` (copy of `/Users/chuongnd/.copilot/skills/how/references/explorer-prompt.md`, unchanged)
- Create: `how/references/explainer-prompt.md` (copy, unchanged)
- Create: `how/references/critic-prompt.md` (copy, unchanged)
- Create: `how/references/critique-rubric.md` (copy, unchanged)
- Modify: `README.md:38` (Skills Overview list) and the Comprehensive Skills Table
- Modify: `AGENTS.md` (Skills section)

**Interfaces:**
- Produces: a standalone, installable `how` skill at repo root, `metadata.version: "0.1.0"`. Not
  invoked by `speckit-auto`'s pipeline (established in the spec's Non-goals / New skills section).

- [ ] **Step 1: Copy the four reference files verbatim**

```bash
mkdir -p how/references
cp /Users/chuongnd/.copilot/skills/how/references/explorer-prompt.md how/references/explorer-prompt.md
cp /Users/chuongnd/.copilot/skills/how/references/explainer-prompt.md how/references/explainer-prompt.md
cp /Users/chuongnd/.copilot/skills/how/references/critic-prompt.md how/references/critic-prompt.md
cp /Users/chuongnd/.copilot/skills/how/references/critique-rubric.md how/references/critique-rubric.md
```

- [ ] **Step 2: Write `how/SKILL.md`**

Copy the body of `/Users/chuongnd/.copilot/skills/how/SKILL.md` (everything after its frontmatter)
unchanged, and replace its frontmatter with one that satisfies this repo's `SKILL_SPEC.md` (the
original has no `compatibility` or `metadata` keys at all, which this repo requires):

```markdown
---
name: how
description: "Use for \"how does X work\", code walkthroughs before changing something, and placement / ownership / layering questions (\"where should this live\", \"which package owns this\", \"is this the right layer\"). Explains subsystem architecture, runtime flow, onboarding mental models. Can critique architecture. Use why for motivation."
compatibility: Runs on GitHub Copilot, Claude Code, and OpenCode. Uses each host's background-agent/subagent-dispatch capability (Copilot/Claude Code `task` tool, OpenCode equivalent) to explore in parallel; falls back to direct exploration in a single pass on hosts without subagent dispatch.
license: MIT
allowed-tools: bash glob grep view task
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# How

Explore the codebase to answer "how does X work?" questions. Produce clear architectural explanations at the level of a senior engineer onboarding onto a subsystem. Enough to build a working mental model, not annotated source code.

Two modes:

1. **Explain** (default). Explore the codebase and produce a clear explanation
2. **Critique.** Explain first, then spawn multiple models to independently identify architectural issues

## Explain Mode

### Step 1. Understand the Question and Assess Complexity

Parse what the user is asking about:

- "How does the rate limiter work?", a subsystem
- "How do we handle billing for on-demand usage?", a feature flow
- "How is the auth service structured?", an architectural overview
- "Walk me through what happens when a user submits a form", a runtime trace

Identify the scope. If ambiguous, state your best-guess interpretation before exploring. Don't ask. Let the user redirect if you're off.

**Assess complexity to decide the approach:**

- **Simple** (a single module, a small utility, a narrow question like "how does function X work"): skip explorer agents; the explainer explores and explains in a single pass. Go to Step 2b.
- **Complex** (a subsystem spanning multiple files/services, a cross-cutting feature, a full architectural overview): spawn parallel explorer agents first, then hand off to the explainer. Go to Step 2a.

When in doubt, lean simple. You can always spawn explorers if the explainer hits a wall.

### Step 2a. Explore (complex questions only)

Decompose the question into 2-4 parallel exploration angles, each a distinct slice of the subsystem so explorers don't duplicate work. Example split for "how does the rate limiter work?":

- Explorer 1: data model and state management
- Explorer 2: request path and enforcement
- Explorer 3: configuration and metrics infrastructure

The right decomposition depends on the question. Use your judgment. Narrow questions: 2 explorers is fine. Broad subsystems: up to 4.

Spawn all explorers in a single message using the host's subagent-dispatch tool (`task` on
Copilot/Claude Code; the OpenCode equivalent), read-only:

- One dispatch per exploration angle, all in the same batch/message.
- Read-only tools only (no edit/write capability granted to the explorer).

Each explorer gets the same base prompt from `references/explorer-prompt.md` plus a specific exploration angle naming its slice. Each explorer should:
- Start broad: Glob for relevant directories, Grep for key types/interfaces/class names
- Follow the thread: from an entry point, trace the call chain (callers, callees, data flow, type definitions)
- Read the actual code, don't guess from file names
- Stop when it can describe the full path from input to output (or trigger to effect) without hand-waving any step
- Note things that are surprising, non-obvious, or that a newcomer would get wrong

Each explorer returns structured findings: components found, flow traced, files read, anything non-obvious. Overlap between explorers is fine; the explainer reconciles.

Then proceed to Step 3.

### Step 2b. Direct Explain (simple questions)

Spawn a single subagent (via `task`, or explore directly yourself if the host has no
subagent-dispatch tool) that explores and explains in one pass, read-only.

The agent does its own exploration (Glob, Grep, Read) and writes the explanation directly. Read `references/explainer-prompt.md` for the communication style and output format. Same structure, just no explorer findings as input.

Proceed to Step 4.

### Step 3. Synthesize (complex questions only)

Once all explorers return, spawn a single subagent to synthesize their findings into one coherent explanation, read-only.

The explainer gets all explorers' findings and writes the human-facing explanation (output format below). Read `references/explainer-prompt.md` for the full prompt template. The explainer reconciles overlapping findings, resolves contradictions, and weaves the slices into a unified picture.

### Step 4. Present

Present the explainer's output to the user. You may lightly edit for clarity or add context from the conversation, but don't substantially rewrite. The explainer's communication is the product.

### Output Format

Follow this structure, adapted to the question. Not every section is needed for every question.

**Overview.** 1-2 paragraphs. What it is, what it does, why it exists. Enough to decide whether to keep reading.

**Key Concepts.** The important types, services, or abstractions. Brief definition of each. Not exhaustive, just the ones needed to understand the rest.

**How It Works.** The core of the explanation. Walk through the flow: what triggers it, what happens step by step, where data goes, the decision points. Prose, not pseudocode. Reference specific files and functions so the reader can go look, but don't dump code blocks unless a snippet is genuinely necessary.

**Where Things Live.** A brief map of the relevant files/directories. Not every file, just the ones needed to start working in this area.

**Gotchas.** Non-obvious or surprising things that would trip someone up. Historical context that explains why something looks weird. Known sharp edges.

## Critique Mode

Triggered when the user asks for architectural issues, problems, or improvements, not just understanding.

### Step 1. Explain First

Run the full explain flow above (Steps 1-4). You must understand the architecture before critiquing it.

### Step 2. Spawn Critics

After the explanation is complete, spawn one architectural critic per configured critic model,
all in a single message, using the host's subagent-dispatch tool, read-only.

For each critic, read `references/critic-prompt.md` for the prompt template. Each critic gets:
1. The explanation from Step 1 (so they don't re-explore)
2. The relevant file paths (so they can read the actual code)
3. The architectural critique rubric from `references/critique-rubric.md`

### Step 3. Lead Judgment

Categorize findings:
- **Act on.** Architectural problems worth fixing now
- **Consider.** Real concerns, but the cost/benefit is unclear
- **Noted.** Valid observations, low priority
- **Dismissed.** Wrong, missing context, or style preference

Present the explanation first (from Step 1), then the critique verdict below it. The explanation should stand on its own; someone who just wants to understand the system shouldn't wade through critique.

## References

- [Explorer prompt](references/explorer-prompt.md)
- [Explainer prompt](references/explainer-prompt.md)
- [Critic prompt](references/critic-prompt.md)
- [Critique rubric](references/critique-rubric.md)
```

Note: the frontmatter and body above deliberately drop the original's hardcoded model names
(`grok-4.6-fast-xhigh`, `claude-fable-5-thinking-max`, etc.) and "spawn a Task subagent with
`subagent_type: generalPurpose`" wording, replacing them with host-agnostic "subagent-dispatch
tool" language, since this repo's skills must work across GitHub Copilot, Claude Code, and
OpenCode (per `SKILL_SPEC.md` compatibility contract) without hardcoding one host's model catalog.

- [ ] **Step 3: Write `how/README.md`**

```markdown
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
```

- [ ] **Step 4: Add `how` to the root README**

In `README.md`, under `## Skills Overview`, add a new subsection (after `### Spec-Driven
Delivery`, before `## Comprehensive Skills Table`):

```markdown
### Architecture & Understanding
- **how** — Explain subsystem architecture and runtime flow; can critique an architecture after explaining it
```

In the Comprehensive Skills Table, add a row (alphabetical position is not enforced elsewhere in
the table, so append after the existing `jira-to-speckit` row):

```markdown
| [how](./how/README.md) | Explains subsystem architecture and runtime flow at onboarding depth; can critique the architecture it just explained. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "how does X work", "walk me through...", "which package owns this" | v0.1.0 / Alex Nguyen |
```

- [ ] **Step 5: Add `how` to `AGENTS.md`**

In the `## Skills` section, change:

```markdown
- `speckit-auto` — orchestrator; depends on `jira-to-speckit` + `speckit-code-review` being installed
- `speckit-code-review`, `jira-to-speckit`, `job-security-scan`
```

to:

```markdown
- `speckit-auto` — orchestrator; depends on `jira-to-speckit` + `speckit-code-review` +
  `create-verification-skill` being installed
- `speckit-code-review`, `jira-to-speckit`, `job-security-scan`
- `how`, `create-verification-skill` — standalone; `create-verification-skill` is also a
  `speckit-auto` install dependency (Stage 05, conditional on the `--integration` verification
  opt-in)
```

- [ ] **Step 6: Validate**

```bash
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
```

Expected: `PASS how` in the validator output; `all self-tests passed` from the self-test script;
0 errors overall.

- [ ] **Step 7: Commit**

```bash
git add how/ README.md AGENTS.md
git commit -m "feat(how): add how skill (architecture/runtime-flow explanations)"
```

---

### Task 2: Clone `create-verification-skill` into this repo, add incremental update mode

**Files:**
- Create: `create-verification-skill/SKILL.md`
- Create: `create-verification-skill/README.md`
- Create: `create-verification-skill/references/feature-map-example/README.md` (copy of
  `/Users/chuongnd/.copilot/skills/create-verification-skill/references/feature-map-example/README.md`)
- Create: any other files under
  `/Users/chuongnd/.copilot/skills/create-verification-skill/references/feature-map-example/`
  (copy verbatim — inspect the source directory first; copy every file it contains)
- Modify: `README.md` (Skills Overview + Comprehensive Skills Table)
- Modify: `AGENTS.md` (already updated in Task 1 Step 5 to mention this skill)

**Interfaces:**
- Produces: a standalone `create-verification-skill`, `metadata.version: "0.1.0"`, with a new
  **update mode** not present in the original, consumed later by Stage 05
  (`speckit-auto/references/pipeline/stage-05-verification.md`, Task 5).

- [ ] **Step 1: Copy the feature-map example directory verbatim**

```bash
mkdir -p create-verification-skill/references
cp -R /Users/chuongnd/.copilot/skills/create-verification-skill/references/feature-map-example \
      create-verification-skill/references/feature-map-example
```

- [ ] **Step 2: Write `create-verification-skill/SKILL.md`**

```markdown
---
name: create-verification-skill
description: Use when a project has no scripted way to prove UI/CLI/service behavior end to end, or when an existing generated verify-<app> skill needs a new or updated feature added to its map. Generates (or incrementally updates) a project-local verification skill (.cursor/skills/verify-<app>/) that launches the real app, drives one feature the way a user would, and captures evidence. Triggers include "make a control skill for this repo" and being invoked by speckit-auto's Stage 05 with an already-generated skill present.
compatibility: Runs on GitHub Copilot, Claude Code, and OpenCode. Requires the target project to be buildable/runnable locally; requires whatever browser/CDP, PTY/tmux, or HTTP tooling the chosen harness needs.
license: MIT
allowed-tools: bash glob grep view create edit
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# Create a verification skill

Every serious project needs a scripted way to drive the real app and prove behavior: launch it, exercise a feature the way a user would, and capture evidence. This skill generates that as a project-local skill (`.cursor/skills/verify-<app>/`) tailored to the repo, or incrementally updates one that already exists. You write the generator's output for the next agent, not for a human: it will be read cold, mid-task, by an agent that has never seen the app.

## 0. Choose create mode or update mode

- **No `.cursor/skills/verify-<app>/` exists yet** (or the caller says so explicitly) → **create
  mode**: run Steps 1-5 below in full.
- **`.cursor/skills/verify-<app>/` already exists** and the caller names one specific feature that
  was just added or changed (this is how `speckit-auto`'s Stage 05 calls this skill, once per
  implemented feature) → **update mode**:
  1. Read the existing `SKILL.md` and `features/README.md`.
  2. Run only the parts of Step 1 (Interview) needed to describe the named feature — do not
     re-interview the whole app's surface/run/drive/observe/isolate story unless the named feature
     genuinely changes one of those (e.g. it adds a new port, a new auth mode, a new harness).
  3. Write or overwrite exactly one file: `features/<feature-slug>.md` for the named feature,
     following the same shape as every other feature file (Step 3 below). Add its entry to
     `features/README.md`'s index if it's new; update the existing index line if the feature
     already existed.
  4. Touch `SKILL.md` itself **only if** Launch, Doctor, Drive, Evidence, Cleanup, or Helpers
     actually changed because of this feature (a new command, a new port, a new harness) —
     otherwise leave it untouched. Never regenerate `SKILL.md` wholesale in update mode.
  5. Run Step 4 (Prove) scoped to only this one feature file, not the whole map.
  6. Skip Step 5 (Offer the maintenance loop) — already offered at create time.

## 1. Interview the repo, not the user

Answer these from the codebase and only ask the user what you cannot observe:

- **Surface:** what does a user actually touch? A web UI, a CLI/TUI, a desktop app, an API, a mobile app, a library? A repo can have several; pick the primary one and note the rest.
- **Run:** how does the app start locally? Prefer the repo's own documented dev command (package scripts, Makefile, README quickstart). Note ports, env vars, seed data, auth.
- **Drive:** how can an agent interact with it programmatically? Existing harnesses first — Playwright/Cypress specs, expect scripts, PTY helpers, curl-able endpoints, a debug port. Only then pick a generic recipe: browser/CDP for web and Electron, a tmux/PTY harness for CLI/TUI, plain HTTP for services.
- **Observe:** what evidence can be captured? Screenshots, terminal transcripts, response bodies, logs, exit codes, DB state.
- **Isolate:** can two instances run side by side (ports, data dirs, profiles)? If not, say so in the generated skill: refusing to double-drive a shared instance beats corrupting the user's session.

If the checkout doesn't build or start as-is, fix that first (or report it precisely) before generating; a skill written against a broken base teaches wrong steps. When an irrelevant missing asset blocks startup (a static dir the API never serves, a sample config), the generated skill may create it, clearly marked as verification scaffolding, and remove it in cleanup.

## 2. Generate the skill

Write `.cursor/skills/verify-<app>/SKILL.md` with YAML frontmatter (`name: verify-<app>` and a `description` that names the app, the surface, and when to reach for it — without frontmatter the skill never registers) and these sections, each grounded in what the interview actually found (no placeholders left):

- **Launch:** the exact command that starts the app for verification, and how to tell it's ready (a log line, a port answering, a prompt). Include teardown. For a short-lived CLI or TUI there is no server to keep alive: launch means build the binary (or install deps) once, then start each drive in its own isolated PTY or tmux session.
- **Doctor:** one read-only check that answers "is this instance worth driving?" — process up, right version/build, port owned by us, auth valid. An agent runs this first whenever anything looks off.
- **Drive:** the harness recipe with real selectors/commands from this repo, not examples. Prefer stable handles (ARIA labels, data attributes, prompt strings, route paths) over coordinates and tab order.
- **Evidence:** what to capture for a proof and where it goes. State the proof standards: exercise the real user path, not internal setters or test-only endpoints; capture the action and the resulting state, not just the final screen; verify side effects (files written, rows inserted, messages sent) alongside what's visible; mocks only where a production boundary already isolates the external system. When the safe path is a dry-run or test mode, verify what it actually skips by observing (files, network, git refs) rather than trusting its name: some dry-runs still touch the network or open a browser.
- **Cleanup:** how to tear down instances the run created. Never kill by process name; kill what you started. Cleanup removes instances and scratch state, never the evidence: proof artifacts survive the teardown, in a location the skill names.
- **Helpers:** any script the skill ships is executable and its invocation is shown in the skill body. A helper the reader has to reverse-engineer is not a helper.

## 3. Seed the feature map

Create `.cursor/skills/verify-<app>/features/README.md` plus one file per user-facing feature you can identify (aim for the top 3-5 to start, from routes, commands, menus, or docs). Follow the shape in [`references/feature-map-example/`](references/feature-map-example/), with a README index and one file per feature. Each file answers, from the user's point of view: what the feature is, how to reach it, how to drive it with the harness, and what observable end state proves it works. The four H2s are `Sub-features`, `How to get to it (user POV)`, `Driving it with <harness>`, and `Gotchas`. The map is the repo's maintained verification source; a proof that drives one convenient entry point is incomplete when the map lists others.

## 4. Prove the generated skill before handing it over

Run its own instructions end to end once: launch, doctor, drive ONE mapped feature (one is enough in create mode; exactly the named feature in update mode), capture evidence, clean up. After cleanup, confirm the evidence still exists at the named location — a cleanup that eats the proof fails this step. Fix what fails, and run the generated cleanup after every failed iteration too, so broken attempts don't strand processes and ports. A generated skill that was never executed is a draft, not a deliverable.

## 5. Offer the maintenance loop (create mode only)

Point the user at `/maintain-verification-skill` for keeping the map honest as the app changes. Suggest a cadence only if they ask.

## References

- [Feature map example](references/feature-map-example/README.md)
```

- [ ] **Step 3: Write `create-verification-skill/README.md`**

```markdown
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
```

- [ ] **Step 4: Add `create-verification-skill` to the root README**

In `README.md`, extend the `### Architecture & Understanding` subsection added in Task 1 Step 4:

```markdown
### Architecture & Understanding
- **how** — Explain subsystem architecture and runtime flow; can critique an architecture after explaining it
- **create-verification-skill** — Generate (or incrementally update) a project-local skill that launches an app, drives a feature, and captures evidence
```

Add a row to the Comprehensive Skills Table, after the `how` row added in Task 1:

```markdown
| [create-verification-skill](./create-verification-skill/README.md) | Generates a project-local verification skill that launches the real app, drives a feature, and captures evidence; supports incremental updates to an existing generated skill's feature map. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | "make a control skill for this repo", "/create-verification-skill" | v0.1.0 / Alex Nguyen |
```

- [ ] **Step 5: Validate**

```bash
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
```

Expected: `PASS create-verification-skill`; all self-tests passed; 0 errors.

Note (documented, not automated): `create-verification-skill`'s own Step 4 ("Prove the generated
skill before handing it over") describes running the generated skill against a real target
project. This repo has no such target project (per `AGENTS.md`, "no application code, no build/dev
server"), so that proof step cannot be executed here — it will run for real the first time
`speckit-auto`'s integration setup (Task 3) invokes this skill against an actual consumer repo.

- [ ] **Step 6: Commit**

```bash
git add create-verification-skill/ README.md
git commit -m "feat(create-verification-skill): add skill with incremental update mode"
```

---

### Task 3: Add the verification opt-in to `speckit-auto`'s `--integration` setup

**Files:**
- Modify: `speckit-auto/references/shared/integration-setup.md`

**Interfaces:**
- Consumes: `create-verification-skill` (Task 2), invoked via the `skill` tool.
- Produces: a `verification: true|false` field in `.speckit/integration.json`, read by Stage 05
  (Task 5) via the same mirrored file Stage 01 already copies into the worktree.

- [ ] **Step 1: Insert the verification opt-in step and update the persisted JSON shape**

In `speckit-auto/references/shared/integration-setup.md`, replace step 2 (the `Persist` step) with
an expanded version that adds the new field and a new sub-step:

```markdown
2. **Persist** `{"integration": "<value>", "verification": <bool>, "updated_at": "<ISO-8601>",
   "set_by": "speckit-auto"}` to `<repo-root>/.speckit/integration.json` (`mkdir -p` first; root
   from `git rev-parse --show-toplevel`). This repo-local file is the **only** provider and
   verification-opt-in source — there is no global state. If the cwd is not inside a git repo,
   stop and tell the user to re-run from the target repository. Overwrite silently; report the
   previous value if one existed. Never ignore `--global`: if passed, reject it — global state is
   no longer supported.

   `<bool>` comes from a new question asked right after the provider is normalized, before
   persisting: **"Enable implementation verification for this project?"** (Yes/No), via the host
   ask tool ([host-adaptation.md](host-adaptation.md)). No answer → default `false` and say so;
   never block setup waiting on this answer the way step 1's provider value can.

2a. **If verification = true, generate the project's verification skill now:**
   1. Invoke the `skill` tool with name `create-verification-skill`, in **create mode** (no
      `.cursor/skills/verify-<app>/` exists yet for this repo). It runs its own repo interview
      (surface, run, drive, observe, isolate) directly — no separate analysis step is needed
      first.
   2. It writes `.cursor/skills/verify-<app>/SKILL.md` plus a feature map covering the repo's
      existing top 3-5 features, and proves itself once per its own Step 4.
   3. Commit the generated skill: `git add .cursor/skills/verify-<app>/` then
      `git commit -m "chore(verify-<app>): scaffold project verification skill"` (on whatever
      branch setup mode is running on — setup mode does not create its own dedicated branch
      unless installing a provider framework, per step 3 below).
   4. Any failure in this sub-step (skill unavailable, generation fails, self-proof fails) is
      reported but does **not** abort the rest of setup — the provider is still persisted and
      usable; report `verification: false` was effectively left in place for this run and tell the
      user they can retry by re-running `/speckit-auto --integration <value>`.

   **If verification = false:** skip this sub-step entirely; nothing is generated.
```

- [ ] **Step 2: Update the post-setup message to mention verification status**

In the same file, extend both bullet messages under step 4 (`Post-setup message`) with one more
line each, appended after the existing restart instruction:

For **github-speckit**:
```markdown
   > Verification is **enabled** for this project (a `.cursor/skills/verify-<app>/` skill was
   > generated and committed) — Stage 05 will run it after every implementation. / Verification is
   > **disabled** — Stage 05 will be skipped on every run until you re-run
   > `/speckit-auto --integration <value>` and opt in.
```

For **superpowers**: the same line, verbatim (the message does not differ by provider).

- [ ] **Step 3: Update the final report step**

Change step 5 (`Report: resolved provider and file path written. END TURN.`) to:

```markdown
5. Report: resolved provider, verification opt-in result (enabled/disabled, and the generated
   skill's commit hash if enabled), and file path written. **END TURN.**
```

- [ ] **Step 4: Grep for stale references and validate**

```bash
grep -n "Report: resolved provider and file path written" speckit-auto/references/shared/integration-setup.md
```

Expected: no match (confirms the old step 5 text was fully replaced).

```bash
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/test_validate_skills.py
```

Expected: `PASS speckit-auto`; all self-tests passed.

- [ ] **Step 5: Commit**

```bash
git add speckit-auto/references/shared/integration-setup.md
git commit -m "feat(speckit-auto): add verification opt-in to --integration setup"
```

---

### Task 4: Narrow Stage 04 to approval + implementation commit only

**Files:**
- Modify: `speckit-auto/references/pipeline/stage-04-finish.md`

**Interfaces:**
- Consumes: `shared/commit.md` (unchanged call).
- Produces: hands off to Stage 05 (Task 5) instead of doing spec-completion/PR itself.

- [ ] **Step 1: Rewrite the file, removing spec-completion and the `finishing-a-development-branch` call**

Replace the entire contents of `speckit-auto/references/pipeline/stage-04-finish.md` with:

```markdown
# Stage 04: Human Review / Implementation Commit (Provider-Agnostic)

Load after `speckit-code-review` returns `pass`. Two paths: **default mode** (human review gate is
mandatory, never skipped) and **YOLO** (no human interactions). Both paths end at the same place:
the implementation is committed, and control passes to Stage 05.

## Default Mode — Human Manual Review Gate

1. Present a concise summary from spec + plan: key use cases, expected usage scenarios.
2. Recommend the reviewer run the app / execute manual self-tests for those scenarios.
3. Ask via the host ask tool: `Approve implementation` / `Request changes`.

### If Request Changes

1. Collect the detailed human feedback.
2. Route the restart to the earliest affected step: requirement change → `specify` /
   `brainstorming`; solution/architecture change → `plan` / `writing-plans` (structure);
   task/detail change → `tasks` / `writing-plans` (task breakdown); code-only change →
   implementation step / direct edits under TDD.
3. **Restart through, not just at, that step**: re-run every downstream Stage 02 step in order so
   no derived artifact is left stale, re-run the Stage 02 mandatory self-review gate, commit + push
   the regenerated Stage 02 artifacts via the Spec/Plan Commit Gate (Stage 02), then re-enter the
   **full** Stage 03 flow (PHASE 1 + PHASE 2) until `status = pass` — the no-stop rules apply
   again for that re-entry.
4. Return to this gate and repeat until approved.

### If Approved

Ask for the commit message, then run the commit + push procedure in
[../shared/commit.md](../shared/commit.md) with that message.

## YOLO Path

Skip every human review/approval interaction. Auto-generate the commit message
`feat(<artifact_id>): <short summary from the spec or Jira summary>`, then run the commit + push
procedure in [../shared/commit.md](../shared/commit.md) with that message.

## Handoff (both modes)

After the implementation commit succeeded (or was skipped because nothing needed committing — see
[../shared/commit.md](../shared/commit.md)'s conditional-commit rule), load
[stage-05-verification.md](stage-05-verification.md) and enter Stage 05 in the same turn. Stage 05
owns everything from here: verification (conditional), cleanup, marking the spec completed,
pushing, and PR creation.

## Failure Handling

- A commit that was actually needed failing, a failed push, or an unresolved rebase → stop and
  report (shared/commit.md).

## Report

At this checkpoint report: resolved provider, `speckit-code-review` final status (`pass`), the
implementation commit(s) (hash + subject) and pushed branch, then note Stage 05 is next.
```

- [ ] **Step 2: Confirm no other file still expects Stage 04 to do spec-completion or PR creation**

```bash
grep -rn "Mark Spec Completed\|finishing-a-development-branch" speckit-auto/
```

Expected: no matches inside `stage-04-finish.md` (they now live only in the new
`stage-06-finish.md`, created in Task 6 — this grep will still show matches there once Task 6
lands; that's expected and fine at that point).

- [ ] **Step 3: Validate**

```bash
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/test_validate_skills.py
```

Expected: `PASS speckit-auto` (the link to `stage-05-verification.md` won't exist as a file yet
until Task 5 — if the validator's link checker flags it as broken at this point, that's expected
and will resolve once Task 5's commit lands; do not treat it as a regression in *this* task, but do
not merge Task 4 alone without Task 5 immediately following in the same work session).

- [ ] **Step 4: Commit**

```bash
git add speckit-auto/references/pipeline/stage-04-finish.md
git commit -m "refactor(speckit-auto): narrow Stage 04 to approval + implementation commit"
```

---

### Task 5: Create Stage 05 (Verification)

**Files:**
- Create: `speckit-auto/references/pipeline/stage-05-verification.md`

**Interfaces:**
- Consumes: `create-verification-skill` (Task 2, update mode), the `verification` field from
  `.speckit/integration.json` (Task 3), the host ask tool ([host-adaptation.md](../shared/host-adaptation.md)).
- Produces: hands off to Stage 06 ([stage-06-finish.md](stage-06-finish.md), Task 6) in every
  case (skip or ran).

- [ ] **Step 1: Write the file**

```markdown
# Stage 05: Verification (Provider-Agnostic, Conditional)

Load right after Stage 04's implementation commit succeeds (or was skipped because nothing needed
committing). Runs only when this repo opted in to verification at `--integration` setup time.

## 1. Read the opt-in

Read `verification` from the mirrored `<worktree>/.speckit/integration.json` (the same file Stage
01 §1.4 already copies into the worktree on every entry). Missing file, or the field absent
entirely (a repo that ran `--integration` before this field existed) → treat as `false`. Never
default a pre-existing repo into unexpected new behavior.

- `false` → skip this stage entirely. Load [stage-06-finish.md](stage-06-finish.md) and enter
  Stage 06 in the same turn, noting `verification: skipped` for the final report.
- `true` → continue with steps 2-5 below.

## 2. Update the project verification skill for this feature

Invoke the `skill` tool with name `create-verification-skill`, in **update mode**: name the one
feature this run just implemented (from the spec title / Jira summary) and pass the spec, plan,
and the list of files changed in the implementation commit as context. It adds a new
`features/<feature-slug>.md` file, or updates the existing one if this run modified a
previously-mapped feature, inside the already-generated `.cursor/skills/verify-<app>/features/`
map. It never touches other features' files, and only touches `SKILL.md` itself if this feature
changed Launch/Doctor/Drive/Evidence/Cleanup.

**Hard failure** (skill unavailable, or it reports it could not complete the update) → stop and
report the exact error. Verification was explicitly opted into; a silent skip here would be
misleading. Tell the user the implementation is already committed and pushed-pending (per Stage
04), and that they can re-run Stage 05 manually or disable verification via
`/speckit-auto --integration <value>` and re-run.

## 3. Execute the verification skill for this feature

Run the (now current) `verify-<app>` skill's own instructions, scoped to only this run's feature:
launch, doctor, drive using the harness recipe from `features/<feature-slug>.md`, capture
evidence, per its own Cleanup section — but do **not** run cleanup yet; that happens once, in
Stage 06, after the human confirms verification passed (a failed confirmation may mean rerunning
the drive against the same still-launched instance).

**Hard failure** (launch fails, doctor fails, the drive step cannot complete) → stop and report
the exact error, same failure philosophy as step 2.

## 4. Present evidence and confirm

Present the captured evidence (screenshots, transcripts, response bodies — whatever
`features/<feature-slug>.md` named) as a concise summary. Ask via the host ask tool:
`Verification passed, proceed to finish` / `Investigate further`.

### If Investigate Further

Route back exactly like Stage 04's "Request changes" path: collect the feedback, restart through
the earliest affected step (requirement/architecture/task/code-level), re-run every downstream
Stage 02 step and its self-review gate if regenerated, re-enter the full Stage 03 flow if code
changed, re-enter Stage 04's approval gate, then re-enter this stage (Stage 05) from the top —
including a fresh `create-verification-skill` update-mode call, since the feature's behavior may
have changed.

### If Approved

Continue to Stage 06 with `verification: passed`.

## 5. Handoff

Load [stage-06-finish.md](stage-06-finish.md) and enter Stage 06 in the same turn, carrying
forward whether this stage ran (`skipped` or `passed`) and, if it ran, a reference to what
`verify-<app>` launched so Stage 06 can run its Cleanup step.
```

- [ ] **Step 2: Validate**

```bash
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/test_validate_skills.py
```

Expected: `PASS speckit-auto`; all self-tests passed. (The link to `stage-06-finish.md` resolves
once Task 6 lands — same note as Task 4 Step 3; land Task 6 in the same session immediately after.)

- [ ] **Step 3: Commit**

```bash
git add speckit-auto/references/pipeline/stage-05-verification.md
git commit -m "feat(speckit-auto): add Stage 05 conditional verification"
```

---

### Task 6: Create Stage 06 (Clean, Commit, Push, PR, Complete)

**Files:**
- Create: `speckit-auto/references/pipeline/stage-06-finish.md`
- Modify: `speckit-auto/references/shared/commit.md` (add Stage 06 call sites to the "Used by" /
  message table)

**Interfaces:**
- Consumes: `shared/commit.md` (existing procedure, two more call sites), `gh` CLI (new, direct
  invocation, no external skill call).
- Produces: the pipeline's final report (replaces the one Stage 04 used to give).

- [ ] **Step 1: Add Stage 06 call sites to `shared/commit.md`**

Replace the file's opening two paragraphs:

```markdown
# Shared: Commit + Push Procedure (Provider-Agnostic)

Used by: the Stage 02 → Stage 03 spec/plan commit gate, Stage 04 human-review commit (default
mode), the Stage 04 YOLO auto-commit, and Stage 06's two commits (verification artifacts, spec
completion). The procedure is identical; only the commit message source differs:

| Call site | Message |
|-----------|---------|
| Stage 02 → 03 gate | auto: `docs(<artifact_id>): add spec, plan, and tasks` |
| Stage 04 default | asked from the user |
| Stage 04 YOLO | auto: `feat(<artifact_id>): <short summary from the spec or Jira summary>` |
| Stage 06 verification artifacts | auto: `chore(verify-<app>): update verification for <artifact_id>` |
| Stage 06 spec completion | auto: `chore(spec): mark <artifact_id> completed` |
```

(Everything below the table in this file is unchanged — the conditional-commit, submodule, and
push-and-sync sections all apply identically to the two new call sites.)

- [ ] **Step 2: Write `speckit-auto/references/pipeline/stage-06-finish.md`**

```markdown
# Stage 06: Clean / Commit / Push / PR / Complete (Provider-Agnostic)

Load right after Stage 05 hands off (whether it ran or was skipped). Final stage of the pipeline.

## 1. Clean (only if Stage 05 ran)

If Stage 05 was skipped, go straight to step 2. Otherwise, run the generated `verify-<app>`
skill's own Cleanup step now: tear down only what it launched (kill by tracked PID/handle, never
by process name). Evidence artifacts are never deleted by this step — they stay wherever
`verify-<app>` named them in its Evidence section. A cleanup that fails to find what it expects to
tear down is a warning, not a stop — log it and continue.

## 2. Commit verification artifacts (only if Stage 05 ran)

Commit the `.cursor/skills/verify-<app>/` skill files and feature-map changes only — never the
run's evidence/screenshots — via [../shared/commit.md](../shared/commit.md), call site "Stage 06
verification artifacts". The conditional-commit rule applies: if `create-verification-skill`'s
update-mode call in Stage 05 already produced no changes worth committing (rare, but possible if
the feature needed no map update), skip this commit and log why.

## 3. Mark spec completed

1. Update the active spec (`specs/<feature_folder>/spec.md`): set the status field to `completed`
   or add `Status: completed`.
2. Commit via [../shared/commit.md](../shared/commit.md), call site "Stage 06 spec completion".

## 4. Push

Run the Branch Sync + Push section of [../shared/commit.md](../shared/commit.md) for the parent
repo and every submodule with local commits ahead of its pushed base — this section already
handles submodules; do not re-derive push logic here.

## 5. PR creation (provider-agnostic, per repo)

For the parent repo, then for each submodule with commits ahead of its base branch (the same set
identified for push in step 4):

1. Detect the remote: `git -C <repo-or-submodule-path> remote get-url origin`.
2. Host is `github.com` → run `gh pr create` for that repo/submodule (title/body derived from the
   spec: title from the spec's title or `artifact_id`, body summarizing the spec's problem
   statement and this run's implementation commit(s)). Treat "a pull request for branch `<branch>`
   already exists" as **success**, not an error — idempotent.
3. Any other host, or `gh` not installed/not authenticated → report `PR not created for <repo>:
   <reason>` and continue. Non-blocking: one repo's failure never stops another repo's PR attempt
   or the rest of this stage.
4. Record the outcome per repo (`created` / `already existed` / `skipped: <reason>`) for the final
   report below.

## Failure Handling

- Verification-artifact commit or spec-completion commit failing when one was actually needed, a
  failed push, or an unresolved rebase → stop and report the exact error (same philosophy as
  [../shared/commit.md](../shared/commit.md)); do not claim pipeline success without the
  completion commit.
- PR creation failures are per-repo non-blocking, per step 5 above — never a stage-level stop.

## Final Report

At completion report: resolved provider, `speckit-code-review` final status (`pass`),
verification outcome (`verification: skipped` or `verification: passed`, plus
`investigate_loops: N` if Stage 05 looped at least once), the implementation commit(s) (from Stage
04), the verification-artifact commit (if any), the spec completion commit hash, pushed branches,
and per-repo PR outcomes. In `--issue` mode, update the execution report first (Stage 01 §7).
```

- [ ] **Step 3: Validate**

```bash
python3 tools/validate_skills.py --skill speckit-auto
python3 tools/test_validate_skills.py
```

Expected: `PASS speckit-auto`; all self-tests passed; 0 errors. This is the point where the
`stage-05-verification.md` → `stage-06-finish.md` and `stage-04-finish.md` → `stage-05-verification.md`
links from Tasks 4-5 all resolve for the first time — confirm no broken-link warnings remain:

```bash
grep -n "stage-05\|stage-06" speckit-auto/references/pipeline/*.md speckit-auto/SKILL.md
```

- [ ] **Step 4: Commit**

```bash
git add speckit-auto/references/pipeline/stage-06-finish.md speckit-auto/references/shared/commit.md
git commit -m "feat(speckit-auto): add Stage 06 clean/commit/push/PR/complete"
```

---

### Task 7: Update `speckit-auto/SKILL.md` for the six-stage pipeline

**Files:**
- Modify: `speckit-auto/SKILL.md`

**Interfaces:**
- Produces: the updated loading map, sub-skill dependency table, modes section, and output
  behavior description that Tasks 3-6 now require.

- [ ] **Step 1: Update the Loading Map table**

Replace:

```markdown
| `references/pipeline/stage-04-finish.md` | `speckit-code-review` returns `pass` |
```

with:

```markdown
| `references/pipeline/stage-04-finish.md` | `speckit-code-review` returns `pass` |
| `references/pipeline/stage-05-verification.md` | Stage 04 implementation commit succeeds (or is skipped as already-clean) |
| `references/pipeline/stage-06-finish.md` | Stage 05 hands off (whether it ran or was skipped) |
```

- [ ] **Step 2: Update the Sub-Skill Dependencies table**

Replace:

```markdown
## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |

Both are provider-independent and used by every provider.
```

with:

```markdown
## Sub-Skill Dependencies

| Sub-skill | Purpose | Invocation |
|-----------|---------|------------|
| `jira-to-speckit` | Jira fetch + compaction (steps 1–5 only) + ticket snapshot write | `skill` tool, name `jira-to-speckit` |
| `speckit-code-review` | Authoritative JSON pass/fail review gate | `skill` tool, name `speckit-code-review` |
| `create-verification-skill` | Generate/update the project's `.cursor/skills/verify-<app>/` verification skill | `skill` tool, name `create-verification-skill`; only invoked when `--integration` setup enabled verification |

All three are provider-independent and used by every provider. `create-verification-skill` is
conditional on the `verification` opt-in persisted at `--integration` setup time
([shared/integration-setup.md](references/shared/integration-setup.md)); the other two run on
every pipeline invocation.
```

- [ ] **Step 3: Update the Modes section**

Replace:

```markdown
## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, and Stage 04.
- **YOLO** (`--yolo`): no human checkpoints; Stage 02 interactions and Stage 04 human review are
  skipped, with an auto-generated commit message.

Stage 03 is a NO-STOP ZONE in both modes.
```

with:

```markdown
## Modes

- **Default**: human-in-the-loop. Mandatory checkpoints: the Stage 02 approval interactions, the
  Stage 02 → Stage 03 start-implementation confirmation, Stage 04's human review, and (when
  verification is enabled) Stage 05's verification confirmation.
- **YOLO** (`--yolo`): no human checkpoints; Stage 02 interactions, Stage 04 human review, and (when
  verification is enabled) Stage 05's confirmation are all skipped, with an auto-generated commit
  message and an auto-approved verification result.

Both Stage 04 and Stage 06 always run in both modes — Stage 06 (commit verification artifacts,
mark spec completed, push, open PRs) is never optional. Stage 05 itself is conditional on the
`--integration`-time verification opt-in, independent of default/YOLO mode. Stage 03 is a NO-STOP
ZONE in both modes.
```

- [ ] **Step 4: Update the Output Behavior section**

Replace:

```markdown
## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion, report: resolved provider, `speckit-code-review` final status (`pass`),
implementation commit status/hash, and the spec completion commit hash. For a setup invocation
(`--integration`), report: resolved provider, file written, scope, and the next command.
```

with:

```markdown
## Output Behavior

At each checkpoint, report: current stage, result (`done` / `needs changes` / `failed`), next
stage. At completion (Stage 06), report: resolved provider, `speckit-code-review` final status
(`pass`), verification outcome (`skipped` or `passed`, plus investigate-loop count if any),
implementation commit status/hash, the verification-artifact commit (if any), the spec completion
commit hash, pushed branches, and per-repo PR outcomes. For a setup invocation (`--integration`),
report: resolved provider, verification opt-in result, file written, scope, and the next command.
```

- [ ] **Step 5: Bump the version**

In the frontmatter, change `version: "0.3.0"` to `version: "0.4.0"` — a minor bump, since this adds
new pipeline stages and a new sub-skill dependency (not a patch-level fix).

- [ ] **Step 6: Sync the root README badge**

In `README.md`, change the `speckit-auto` row's trailing badge from `v0.3.0 / Alex Nguyen` to
`v0.4.0 / Alex Nguyen`. Also update that row's description to mention the six-stage pipeline:

```markdown
| [speckit-auto](./speckit-auto/README.md) | End-to-end spec-driven delivery orchestrator. Runs intake, spec creation, design, implementation, code review loop, optional verification, commit, and PR creation—all in one turn. Supports `--yolo` mode for zero-human automation. | `.github/skills/` or `~/.agents/skills/` | GitHub Copilot, Claude, Local | Requirement text, `--issue <jira-url>`, `--yolo`, `--integration` | v0.4.0 / Alex Nguyen |
```

- [ ] **Step 7: Validate**

```bash
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
```

Expected: 0 errors across all skills; all self-tests passed.

- [ ] **Step 8: Commit**

```bash
git add speckit-auto/SKILL.md README.md
git commit -m "feat(speckit-auto): wire six-stage pipeline into SKILL.md, bump to 0.4.0"
```

---

### Task 8: Update `speckit-auto/README.md`, `AGENTS.md`, and manual test cases

**Files:**
- Modify: `speckit-auto/README.md`
- Modify: `AGENTS.md`
- Modify: `test-case/speckit-auto/test-cases.md`

**Interfaces:**
- Produces: user-facing documentation and manual test coverage consistent with the six-stage
  pipeline; also fixes a pre-existing inaccuracy in `test-cases.md` (T22) that this plan's work
  makes newly relevant to get right.

- [ ] **Step 1: Update `speckit-auto/README.md`'s Overview stage list**

Find the numbered stage list in the Overview section (four items: Stage 01-04) and replace it
with:

```markdown
1. **Stage 01 — Preflight + Intake**: linked worktree + feature branch, mandatory startup
   framework recovery gate (checks provider skills/agents and auto-installs on user confirmation
   if missing), project context from
   `docs/guidelines/architecture.md`, Jira intake via `jira-to-speckit` when `--issue` is used.
2. **Stage 02 — Spec / Design**: spec, plan, tasks via the provider's stages, with review
   interviews (default mode) or autonomous self-review (YOLO), a mandatory self-review gate, and a
   spec/plan commit before implementation starts.
3. **Stage 03 — Implement + Code Review Loop** (NO-STOP ZONE): implement → converge/verify → run
   `speckit-code-review` → fix → repeat until `pass`. No human gates in either mode.
4. **Stage 04 — Human Review / Implementation Commit**: default mode asks for human approval
   before committing; YOLO mode auto-commits. Both modes hand off to Stage 05.
5. **Stage 05 — Verification** (conditional): only runs when verification was enabled at
   `--integration` setup time. Updates the project's generated `verify-<app>` skill for the
   just-implemented feature, runs it, and asks for a pass/investigate confirmation before
   continuing. Skipped entirely (with a report line saying so) when verification was not opted
   into.
6. **Stage 06 — Clean / Commit / Push / PR / Complete**: tears down anything Stage 05 launched,
   commits verification artifacts (if any), marks the spec completed, pushes every repo/submodule
   with local commits, and opens a pull request per repo (parent + each submodule) via `gh pr
   create` where the remote is GitHub — non-blocking per repo.
```

- [ ] **Step 2: Update the YOLO vs Default Mode section**

In the `### YOLO vs Default Mode` section, update the bullets to reflect verification as an
independent axis:

```markdown
### YOLO vs Default Mode

**Default Mode** (recommended for critical features):
- Runs Stages 01–06, with mandatory human checkpoints at Stage 04 and (when verification is
  enabled) Stage 05
- Requires explicit human approval before code is merged, and — if verification is enabled —
  explicit confirmation that verification passed
- Best for production, regulatory, or high-stakes work

**YOLO Mode** (`--yolo` flag):
- Still routes through every stage, but skips the human checkpoints at Stage 04 and (when
  verification is enabled) Stage 05
- Zero human checkpoints; fully automated merge, verification confirmation, and commit/push/PR
- Ideal for internal tools, experiments, or when continuous delivery is the goal
- All code still passes speckit-code-review before merge; if verification is enabled, it still
  runs — YOLO only skips asking a human to confirm the result

**Verification is independent of mode.** It is enabled or disabled once, per repo, at
`--integration` setup time — not per run, and not tied to `--yolo`.
```

- [ ] **Step 3: Fix `AGENTS.md`'s integration.json gotcha to mention `verification`**

Find the gotcha line:

```markdown
- `speckit-auto` resolves its provider only from repo-local `.speckit/integration.json` (no global state, no first-run prompt; missing file → stop and direct the user to `/speckit-auto --integration <provider>`). Provider is fixed for the whole run — never infer it from repo contents.
```

Replace with:

```markdown
- `speckit-auto` resolves its provider only from repo-local `.speckit/integration.json` (no global state, no first-run prompt; missing file → stop and direct the user to `/speckit-auto --integration <provider>`). Provider is fixed for the whole run — never infer it from repo contents. The same file's `verification` field (added at `--integration` setup time) gates Stage 05; absent or `false` → Stage 05 is skipped, never assumed enabled.
```

- [ ] **Step 4: Fix the T22 inaccuracy and add Stage 05/06 test rows to `test-case/speckit-auto/test-cases.md`**

Replace:

```markdown
| T22 | YOLO mode skips human gates | Mode = yolo | Run with `--yolo` | Skips Stage 02 interview/confirmation and Stage 04 entirely | Both |
```

with:

```markdown
| T22 | YOLO mode skips human gates | Mode = yolo | Run with `--yolo` | Skips Stage 02 interview/confirmation and Stage 04's human-approval interaction (Stage 04 itself still runs: implementation is still committed) | Both |
```

Then append these rows to the main table (after T25, before the `## Host-specific checks`
heading):

```markdown
| T26 | Verification opt-in at setup | Running `--integration` for the first time on a repo | Answer "Yes" to the verification question | Generates `.cursor/skills/verify-<app>/`, proves it once, commits it, persists `verification: true` | Both |
| T27 | Verification opt-out at setup | Running `--integration` for the first time on a repo | Answer "No" (or no answer) | Persists `verification: false`; nothing generated | Both |
| T28 | Stage 05 skipped when disabled | `verification: false` in `.speckit/integration.json` | Run pipeline through Stage 04 | Stage 05 is skipped; report shows `verification: skipped`; proceeds straight to Stage 06 | Both |
| T29 | Stage 05 runs when enabled | `verification: true` | Run pipeline through Stage 04 | Invokes `create-verification-skill` in update mode for the implemented feature, runs `verify-<app>`, asks pass/investigate | Both |
| T30 | Stage 05 investigate loop | Verification enabled; human answers "Investigate further" | Reach Stage 05's confirmation | Routes back like a Stage 04 "Request changes"; re-enters Stage 05 after re-verification | Both |
| T31 | Stage 06 always runs | Any mode, verification enabled or not | Reach end of Stage 05 | Cleans up (if Stage 05 ran), marks spec completed, pushes, attempts PR creation per repo | Both |
| T32 | PR creation on GitHub remote | Parent repo (or submodule) origin is a `github.com` URL, `gh` installed and authenticated | Reach Stage 06 PR step | Runs `gh pr create`; treats an already-existing PR for the branch as success | Both |
| T33 | PR creation skipped on non-GitHub or missing `gh` | Origin is not `github.com`, or `gh` unavailable | Reach Stage 06 PR step | Reports "PR not created for `<repo>`: `<reason>`" and continues; does not stop the stage | Both |
| T34 | Submodule PR fan-out | Repo has submodules with local commits ahead of base | Reach Stage 06 PR step | Attempts a PR for the parent and for each such submodule independently; one failing does not block another | Both |
```

- [ ] **Step 5: Validate**

```bash
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
```

Expected: 0 errors; all self-tests passed. (`test-case/` and `AGENTS.md` are not skills and are
not schema-checked, but the command still confirms nothing else broke.)

- [ ] **Step 6: Commit**

```bash
git add speckit-auto/README.md AGENTS.md test-case/speckit-auto/test-cases.md
git commit -m "docs(speckit-auto): document six-stage pipeline, fix T22, add verification/PR test cases"
```

---

## Post-Plan Verification (run once, after all 8 tasks are committed)

- [ ] **Final full validation pass**

```bash
python3 tools/validate_skills.py
python3 tools/test_validate_skills.py
```

Expected: `5 checked` becomes `7 checked` (two new skills), `0 error(s)`, all self-tests passed.

- [ ] **Cross-file link sanity check**

```bash
grep -rn "how/SKILL.md\|create-verification-skill/SKILL.md" speckit-auto/ README.md AGENTS.md
```

Confirm every hit is a prose mention (skill name in backticks or a root-README relative link), not
a broken cross-skill link from inside `speckit-auto/`'s own folder — per `SKILL_SPEC.md`
self-containment, `speckit-auto`'s own files must never link into `how/` or
`create-verification-skill/`'s folders, only reference them by name.

- [ ] **Push and open a PR**

```bash
git push -u origin feature/speckit-auto-verification-and-pr-stages
gh pr create --base main --title "feat: add verification and PR stages to speckit-auto" \
  --body "Implements docs/superpowers/specs/2026-09-24-speckit-auto-verification-pr-stages-design.md. Adds how and create-verification-skill skills; extends speckit-auto to a six-stage pipeline (Stage 05 conditional verification, Stage 06 clean/commit/push/PR/complete)."
```
