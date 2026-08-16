# Token Usage Analysis & Optimization Plan — speckit-auto Pipeline

**Date:** 2026-08-15 (re-analyzed 2026-08-16 after worktree-support merge `ec7a85f`)
**Scope:** `speckit-auto`, `speckit-code-review`, `jira-to-speckit`
**Status:** Analysis only — no changes applied yet. Implementation starts after explicit confirmation.

Re-analysis note: origin/develop merged a worktree-support change (global rule 3 now *requires* a
linked git worktree at `.worktrees/<branch-name>`). Static instruction load rose +1,134 chars
(manifest 108,720 → 109,854) and Stage 01 gained 3–6 tool calls; superpowers refs net-shrank
−378 chars. Baseline figures below were refreshed in
[`docs/token-baseline-report.md`](token-baseline-report.md) §7; projections in §5 are unchanged
in percentage terms. New item P2-10 recovers the worktree-gate round-trip cost.

Analysis basis: all 44 markdown files across the three skills (~226 KB total), the load-on-demand
flow defined in `speckit-auto/SKILL.md` Entry Dispatch + Stage Router, and the github-speckit
provider reference chain. Token estimates use ~4 chars/token for English prose + markdown.

**Cost basis (Claude Sonnet 4.6, Anthropic list prices):** input $3.00/MTok, output $15.00/MTok,
cache read $0.30/MTok. Frozen baseline cost figures live in
[`docs/token-baseline-report.md`](token-baseline-report.md) — per-pass static instructions
~$0.084; full run **$3.75–$13.50 uncached**, **$1.20–$5.70 with prompt caching**. Projected
post-optimization costs and % savings are in §5 of this plan.

---

## 1. What Gets Loaded Per Run

The pipeline is progressive-disclosure by design (load-on-demand, discard-on-exit), but within a
single run almost every file passes through the context window at least once.

### 1.1 Static skill instructions — github-speckit provider, `--issue`, default mode

| Load point | File | chars | ~tokens |
|---|---|---|---|
| Entry | SKILL.md | 8,891 | 2,200 |
| Entry | shared/host-adaptation.md | 5,224 | 1,300 |
| Entry | integration-mode.md | 4,048 | 1,000 |
| Entry | shared/global-rules.md | 8,120 | 2,000 |
| Entry | github-speckit/provider-rules.md | 2,407 | 600 |
| Stage 01 | github-speckit/stage-01-preflight-intake.md | 5,437 | 1,350 |
| Stage 01 | shared/branching.md | 4,416 | 1,100 |
| Stage 01 | shared/intake.md | 8,085 | 2,000 |
| Stage 01 | shared/preflight-guidelines-context.md | 4,432 | 1,100 |
| Stage 01 | shared/scratch-hygiene.md | 1,174 | 300 |
| Stage 01 | shared/execution-report.md (`--issue` only) | 1,356 | 350 |
| Stage 02 | github-speckit/stage-02-spec-design-flow.md | 7,158 | 1,800 |
| Stage 02 | github-speckit/review-interview.md (default mode) | 2,891 | 720 |
| Stage 03 | github-speckit/stage-03-implement-and-code-review-loop.md | 8,854 | 2,200 |
| Stage 04+06 | stage-04 + stage-06 + shared/commit.md | 5,707 | 1,430 |
| **Subtotal** | | **77,580** | **~19,400** |

### 1.2 Sub-skill instructions

| Skill | Load | chars | ~tokens |
|---|---|---|---|
| jira-to-speckit | SKILL.md (+ JIRA_API.md 2,280 on fallback) | 11,551 | ~2,900 |
| speckit-code-review | SKILL.md | 8,043 | ~2,000 |
| speckit-code-review | 5 area refs (serial load/discard) | 10,926 | ~2,700 |
| **Subtotal** | | | **~9,100** |

**Static total ≈ 28k tokens** (github-speckit, `--issue`, default mode).

Variants:
- **superpowers provider**: heavier — refs total ~96k chars (~24k tok) + sub-skills ≈ **33k static**.
- **Manual mode** (no `--issue`): saves ~3.3k (jira-to-speckit SKILL.md + execution-report.md).

### 1.3 Dynamic runtime content (dominates on real runs)

| Source | Est. per occurrence |
|---|---|
| Raw Jira payload in tool result (capped at 12k chars input budget) | 1k–3k |
| Compact brief (capped 2.5k chars) | ~600 |
| spec.md / plan.md / tasks.md written + re-read across stages | 3k–15k per artifact set |
| Repo-installed `speckit.*` stage skills (8 invocations, own instructions) | 9k–15k |
| Code reads/edits in Stage 03 + fix iterations | 20k–60k+ |
| speckit-code-review iteration (diff + spec + refs) | 5k–20k; ×2–4 iterations |
| Interview round-trips (default mode) | 1k–2k each |

---

## 2. Total Estimation

Two distinct numbers matter:

- **Peak context footprint:** ~45k–120k tokens for a medium feature with 2–3 review iterations.
  YOLO mode can exceed this (more autonomous retries, no human course-correction).
- **Cumulative billed tokens** (sum of context re-sent on every API call): the same-turn mandate
  means the transcript grows monotonically. ~30–60 tool calls × growing context ≈
  **1M–3M cumulative input tokens** without prompt caching; ~150k–400k effective with caching.

---

## 3. Key Findings (Inefficiencies)

1. **Rule duplication.** The "no-stop zone" / absolute-operating-premise is restated ~6×
   (SKILL.md, global-rules rules 6/11/20/48, stage-02, stage-03, review-interview). Global rules +
   provider rules + stage files overlap heavily — ~30–40% redundancy ≈ **~6k tok/run**.
2. **Heavy entry load.** 5 files (~7.2k tok) load before Stage 01 does any work.
   host-adaptation.md is ~60% install-recovery tables needed only on failure.
3. **"Discard from context" is mostly aspirational.** On stateless API hosts (Copilot), tokens
   already in the transcript stay billed on every subsequent call. The design pays cumulative,
   not max, cost.
4. **Raw Jira payload enters model context.** Compaction happens *after* the full fetch sits in a
   tool result; only the snapshot goes to disk directly.
5. **R5 full regeneration.** Any FR-*/ARCH-* fix re-runs plan → checklist → tasks → analyze
   (≈ +8k–20k tok per iteration) even for a single-requirement gap; partitioning only triggers
   for "large scope".
6. **speckit-code-review reloads all 5 area refs every iteration**, even when the failure is
   single-category.
7. **Frontmatter descriptions** (~150 words each) sit in every host session's skill-list context
   permanently (~160 tok × 3 skills), even when unused.

---

## 4. Optimization Plan

### P1 — high impact, low risk

| # | Change | Est. saving (tokens) | Est. cost saving | % saving (base) |
|---|---|---|---|---|
| 1 | **Deduplicate canonical rules.** One `global-rules.md` statement + one-line back-references from stage files (e.g. "Stage 03 no-stop rule: see global-rules.md #11"). | −6–8k/run instructions | −$0.018–0.024 per pass (compounds ×~30–60 calls uncached: −$0.54–1.44/run) | 21–29% of static instruction layer (~28k) |
| 2 | **Slim entry bundle.** Compress host-adaptation to a ~15-line table; inline provider resolution (3 lines) into SKILL.md; load install-recovery tables only on preflight failure. | −3k at entry | −$0.009 per pass (−$0.27–0.54/run uncached) | ~40% of entry bundle (~7.2k) |
| 3 | **Stage-boundary compaction.** Persist run state + Project Context to `.speckit/run-state.json` **inside the Stage 01 linked worktree** (state must include `worktree_path`; resume re-enters the worktree before any stage call) and allow context compaction / fresh turn between stages; keep same-turn only within a stage. | Up to −50% cumulative billed input (1M–3.2M → 0.5M–1.6M) | **Up to −$1.90–6.75 uncached / −$0.60–2.85 cached per run** | Up to 50% of total run cost |
| 4 | **speckit-code-review selective refs.** Load only the category ref matching the failure (extend the existing `detail_files` mechanism to review refs); skip unit-test-coverage ref when no test runner detected. | −1.5–2.5k per review iteration | −$0.0045–0.0075 per iteration (−$0.01–0.03/run at 2–4 iterations) | 55–93% of area-ref layer (~2.7k) |

### P2 — medium impact

| # | Change | Est. saving (tokens) | Est. cost saving | % saving (base) |
|---|---|---|---|---|
| 5 | **jira-to-speckit scripted fetch.** Fetch via `curl` + `jq` writing the snapshot straight to disk; model reads only bounded summary/description fields, never raw JSON. | −1–3k per Jira run | −$0.003–0.009 per pass (compounds uncached) | up to ~100% of raw-payload tool result |
| 6 | **R5 scoped regeneration.** Regenerate only the affected package/slice (reuse partitioning machinery unconditionally), not the whole plan/tasks chain. | −8–20k per FR/ARCH fix iteration | −$0.024–0.06 per iteration | 60–90% of regeneration cost per iteration |
| 7 | **Artifact digest.** Maintain a ≤500-token spec digest for prompt wiring instead of re-sending full spec.md + plan.md to every `speckit.*` stage. | −2–6k per stage invocation (−16–48k/run at 8 invocations) | −$0.05–0.14/run | ~70–90% of artifact re-send volume |
| 10 | **One-shot worktree bootstrap script** (new after worktree merge). Batch the Stage 01 gate — base sync, worktree add/reuse, `.gitignore` edit, rename/move alignment — into a single `scripts/worktree-bootstrap.sh` invocation returning compact JSON (`branch`, `worktree_path`, `base`, `warnings`). | −3–6 round-trips/run; −~1k gate instructions | −$0.05–0.25/run uncached, −$0.01–0.03 cached | recovers ~100% of the worktree-gate cost added by the merge |

### P3 — polish

| # | Change | Est. saving (tokens) | Est. cost saving | % saving (base) |
|---|---|---|---|---|
| 8 | Trim the three frontmatter `description` fields to ~2 lines each. | ~−360 tok permanent | −$0.001 per session | ~75% of description overhead (~480 tok) |
| 9 | Add per-stage token/char accounting to the execution report so future tuning is measurable. | observability | enables measured % reporting | — |

### Constraints for implementation

- All changes must keep `python3 tools/validate_skills.py` green (description ≥ 40 chars,
  frontmatter key whitelist, self-contained links, README version badges).
- `metadata.version` bumps + root README badge sync per skill touched.
- No behavioral changes to the no-stop / same-turn semantics without explicit approval — P1-3
  relaxes same-turn *between stages only*, which is the one semantic change in this plan and
  requires sign-off.

---

## 5. Projected Cost After Optimization (Claude Sonnet 4.6 list prices)

Estimates assume all P1 items land; P2 adds further reduction on top (not stacked into the
projection below except where noted). Ranges keep the baseline run profile (medium feature,
2–3 review iterations, 30–60 tool calls).

| Layer | Baseline | Projected after P1 (+P2 where noted) | Δ | % saving |
|---|---|---|---|---|
| Static instructions, per pass | ~28k tok / ~$0.084 | ~17–19k tok / ~$0.051–0.057 (P1-1+2+4) | −$0.027–0.033 | **−32–39%** |
| Entry bundle, per pass | ~7.2k tok / ~$0.022 | ~4.2k tok / ~$0.013 | −$0.009 | **~−40%** |
| Full run — uncached | $3.75–13.50 | $1.90–8.10 (P1-3 midpoint ~−40–50%, plus P1-1/2 compounding) | −$1.85–5.40 | **−40–50%** |
| Full run — with prompt caching | $1.20–5.70 | $0.70–3.50 | −$0.50–2.20 | **−35–45%** |
| With P2-6 + P2-7 also landed (runs that hit FR/ARCH fixes) | — | additional −$0.07–0.20/run typical | extra −3–6% of run cost | — |

Rules of thumb: instruction-layer savings (P1-1/2/4, P2-7) mostly protect the uncached and
first-call bill plus cache-write volume; transcript-shape savings (P1-3, P2-6) are the only ones
that also shrink the cached-run bill materially. All figures are projections — measured results
replace them via the comparison procedure in
[`test-case/speckit-auto/token-optimization-test-cases.md`](../test-case/speckit-auto/token-optimization-test-cases.md).

---

## 6. Proposed Execution Order (after confirmation)

1. P1-1, P1-2 (pure prose dedup — no semantic change)
2. P1-4 (code-review selective refs — local to one skill)
3. P2-5, P2-10 (scripted helpers — jira fetch + worktree bootstrap; stdlib/curl only)
4. P1-3 (stage-boundary compaction — semantic change, needs sign-off)
5. P2-6, P2-7, P3-8, P3-9
