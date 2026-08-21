# Shared: Discovery

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## Overview

A story is rarely the whole picture. The behaviour it describes may already be covered by a manual
test case written two years ago, by a Cucumber test another team automated last sprint, or by a
`.feature` file sitting in the repository that nobody linked to Jira at all. Designing tests
without looking at any of that produces duplicates — and duplicates are the single failure mode a
QA pipeline can least afford, because they cost review time forever, not once.

Discovery is the sweep that looks. It runs at Stage 01, before any design exists, and it writes
what it found into `discovery.*` in run state.

## Discovery Gathers Evidence, Never Verdicts

**This is the rule the rest of the file exists to protect.** Every sweep below returns *things that
exist*: issue keys, test keys, file paths, tags, quoted step text. No sweep returns a judgement —
not "this is already covered", not "this duplicates MOM-5678", not "this scenario is redundant".

The reason is mechanical, not stylistic. The dedup labels applied later — `NEW`, `UPDATE`, `SKIP`,
`REVIEW` — are produced by a normalized-key match, precisely so that two runs over unchanged inputs
produce an identical label set. Discovery runs in subagents, and subagent output varies between
runs over identical inputs. A coverage judgement made inside a subagent would make the label set
vary too, and the guarantee would be gone with nothing announcing its departure.

So: subagents find, the main run decides. A sweep that returns "covered" has exceeded its mandate,
and its result is evidence to be re-read, not a conclusion to be adopted.

## The Three Sweeps

Run *these three* concurrently — **these three** share no inputs and no ordering. A fourth sweep,
impact analysis, runs after them and is specified in its own leaf, `impact-analysis.md`: its
test-inventory branch consumes Sweep 2's Xray list and Sweep 3's repository-test list, so it is
sequenced rather than concurrent. Naming that dependency here is what keeps the claim above true
rather than nearly true — a fourth sweep quietly folded into a set described as order-free would
make the description false for the whole set.

Each of the three is a subagent that receives the
anchor and returns one structured list.

### Sweep 1 — Jira linkage

From the anchor issue, walk one hop of every link type and record what is on the other end:

| Anchor is | Walk |
|---|---|
| `story` | subtasks, `relates to`, `blocks` / `is blocked by`, `duplicates`, parent epic |
| `epic` | every child issue, then each child's links as above |
| `test` | the test's requirement links — this is where the `@REQ_` target comes from |

Returns `discovery.linked_issues[]`: `{key, issue_type, relation, status}`. Nothing else — not
descriptions, not comments. One hop only: two hops from a mature epic reaches most of the project
and returns noise priced as signal.

### Sweep 2 — Xray tests

Every test linked to the anchor, and to every issue Sweep 1 returned. Both test types are
collected and the type is always recorded:

Returns `discovery.xray_tests[]`: `{key, test_type, summary, requirement}`, where `test_type` is
`Cucumber`, `Manual`, or `Generic`.

The type is not a detail. A Cucumber test has Gherkin, so it has a normalized key and can be
matched mechanically. A Manual test has prose steps, so it cannot — it is advisory input to a human
decision, and it is also the raw material a Manual-to-Gherkin conversion reads. Losing the type
collapses two very different downstream paths into one.

**The steps themselves go to disk, not into `discovery.xray_tests[]`.** The sweep writes them
verbatim into `existing-tests-manual.md` in the artifact folder, and the run-state entries carry
keys, types, summaries, and requirements only. This is what lets the bounds below hold while a
conversion still has the full step text to work from: the content lives in a file anything can read,
and only the index travels through run state.

### Sweep 3 — Repository tests

Scan the test tree the repo profile named. Returns three things at once:

- `discovery.repo_tests[]`: `{feature_path, scenarios, tags}` for every `.feature` already in the
  tree — the repository's own answer to "what is already automated here", which Xray does not hold
  and the Jira sweeps cannot see.
- `discovery.framework`: `playwright-bdd` when the tree, `bddgen`, and a `.feature` / `.steps.ts`
  pair are all present; `none` otherwise.
- `discovery.orphan_features[]`: see below.

`discovery.framework` is what a missing test framework is detected by, and detecting it here — at
Stage 01, before a single scenario has been designed and two stages before anything would run
`generate_cmd` — is the whole point of putting the sweep this early. The
alternative is discovering it when the automation stage runs a `generate_cmd` that was never
installed, after all of that work.

## Orphan `.feature` Files Are Reported, Never Adopted

An **orphan** is a `.feature` file under the test tree with no counterpart under `artifact_root`.
Teams that automated before adopting this pipeline have them by definition: the file was authored
directly in the test tree, which is exactly where this pipeline says nothing is ever authored.

They are **recorded in `discovery.orphan_features[]` and reported. Nothing else.** Not copied into
the artifact root, not rewritten, not deleted, not treated as the derived copy of anything.

Adoption is refused because the artifact folder is named `<jira-key>-<slug>` and an orphan has no
Jira key. Copying one in would either invent a key or create a folder outside the naming rule, and
that name is not decoration — it is the `@REQ_` tag, the dedup key, and the glob the resume check
matches on. A pipeline that quietly breaks its own identity rule to be helpful has traded a
reported inconvenience for an unreported inconsistency.

Deletion is refused for a blunter reason: an orphan is somebody's working test. The degenerate-case
rule that deletes a materialized copy when every scenario in it is blocked applies to copies **this
pipeline materialized**, and an orphan is not one.

To bring an orphan under management, run the pipeline against the ticket that owns the behaviour.
That path has a key, a gate, and a human — the three things automatic adoption would skip.

## When A Sweep Cannot Run

Absent Jira or Xray credentials, an unreachable API, a test tree that does not exist yet: the sweep
returns empty and `discovery.ran` records **why**, per sweep. Empty-because-nothing-exists and
empty-because-the-sweep-could-not-run are different facts, and every consumer downstream treats
them differently — a genuinely empty Xray means everything really is `NEW`, while an unreachable
Xray means nothing is known and the dedup label has to say so.

This is the same distinction the dedup rule draws between `ran` and `not-run`, for the same reason,
and it is drawn here first because this is where the information exists.

## Bounds

Discovery is a read sweep, not a crawl. It is bounded so a mature project cannot turn Stage 01 into
an unbounded traversal:

- One link hop from the anchor (two from an epic: epic → child → child's links)
- Subagents return structured lists, never full issue bodies or full DOM or full file contents
- A sweep that would return more than a page of entries returns the entries and a count of what it
  truncated — a silent cap reads as a complete answer

## What Discovery Writes

`discovery.ran`, `discovery.framework`, `discovery.linked_issues[]`, `discovery.xray_tests[]`,
`discovery.repo_tests[]`, `discovery.orphan_features[]` — every one of them a field in the run-state
contract, written to `execution-report.md` before the stage ends. A finding held only in the
subagent's reply is a finding no later stage can read.

## Red Flags — thoughts that mean a sweep has exceeded its mandate

| Thought | Reality |
|---|---|
| "This manual test obviously covers the same thing, I'll note it as covered" | Discovery records that the test exists, with its key and summary. Whether it covers anything is decided later, by the normalized-key rule and by a human — never inside a sweep |
| "The orphan feature is clearly the old version of this, I'll move it into the artifact folder" | Orphans are reported and left alone. An orphan has no Jira key, and the artifact folder name is the identity the whole pipeline indexes on |
| "Xray credentials are missing, so record zero tests and move on" | Zero-because-empty and zero-because-unreachable are different facts. Record which one happened, every time |
| "Walking one more hop would find the related epic" | One hop. Two hops from a mature epic returns most of the project as if it were relevant |
| "I'll have the subagent read the whole ticket so the design has context" | Sweeps return keys, paths, types, and tags. Ticket content comes through intake, once, where it can be read against acceptance criteria |
