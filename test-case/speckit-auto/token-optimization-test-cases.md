# Token Optimization Test Cases

Scope: validate the results of the token-optimization work on `speckit-auto`, `speckit-code-review`,
and `jira-to-speckit`. Two layers:

1. **Static measurement** (deterministic, repeatable via `wc -c`) — proves instruction-payload
   reduction and catches regressions.
2. **Behavioral regression** — proves the optimization changed cost, not correctness.

Baseline: `docs/token-baseline-report.md` (commit `ec7a85f`, re-baselined after the worktree-support
merge — see report §7 for the delta from the original `d2a9fb1` baseline).
Post-optimization comparison report template: appendix of this file, filled into
`docs/token-optimization-comparison.md` when optimization completes.

Conversion: tokens ≈ chars / 4.

---

## A. Static Measurement Procedure (deterministic)

Run on any commit; record results in the measurement table below.

### A.1 File size census

```bash
find speckit-auto speckit-code-review jira-to-speckit -name "*.md" -not -path "*/.state/*" \
  | xargs wc -c | sort -n
```

Baseline total: 227,101 chars (45 files, incl. READMEs/assets; +1,226 vs pre-worktree merge).

### A.2 Per-run load manifest (primary scenario: github-speckit, `--issue`, default mode)

Sum the sizes of exactly these files (baseline manifest; update the list if the optimization
intentionally adds/removes/relocates a load point, and note the change):

| Group | Files (paths relative to skill folder) |
|---|---|
| Entry | `speckit-auto/SKILL.md`, `references/shared/host-adaptation.md`, `references/integration-mode.md`, `references/shared/global-rules.md`, `references/github-speckit/provider-rules.md` |
| Stage 01 | `references/github-speckit/stage-01-preflight-intake.md`, `references/shared/branching.md`, `references/shared/intake.md`, `references/shared/preflight-guidelines-context.md`, `references/shared/scratch-hygiene.md`, `references/shared/execution-report.md` |
| Stage 02 | `references/github-speckit/stage-02-spec-design-flow.md`, `references/github-speckit/review-interview.md` |
| Stage 03 | `references/github-speckit/stage-03-implement-and-code-review-loop.md` |
| Stage 04+06 | `references/github-speckit/stage-04-human-review-and-commit.md`, `references/github-speckit/stage-06-spec-completion.md`, `references/shared/commit.md` |
| Sub-skill: jira | `jira-to-speckit/SKILL.md` |
| Sub-skill: review | `speckit-code-review/SKILL.md`, its 5 `references/*.md` area files |

```bash
# primary scenario total (run from repo root)
cat speckit-auto/SKILL.md \
    speckit-auto/references/shared/host-adaptation.md \
    speckit-auto/references/integration-mode.md \
    speckit-auto/references/shared/global-rules.md \
    speckit-auto/references/github-speckit/provider-rules.md \
    speckit-auto/references/github-speckit/stage-01-preflight-intake.md \
    speckit-auto/references/shared/branching.md \
    speckit-auto/references/shared/intake.md \
    speckit-auto/references/shared/preflight-guidelines-context.md \
    speckit-auto/references/shared/scratch-hygiene.md \
    speckit-auto/references/shared/execution-report.md \
    speckit-auto/references/github-speckit/stage-02-spec-design-flow.md \
    speckit-auto/references/github-speckit/review-interview.md \
    speckit-auto/references/github-speckit/stage-03-implement-and-code-review-loop.md \
    speckit-auto/references/github-speckit/stage-04-human-review-and-commit.md \
    speckit-auto/references/github-speckit/stage-06-spec-completion.md \
    speckit-auto/references/shared/commit.md \
    jira-to-speckit/SKILL.md \
    speckit-code-review/SKILL.md \
    speckit-code-review/references/business-gap.md \
    speckit-code-review/references/code-quality.md \
    speckit-code-review/references/security.md \
    speckit-code-review/references/architecture.md \
    speckit-code-review/references/unit-test-coverage.md \
    | wc -c
```

Baseline result: 109,854 chars ≈ 27.5k tok (matches report §1 within rounding).

Variants (recompute by adding/removing manifest rows):

| Variant | Delta vs primary |
|---|---|
| superpowers provider | replace `references/github-speckit/*` rows with `references/superpowers/*` |
| manual mode (no `--issue`) | drop `jira-to-speckit/SKILL.md` and `execution-report.md` |

### A.3 Entry bundle metric

Sum of the Entry group only. Baseline: 28,763 chars ≈ 7.2k tok.

### A.4 Frontmatter description census

```bash
awk '/^description:/{flag=1} flag{print} /^---$/ && NR>1{flag=0}' \
  speckit-auto/SKILL.md speckit-code-review/SKILL.md jira-to-speckit/SKILL.md | wc -c
```

Baseline: ~1,930 chars ≈ 480 tok permanent skill-list overhead.

### A.5 Duplication spot-check

Count restatements of the no-stop/premise rule:

```bash
grep -rniE "no-stop|never end the turn|stop condition|same turn" \
  speckit-auto/SKILL.md speckit-auto/references | wc -l
```

Baseline: 44 matching lines across files. Post-optimization expect a significant drop with zero
behavioral change (verified by section C).

---

## B. Dynamic Measurement Procedure (controlled run)

Instrumented manually on a fixed scenario. Preconditions: throwaway git repo with a small
pre-seeded codebase, `docs/guidelines/architecture.md` present, provider pre-installed
(github-speckit), `.env` Jira creds for a fixed medium-size ticket (or manual mode with a fixed
500-word requirement).

Protocol:

1. Run the full pipeline end-to-end once on baseline commit; record:
   - tool call count per stage
   - est. peak context (host usage display if available)
   - billing/usage total if the host reports it
   - count of review-loop iterations
2. Re-run identically on optimized commit.
3. Record both in the comparison template (appendix).

---

## C. Behavioral Regression Cases

All existing cases in [`test-cases.md`](test-cases.md) (T01–T25, H01–H11) **and**
[`worktree-support.md`](worktree-support.md) (WT01–WT21, added by the worktree merge) must still
pass. The following are optimization-specific additions:

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| TC-OPT-01 | Rules still enforced after dedup | Optimized commit | Run T20 (review failure loop) and attempt to stop the agent mid-Stage 03 with a distracting user message | Agent continues the loop autonomously; no-stop semantics identical to baseline |
| TC-OPT-02 | Entry dispatch intact after entry slimming | Optimized commit | Run T05 (first-run selection) | Provider resolution, persistence, same-turn continue all unchanged |
| TC-OPT-03 | Conditional load actually conditional | Optimized commit | Trigger single-category review failure (e.g. SEC-only) | Only the security area ref + security detail file are loaded; other four refs never enter context |
| TC-OPT-04 | Jira snapshot bypasses context | Optimized commit, `--issue` | Run T09 | Raw Jira JSON never appears in any tool result visible to the model; compact brief still ≤2.5k chars; snapshot file on disk complete |
| TC-OPT-05 | R5 scoped regeneration | Optimized commit | Inject one FR-* gap post-review | Only the affected package/slice artifacts regenerate; unaffected tasks/plan sections unchanged on disk |
| TC-OPT-06 | architecture.md chain survives | Optimized commit, `docs/guidelines/architecture.md` present | Full run | Project Context built in Stage 01; `repo_map` present in plan/tasks; review findings carry `guideline_source` tag (baseline report §5) |
| TC-OPT-07 | Resume after stage compaction (if P1-3 done) | Optimized commit, mid-run interruption | Interrupt after Stage 02; new turn | Run state rehydrated from `.speckit/run-state.json` **inside the linked worktree**; `worktree_path` restored and all further stage calls execute from the worktree (never the base checkout — see WT17/WT21); pipeline resumes at Stage 03 without re-asking provider/mode |
| TC-OPT-08 | Validator + spec still green | Optimized commit | `python3 tools/validate_skills.py` and `python3 tools/test_validate_skills.py` | Exit 0; README badges match bumped versions |
| TC-OPT-09 | Worktree bootstrap script (if P2-10 done) | Optimized commit, fresh repo state | Run Stage 01 gate | Single script invocation returns compact JSON (`branch`, `worktree_path`, `base`, `warnings`); WT01–WT15 behaviors unchanged; tool-call count for the gate ≤ 2 |

Pass criteria: all static targets in baseline report §6 met (or documented why not), all T/H cases
pass, all TC-OPT cases pass.

---

## D. Incremental Review-Loop Optimization Cases (execution-based)

Covers the review-loop token optimization (incremental scope, diff digest, pinned checklist,
granular invalidation, task delta detection) by **actually running the `speckit-auto` skill
through a coding agent** on the build-a-to-do-app scenario, then validating the on-disk outcomes.

Driver: `tools/test_speckit_auto.py` (stdlib only; requires an agent CLI with credentials).

```bash
python3 tools/test_speckit_auto.py                         # run via OpenCode (default)
python3 tools/test_speckit_auto.py --agent claude          # run via Claude Code
python3 tools/test_speckit_auto.py --model opencode-go/deepseek-v4-pro
python3 tools/test_speckit_auto.py --timeout 1200 --keep   # keep the workspace for inspection
python3 tools/test_speckit_auto.py --json
```

What the driver does, in order:

1. Copies the current repo's `speckit-auto`, `speckit-code-review`, `jira-to-speckit` into the
   agent's skill directory.
2. Seeds a fresh git repo as a minimal to-do app (`package.json` with `node --test`,
   `docs/guidelines/architecture.md`, one commit) — provider defaults to `superpowers` (its skills
   are already installed).
3. Invokes the agent headlessly with `Run the speckit-auto skill with --yolo on this requirement:
   <to-do requirement>`.
4. Validates the artifacts the pipeline should have produced and prints a coverage report.

Scenario: **build a to-do application** (create/edit/complete/delete tasks, organize into lists,
set due dates; plain Node.js, no external deps).

| ID | Check | Expected result |
|---|---|---|
| V01 | spec produced | `specs/<feature>/spec.md` exists (brainstorming design spec) |
| V02 | plan produced | `specs/<feature>/plan.md` exists (writing-plans plan) |
| V03 | implementation | code written under `src/` |
| V04 | tests | at least one `*.test.js` (TDD via `node --test`) |
| V05 | commits | ≥1 commit on top of the seed commit |
| V06 | run-state | `.speckit/run-state.json` persisted |
| V09 | review gate | `.speckit/review-*/state.json` written (speckit-code-review ran) |
| V07 | isolation | linked worktree under `.worktrees/` or a non-`main` feature branch |
| V08 | completion | agent run finished without timeout; token cost reported |

Pass criteria: `python3 tools/test_speckit_auto.py` exits 0 (all checks PASS). A non-zero exit or
any FAIL documents exactly which pipeline artifact was not produced. Validation runs against the
Stage 01 linked worktree, not the base checkout (the pipeline always executes inside the worktree).

Note: this driver is a local/developer tool — it needs agent credentials, so it is intentionally
not part of CI.

---

## Appendix: Comparison Report Template

Copy to `docs/token-optimization-comparison.md` and fill after optimization. Every cell must come
from re-running section A/B on the stated commits.

```markdown
# Token Optimization Comparison Report

Baseline commit: <sha>   Optimized commit: <sha>   Date: <date>

Cost basis: Claude Sonnet 4.6, Anthropic list prices — input $3.00/MTok, output $15.00/MTok,
cache read $0.30/MTok. Cost cells = input tokens × $3.00/MTok (chars/4 ≈ tokens).

## Static (section A)

| Metric | Baseline | Baseline cost | Optimized | Optimized cost | Δ cost | Δ % | Target (report §6) | Met? |
|---|---|---|---|---|---|---|---|---|
| Primary manifest total (chars/tok) | 109,854 / ~27.5k | ~$0.082 | | | | | | |
| Entry bundle (chars/tok) | 28,763 / ~7.2k | ~$0.022 | | | | | | |
| All-skill .md census (chars) | 227,101 | ~$0.17 | | | | | | |
| Frontmatter descriptions (chars/tok) | ~1,930 / ~480 | ~$0.0014 | | | | | | |
| Duplication spot-check (lines) | 44 | — | | | — | | | |
| speckit-code-review area refs per iteration | 5 | ~$0.0081 | | | | | | |
| Stage 01 gate tool calls (worktree bootstrap) | 7–12 | — | | | — | | | |

## Dynamic (section B, controlled run)

| Metric | Baseline | Optimized | Δ | Δ % |
|---|---|---|---|---|
| Tool calls (total / per stage) | | | | |
| Review-loop iterations | | | | |
| Peak context (est. or reported) | | | | |
| Billed input tokens (if reported by host) | | | | |
| **Est. input cost** ($3.00/MTok) | | | | |
| **Est. output cost** (output tok × $15.00/MTok) | | | | |
| **Est. total cost per run** | | | | |

Compare Δ % against the projections in
[`docs/token-optimization-plan.md`](../../docs/token-optimization-plan.md) §5
(−40–50% uncached run cost, −35–45% cached, −32–39% static instructions).

## Behavioral

- test-cases.md T01–T25: <pass/fail count>
- Host checks H01–H11: <pass/fail count>
- Worktree checks WT01–WT21: <pass/fail count>
- TC-OPT-01..09: <results>

## Verdict

<overall statement: targets met / partially met, with notes>
```
