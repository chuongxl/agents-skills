# Stage 03: Implement + Code Review Loop (Provider-Agnostic)

Implementation identity, convergence step, and fix-application style come from the resolved
provider adapter ([../providers/](../providers/)): github-speckit runs
`speckit-implement → speckit-converge`; superpowers runs its implementation skill
(`subagent-driven-development` preferred, `executing-plans` fallback, chosen once at entry) with
per-step `test-driven-development` and `systematic-debugging` on failures. Discard Stage 02
interview context at entry — this stage is a NO-STOP ZONE.

## Repository-Aware Implementation

Before the implementation step, inject into its input: the Stage 01 Project Context `summary`,
the `repo_map` (so each file lands in the right workspace), any relevant guideline from
`loaded_guidelines` matched by task topic (load + cache now if matched but not yet cached), and —
superpowers — the plan path `specs/<feature_folder>/plan.md`.

## Invocation

Invoke every step via the `skill` tool using the skill name from the provider adapter's Stage
Skill Map. Identical on all three hosts:

- **github-speckit:** `skill speckit-implement`, `skill speckit-converge`, etc.
- **superpowers (all hosts):** `skill subagent-driven-development`, etc.

The `skill` tool is **synchronous** — it blocks until the skill finishes and returns inline.
After every call, apply the **Step Execution and Completion Protocol** from the provider adapter:
read the return value, verify the expected artifact on disk (for `speckit-implement`: source/test
files written; for `speckit-converge`: return value reports status), retry once on failure, stop
if still failing. Never continue the loop until the current step's completion is confirmed.

`speckit-code-review` runs **inline** via the `skill` tool on all hosts — never as a background
agent — and always with the spec path passed explicitly (`specs/<feature_folder>/spec.md`).

Never the `task` tool with any skill name; never a nested CLI subprocess. Never emit `@speckit.*`
or `/speckit.*`.

If any `skill` invocation fails (skill not found, tool error) → **stop immediately** and tell
the user:
> "Provider skills are not installed or not available. Please run
> `/speckit-auto --integration {provider}` first, then re-run your command."

## Large Scope (condensed)

Large scope → build `implementation_packages[]` from the tasks/plan grouped by `workspace` +
bounded capability, invoke the implementation step once per package until the queue is empty,
parallel only for independent packages (superpowers: `dispatching-parallel-agents`). Per-package
outputs merge into the single plan/tasks artifact. Pass only minimum slices per invocation.

## Submodules (condensed)

Modified submodules: branch inside each one off a synced base (Stage 01 rules), commit submodule
changes first, then the parent pointer update.

## NO-STOP ZONE (canonical statement)

For the entire duration of this stage, in **both** modes: no human approval gates, no interview
questions, no "do you approve?" prompts, no pauses, no report-and-stop on failed results.

- The **only** success exit is `status = pass` from `speckit-code-review`.
- The **only** other permitted exit is the circuit breaker: the exact same failure repeating 5
  consecutive iterations with no file change between them, or a git/filesystem error that
  prevents writing code. Report the stuck state and stop.
- A `failed` review is NEVER a stop condition — it is the input for the next fix iteration. Fix
  and loop immediately, in the same turn; never produce a prose summary of a failed result and
  never ask the user what to do.
- Superpowers gate skills are subordinated: `verification-before-completion` is a check to run,
  not a place to stop; `requesting-code-review` verdicts never exit the stage;
  `receiving-code-review` never authorizes ending the turn; `finishing-a-development-branch` is
  **never called in Stage 03** — it belongs only to Stage 04 after final approval. The
  implementation skill reporting "all tasks complete" or its terminal "finish the branch" handoff
  are data, not exits (no PR, merge, branch/worktree deletion inside this stage).

## Review Range (superpowers)

At Stage 03 entry, before any dispatch: `BASE_SHA=$(git merge-base HEAD <base-branch>)`;
re-read `HEAD_SHA=$(git rev-parse HEAD)` fresh at each review pass. Never use `HEAD~1` as
`BASE_SHA` (silently drops all but the last commit; can yield an empty diff with `executing-plans`).
If `BASE_SHA == HEAD_SHA` at the first review pass: dirty tree → commit a checkpoint
(`chore(<feature>): checkpoint implementation`) and continue; clean tree → return to PHASE 1 once;
a second empty pass with a clean tree is a stalled implementation → apply the circuit breaker.

## Loop Algorithm (execute until DONE — no exits in between)

```
PHASE 1 — Implementation + convergence
  C1 — Run the implementation step for the next package/batch
       - github-speckit: speckit.implement
       - superpowers: subagent-driven-development (or executing-plans), each step under
         test-driven-development; unexpected test/bug failures route through systematic-debugging
  C2 — Run the convergence check
       - github-speckit: speckit.converge (codebase vs spec/plan/tasks)
       - superpowers: verification-before-completion against the plan — fresh evidence required
         (tests run, output observed)
  C3 — Read the result
       IF gaps / unmet tasks / missing evidence:
         - record as remaining work and return to C1 immediately
       IF converged / all tasks implemented with clean evidence:
         - proceed to PHASE 2

PHASE 2 — Code review loop
  R0 — Native advisory pass (superpowers ONLY, first PHASE-2 entry only)
       - requesting-code-review with description, plan excerpt, BASE_SHA, HEAD_SHA
       - apply Critical/Important findings immediately (TDD); log Minor findings
       - once it returns findings, set r0_completed = true and skip R0 on every later re-entry
         (speckit-code-review is the authoritative gate)
  R1 — Invoke speckit-code-review with the explicit spec path; receive the JSON result
  R2 — Read result.status
       IF "pass"   → EXIT STAGE 03 → load stage-04-finish.md immediately in the same turn
                     (default mode: Stage 04 human review; --yolo: YOLO auto-commit path)
       IF "failed" → go to R3 immediately. No summary, no turn end, no user question.
  R3 — Read the compact result fields only:
       status, "Business cover", unit-test-coverage (<80% → all TEST-* fixes apply),
       state_file (resume from this), detail_files (category → file map), fixes[] (flat list of
       actionable fix targets — THIS drives R4). Drop the rest of the failed review body and
       rebuild the next attempt from state_file + fixes[].
  R4 — Build the corrective action list from fixes[]:
       classify each entry by ID prefix — FR-*/NFR-*: business gap; ARCH-*: architecture;
       SEC-*/CODE-*: code-level; TEST-*: missing test. If an entry's action is unclear, load ONLY
       the matching category file from detail_files (business-gap / architecture / security /
       code-quality / unit-tests). Never load a category file you don't need.
  R5 — Route:
       - ALL fixes are FR-*/NFR-*/ARCH-*  → re-run the plan step (speckit.plan / writing-plans
         slice, then checkout checklist→tasks or task breakdown as the adapter specifies) → R5b
       - MIXED FR/ARCH + code/test            → re-run the task-level step (speckit.checklist →
         speckit.tasks / writing-plans task breakdown) → R5b
       - ONLY SEC-*/CODE-*/TEST-*             → go straight to R6
       R5b — after ANY artifact regeneration, re-run the Stage 02 self-review gate (read-only)
       before the fix iteration (operating rule 6).
  R6 — Apply the fixes via the provider's style:
       - github-speckit: re-invoke speckit.implement with a focused correction prompt built from
         the corrective action list (never direct file edits as a substitute)
       - superpowers: edit the specific files named in the fixes directly, following the TDD
         cycle for behavior changes; never delegate code-only/test-coverage fixes back to the
         implementation skill
       Do NOT end the turn after applying fixes — continue the flow immediately.
  R7 — Superpowers: re-run verification-before-completion scoped to the touched tasks/tests, then
       go to R1 (never to R0 — r0_completed). Github-speckit: go straight to R1.
```

## Loop Invariants

- Never exit with `status = failed`; never end a turn or write a prose summary after one — the
  next action is always the next fix iteration.
- Never ask the user for help; the only stop is the circuit breaker.
- Retain only `state_file`, the top `fixes[]`, and the one category file needed for the current fix.
- On iteration 3+ with the same failure, escalate fix depth (rewrite the method, not patch a line).
- Log each iteration: `[Review loop #N] status=failed, scope=<code|tasks|plan>, fixing: <summary>`.

## Exit Routing

`status = pass` from `speckit-code-review` is the **only** normal exit from Stage 03. When it
fires, immediately load and execute [stage-04-finish.md](stage-04-finish.md) **in the same turn**
— no summary, no turn end, no user question before Stage 04 begins. **Never invoke
`finishing-a-development-branch` here — it fires only in Stage 04 after final approval.**

- **Default mode:** Stage 04 human review + commit (mandatory, never skipped).
- **`--yolo` mode:** Stage 04 YOLO auto-commit path.

Do not wait for a user message to trigger Stage 04. The transition is automatic and immediate.