# Token Optimization Test Cases

Scope: validate the results of the token-optimization work on `speckit-auto`, `speckit-code-review`,
and `jira-to-speckit`. Two layers:

1. **Static measurement** (deterministic, repeatable via `wc -c`) — proves instruction-payload
   reduction and catches regressions.
2. **Behavioral regression** — proves the optimization changed cost, not correctness.

Baseline: `docs/token-baseline-report.md` (commit `d2a9fb1`).
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

Baseline total: 225,875 chars (44 files, incl. READMEs/assets).

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

Baseline result: 108,720 chars ≈ 27.2k tok (matches report §1 within rounding).

Variants (recompute by adding/removing manifest rows):

| Variant | Delta vs primary |
|---|---|
| superpowers provider | replace `references/github-speckit/*` rows with `references/superpowers/*` |
| manual mode (no `--issue`) | drop `jira-to-speckit/SKILL.md` and `execution-report.md` |

### A.3 Entry bundle metric

Sum of the Entry group only. Baseline: 28,690 chars ≈ 7.2k tok.

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

All existing cases in [`test-cases.md`](test-cases.md) must still pass (T01–T25, H01–H11). The
following are optimization-specific additions:

| ID | Scenario | Preconditions | Steps | Expected result |
|---|---|---|---|---|
| TC-OPT-01 | Rules still enforced after dedup | Optimized commit | Run T20 (review failure loop) and attempt to stop the agent mid-Stage 03 with a distracting user message | Agent continues the loop autonomously; no-stop semantics identical to baseline |
| TC-OPT-02 | Entry dispatch intact after entry slimming | Optimized commit | Run T05 (first-run selection) | Provider resolution, persistence, same-turn continue all unchanged |
| TC-OPT-03 | Conditional load actually conditional | Optimized commit | Trigger single-category review failure (e.g. SEC-only) | Only the security area ref + security detail file are loaded; other four refs never enter context |
| TC-OPT-04 | Jira snapshot bypasses context | Optimized commit, `--issue` | Run T09 | Raw Jira JSON never appears in any tool result visible to the model; compact brief still ≤2.5k chars; snapshot file on disk complete |
| TC-OPT-05 | R5 scoped regeneration | Optimized commit | Inject one FR-* gap post-review | Only the affected package/slice artifacts regenerate; unaffected tasks/plan sections unchanged on disk |
| TC-OPT-06 | architecture.md chain survives | Optimized commit, `docs/guidelines/architecture.md` present | Full run | Project Context built in Stage 01; `repo_map` present in plan/tasks; review findings carry `guideline_source` tag (baseline report §5) |
| TC-OPT-07 | Resume after stage compaction (if P1-3 done) | Optimized commit, mid-run interruption | Interrupt after Stage 02; new turn | Run state rehydrated from `.speckit/run-state.json`; pipeline resumes at Stage 03 without re-asking provider/mode |
| TC-OPT-08 | Validator + spec still green | Optimized commit | `python3 tools/validate_skills.py` and `python3 tools/test_validate_skills.py` | Exit 0; README badges match bumped versions |

Pass criteria: all static targets in baseline report §6 met (or documented why not), all T/H cases
pass, all TC-OPT cases pass.

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
| Primary manifest total (chars/tok) | 108,720 / ~27.2k | ~$0.082 | | | | | | |
| Entry bundle (chars/tok) | 28,690 / ~7.2k | ~$0.022 | | | | | | |
| All-skill .md census (chars) | 225,875 | ~$0.17 | | | | | | |
| Frontmatter descriptions (chars/tok) | ~1,930 / ~480 | ~$0.0014 | | | | | | |
| Duplication spot-check (lines) | 44 | — | | | — | | | |
| speckit-code-review area refs per iteration | 5 | ~$0.0081 | | | | | | |

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
- TC-OPT-01..08: <results>

## Verdict

<overall statement: targets met / partially met, with notes>
```
