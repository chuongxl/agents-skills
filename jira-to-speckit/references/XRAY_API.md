# Xray API Reference

This reference supports the `jira-to-speckit` skill's optional Xray read mode (`xray_tests: true`).
It covers reading the Xray tests that cover a story. It does not cover importing, creating test
executions, or uploading results — see "Not This Skill's Job" below.

## 1. Credentials

Read these from the repository `.env` file:

- `XRAY_CLIENT_ID`
- `XRAY_CLIENT_SECRET`

Never print these values, or the bearer token derived from them, in logs or chat output.

If either variable is absent, do not stop the skill. Report `xray: unavailable` in the output and
continue — the compact brief is still valid without Xray data. This is a warning, never a stop.

## 2. Authenticate

```bash
curl -s -H "Content-Type: application/json" -X POST \
  --data "{\"client_id\":\"$XRAY_CLIENT_ID\",\"client_secret\":\"$XRAY_CLIENT_SECRET\"}" \
  https://xray.cloud.getxray.app/api/v2/authenticate
```

The response body is a bare quoted bearer token, for example `"eyJhbGciOi..."`. Strip the
surrounding quotes before using it in the `Authorization: Bearer` header of later requests. Never
echo this token.

## 3. Discovery: one fixed query

Discover the tests covering `<STORY-KEY>` with exactly one of these two JQL queries — never both,
and never merged. Running the same query twice for the same story must return the same set, so no
label or summary heuristics are ever added on top.

Primary query, used whenever the Xray JQL functions are available on the instance:

```
issue in testRequirement("<STORY-KEY>") ORDER BY key ASC
```

`testRequirement` is the Xray-provided JQL function for "tests that cover this requirement" — the
same relationship the `@REQ_` tag (see §5) creates on import.

Fallback query, used only when the Xray JQL functions are unavailable on the instance:

```
issuetype = Test AND issue in linkedIssues("<STORY-KEY>") ORDER BY key ASC
```

Report which query ran as `Xray query: testRequirement | linkedIssues`.

## 4. Split by test type

The discovered tests do not all travel through the same endpoint, because Xray's Cucumber export
only understands Cucumber tests.

**Cucumber tests** — export and unzip:

```bash
curl -s -H "Authorization: Bearer $token" \
  "https://xray.cloud.getxray.app/api/v1/export/cucumber?keys=A;B" \
  -o features.zip
```

The response is a zip of `.feature` files. Unzip it and concatenate the contents into
`xray_output_path`.

**Every other type (Manual, Generic)** — fetch through the Jira REST API instead, using the same
credentials and endpoints documented in [`JIRA_API.md`](JIRA_API.md) (`GET
{JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,labels,issuetype`). **`export/cucumber`
returns nothing for Manual and Generic tests** — do not treat an empty export as "no manual tests
exist." Write the results to `xray_manual_output_path` as a markdown table (key, summary, labels).

When `XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET` are present, additionally fetch each non-Cucumber
test's steps through the Xray Cloud GraphQL API and add a steps column to the same table. Those
steps are what let a reviewer at the design gate judge whether a proposed scenario duplicates
existing manual coverage — key and summary alone are too thin for that call. The exact GraphQL
query shape (endpoint, query name, field selection for step text) is **not verified in this
reference** and must be confirmed against Xray's current GraphQL schema before this call is
implemented; do not write a query here that looks authoritative and turns out wrong. When Xray
credentials are absent, or the GraphQL call itself is unavailable or fails, emit the table with
key/summary/labels only and say so explicitly in the report — so a reader can tell a stepless
table (steps could not be fetched) from a test that genuinely has no steps.

Both files are optional and named by the caller. Whichever path is not supplied is not written.

Report per file: how many tests, which query ran, and whether the non-Cucumber set could be
fetched. A caller that receives Cucumber tests but no Manual tests is looking at partial coverage
and must be told so, not left to assume the story has none.

## 5. Tag conventions

Xray binds issues to Gherkin through tags. These are read-only facts this skill reports on, not
tags it writes:

| Tag | Level | Meaning |
|---|---|---|
| `@REQ_<STORY-KEY>` | Feature | Links every test in the file to the story as its requirement |
| `@TEST_<TEST-KEY>` | Scenario | Binds the scenario to an existing Test issue — an import updates it in place instead of creating a duplicate |

## 6. Not this skill's job

This skill only reads Xray. It never:

- Imports a `.feature` file into Xray (`POST /api/v2/import/feature`)
- Creates or updates a test execution
- Uploads test results

Those are CI's responsibility, exercised after the tests this skill exports have been reviewed and
approved.
