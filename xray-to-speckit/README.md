# xray-to-speckit: Export the Xray tests that already cover a story

**Version**: 0.1.0 · **Author**: Alex Nguyen · **License**: MIT

## Overview

**xray-to-speckit** answers one question about a Jira story: *what test coverage already exists?*
It discovers the Xray tests covering the story, splits them by test type, and writes them as files
a caller can read — Cucumber tests as a concatenated `.feature`, Manual and Generic tests as a
markdown table carrying each test's steps **verbatim**.

It is a **pure reader**. Nothing it does reaches Xray as a write: no feature import, no test
execution, no result upload, no edit to a test or its steps. Those belong to CI, after a human has
reviewed what this skill exported.

## Quick Start

```
@xray-to-speckit MOM-1234
```

or with output paths, which is how a pipeline calls it:

```
xray-to-speckit
  issue:                    MOM-1234
  xray_output_path:         docs/qa/mom-1234-feature/existing-tests.feature
  xray_manual_output_path:  docs/qa/mom-1234-feature/existing-tests-manual.md
```

Both paths are optional and both are named by the caller. Supplying neither is legal — the skill
runs discovery and reports the counts, which is enough for a caller that only needs to know whether
coverage exists.

## Prerequisites

`.env` in your repository root:

```env
# Xray Cloud credentials — required
XRAY_CLIENT_ID=your-xray-client-id
XRAY_CLIENT_SECRET=your-xray-client-secret

# Jira credentials — required for the non-Cucumber tests' issue metadata
JIRA_URL=https://your-jira-instance.atlassian.net
JIRA_USERNAME=your-email@company.com
JIRA_API_TOKEN=your-api-token-here
```

**Two different credential pairs are in play, and mixing them is the most common failure.** Jira
REST uses basic auth with `JIRA_USERNAME` / `JIRA_API_TOKEN`. Xray's own APIs — the Cucumber export
and GraphQL — use a bearer token minted from `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET`. A Jira token
does not authenticate against `xray.cloud.getxray.app`, and the reverse.

Missing Xray credentials are a **warning, never a stop**: the skill reports `xray: unavailable` with
the reason and returns. A caller told `unavailable` knows it has no coverage data; a caller whose run
aborted has nothing.

## What it does

### One fixed discovery query

Exactly one JQL query runs, never both and never merged:

- **Primary** — `issue in testRequirement("<STORY-KEY>") ORDER BY key ASC`, whenever the Xray JQL
  functions are available on the instance.
- **Fallback** — `issuetype = Test AND issue in linkedIssues("<STORY-KEY>") ORDER BY key ASC`, only
  when they are not.

Which one ran is always reported (`Xray query:`). No label, summary, or component heuristic is ever
added on top, so two runs against the same story return the same set. The two queries can return
different sets, and a caller reading a count without knowing which produced it cannot tell a story
with thin coverage from one whose Xray functions were down.

### Two files, split by test type

| Test type | Route | Written to |
|---|---|---|
| Cucumber | Xray's `export/cucumber`, unzipped and concatenated | `xray_output_path` |
| Manual, Generic | Jira REST for metadata + Xray GraphQL for steps | `xray_manual_output_path` |

**Manual and Generic tests never appear in the Cucumber export.** An empty export is not evidence
that a story has no manual coverage. A caller that receives Cucumber tests but no Manual tests is
looking at **partial coverage**, and the skill says so explicitly rather than leaving it to be
assumed.

Each test is reported with its `description` — typically a `Test Objective:` paragraph and a
numbered scenario list — which is the cheapest available answer to *what does this test actually
cover?* It costs no extra request: the field list belongs to a call that already runs.

### Steps are verbatim, and that is the contract

One row per raw step object, in Xray's own Action / Data / Expected Result columns, in original
order, with unedited wording and no invented section headers.

A caller reads this table either to judge whether coverage already exists or to convert the test
into Gherkin, and **both readings treat an edit as the original**. A tidied step or a helpful
heading is indistinguishable downstream from what the test actually says — and the test, not this
export, is the approved artifact a QA team has been executing for years.

When steps cannot be fetched, the table is written with metadata and the report says so. **A table
without steps and a test with no steps are different facts and must not print the same way.**

## Output

```
- Jira issue key:
- Xray tests:         (count and path written, or `not requested`, or `xray: unavailable`)
- Xray query:         (`testRequirement` or `linkedIssues`)
- Xray manual tests:  (count and path written, or `not requested`, or could-not-fetch)
- Xray manual steps:  (`fetched`, or `unavailable` with the reason)
```

## What it does NOT do

- **No write reaches Xray** — no import, no test execution, no result upload, no test or step edit.
- Does not fetch, compact, or summarize the Jira ticket. That is `jira-to-speckit`, invoked
  separately by name.
- Does not judge coverage. It reports what exists; whether a story is covered is the caller's call,
  and a filter applied here would silently shrink the corpus that judgement runs over.
- Does not write any file beyond the two the caller names, and does not choose either path itself.
- Does not run Speckit stages, git operations, or an execution report.

## Installation

Copy the `xray-to-speckit` folder into the host's skills directory:

| Host | Location |
|---|---|
| GitHub Copilot | `.github/skills/xray-to-speckit/` |
| Claude Code | `~/.claude/skills/xray-to-speckit/` or `.claude/skills/` |
| OpenCode | `~/.config/opencode/skills/xray-to-speckit/` |

It has no sub-skills and depends on no other skill. `speckit-qa-auto` invokes it by name for its
existing-test sweep; installing that pipeline means installing this skill beside it.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `xray: unavailable` | `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET` absent from `.env` | Add both. This is a warning by design, not a failure |
| `401` from `xray.cloud.getxray.app` | A Jira token was used where an Xray bearer token belongs | Mint the token per `references/XRAY_API.md` §2 |
| `Xray query: linkedIssues` unexpectedly | The instance's Xray JQL functions were unavailable | Not an error; the fallback set may differ from `testRequirement`'s |
| Cucumber file empty, tests were found | The covering tests are Manual or Generic | Read `xray_manual_output_path`; this is not "no tests" |
| Manual table has no steps column | Steps could not be fetched | Check `Xray manual steps:` for the reason; do not read it as "these tests have no steps" |

## References

- [Xray API guide](references/XRAY_API.md) — credentials, authentication, the discovery query, the
  test-type split, the GraphQL steps query and its `getTest` gotcha, verbatim recording, the MCP
  alternative, tag conventions, and what is out of scope.
