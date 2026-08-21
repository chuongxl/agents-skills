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

**Two different credentials are in play, and mixing them is the most common failure here.** Jira
REST calls use basic auth with `JIRA_USERNAME` / `JIRA_API_TOKEN` (see `JIRA_API.md`). Xray's own
APIs — the Cucumber export and GraphQL — use a bearer token minted from `XRAY_CLIENT_ID` /
`XRAY_CLIENT_SECRET`. A Jira token will not authenticate against `xray.cloud.getxray.app`, and an
Xray token will not authenticate against the Jira REST API.

## 2. Authenticate

```bash
curl -s -H "Content-Type: application/json" -X POST \
  --data "{\"client_id\":\"$XRAY_CLIENT_ID\",\"client_secret\":\"$XRAY_CLIENT_SECRET\"}" \
  https://xray.cloud.getxray.app/api/v2/authenticate
```

The response body is a bare quoted bearer token, for example `"eyJhbGciOi..."`. Strip the
surrounding quotes before using it in the `Authorization: Bearer` header of later requests. Never
echo this token.

The token is valid for roughly an hour. One authentication per run is enough; do not re-mint it per
request.

## 3. Discovery: one fixed query

Discover the tests covering `<STORY-KEY>` with exactly one of these two JQL queries — never both,
and never merged. Running the same query twice for the same story must return the same set, so no
label or summary heuristics are ever added on top.

Primary query, used whenever the Xray JQL functions are available on the instance:

```
issue in testRequirement("<STORY-KEY>") ORDER BY key ASC
```

`testRequirement` is the Xray-provided JQL function for "tests that cover this requirement" — the
same relationship the `@REQ_` tag (see §7) creates on import.

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

**Every other type (Manual, Generic)** — fetch through the Jira REST API for the issue metadata,
using the same credentials and endpoints documented in [`JIRA_API.md`](JIRA_API.md) (`GET
{JIRA_URL}/rest/api/2/issue/{issueKey}?fields=summary,labels,issuetype,description`), and through
Xray's GraphQL API for the steps (§5). **`export/cucumber` returns nothing for Manual and Generic
tests** — do not treat an empty export as "no manual tests exist."

**`description` is in that field list deliberately, and it costs nothing.** A field list is one
parameter of a call that already runs, so asking for the description adds no request. Teams use the
field as the test's own summary — typically a `Test Objective:` paragraph followed by a numbered
scenario list — which makes it the cheapest available answer to *what does this test actually
cover?* Report it per test alongside key, summary, and labels; report `null` when the issue has
none, never an empty string, so a caller can tell an absent description from a blank one.

This is a read. Nothing here writes the field back — see §"What this skill does not do."

Both files are optional and named by the caller. Whichever path is not supplied is not written.

Report per file: how many tests, which query ran, and whether the non-Cucumber set could be
fetched. A caller that receives Cucumber tests but no Manual tests is looking at partial coverage
and must be told so, not left to assume the story has none.

## 5. Test steps for non-Cucumber tests

A Manual test's steps are the whole of its content. Key, summary, and labels are metadata about a
test; the steps are the test. A caller deciding whether a proposed scenario duplicates existing
coverage — or converting a Manual test into Gherkin — cannot do either from a summary line.

Steps are not on the Jira issue. They live in Xray and come out of its GraphQL API.

### Endpoint and shape

```
POST https://xray.cloud.getxray.app/api/v2/graphql
Authorization: Bearer <token from §2>
Content-Type: application/json
Body: {"query": "<graphql>"}
```

**Query by JQL, in one call** — the same JQL §3 already resolved, so no second discovery pass and
no key-to-id translation:

```graphql
{
  getTests(jql: "issue in testRequirement(\"MOM-1234\")", start: 0, limit: 100) {
    total
    start
    limit
    results {
      issueId
      jira(fields: ["key", "summary", "labels"])
      testType { name kind }
      steps { id action data result }
    }
  }
}
```

The step fields are `action`, `data`, and `result` — Xray's own three columns, surfaced in its UI as
Action, Data, and Expected Result. Any of the three may be an empty string or `null`; that is
ordinary, not an error, and it is rendered as an empty cell rather than filled in.

### The `getTest` gotcha

The single-test form is `getTest(issueId: "64459")` and it takes a **numeric issue id, not a Jira
key**. `getTest(issueId: "MOM-1234")` returns nothing. This is the reason the `getTests(jql: …)`
form above is the one specified here: it accepts the JQL that is already in hand and returns
`jira(fields: ["key"])` alongside the steps, so keys and steps arrive together and no id lookup is
needed.

### Pagination and limits

`getTests` returns `total`, `start`, and `limit`. When `total` exceeds what came back, page with
`start`. Xray caps how many resolvers one request may expand, so keep the field selection to what is
listed above rather than adding nested test runs, executions, or attachment expansions to the same
query — this call needs steps and keys, nothing else.

### When steps cannot be fetched

Absent Xray credentials, a GraphQL error, or a test type with no steps at all: emit the table with
key/summary/labels only, and **say so explicitly in the report**. A reader must be able to tell a
stepless table (steps could not be fetched) from a test that genuinely has no steps. Never
paraphrase a summary into a step to fill the gap — a fabricated step reads exactly like a real one
to everything downstream.

## 6. Record steps verbatim

`xray_manual_output_path` is a markdown table, one section per test:

```markdown
### MOM-5678 — Reset an agreement from the header

- Type: Manual
- Labels: regression, agreements

| Step | Action | Data | Expected Result |
|---|---|---|---|
| 1 | <verbatim> | <verbatim> | <verbatim> |
| 2 | <verbatim> | <verbatim> | <verbatim> |
```

Four rules, and they exist because this table is read by people and by conversion tooling that
cannot tell an edit from an original:

1. **One row per raw step object returned by the API.** Never merge two steps into one row, never
   split one step across two.
2. **Original order.** The order the API returned is the order the test is executed in.
3. **Unedited wording.** Not tidied, not shortened, not corrected for grammar. A step that reads
   oddly is evidence about the test as it exists.
4. **No invented structure.** Never add section headers, phase labels, or groupings of your own
   ("Setup", "Step 3 — Actions 6-8"). If Xray itself groups steps, use its own label verbatim;
   otherwise there are no sections, only steps 1..N.

The reason is downstream: a caller comparing this table against a proposed scenario is checking
whether coverage already exists, and a caller converting the test into Gherkin is reproducing it.
Both read an edit as the original. Rewriting a step here silently rewrites the team's test.

## 7. Using the Xray MCP server instead

Some repositories configure the `@korfu/xray-mcp` MCP server, which wraps these same APIs. Where the
host exposes it, its `get_test_with_steps` tool is the equivalent of §5's GraphQL call and may be
used in place of it — it performs the same GraphQL query and needs the same
`XRAY_CLIENT_ID` / `XRAY_CLIENT_SECRET`. Its plain `get_test` does **not** reliably return steps; the
`_with_steps` form is the one that does.

The HTTP path in §5 is what this reference specifies, because it works on every host with nothing
installed. The MCP server is an alternative when it happens to be there, never a prerequisite.

Note the environment-variable names differ between the two. The MCP server reads `JIRA_BASE_URL` /
`JIRA_EMAIL` / `JIRA_API_TOKEN`; this skill reads `JIRA_URL` / `JIRA_USERNAME` / `JIRA_API_TOKEN`
from `.env`. The Xray pair is spelled the same in both. Do not assume a configured MCP server means
this skill's own variables are set.

## 8. Tag conventions

Xray binds issues to Gherkin through tags. These are read-only facts this skill reports on, not
tags it writes:

| Tag | Level | Meaning |
|---|---|---|
| `@REQ_<STORY-KEY>` | Feature | Links every test in the file to the story as its requirement |
| `@TEST_<TEST-KEY>` | Scenario | Binds the scenario to an existing Test issue — an import updates it in place instead of creating a duplicate |

## 9. Not this skill's job

This skill only reads Xray. It never:

- Imports a `.feature` file into Xray (`POST /api/v2/import/feature`)
- Creates or updates a test execution
- Uploads test results
- Creates or edits a test, or its steps

Those are CI's responsibility, exercised after the tests this skill exports have been reviewed and
approved. The GraphQL endpoint in §5 also serves mutations that would do all of the above; this
reference specifies queries only, and a mutation sent from this skill is out of scope regardless of
how convenient it looks.

## Sources

The GraphQL endpoint, authentication shape, `getTest` / `getTests` query forms, and the
`action` / `data` / `result` step fields in §5 are taken from Xray Cloud's own documentation
(`docs.getxray.app`, Xray Cloud REST/GraphQL API and Product KB), verified 2026-08-20. The MCP tool
names in §7 are from the `@korfu/xray-mcp` server as configured in the `om-mom-e2e-playwright`
repository's `jira-xray` skill.
