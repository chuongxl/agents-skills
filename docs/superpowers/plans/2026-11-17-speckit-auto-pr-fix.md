# Speckit Auto PR-fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix existing PRs through the normal pipeline without changing their identity.

**Architecture:** Add PR-fix routing to the generic skill and then update the client caller to
pass the PR URL. Existing feature and Jira runs retain their behavior. The client PR depends on
the updated skill being installed in the target repository.

**Tech Stack:** Markdown agent skills, Git, GitHub CLI, Node.js ESM, Node test runner.

**Spec:** `docs/superpowers/specs/2026-11-17-speckit-auto-pr-fix-design.md` in agents-skills.

## Global Constraints

- `--pr-fix <PR URL>` requires an open PR and a fix request; never create another PR.
- Preserve a supplied linked worktree and branch; manual runs create one from the fetched PR head.
- Do not force-push, discard user edits, or push when the remote head has diverged.
- Use the existing run-event schema, run ID, provider selection, approvals, and verification opt-in.
- Preserve ordinary feature and Jira behavior when the flag is absent.
- Skill files remain self-contained and use no new third-party dependencies.

## Review Focus

- Missing PR URL or fix request: stop with an actionable diagnostic before modifying files.
- Head belongs to a fork or cannot be pushed: resolve the correct repository or stop safely.
- Another process moves the remote head: never force-push or overwrite its commits.
- No matching spec: perform a real review without inventing a spec-based pass.
- Pre-existing unrelated edits or formatting failures: preserve edits and classify checks honestly.

---

### Task 1: PR identity and worktree routing

**Files:**
- Modify: `speckit-auto/SKILL.md`, `speckit-auto/references/pipeline/stage-01-intake.md`,
  `speckit-auto/references/shared/operating-rules.md`, `speckit-auto/README.md`
- Modify: `test-case/speckit-auto/worktree-support.md`, `test-case/speckit-auto/test-cases.md`

**Interfaces:**
- Consumes: `--pr-fix <absolute PR URL>`, fix request, optional existing worktree/branch, optional
  run ID, and the existing integration configuration.
- Produces: run state with validated PR base, head repository, head branch, fetched head SHA,
  actual worktree and branch, fix request, and run ID for later stages.

- [ ] Add agent-execution scenarios asserting manual creation from the PR head, supplied-worktree
  reuse without a checkout/rename/move, missing arguments, a closed PR, mismatched worktree,
  an occupied PR branch, inaccessible fork, and unchanged feature/Jira behavior.
- [ ] Run the scenarios against the unmodified skill and record the failing behaviors. Use an
  isolated disposable Git repository and controlled GitHub fixtures; do not touch live PRs.
- [ ] Define flag dispatch and the Stage 01 PR path, including read-only resolution and checks
  before any destructive operation. Validate that the supplied branch contains the fetched head;
  never infer a writable push target from a display URL.
- [ ] Rerun scenarios and record outcomes. Run `python3 tools/validate_skills.py` and
  `python3 tools/test_validate_skills.py` from agents-skills; both must pass.
- [ ] Commit this task with a Conventional Commit and the required Copilot co-author trailer.

### Task 2: Spec, review, checks, and existing-PR finish

**Files:**
- Modify: `speckit-auto/references/pipeline/stage-02-spec-design.md`,
  `stage-03-implement-review.md`, `stage-04-finish.md`, `stage-05-verification.md`,
  `stage-06-finish.md`, `speckit-auto/references/shared/commit.md`
- Modify: `speckit-auto/references/providers/github-speckit.md`,
  `speckit-auto/references/providers/superpowers.md` where provider routing differs.
- Modify: `test-case/speckit-auto/test-cases.md`

**Interfaces:**
- Consumes: Task 1 PR state and the existing provider and verification configuration.
- Produces: scoped changes, review/check evidence, one terminal event, and a safe update to
  the resolved existing PR branch. With no spec, report direct-review evidence, not a
  `speckit-code-review` pass.

- [ ] Add execution scenarios covering relevant spec reuse, requirement changes, no matching
  spec, default approvals, YOLO, verification opt-in and unavailable verification, a stale
  remote head, a failed push, unrelated dirty files, and pre-existing formatting failures.
- [ ] Run the scenarios against the old stage instructions and record failures. Include a
  sandbox remote with a second clone that advances the head before push.
- [ ] Route the existing stages according to the spec. Verify changed-file formatting and
  classify a full-check failure as pre-existing only after a baseline check proves it.
  Keep the event history truthful and never publish unrelated edits.
- [ ] Re-run scenarios, both skill validation commands from Task 1, and
  `git diff --check`; confirm feature and Jira scenarios remain unchanged.
- [ ] Update the skill metadata version and root README badge together. Commit the task with a
  Conventional Commit and the required Copilot co-author trailer.

### Task 3: Client integration

**Files:** In the separate ticket-pilot worktree:
- Modify: `agent/src/worker.js`, `agent/test/prFix.test.js`, `agent/test/pr-fix.e2e.test.js`
- Update the installed `.agents/skills/speckit-auto/` copy to the reviewed upstream skill
  version if it is tracked and used at runtime.

**Interfaces:**
- Consumes: Task 1 flag contract and the existing `prFixPrompt` arguments.
- Produces: owner-comment and failing-check prompts that include
  `/speckit-auto --pr-fix <PR URL> --yolo`, the unchanged run ID and worktree/branch context.
  Check log text remains data, not instructions.

- [ ] Change the existing prompt unit and e2e assertions to require the flag and URL for both
  trigger types, preserve `--run-id`, and preserve the worktree and push target. Run
  `cd agent && node --disable-warning=ExperimentalWarning --test test/prFix.test.js test/pr-fix.e2e.test.js`
  and observe the expected failures before implementation.
- [ ] Update `prFixPrompt` without weakening untrusted-log handling or changing ticket prompts.
  Mirror the reviewed upstream skill using the repository's existing installation mechanism.
- [ ] Re-run the targeted tests, `npm run lint`, and `npm run test:coverage` from `agent/`.
  Unset inherited GitHub-token and internal-background-child variables for isolated tests.
  Record real failures and coverage.
- [ ] Commit this task with a Conventional Commit and the required Copilot co-author trailer.

### Task 4: Cross-repository delivery

**Files:**
- Review both branch diffs and the scenario evidence; do not add generated scratch files.

**Interfaces:**
- Consumes: reviewed Task 2 skill and Task 3 client commits.
- Produces: one PR in `chuongxl/agents-skills` and one in `chuongxl/ticket-pilot`, linked by
  the skill-version dependency and rollout order.

- [ ] Exercise the installed skill and client together against a disposable PR fixture.
  Verify the existing remote PR branch advances, no new PR is requested, and the terminal
  event reflects the actual push result.
- [ ] Check both worktrees for unrelated changes, run each repository's required checks,
  and review both diffs. State any unavailable validation rather than claiming success.
- [ ] Push each feature branch without force and create its PR. The client PR must state that
  the updated skill must be installed before the client change is enabled.
