# Shared: Gherkin Conventions

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

One `.feature` file serves three consumers, and nothing is authored twice:

| Consumer | Reads it as |
|---|---|
| Manual tester | The test case — Given/When/Then steps to execute by hand |
| `playwright-bdd` | The spec that `bddgen` compiles into Playwright tests |
| Xray (via CI on merge) | A Cucumber Test issue, created or updated in place |

There is no translation step between formats. The file authored at `feature_path` (see
`repo-profile.md`'s field table) under `docs/qa/<jira-key>-<slug>/` is the source of truth; the
copy materialized into the test tree in Stage 03 is a derived subset of it, never a second
authoring.

## Tags

Two tags bind the file to Xray:

| Tag | Level | Meaning |
|---|---|---|
| `@REQ_<STORY-KEY>` | Feature | Links every test in the file to the story as its requirement |
| `@TEST_<TEST-KEY>` | Scenario | Applied **only** to `UPDATE` rows — binds the scenario to an existing Test issue so import updates it in place instead of creating a duplicate |

Both are **additive**. The profile's `existing_tags` (`@Automation`, `@Regression_Test`, domain
tags, etc.) stay exactly where they already are on every scenario that carries them — nothing is
removed, renamed, or reordered. This is what keeps `--grep` filtering and the repo's current CI
workflow working unchanged after this pipeline starts writing to the same files.

A `@TEST_<TEST-KEY>` tag is never added to a `NEW` scenario — there is no existing Test issue yet
to bind to. It is never added to `SKIP` or `REVIEW` scenarios either; those are dedup outcomes, not
import targets.

## Surface

Every scenario carries a `surface`, matching `design.scenarios[].surface` in the run-state
contract:

| `surface` | Meaning | Selector gate | Stage 03 |
|---|---|---|---|
| `ui` | Drives the application through its interface | **Applies.** Every element resolves, or the run stops | Automated |
| `api` | Exercises an endpoint or a service contract, no interface | Does not apply. The scenario must instead name its endpoint and request/response fixture | Automated |
| `manual` | Cannot or should not be automated — visual judgement, external system, physical device | Does not apply | Not automated; lives in the artifact only |

A `surface: ui` scenario with zero UI elements is a design error, not a pass — it means the
scenario was misclassified, not that the gate found nothing to check. A `surface: manual` scenario
needs an explicit one-line reason recorded beside it; without the reason, self-review fails,
because `manual` is otherwise the easiest way to make the selector gate disappear without actually
earning that exemption.

## Scenario Granularity

One behaviour per scenario. Negative and boundary cases are included as their own scenarios, not
folded into the happy path with extra `And` steps. A scenario that asserts two unrelated behaviours
is two scenarios that happen to share a `Given`.

## The Anti-Drift Rule

The materialized copy in the test tree is a **scenario-level subset** of the artifact version.
Subset, yes; modification, never. Because a subset is not a textual match, checking it is
Gherkin-aware, not a text diff:

| Element | Rule |
|---|---|
| `Feature:` name, feature-level tags, `Background:` | Must be **identical** in both files. These are never subset, never edited |
| Each `Scenario` / `Scenario Outline` | Present in the copy → its name, tags, step sequence, and `Examples` table must match the artifact version exactly. Absent from the copy → allowed only when it was marked blocked |
| Scenario order | Follows the artifact version. Reordering is a modification |
| A scenario in the copy that is absent from the artifact | Always a violation. Nothing is authored in the test tree |

## Two Degenerate Cases

Stated so they are not improvised at Stage 03:

- **Every scenario in a file is blocked** → the file is **not materialized at all**, and any
  previously materialized copy is deleted. An empty `Feature:` block is not a valid artifact.
- **A `Scenario Outline` with some rows blocked** → the whole outline is blocked. Example rows are
  never individually omitted — splitting an `Examples` table would change the scenario, and a
  changed scenario is a modification, not a subset.

## Red Flags — thoughts that mean the tag or drift rule is being bent

| Thought | Reality |
|---|---|
| "I'll drop the old domain tag, it's not part of this scheme" | Tags are additive. Removing an existing tag breaks `--grep` filtering and the current CI for everyone else, not just this run |
| "This scenario is basically the same as the artifact, close enough" | Close enough is a modification. The copy must match exactly or be absent-because-blocked — there is no third state |
| "I'll skip just this one Examples row instead of blocking the whole outline" | Splitting an `Examples` table changes the scenario. Block the whole outline |
| "The file has one working scenario left, I'll materialize just that" | If every other scenario in the file is blocked and one survives, that one is materialized alone — but if all are blocked, the file is not materialized at all. Check which case actually applies before writing anything |
| "I'll tag this NEW scenario with `@TEST_...` so Xray has something to bind to early" | There is no Test issue yet for a `NEW` scenario. Only `UPDATE` rows carry `@TEST_<TEST-KEY>` |
