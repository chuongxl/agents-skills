---
name: speckit-qa-auto
description: |
  Runs an end-to-end QA delivery pipeline from a Jira issue: discovery of linked issues and
  existing tests, an impact sweep that finds which existing flows the story imposes new invariants
  on, requirement analysis over the whole ticket, BDD test design, an adversarial review that
  attacks the design before a human sees it, selector verification, Playwright-BDD automation, a
  bounded run-and-fix loop, then human review and a pushed branch. Anchors on a story, an epic, or
  an existing Xray test; converts existing Manual test cases into Gherkin; and bootstraps a test
  framework when the repository has none. The Gherkin feature file is the single artifact, serving
  manual testers and automation alike. Use when a Jira issue needs test cases and automated tests
  produced together, from one command — including the regression tests the ticket never mentions.
compatibility: "Runs on GitHub Copilot, Claude Code, and OpenCode. Discovered from ~/.agents/skills/, ~/.claude/skills/, or ~/.config/opencode/skills/. Requires git, bash, and a TypeScript repository; a Playwright-BDD test tree is used when present and created by bootstrap when absent. Network access for Jira and Xray."
license: MIT
allowed-tools: bash glob grep view create edit skill
metadata:
  author: Alex Nguyen
  version: "0.5.0"
---

# Speckit QA Auto

## Entry Dispatch (Do This First, Every Invocation)

Load `references/shared/host-adaptation.md` once and fix the host for the rest of the run. Parse
the invocation: `--issue <jira-url-or-key>`, `--design-only`, `--full-suite`, `--parallel-worktree`,
`--pr`.

**`--issue` is required.** A missing `--issue` stops the run, with the reason: the Jira key is the
artifact folder's identity, the `@REQ_` tag every scenario carries, and the dedup key against
existing Xray coverage — three parts of the pipeline have no defined behaviour without it.

`--issue` accepts three kinds of key, recorded as `run.anchor_type`:

| Anchor | `anchor_type` | Produces |
|---|---|---|
| A story | `story` | One `.feature` set for that requirement |
| An epic | `epic` | One `.feature` per child issue, each tagged with the child's key |
| An existing Xray test | `test` | Scenarios converted from that test, tagged with the requirement the test links to |

Impact analysis and the adversarial review run at **every** anchor type, and each type resolves them
differently:

| Anchor | Impact sweep + depth | Adversarial review |
|---|---|---|
| `story` | Once, over the story's entity | Three attack tasks |
| `epic` | Per child, values under `impact.by_child` | Per child, against that child's files; the **fidelity set** when the children are conversions |
| `test` | Over the requirement the test links to; skipped when it links to none | **Fidelity set** — both directions |

`epic` fans out because the pipeline already produces one `.feature` per child, and an epic-level
entity no child's ticket names is one no evidence path can support. **The fan-out adds fields, not
folders.** An epic run has exactly one artifact folder — the epic's — because that name is the
`@REQ_` target, the dedup key, and the resume glob, and a second folder would be a second identity.
Child impact files live in the epic's folder, named for the child, beside that child's `.feature`.
Per-child values live under `impact.by_child`; without that dimension the fields are flat scalars
and an epic's second child overwrites its first.

The ceiling is the gate. Per-child depth, sweep, and review multiply quickly, and the gate is one
human reading one output — an epic wider than that is split, and the split is stated, in the words
`references/shared/manual-conversion.md` already uses for a conversion batch.

`test` swaps the task set because attack tasks 1 and 3 have no subject in a conversion: there is no
ticket prose to mine for constraints and no heading to misclassify. Fidelity replaces them, asked
**both** ways — what the Gherkin omits *and* what it adds — because a silent addition is
indistinguishable from a mistranslation. An `epic` whose children are conversions gets that set too,
per child; giving it the story tasks would leave the largest batches with no fidelity review at all.

One argument, three resolutions — never a second entry flag. The artifact folder is named
`<jira-key>-<slug>` and that name is also the `@REQ_` target, the dedup key, and the glob the resume
check matches; a second way in would mean a second identity, and every one of those four things
would need a second definition.

`--impact "<flow>[, <flow>...]"` is optional, and is **not** a second entry flag: `--issue` remains
required and remains the only anchor. It populates `impact.declared[]` verbatim, and that list is
never merged into what the sweep found — a flow both produced is a cross-confirmation, a flow only
the sweep found is a gap in the human's memory, and a flow only the human named is a gap in the
sweep's reach. Its absence answers nothing; the required answer is taken from a human at the
Stage 02 gate.

Once `--issue` is present, load `references/shared/operating-rules.md` and enter Stage 01 in the
same turn.

## Stage Router

Load only the current stage's file. Each stage names its own successor in prose; the router does
not link ahead, and a stage never links back to the one before it.

| Stage | File | Human gate |
|---|---|---|
| 01 — Intake | `references/pipeline/stage-01-intake.md` | none |
| 02 — Test Design | `references/pipeline/stage-02-test-design.md` | yes — **two**: 2.2b approach, 2.8 design |
| 03 — Automate | `references/pipeline/stage-03-automate.md` | none — no-stop zone |
| 04 — Finish | `references/pipeline/stage-04-finish.md` | yes |

Shared leaves, each loaded only by the stage that needs it, never all at once:
`references/shared/run-state.md` (the state contract every stage reads and writes),
`references/shared/operating-rules.md`, `references/shared/workspace-guard.md`,
`references/shared/repo-profile.md`, `references/shared/discovery.md`,
`references/shared/impact-analysis.md`,
`references/shared/selector-verification.md`, `references/shared/gherkin-conventions.md`,
`references/shared/host-adaptation.md`, `references/shared/commit.md`.

Two further leaves are loaded **conditionally**, by the one stage that needs them and only on the
runs that need them: `references/shared/bootstrap.md` (Stage 01, when discovery found no test
framework) and `references/shared/manual-conversion.md` (Stage 02, when the run converts existing
Manual Xray tests). A repository that already has a test tree never pays for the file that builds
one.

## Isolation

The run works on a branch named `<branch_prefix><jira-key>-<slug>`, and `--parallel-worktree`
decides where that branch lives:

| `run.isolation` | Selected by | Workspace |
|---|---|---|
| `branch` | the default | the source checkout itself |
| `worktree` | `--parallel-worktree` | a linked worktree at `<repo-root>/.worktrees/<branch>` |

**The default is `branch`** because the ordinary run is one developer, one story, one pipeline, and
a branch in the checkout they are already standing in is where a branch is expected to be. A
worktree costs a second checkout and its own dependency install before a single test can run, and
leaves the result in a directory the developer then has to go find.

`--parallel-worktree` buys real isolation, for the two cases the default cannot serve: more than
one run against the same repository at once, and a checkout too dirty for git to switch branches.
Both are the same underlying fact — the developer's working tree is already in use.

The two modes are not the same safety property, and the skill does not pretend they are. Under
`worktree`, Stage 04 verifies the developer's checkout came out of the run byte-identical. Under
`branch` that guarantee is unavailable — the pipeline is writing into that checkout by design — so
two narrower ones replace it: the run stages and writes only inside `baselines.owned_paths[]`, and
every path already dirty at intake still hashes at Stage 04 to what it hashed then.
`references/shared/workspace-guard.md` is the authority on both, and `git add -A` is forbidden in
branch mode for the reason `run-state.md` rule 17 gives.

Stage 01's branch gate stops the run when git refuses the switch onto the base branch, quoting the
error and naming `--parallel-worktree` as the way through. It never stashes, forces, or commits the
developer's work to clear its own path.

## Modes

Isolation above is *where* the run works; this section is *what the run skips*, and the answer is
nothing. There is one mode. All three human gates — the Stage 02 **approach** gate at 2.2b, the
Stage 02 **design** gate at 2.8, and Stage 04's commit-and-push approval — always run, and so do the
Stage 02 self-review gate and the selector gate at the head of Stage 03. **No flag skips a gate.** An earlier `--yolo` flag that skipped the two approvals has been
removed: its documented effect was to skip approvals, but its actual effect was to let a run whose
Xray dedup never ran ship every scenario as `NEW`, with no human ever seeing the `not-run` label —
which creates a duplicate Xray test for every scenario a team already had.

No flag disables the adversarial review at 2.7b or the impact section of the Stage 02 design gate
either. `run.design_depth` scales how wide the impact sweep looks, how long the design document
runs, and how many alternatives the 2.2b approach gate presents; it never scales what the ticket
read covers, it never decides whether an answer is taken at a gate, and it never turns a check off.
A gate that "scales to nothing" at `trivial` is a gate that was removed. Narrowing the read is the
defect the review exists to catch, and the pass that would authorize the narrowing is the pass being
audited.

Stage 03 remains a no-stop zone: once entered, it runs to a verdict on every scenario in scope, an
infrastructure stop, or the circuit breaker, and asks no question along the way.

`--design-only` ends the run after Stage 02 instead of entering Stage 03, leaving
`run.resume_from` set so a later invocation continues into automation. It stops the pipeline early;
it does not skip anything the pipeline would otherwise do. A run whose `run.code_state` resolves to
`pending` behaves this way whether or not the flag was passed — with no code, Stage 03 has nothing
to run against.

## Sub-Skill Dependencies

| Skill | Invoked | For |
|---|---|---|
| `jira-to-speckit` | By name, through the `skill` tool | Jira ticket intake and Xray existing-test reads (Stage 01) |

Never linked to — a link outside this skill folder fails the validator and breaks the moment this
skill is installed on its own. Refer to it by name only.

## Required Inputs

- `--issue <jira-url-or-key>` — required; see Entry Dispatch.
- `--impact "<flow>[, <flow>...]"` — optional; see Entry Dispatch.
- `--parallel-worktree` — optional; see Isolation. Without it the run branches in the source
  checkout.
- `.env` in the repository root: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — required for
  intake. `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET` — optional, enable the Xray read in Stage 01.
  None of these are ever printed.

## Portability Note

`allowed-tools` above uses GitHub Copilot's tool names. Claude Code and OpenCode expose the same
capabilities under different names — `Bash`/`bash`, `Read`/`view`, `Write`/`create`, `Edit`/`edit`,
`Glob`/`glob`, `Grep`/`grep`, `Skill`/`skill` — per `references/shared/host-adaptation.md`'s tool
map. Never refuse to act because a tool is named differently than expected.
