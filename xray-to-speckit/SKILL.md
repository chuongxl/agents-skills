---
name: xray-to-speckit
description: |
  Export the Xray tests that already cover a Jira story, using credentials from `.env`. Discovers them
  with one fixed JQL query, splits them by test type, and writes Cucumber tests as a concatenated
  `.feature` file and every other type (Manual, Generic) as a markdown table carrying each test's
  steps verbatim from Xray's GraphQL API, each reported with its `description` so a caller can triage
  before reading steps. Use when a caller needs to know what test coverage a story already has — to
  dedup against it, to convert a Manual test into Gherkin, or to review it. This skill is read-only:
  it never imports a feature file, creates a test execution, uploads results, or edits a test.
compatibility: Requires network access, Jira REST API access, and Xray Cloud API access. Requires `.env` entries for `XRAY_CLIENT_ID` and `XRAY_CLIENT_SECRET`, plus `JIRA_URL`, `JIRA_USERNAME`, and `JIRA_API_TOKEN` for the non-Cucumber tests' Jira metadata.
license: MIT
allowed-tools: bash view create
metadata:
  author: Alex Nguyen
  version: "0.1.0"
---

# Xray to Speckit

Use this skill when a caller needs the existing Xray test coverage of a Jira story as files it can
read — to judge whether coverage already exists, to convert a Manual test into Gherkin, or to put
in front of a reviewer.

This skill is a **pure Xray reader**. It takes one story key, runs one fixed discovery query, and
writes at most the two files the caller names. It does not compact the ticket, does not produce a
feature brief, and does not run any Speckit stage — a caller that needs the ticket itself calls
`jira-to-speckit`, by name, separately. The two skills are independent and either installs alone.

Portability note: `allowed-tools` uses GitHub Copilot-style names (`bash view create`). Claude Code
and OpenCode expose the same capabilities under their own names (`Bash`, `Read`, `Write`). The
workflow below is identical on all three hosts.

## What This Skill Does

- Resolves Xray credentials from the repository `.env` and mints a bearer token.
- Discovers the tests covering one story with **one** fixed JQL query, and reports which one ran.
- Splits the result by test type: Cucumber through Xray's Cucumber export, every other type through
  the Jira REST API for metadata and Xray's GraphQL API for steps.
- Writes the Cucumber tests to `xray_output_path` as one concatenated `.feature` file.
- Writes the Manual and Generic tests to `xray_manual_output_path` as a markdown table whose steps
  are **verbatim** — one row per raw step object, original order, unedited wording.
- Reports per file how many tests it found, which query ran, and whether steps could be fetched.

## What This Skill Does NOT Do

- **No write reaches Xray.** No feature import (`POST /api/v2/import/feature`), no test execution,
  no result upload, no test or step edit. Those belong to CI, after the exported tests have been
  reviewed. `references/XRAY_API.md` §9 states this against the endpoints, and the GraphQL endpoint
  in §5 serves mutations that would do all of it — this skill sends queries only.
- Does not fetch, compact, or summarize the Jira ticket itself. It reads Jira only for the
  non-Cucumber tests' own issue metadata.
- Does not judge coverage. It reports what exists; deciding whether a story is covered is the
  caller's, and a filter applied here would silently shrink the corpus that judgement runs over.
- Does not edit, normalize, or re-word a step. See "Verbatim Is The Contract" below.
- Does not write any file beyond `xray_output_path` and `xray_manual_output_path`, does not choose
  either path itself, and writes each only when the caller supplies it.
- Does not run Speckit stages, git operations, or an execution report.

## Required Inputs

- A Jira story key such as `MOM-1234`, or a Jira browse URL.
- Access to the repository root `.env` file.
- Xray credentials in `.env`: `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET`.
- Jira credentials in `.env`: `JIRA_URL`, `JIRA_USERNAME`, `JIRA_API_TOKEN` — needed for the
  non-Cucumber tests' metadata, per `references/XRAY_API.md` §4.

## Optional Inputs

- `xray_output_path` — where to write the covering Cucumber tests, as one concatenated `.feature`
  file. Omitted → Cucumber tests are not written.
- `xray_manual_output_path` — where to write the covering Manual and Generic tests, as a markdown
  table. Omitted → the table is not written.

Both are optional and both are named by the caller. Supplying neither is legal: the skill still runs
discovery and reports the counts, which is enough for a caller that only needs to know whether
coverage exists.

## Guardrails

- Never print `XRAY_CLIENT_ID`, `XRAY_CLIENT_SECRET`, the bearer token derived from them, or any
  `.env` value, in logs or chat output.
- Do not ask the user to paste secrets into chat.
- **Missing Xray credentials are a warning, never a stop.** Report `xray: unavailable` with the
  reason and return. A caller told `unavailable` knows it has no coverage data; a caller whose run
  aborted has nothing.
- **Read-only, absolutely.** No import, no test-execution creation, no result upload, no test edit.
- Run **one** discovery query, never both, and never merge two result sets. Report which ran.
- Never add label, summary, or component heuristics on top of the query. Two runs against the same
  story must return the same set.
- Write no file other than `xray_output_path` or `xray_manual_output_path`, and each only when the
  caller supplied its path.
- Never return raw API payloads to the caller. Files go to disk; the return value carries counts,
  paths, and status only.

## Verbatim Is The Contract

Every step is recorded exactly as Xray returned it — one row per raw step object, in the original
order, with the original wording, and no invented section headers.

This is the one rule in the skill with no latitude, and the reason is what a caller does with the
table. It reads the steps to decide whether coverage already exists, or to translate the test into
Gherkin. Both readings treat an edit as the original. A tidied step, a merged pair of steps, or a
helpful heading is indistinguishable downstream from what the test actually says, and the test —
not this export — is the approved artifact a QA team has been executing.

**A table without steps and a test with no steps are different facts and must not print the same
way.** `references/XRAY_API.md` §5 fixes how each is reported.

## Workflow

Follow [`references/XRAY_API.md`](references/XRAY_API.md) exactly. It is the specification; this
list is the order.

### 1. Resolve credentials

Read `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET` from `.env` (§1). Either absent → report
`xray: unavailable` with the reason and stop, without error.

### 2. Authenticate

Mint the bearer token (§2). Once per run — it is valid for roughly an hour; do not re-mint per
request. Strip the quotes the response wraps it in.

### 3. Discover the covering tests

One fixed JQL query (§3): `testRequirement`, falling back to `linkedIssues` **only** when the Xray
JQL functions are unavailable. Never both, never merged, no heuristics on top. Record which ran —
the two queries can return different sets, and a caller reading a count without knowing which query
produced it cannot tell a story with thin coverage from one whose Xray functions were down.

### 4. Split by test type

Cucumber tests through the Cucumber export, unzipped and concatenated into `xray_output_path` (§4).
Every other type through the Jira REST API for metadata — including `description`, which costs no
extra request because the field list belongs to a call that already runs — and through Xray's
GraphQL API for steps (§5), written to `xray_manual_output_path` as a markdown table.

**`export/cucumber` returns nothing for Manual and Generic tests.** An empty export is not evidence
that a story has no manual coverage.

### 5. Record the steps verbatim

Per §6, and per "Verbatim Is The Contract" above.

### 6. Return the output and stop

Produce the Output Template below and end the turn.

## Output Template

Always return the result in this exact shape:

- Jira issue key:
- Xray tests: (count and path written, or `not requested`, or `xray: unavailable` with the reason)
- Xray query: (`testRequirement` or `linkedIssues`)
- Xray manual tests: (count and path written, or `not requested`, or a note that the non-Cucumber
  set could not be fetched)
- Xray manual steps: (`fetched`, or `unavailable` with the reason — omitted when no non-Cucumber
  tests were found)

## Common Edge Cases

- **Jira URL instead of key**: extract the key and continue.
- **Missing Xray credentials**: report `xray: unavailable` and return. Never a stop.
- **Xray JQL functions unavailable**: fall back to `linkedIssues` and say so in `Xray query:`.
- **Cucumber export empty but tests were discovered**: the covering tests are Manual or Generic.
  Report the counts; do not report "no tests."
- **Steps cannot be fetched** (§5, "When steps cannot be fetched"): write the table with metadata
  and report `Xray manual steps: unavailable` with the reason. Never write an empty steps column
  that reads as "this test has no steps."
- **A test issue the caller cannot see**: report it as inaccessible rather than dropping it from the
  count silently.

## References

- [Xray API guide](references/XRAY_API.md)
