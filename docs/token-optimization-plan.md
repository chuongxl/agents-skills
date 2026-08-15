# Token Usage Analysis & Optimization Plan — speckit-auto Pipeline

**Date:** 2026-08-15
**Scope:** `speckit-auto`, `speckit-code-review`, `jira-to-speckit`
**Status:** Analysis only — no changes applied yet. Implementation starts after explicit confirmation.

Analysis basis: all 44 markdown files across the three skills (~226 KB total), the load-on-demand
flow defined in `speckit-auto/SKILL.md` Entry Dispatch + Stage Router, and the github-speckit
provider reference chain. Token estimates use ~4 chars/token for English prose + markdown.

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
2. **Heavy entry load.** 4 files (~5.1k tok) load before Stage 01 does any work.
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

| # | Change | Est. saving |
|---|---|---|
| 1 | **Deduplicate canonical rules.** One `global-rules.md` statement + one-line back-references from stage files (e.g. "Stage 03 no-stop rule: see global-rules.md #11"). | −25–35% instruction tokens (−6–8k/run) |
| 2 | **Slim entry bundle.** Compress host-adaptation to a ~15-line table; inline provider resolution (3 lines) into SKILL.md; load install-recovery tables only on preflight failure. | −3k at entry |
| 3 | **Stage-boundary compaction.** Persist run state + Project Context to `.speckit/run-state.json` (resume-marker mechanism already half-exists) and allow context compaction / fresh turn between stages; keep same-turn only within a stage. | Up to −50% cumulative billed tokens |
| 4 | **speckit-code-review selective refs.** Load only the category ref matching the failure (extend the existing `detail_files` mechanism to review refs); skip unit-test-coverage ref when no test runner detected. | −1.5–2.5k per review iteration |

### P2 — medium impact

| # | Change | Est. saving |
|---|---|---|
| 5 | **jira-to-speckit scripted fetch.** Fetch via `curl` + `jq` writing the snapshot straight to disk; model reads only bounded summary/description fields, never raw JSON. | −1k–3k per Jira run |
| 6 | **R5 scoped regeneration.** Regenerate only the affected package/slice (reuse partitioning machinery unconditionally), not the whole plan/tasks chain. | −8k–20k per FR/ARCH fix iteration |
| 7 | **Artifact digest.** Maintain a ≤500-token spec digest for prompt wiring instead of re-sending full spec.md + plan.md to every `speckit.*` stage. | −2k–6k per stage invocation |

### P3 — polish

| # | Change | Est. saving |
|---|---|---|
| 8 | Trim the three frontmatter `description` fields to ~2 lines each. | ~160 tok × 3 skills, permanent, every session |
| 9 | Add per-stage token/char accounting to the execution report so future tuning is measurable. | observability |

### Constraints for implementation

- All changes must keep `python3 tools/validate_skills.py` green (description ≥ 40 chars,
  frontmatter key whitelist, self-contained links, README version badges).
- `metadata.version` bumps + root README badge sync per skill touched.
- No behavioral changes to the no-stop / same-turn semantics without explicit approval — P1-3
  relaxes same-turn *between stages only*, which is the one semantic change in this plan and
  requires sign-off.

---

## 5. Proposed Execution Order (after confirmation)

1. P1-1, P1-2 (pure prose dedup — no semantic change)
2. P1-4 (code-review selective refs — local to one skill)
3. P2-5 (jira scripted fetch — new scripts/ helper, stdlib/curl only)
4. P1-3 (stage-boundary compaction — semantic change, needs sign-off)
5. P2-6, P2-7, P3-8, P3-9
