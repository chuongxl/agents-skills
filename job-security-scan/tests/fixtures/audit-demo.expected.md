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

Semgrep (p/javascript, p/nodejs, p/owasp-top-ten) reports nothing for this fixture; the flaws above are the
kind only the deep audit finds.
