# Token Usage Baseline Report — speckit-auto Pipeline

**Date:** 2026-08-16
**Baseline commit:** `ec7a85f` (branch `token-optimization`; re-baselined after merging
origin/develop `0d7e008` — "speckit-auto worktree support". Prior baseline `d2a9fb1`; see §7
for the worktree-merge delta.)
**Scope:** `speckit-auto`, `speckit-code-review`, `jira-to-speckit`
**Purpose:** Frozen pre-optimization measurements. The post-optimization comparison report
(`docs/token-optimization-comparison.md`, to be created when optimization completes) must be
produced by re-running the procedure in
[`test-case/speckit-auto/token-optimization-test-cases.md`](../test-case/speckit-auto/token-optimization-test-cases.md)
against both this baseline commit and the optimized commit, then filling the comparison template.

Conversion basis: ~4 chars/token (English prose + markdown). Dynamic figures are estimates from
instruction analysis, not instrumented counts — the test case defines how to refine them.

**Cost basis (Anthropic list pricing, Claude Sonnet 4.6):** input **$3.00 / MTok**, output
**$15.00 / MTok**, cached input read **$0.30 / MTok** (10% of input), cache write 1.25× for 5 min.
All cost figures below are **input-token costs** unless stated otherwise; output cost is covered
in §3. If Anthropic publishes different Sonnet 4.6 rates, rescale every cost cell linearly.

---

## 1. Static Skill Instruction Load Per Run

### 1.1 github-speckit provider, `--issue` mode, default mode (primary scenario)

| Load point | File | chars | ~tokens | ~cost (input) |
|---|---|---|---|---|
| Entry | `speckit-auto/SKILL.md` | 8,891 | 2,200 | $0.0066 |
| Entry | `references/shared/host-adaptation.md` | 5,224 | 1,300 | $0.0039 |
| Entry | `references/integration-mode.md` | 4,048 | 1,000 | $0.0030 |
| Entry | `references/shared/global-rules.md` | 8,193 | 2,050 | $0.0061 |
| Entry | `references/github-speckit/provider-rules.md` | 2,407 | 600 | $0.0018 |
| Stage 01 | `references/github-speckit/stage-01-preflight-intake.md` | 5,459 | 1,365 | $0.0041 |
| Stage 01 | `references/shared/branching.md` | 5,095 | 1,275 | $0.0038 |
| Stage 01 | `references/shared/intake.md` | 8,242 | 2,060 | $0.0062 |
| Stage 01 | `references/shared/preflight-guidelines-context.md` | 4,432 | 1,100 | $0.0033 |
| Stage 01 | `references/shared/scratch-hygiene.md` | 1,174 | 300 | $0.0009 |
| Stage 01 | `references/shared/execution-report.md` | 1,356 | 350 | $0.0011 |
| Stage 02 | `references/github-speckit/stage-02-spec-design-flow.md` | 7,158 | 1,800 | $0.0054 |
| Stage 02 | `references/github-speckit/review-interview.md` | 2,891 | 720 | $0.0022 |
| Stage 03 | `references/github-speckit/stage-03-implement-and-code-review-loop.md` | 8,854 | 2,200 | $0.0066 |
| Stage 04+06 | `stage-04` + `stage-06` + `references/shared/commit.md` | 5,707 | 1,430 | $0.0043 |
| **Subtotal** | | **79,131** | **~19,800** | **~$0.059** |

### 1.2 Sub-skill instructions

| Skill | Load | chars | ~tokens | ~cost (input) |
|---|---|---|---|---|
| `jira-to-speckit` | `SKILL.md` (+ `references/JIRA_API.md` 2,280 on fallback only) | 11,551 | ~2,900 | ~$0.0087 |
| `speckit-code-review` | `SKILL.md` | 8,246 | ~2,060 | ~$0.0062 |
| `speckit-code-review` | 5 area refs, serial load/discard | 10,926 | ~2,700 | ~$0.0081 |
| **Subtotal** | | | **~9,200** | **~$0.027** |

### 1.3 Baseline totals by variant

| Variant | Static instruction tokens | ~cost (input, per pass) |
|---|---|---|
| github-speckit, `--issue`, default (primary) | **~27.5k** | **~$0.082** |
| superpowers provider refs (~96k chars) + sub-skills | **~33k** | ~$0.099 |
| Manual mode (no `--issue`) | ~24k (saves ~3.3k) | ~$0.073 |

Note: this is the one-pass cost of the instructions. Because the transcript is re-sent on every
call, instructions actually bill once per subsequent API call — the multiplier is what §3 captures.

## 2. Dynamic Runtime Content (estimates)

| Source | Est. per occurrence | ~cost (input) per occurrence |
|---|---|---|
| Raw Jira payload in tool result (input cap 12k chars) | 1k–3k | $0.003–$0.009 |
| Compact brief (cap 2.5k chars) | ~600 | ~$0.0018 |
| Worktree gate setup (base sync, worktree add/list, `.gitignore` edit, rename/move align) — +3–6 bash calls early in run | ~1k instr + 3–6 round-trips | +$0.05–0.25 uncached / +$0.01–0.03 cached per run |
| spec.md / plan.md / tasks.md written + re-read across stages | 3k–15k per artifact set | $0.009–$0.045 |
| Repo-installed `speckit.*` stage skills (8 invocations) | 9k–15k | $0.027–$0.045 |
| Code reads/edits in Stage 03 + fix iterations | 20k–60k+ | $0.06–$0.18 |
| speckit-code-review iteration (diff + spec + refs) | 5k–20k; ×2–4 iterations | $0.015–$0.06 each |
| Interview round-trips (default mode) | 1k–2k each | $0.003–$0.006 each |

## 3. Run-Level Totals and Cost (estimates)

Token totals:

- **Peak context footprint:** ~45k–120k tokens (medium feature, 2–3 review iterations).
- **Cumulative billed input tokens** (same-turn mandate, now ~35–70 tool calls incl. worktree gate):
  **1M–3.2M** uncached; ~150k–430k effective with prompt caching.

Estimated cost per full run (Claude Sonnet 4.6, Anthropic list prices):

| Scenario | Input tok | Input cost | Output tok (est. 5–15% of input) | Output cost | **Total** |
|---|---|---|---|---|---|
| Uncached, low end (1M in / 50k out) | 1M | $3.00 | 50k | $0.75 | **$3.75** |
| Uncached, high end (3M in / 300k out) | 3M | $9.00 | 300k | $4.50 | **$13.50** |
| With prompt caching (150k–400k effective in) | 150k–400k | $0.45–$1.20 | 50k–300k | $0.75–$4.50 | **$1.20–$5.70** |

Caching assumptions: growing transcript prefix served as cache reads at $0.30/MTok plus cache
writes at 1.25×; output is never cached. Static instructions (~28k tok) are the most cache-stable
part of the prefix — which is why shrinking them mainly helps the uncached and first-call costs,
while §3-style stage-boundary compaction is what shrinks the cached bill too.

## 4. Key Findings (inefficiencies targeted by the plan)

1. **Rule duplication** — no-stop-zone premise restated ~6×; ~30–40% overlap across global rules /
   provider rules / stage files ≈ ~6k tok/run.
2. **Heavy entry load** — 4 files (~5.1k tok) before Stage 01 work; host-adaptation ~60%
   install-recovery tables needed only on failure.
3. **"Discard from context" is mostly aspirational** — transcript tokens stay billed on every
   subsequent call on stateless hosts.
4. **Raw Jira payload enters model context** before compaction; only the disk snapshot bypasses it.
5. **R5 full regeneration** — any FR-*/ARCH-* fix re-runs plan → checklist → tasks → analyze
   (≈ +8k–20k tok/iteration) regardless of gap size.
6. **speckit-code-review reloads all 5 area refs every iteration** even for single-category failures.
7. **Frontmatter descriptions** (~150 words each) permanently occupy every host session skill list
   (~160 tok × 3 skills).

## 5. architecture.md Guidance Chain — Verified Intact at Baseline

Confirmed at `d2a9fb1` that `docs/guidelines/architecture.md` still drives design, implementation,
and review in both providers:

| Phase | Enforcement point (baseline line refs) |
|---|---|
| Load (Stage 01, once) | `speckit-auto/references/shared/preflight-guidelines-context.md:8` — parses into Project Context (`arch_pattern`, `dependency_rule`, `repo_map`, `linked_guidelines`, `summary`), cached per run |
| Design (Stage 02) | `references/github-speckit/stage-02-spec-design-flow.md:35-39,58-71,101`; superpowers variant `:62-145` — `summary`/`repo_map`/cached guidelines injected into `specify`/`plan`/`tasks`; self-review gate check 4 verifies workspace assignment |
| Implementation (Stage 03) | `references/github-speckit/stage-03-implement-and-code-review-loop.md:8-16`; superpowers variant `:10-13` — Project Context injected into `speckit.implement` and R5 reruns |
| Review | `speckit-code-review/SKILL.md:71-74` + `references/project-guidelines-review.md` — conditional guidelines pass; findings tagged `guideline_source` |

Constraints on optimization: the Project Context mechanism and this chain must survive every
optimization change (regression check TC-ARCH-01 in the test cases).

Note: two distinct "architecture.md" files exist in review — the skill's own built-in
`speckit-code-review/references/architecture.md` (always loaded, `ARCH-*`) and the project's
`docs/guidelines/architecture.md` (conditional). Both active at baseline.

## 6. Optimization Targets (from `docs/token-optimization-plan.md`)

| ID | Change | Baseline metric | Target |
|---|---|---|---|
| P1-1 | Deduplicate canonical rules | ~19.4k static (primary) | −25–35% |
| P1-2 | Slim entry bundle | 28,690 chars ≈ 7.2k tok at entry (SKILL + host-adaptation + integration-mode + global-rules + provider-rules) | −3k |
| P1-3 | Stage-boundary compaction | monotonic transcript growth | up to −50% cumulative |
| P1-4 | Review selective refs | 5 refs (~2.7k tok) every iteration | −1.5–2.5k per iteration |
| P2-5 | Jira scripted fetch | raw payload 1k–3k in context | −1k–3k per Jira run |
| P2-6 | R5 scoped regeneration | +8k–20k per FR/ARCH fix | regenerate affected slice only |
| P2-7 | Artifact digest | full spec+plan resent per stage | −2k–6k per stage invocation |
| P3-8 | Trim frontmatter descriptions | ~160 tok × 3 skills permanent | ~2 lines each |
| P3-9 | Token accounting in execution report | none | observability |

All changes must keep `python3 tools/validate_skills.py` green, bump `metadata.version` + sync
root README badges, and preserve behavior of every test case in
`test-case/speckit-auto/test-cases.md` plus TC-ARCH-01.

---

## 7. Re-baseline Delta — Worktree Support Merge (`d2a9fb1` → `ec7a85f`)

Origin/develop `0d7e008` ("speckit-auto worktree support") reversed global rule 3: pipeline
execution now **requires** a linked git worktree at `<repo-root>/.worktrees/<branch-name>`,
created/reused at the Stage 01 gate, with rename/move alignment after intake. Effects on this
baseline:

| Item | Before | After | Δ |
|---|---|---|---|
| Primary manifest (chars / ~tok) | 108,720 / ~27.2k | 109,854 / ~27.5k | +1,134 / +0.3k |
| Entry bundle (chars) | 28,690 | 28,763 | +73 (global-rules only) |
| All-skill .md census (chars) | 225,875 | 227,101 | +1,226 |
| `branching.md` (chars) | 4,416 | 5,095 | +679 — worktree steps 5–8 |
| `intake.md` (chars) | 8,085 | 8,242 | +157 — `worktree_path` state, rename/move note |
| `speckit-code-review/SKILL.md` (chars) | 8,043 | 8,246 | +203 — WT21 cwd rule |
| superpowers refs net (chars) | — | — | −378 (rule-3 rewrite deduplicated) |
| Duplication spot-check (lines) | 44 | 44 | unchanged |
| Dynamic: Stage 01 gate tool calls | ~4–6 | ~7–12 | +3–6 calls (worktree add/list, .gitignore, rename, move) |

Run-level cost effect: +$0.05–0.25 uncached / +$0.01–0.03 cached per run (extra early-run
round-trips). §3 ranges widened accordingly. New optimization opportunity P2-10 (one-shot
worktree bootstrap script) added to the plan to recover this.

Behavioral regression surface added: `test-case/speckit-auto/worktree-support.md` WT01–WT21 now
part of the must-pass set (see test-case doc §C).
