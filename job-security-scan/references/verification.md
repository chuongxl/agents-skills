# Independent verification of findings (Phase 9)

Scanners are noisy. Phase 9 sends each high-value finding to a **fresh verifier** that tries to disprove it from
the repository source, then records one of three verdicts in the report. The verdict contract, the verifier prompt
and the severity anchors below are adapted from Cloudflare's
[security-audit skill](https://github.com/cloudflare/security-audit-skill) (commit `c1c8a8c`, MIT;
notice in [third-party/cloudflare-security-audit-LICENSE](third-party/cloudflare-security-audit-LICENSE)).

Verification is **report content only**. A verifier never edits, patches or commits anything, never runs code
from the scanned repository, and never contacts a network service.

## Steps (the parent agent)

1. `python3 -I scripts/triage.py queue security-run-<datetime>` — prints how many findings are queued and writes
   `triage/queue-index.json` plus `triage/batch-NNN.json` (10 items each, most severe first). The run's profile
   decides what is queued: `standard` CRITICAL + HIGH, `deep` also MEDIUM, `quick` nothing. Findings that already
   have a verdict (also verdicts carried over from the previous run for unchanged code) are not queued again.
   Findings with one root cause in one repo become **one item**: dependency findings by advisory id + package +
   installed version (every lockfile and scanner that reports it), misconfigurations by scanner + rule (every
   file). The item lists all members under `group`. Items are ordered most severe first (new before unchanged)
   and capped at the **batch size of `--limit 25` by default**; the `summary` in `queue-index.json` and the printed
   line say how many items and findings stay pending. Options: `--limit N`, `--all` (no cap), `--repo NAME`
   (repeatable, e.g. to work through a large multi-repo scan one repo at a time), `--no-group` (one item per
   finding).
2. Loop, one item at a time:
   1. `python3 -I scripts/triage.py next security-run-<datetime>` prints one queue item as JSON (finding +
      context + group), or `{"done": true, "scope": "current_queue", "next_action": "status"}` when every
      item in the current queue has a recorded verdict. This does not mean the whole run is verified.
   2. Start **one fresh sub-agent that has not seen the scan summary or any other verdict**. Give it only: the
      verifier prompt below, that one item and the repository path. If the agent cannot start sub-agents, do one
      separate pass per item from the item alone, and say in the summary that verification was done in-session,
      not independently.
   3. Keep the reply only if it is exactly one JSON object in the format below. Do not repair a malformed or
      prose-wrapped reply: discard it, retry once with a new verifier, otherwise leave that finding pending
      (record nothing). Apply valid records before stopping or replacing the queue. Report the fingerprint
      and `verifier_result_invalid_after_retry` as the blocker; do not fabricate a needs-validation verdict.
   4. Save the kept object: `python3 -I scripts/triage.py record security-run-<datetime> -` with the object on
      stdin (or a file path instead of `-`). It is checked and stored as `triage/verdicts/<fingerprint>.json`;
      a rejected object stores nothing. A second verdict for the same finding needs `--replace`.

   Report the pending count from the summary; never present pending findings as clean. Never open
   `queue-index.json`, the batch files, `findings/` shards or `security-report.json` yourself — on a large run
   they do not fit in context; `next` hands you exactly one item.
3. `python3 -I scripts/triage.py apply security-run-<datetime>` merges every recorded verdict. `apply` is all or
   nothing: if it lists errors, fix or delete the named file in `triage/verdicts/` and apply again. It
   regenerates `SUMMARY.md` and the three reports and writes `NEEDS-VALIDATION.md`. A verdict on a grouped
   item's fingerprint also applies to every group member in the current queue that has no verdict yet and no
   record of its own. (A whole `{"verdicts": [ ... ]}` file still works: `triage.py apply <run> VERDICTS.json`.)
4. Run `python3 -I scripts/triage.py status security-run-<datetime>`. It reads the validated report and
   prints compact live verification counts, batch progress and `next_action`.
   - `apply` means saved verdicts have not reached the report. Apply them before changing the queue,
     including when resuming. `queue` refuses to overwrite a queue while verdicts remain unapplied.
   - `next` means the current batch still has unrecorded items. Resume it without rebuilding.
   - `queue` means the applied batch is exhausted but eligible findings remain. Queue the next batch,
     using `--repo NAME` when working repo by repo.
   - `done` means the run's profile has no pending eligible findings. Needs-validation verdicts still
     need owner checks; done does not mean clean.
5. Repeat until `python3 -I scripts/triage.py status security-run-<datetime> --require-complete` exits 0.
   The default 25 items limit one batch, not total work or agent invocations. Do not stop after one batch
   or invent a total cap. A user-requested skip or an actual execution, verifier or resource blocker must
   appear in the final summary with the pending count and the command to resume the same run.

When Phase 10 was requested, follow the scheduling rules in [audit/WORKFLOW.md](audit/WORKFLOW.md).
Phase 9 pending findings do not block Phase 10. Keep its audit-agent budget separate from scanner
verification. Never load whole report shards into the parent context to count progress.

## Verifier prompt

```text
You did not find this issue and you have not seen any other result. Your job is to try to
REFUTE one scanner finding using only the repository source and the context you are given.

Rules:
- Read files in the repository; do not change, create or delete any file.
- Do not run any code, script, test, build or package manager from the repository.
- Do not contact any network service, deployed endpoint or registry.
- Secret findings: never open the file that holds the secret and never write any part of a
  credential in your answer. Judge only from the path, the rule and the repository layout.

Check, in order:
1. The location: does the file and line exist, and is the cited code really what the rule claims?
2. Reachability: is the code shipped and reachable from a lower-trust input (HTTP request, CLI
   argument, message, file, dependency install), or is it a test, fixture, example, docs,
   dead code or a dev-only dependency?
3. Controls: name the strongest validation, authorisation, escaping, framework or configuration
   control on the path. Does it already prevent the issue?
4. For dependency findings: is the vulnerable function or package feature actually used, and is
   the installed version really in the affected range?
5. Severity: state the realistic likelihood and the concrete impact you can show from source.
   Use the anchors you were given; overall severity can never exceed the impact.
6. If the item has a "group", your verdict is recorded for every listed location. Give a verdict
   only if it holds for all of them; if the locations differ, answer "needs_validation" and name
   which locations differ in the blocker.

Decide:
- "confirmed"        the issue is real and reachable; give evidence, likelihood, impact, severity.
- "needs_validation" a specific fact you cannot see from source decides it (runtime config, which
                     image is deployed, whether a credential is live); name that blocker exactly and
                     give a safe plan for a person to check it. Never a parking place for a hunch.
- "rejected"         the source refutes it (test fixture, unreachable, mitigated, not affected
                     version, false match); give the reason.

Return exactly one JSON object and nothing else:
{"fingerprint": "<from the item>", "verdict": "confirmed",
 "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "likelihood": "high|medium|low",
 "impact": "critical|high|medium|low|informational", "evidence": "<file:line facts>"}
{"fingerprint": "...", "verdict": "needs_validation", "blocker": "...", "validation_plan": "..."}
{"fingerprint": "...", "verdict": "rejected", "reason": "..."}
```

## Verdict format

| Verdict | Required fields | Not allowed | Effect in the report |
|---|---|---|---|
| `confirmed` | `evidence`, `likelihood`, `impact`, `severity` (≤ impact) | `blocker`, `reason` | verified severity replaces the tool's (both shown) |
| `needs_validation` | `blocker`, `validation_plan` | `severity` | keeps the tool's severity, listed in `NEEDS-VALIDATION.md` |
| `rejected` | `reason` | `severity` | moved to "Dismissed (with reason)", out of all counts |

Text fields are capped at 2,000 characters and pass through secret redaction. Unknown fields, unknown or
duplicate fingerprints and non-JSON files are refused.

## Severity anchors

- **critical** — an unauthenticated actor gains code execution, full data-store access, or takeover of
  arbitrary accounts.
- **high** — an actor fully defeats an explicit security control with real consequences: authentication bypass,
  cross-tenant read or write, stored script execution affecting other users, authenticated code execution, or an
  unauthenticated remote stop of a shared service.
- **medium** — a real boundary violation with limited blast radius, uncommon preconditions, or consequences
  confined to a narrow resource set.
- **low** — disclosure of non-secret internals, or an effect requiring sustained effort for minimal gain.
- **informational** — a confirmed but minimal-impact observation, useful mainly as a prerequisite inside a
  larger finding.

The high/medium discriminator: does the demonstrated result fully defeat an explicit control for an action with
real consequences, or only weaken it? If you cannot state the concrete damage, the severity is lower than it
feels.

For this skill: a secret that is live and grants access stays CRITICAL; a known-compromised package (Shai-Hulud
AFFECTED) is not downgraded by reachability — installing it is the attack.
