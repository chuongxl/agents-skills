# audit-demo — expected deep-audit outcome

Kept outside `audit-demo/` on purpose: the fixture must not tell an auditing agent where its flaws are.

`audit-demo/` is a dependency-free Node notes service with a CI workflow. A deep audit
(`run-scan.sh --audit`, then `references/audit/WORKFLOW.md`) should end with:

| Expected verdict | Where | What |
|---|---|---|
| confirmed (high) | `src/app.js` `GET /notes/:id` branch | Any authenticated user reads any note: the branch returns `findNote()` without the owner check that the `DELETE` sibling has. Sandboxed harness: bob's token reads alice's note (status 200). |
| confirmed or needs_validation | `src/app.js` `authenticate()` | `store.tokens[token]` is a plain-object lookup: `Bearer __proto__` / `constructor` resolve to inherited values, so an unauthenticated caller passes the 401 gate (combined with the read flaw: unauthenticated read of every note). Not planted; found by the method during development. |
| needs_validation | `.github/workflows/ci.yml` | `pull_request_target` checks out the PR head and runs `npm test` with `NPM_TOKEN` in the environment. Whether fork PRs can trigger it without approval is a repository setting outside the source. |
| rejected or not a candidate | `src/app.js` `GET /version` | `execFileSync` with a fixed argument list and no request data; not an injection sink. |

These are logic and trust-boundary flaws (a missing owner comparison, an inherited-key lookup, a privileged
CI trigger), the kind pattern-based scanners are not designed to establish end to end.

First end-to-end run of the method (quick profile, 12 agent invocations, sandboxed local checks): both
confirmed findings and both needs-validation leads above were produced, each re-verified by a fresh agent;
the `/version` exec was correctly not reported as injection (its crash on git failure stayed
needs-validation). The final critic added the listener crash paths and the hardcoded tokens as deferred units.

## Deep-run completion and resume cases

These are agent-behavior acceptance cases. Deterministic CLI regressions run in `test-verification.py`
and `test-audit.py`; they do not prove that an agent follows the scheduling instructions.

| Setup | Required behavior | Failure |
|---|---|---|
| Full `--audit --profile deep` run with 27 repos and thousands of scanner findings | Start Phase 10 reconnaissance and ledgers before draining Phase 9, rotate audit phases and at most one verification batch per repo, finish every repo's reports and checks | Spend the session on Phase 9 and leave all audits without ledgers or reports |
| More than 25 independent queued root causes | Apply the first batch, inspect live status, queue subsequent batches until run-wide pending is zero | Treat `next` returning `done` as completion of the whole run |
| Interrupted after recording a grouped verdict but before `apply` | Resume the same run, apply the record with the original group, then resume or rebuild the queue | Lose group membership by requeuing before applying |
| Source-only audit with fresh hunters and verifiers available | Hunt and independently validate source-grounded leads, retain exact execution blockers, produce all reports | Skip the audit because local execution is disabled, or invent confirmed findings |
| Strict audit budget exhausted with candidates left | Keep invocation count, unvalidated fingerprints and uncovered units, write partial reports, fail the completion check | Reset budget on resume or relabel unvalidated candidates to make the run pass |
| Scanner report validates but audit output is missing | Mark Phase 10 incomplete and resume its tasks | Present a completed deep audit |
| Source changes before resume | Revalidate affected evidence and ledger units before carrying them | Reuse stale coverage because the commit alone matches |
