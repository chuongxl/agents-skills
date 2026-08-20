# Shared: Bootstrap

Needs at load time: nothing. This file is a leaf — it links to no other file, and reads none.

## When This Runs

Only when discovery resolved `discovery.framework: none` — the repository has no Playwright-BDD
test tree to generate into. Two very different teams arrive here: one that has never written an
automated test, and one that has years of manual test cases in Xray and no automation repository to
put them in. Both need the same thing built, once.

When `discovery.framework` is `playwright-bdd`, this file is not loaded at all.

## Why It Is A Step And Not A Stage

Bootstrapping is setup, and the intake stage is the setup stage — it already discovers conventions,
creates the worktree, and initializes the frontend submodule. Making bootstrap its own stage would
require the intake stage to hand control forward and take it back, and no stage in this pipeline
links back to another. So it is a conditional step, loaded from its own file so the intake stage
pays for it only on the runs that need it.

It runs **after** discovery, not before. Nothing in intake up to that point needs a test framework:
the profile, the baselines, the worktree, the submodule, and all three sweeps work identically on a
repository that has no tests at all. The first thing that needs a framework is the automation
stage's `generate_cmd`, and that is two stages away.

## One Approval, Listing Everything First

This step writes files into the repository — the only step in intake that does. Present the
complete list of paths to be created, then take one approval for the list. Not one approval per
file, and not none.

**Nothing here is ever overwritten.** A path that already exists is reported as already present and
skipped. Bootstrap adds what is missing; it does not reconcile, migrate, or replace. A half-built
test tree is a common state, and stamping a template over one destroys work that was deliberate.

## What Gets Created

### 1. The test framework

`@playwright/test` and `playwright-bdd` as dev dependencies, a `playwright.config.ts` wired to
`playwright-bdd`'s `defineBddConfig`, and the `generate_cmd` script the profile names — `bddgen` by
convention. Install, do not hand-write, the dependency versions.

### 2. The test tree

The directories the repo profile's path fields name — `test_root`, and the parents of
`feature_path`, `steps_path`, `page_path`, `selectors_path`, `testdata_path`. On a greenfield
repository those fields have no discovered source, so they were asked at profile discovery; this
step is where the answers become directories that exist.

### 3. A base page object and a selectors module

One base page class that page objects extend, and one selectors module they import from. The
automation stage's coverage review checks that page objects go through the base page and that
selectors stay centralized — checks that cannot pass in a repository where neither exists. Creating
them here is what makes that review meaningful rather than vacuous.

### 4. One worked example

A single `.feature` / `.steps.ts` pair that runs green. Two reasons, and the second matters more
than the first: it proves the installation works before any real scenario depends on it, and it
becomes the worked example that profile discovery reads on every subsequent run.

### 5. The Xray import CI job

**This is the highest-value file bootstrap writes, and the one most likely to be skipped.** The
pipeline never writes to Xray; import happens in CI, on merge, reading `docs/qa/`. Without that job
the approved `.feature` files never reach Xray, the "one artifact, three consumers" property
silently becomes two, and nothing anywhere reports the gap.

Write `.github/workflows/xray-import.yml`:

```yaml
name: Xray import
on:
  push:
    branches: [main, master, develop]
    paths: ['docs/qa/**/*.feature']
jobs:
  import:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Import approved features into Xray
        env:
          XRAY_CLIENT_ID: ${{ secrets.XRAY_CLIENT_ID }}
          XRAY_CLIENT_SECRET: ${{ secrets.XRAY_CLIENT_SECRET }}
          XRAY_PROJECT_KEY: ${{ secrets.XRAY_PROJECT_KEY }}
        run: |
          set -euo pipefail
          token=$(curl -sf -H "Content-Type: application/json" -X POST \
            --data "{\"client_id\":\"$XRAY_CLIENT_ID\",\"client_secret\":\"$XRAY_CLIENT_SECRET\"}" \
            https://xray.cloud.getxray.app/api/v2/authenticate | tr -d '"')
          # docs/qa holds the full approved set: automated, blocked, and manual scenarios alike.
          # Zipping the test tree instead would silently drop every scenario not yet automated.
          zip -r features.zip docs/qa -i '*.feature' -x '*existing-tests.feature'
          curl -sf -H "Authorization: Bearer $token" -F "file=@features.zip" \
            "https://xray.cloud.getxray.app/api/v2/import/feature?projectKey=$XRAY_PROJECT_KEY"
```

Report, in the same breath as creating it, that the three secrets are **not** set by this step and
the job will fail until somebody sets them. A workflow file that exists and has never run
successfully is worse than none, because it looks like coverage.

### 6. The playbook

A repo-local conventions file — `docs/qa/CONVENTIONS.md` — recording the profile answers this run
had to ask for, in the form profile discovery reads.

This closes a loop that is otherwise open. Profile discovery caches only answers no file can
supply, and re-derives everything else from the playbook on every run. On a greenfield repository
*no* file supplies anything, so without this step every field would be a cached answer forever and
the playbook would never become the source of truth it is supposed to be. Writing the conventions
down converts the answers into exactly the discoverable source the next run expects to find.

## What Bootstrap Never Does

- **It does not touch application code.** No `data-testid` attributes, no component edits. Adding
  test hooks to the application is the selector gate's business, it is report-only by default, and
  it lands on a separate frontend branch — none of which changes because the repository is new.
- **It does not invent conventions.** Every path, command, and tag it uses came from profile
  discovery, which asked when it could not find. Bootstrap materializes those answers; it does not
  author them.
- **It does not write tests for existing features.** It creates one worked example that proves the
  installation. Turning a backlog of manual test cases into scenarios is design work, and design
  work happens at the design stage behind its human gate.
- **It does not run the suite.** Verifying the example passes is the automation stage's job, with
  the same commands every other scenario gets.

## What This Step Produces

`profile.*` fields now backed by directories and commands that exist, `discovery.framework` updated
to `playwright-bdd`, and on disk: the config, the test tree, the base page, the selectors module,
the worked example pair, the CI workflow, and `docs/qa/CONVENTIONS.md`.

## Red Flags — thoughts that mean bootstrap is overreaching

| Thought | Reality |
|---|---|
| "There is a half-built test folder here, I'll normalize it to the template" | Never overwrite. Report what exists, create only what is missing |
| "The CI job needs secrets I do not have, I'll leave the workflow out" | Write it and say the secrets are unset. A missing job is a gap nobody sees; a failing job is a gap somebody fixes |
| "The team clearly wants their manual test cases automated, I'll start converting" | Bootstrap builds the framework. Conversion is design work and belongs behind the design gate |
| "I'll add `data-testid` while I'm in here, it will save the selector gate a round" | Application code is never touched here. That edit is report-only and lands on a frontend branch, by a different rule |
| "The example test does not need to run, the config is obviously right" | The example exists to prove the install. An unverified install fails two stages later, with a scenario to blame it on |
