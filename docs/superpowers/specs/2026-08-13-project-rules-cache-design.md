# Project Rules Cache for `speckit-code-review`

**Date:** 2026-08-13
**Status:** Approved design, ready for implementation
**Scope:** `speckit-code-review` skill only. Provider- and project-agnostic.

## Problem

`speckit-code-review` reviews changed code against generic built-in checklists (business gap, code
quality, security, architecture, unit tests). A repository's own conventions — layering rules,
naming, database and workflow rules — live in `docs/guidelines/architecture.md` and the files it
links. Today those are consulted through `references/project-guidelines-review.md`, which:

- re-reads and re-interprets the full guideline **prose** on every single review run,
- keeps everything in memory only, so nothing survives between runs or between developers,
- treats project rules as an *additional advisory pass* rather than the authoritative ruleset.

The result is repeated token cost for the same parsing work, and project conventions that carry no
more weight than a generic checklist item.

## Goals

1. Extract the repository's own review rules from `docs/guidelines/architecture.md` and its linked
   guidelines **once**, and reuse them on later runs without re-reading those documents.
2. Give project rules **higher priority** than the generic checklists.
3. Stay generic: the skill is installed globally and must work on any repository, discovering
   `docs/guidelines/architecture.md` relative to whatever repo it runs in. No project-specific
   content is baked into the skill.
4. Never let this layer break or block a review.

## Non-Goals

- Replacing the generic checklists (see Approach C, rejected).
- Authoring or editing a repository's guidelines.
- Any change to the inline JSON contract consumed by `speckit-auto`.

## Approach

Three options were considered:

| | Approach | Verdict |
|---|---|---|
| A | Cache as pure memoization — keep lazy per-category loading, cache only the parse | Rejected: each run still re-reads prose to interpret it; priority stays implicit |
| B | **Precompiled rule index** — distil guidelines into atomic, glob-scoped rules | **Chosen** |
| C | Rules-only review — extracted rules fully replace built-in checklists | Rejected: a thin `architecture.md` would silently gut security and coverage review |

**B** is chosen because the atomic `applies_to` glob serves both goals simultaneously: it is the
reuse mechanism (later runs load *rules*, not *documents*) and the prioritisation mechanism (a
matched rule is a hard assertion with a severity floor, not advisory prose). The generic checklists
remain as the safety net that C would lose.

## Design

### 1. Extraction and cache lifecycle

Implemented in a new reference file `references/project-rules-cache.md`, replacing
`references/project-guidelines-review.md` (deleted — the cache subsumes its discovery,
classification, and caching steps).

On every review run, before any review area executes:

1. If `docs/guidelines/architecture.md` does not exist → skip silently, set `rules_cache: "none"`,
   run the generic review only.
2. Otherwise compute the SHA-256 of `architecture.md` and of every guideline file it links.
3. If `docs/guidelines/.review-rules.json` exists, its `version` is recognised, and **every** hash
   matches → load the cache and **read no guideline file at all**. Set `rules_cache: "reused"`.
4. On any mismatch, missing cache, or unreadable/unknown-version cache → run extraction, overwrite
   the cache file, set `rules_cache: "regenerated"`, and note in the result that the file should be
   committed.

Extraction walks `architecture.md` and the relative `.md` links in its `References` section
(falling back to all relative `.md` links in the file when no such section exists). It keeps only
**checkable** statements — imperative MUST / MUST NOT / DO / DON'T / NEVER / ALWAYS / required /
forbidden assertions — distilled into atomic rules. Prose, rationale, and diagrams are discarded.
Code examples are not retained.

The cache is committed to git, so a team and CI share one extraction and it is reviewable in pull
requests.

### 2. Cache schema — `docs/guidelines/.review-rules.json`

```json
{
  "version": 1,
  "generated_at": "2026-08-13T07:00:00Z",
  "source_hashes": {
    "docs/guidelines/architecture.md": "sha256:ab12…",
    "docs/guidelines/naming-convention.md": "sha256:cd34…"
  },
  "missing_sources": [],
  "rules": [
    {
      "id": "PR-001",
      "rule": "Domain layer must not import from application or infrastructure layers",
      "applies_to": ["**/domain/**"],
      "category": "ARCH",
      "severity_floor": "high",
      "source": "docs/guidelines/architecture.md § 1. The Dependency Rule"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `version` | Schema version. Unknown value → re-extract. |
| `source_hashes` | SHA-256 per source file; drives invalidation. |
| `missing_sources` | Linked guidelines that were absent from disk; skipped, not fatal. |
| `id` | Stable `PR-NNN` rule identifier, assigned in document order so IDs survive re-extraction of an unchanged doc. This names the *rule*, not the finding: a violation is emitted as a fix whose `id` uses the rule's `category` prefix (`ARCH-007`, …), and the `PR-NNN` is recorded alongside `guideline_source` in the detail file. |
| `rule` | Exactly one testable assertion. |
| `applies_to` | Path globs the rule constrains. Omitted for repo-wide rules. |
| `category` | `ARCH` \| `CODE` \| `SEC` \| `TEST` \| `FR` — maps the finding onto an existing issue prefix. |
| `severity_floor` | `medium` by default; `high` when the guideline marks the rule inviolable or a hard rule. |
| `source` | `<file> § <heading>` — makes every finding traceable; becomes `guideline_source` on the fix. |

`category` deliberately reuses the existing prefixes rather than introducing a new one, so
`speckit-auto`'s Stage 03 routing (which classifies fixes by ID prefix) keeps working untouched.

### 3. Review integration

Project Rules becomes **review area zero**, running before Business Gap:

1. Select the rules whose `applies_to` matches at least one changed file (repo-wide rules always
   match).
2. Check each matching changed file against each selected rule.
3. Emit every violation under the rule's `category` prefix, with `guideline_source` set from the
   rule's `source` and severity no lower than its `severity_floor`.

The generic areas then run as they do today, under two constraints:

- A generic finding is dropped when it targets the same file and construct as a matched project rule
  and would push the code in a different direction than that rule requires — the project rule wins.
  A generic finding that merely *overlaps* (flags the same violation the rule already caught) is
  merged into the project-rule finding rather than reported twice.
- A project-rule violation is never downgraded, deduplicated away, or suppressed.

### 4. Output contract

Unchanged for all existing fields: same names, same issue prefixes, same top-3 inline `fixes` cap,
same detail-file layout. `speckit-auto` requires no edit.

One additive **optional** field, `rules_cache`, with value `"reused"`, `"regenerated"`, or
`"none"` — purely informational and safely ignorable by any caller.

### 5. Failure modes

All non-fatal; the review never fails because of the rules layer.

| Condition | Behaviour |
|---|---|
| No `docs/guidelines/architecture.md` | Silent skip; generic review only; `rules_cache: "none"` |
| `architecture.md` has no imperative statements | Cache written with `rules: []`; generic review only |
| Cache unreadable or unknown `version` | Re-extract and overwrite |
| A linked guideline missing from disk | Skip it, record under `missing_sources`, continue |

## Verification

- Run against a repo with `docs/guidelines/architecture.md` → cache created, `rules_cache:
  "regenerated"`, rules present with resolved `source` values.
- Rerun unchanged → `rules_cache: "reused"`, and no guideline file is read.
- Touch a linked guideline → hash mismatch → `rules_cache: "regenerated"`.
- Run against a repo with no `docs/guidelines/` → silent skip, generic review still completes.
- Introduce a deliberate rule violation → finding appears under the rule's `category` prefix with
  `guideline_source` set and severity ≥ `severity_floor`.
