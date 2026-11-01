# Structured run events

speckit-auto records one UTF-8 JSON object per line at
`<worktree>/.speckit/events.jsonl`. The contract is versioned with
`schema_version: 1`; `run_id` is a UUID that stays stable across resumes and
changes for a fresh retry. Sequence numbers start at 1 and increase within one
run. Timestamps are ISO 8601 values with an explicit UTC offset.

Use Node.js 22.13 or later. The standalone emitter is
`scripts/run-events.mjs`:

Retain `source_repo_path`, `worktree_path`, `run_id`, optional uppercase `issue_key`,
and absolute `event_helper_path` in run state. Resolve the helper from the loaded skill
folder. Paths may contain spaces or shell metacharacters. Use the host's argument-vector
tool when available. On bash hosts, supply path variables as process-environment data when
the host supports it. Otherwise shell-quote each complete variable value with POSIX single
quotes, escaping an embedded single quote as `'"'"'`. Never paste a raw path/URL into shell
source, including double-quoted assignments, which still expand `$()` and backticks.
Then use these exact invocations; the quoted heredocs prevent source expansion.

Initialization, including discovery refresh after a move:

```sh
node --input-type=module - "$event_helper_path" "$source_repo_path" "$worktree_path" "$run_id" "${issue_key-}" <<'NODE'
import { spawnSync } from 'node:child_process';
const [helper, repo, worktree, runId, issueKey] = process.argv.slice(2);
const args = [helper, 'init', '--repo', repo, '--worktree', worktree, '--run-id', runId];
if (issueKey) args.push('--issue-key', issueKey);
const result = spawnSync(process.execPath, args, { stdio: 'inherit' });
if (result.error) throw result.error;
process.exit(result.status ?? 1);
NODE
```

Every `emit` instruction in a stage means execute this invocation with the corresponding
allowlisted `payload` object. Change only that object, not the invocation. Compose bounded
questions/messages yourself, never paste raw user or tool text into JavaScript or shell
source. For runtime values such as a confirmed PR URL, pass them as an additional
argument-vector element and read them from `process.argv`, never insert them into code.

```sh
node --input-type=module - "$event_helper_path" "$worktree_path" "$run_id" <<'NODE'
import { spawnSync } from 'node:child_process';
const [helper, worktree, runId] = process.argv.slice(2);
const payload = { type: 'stage_finished', stage: '01-intake' };
const result = spawnSync(process.execPath, [helper, 'emit', '--worktree', worktree, '--run-id', runId], {
  input: JSON.stringify(payload), stdio: ['pipe', 'inherit', 'inherit'],
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
NODE
```

For a confirmed URL supplied as the shell-safe data variable `pr_url`:

```sh
node --input-type=module - "$event_helper_path" "$worktree_path" "$run_id" "$pr_url" <<'NODE'
import { spawnSync } from 'node:child_process';
const [helper, worktree, runId, prUrl] = process.argv.slice(2);
const payload = { type: 'pr_opened', pr_url: prUrl };
const result = spawnSync(process.execPath, [helper, 'emit', '--worktree', worktree, '--run-id', runId], {
  input: JSON.stringify(payload), stdio: ['pipe', 'inherit', 'inherit'],
});
if (result.error) throw result.error;
process.exit(result.status ?? 1);
NODE
```

The `emit` input is a JSON object containing `type` and only that event's
payload fields. The emitter adds identity, sequence, and timestamp fields.
Always pass arguments as an argument vector; never interpolate event content
into shell commands. It JSON-serializes data, appends one complete line, and
fails if validation or a write fails.
Check the process exit status before the next pipeline action. A failed init/emit is an
instrumentation error: stop, report the diagnostic, and never claim completion. Do not
swallow it, continue without events, or recursively attempt another event on the broken
writer. Resume only after repairing the cause and inspecting the recorded history.

`init` writes `run_started` and `stage_started` (`01-intake`) once for a new
attempt. Both records go out in a single append and a single fsync, so an
interrupted producer cannot leave a half-initialized run behind. On resume it
validates prior JSONL history, retains the next sequence, and does not repeat
start events. It atomically updates the source repository's
`.speckit/runs/<run_id>.json` discovery record, including the canonical
worktree path. A move updates this record without rewriting event history.
The emitter uses an exclusive lock and rejects overlapping writers rather
than risking duplicate sequence numbers. The lock records its owner as
`<pid> <createdAtMs>`. A lock is reclaimed automatically only when its owner
is provably gone — the pid no longer exists and the lock is at least 30 seconds
old — and the reclaiming process re-runs the exclusive create, so two racing
reclaimers can never both win. A lock whose owner is alive, whose record is
missing or unreadable, or whose owner died moments ago is left in place and
reported instead of removed: dropping a live lock would let two producers write
events and duplicate sequence numbers. To clear a leftover lock manually, run

```sh
node "$event_helper_path" unlock --worktree "$worktree_path"
```

which refuses to remove a lock whose pid is still running.

**Interrupted writes are repaired, not fatal.** A record is durable only once its
terminating newline reaches the disk. Before reading, the producer truncates a
trailing line that has no newline — the remains of an interrupted write — back to
the last complete record, and reports the repair on stderr. Such a line was never
acknowledged, because sequence numbers are derived from the file itself; no
complete record is ever removed. A run that carries only `run_started` is an
initialization that was interrupted between its two records: `init` completes it in
place, and every other run in the file stays usable. `emit` refuses to write into
a run that is not yet initialized, because sequence 2 must be the first
`stage_started` and any other record there would make the file unreadable.

## Event variants

All events contain `schema_version`, `run_id`, `seq`, `ts`, and `type`; ticket
runs also contain `issue_key` (`PROJECT-123`). Exact event-specific fields:

| `type` | Fields |
|---|---|
| `run_started` | none |
| `stage_started`, `stage_finished` | `stage` |
| `gate_waiting` | `stage`, `gate`; optional `question`, `options` |
| `gate_answered` | `stage`, `gate` |
| `question_waiting` | `stage`, `question`; optional `options` |
| `pr_opened` | `pr_url` |
| `run_completed` | none |
| `run_failed` | `reason: {code, message}` |

Stages are `01-intake`, `02-spec-design`, `03-implement-review`, and
`04-finish`. Failure codes are `review_loop_stuck`, `tests_failing`,
`git_error`, `budget_exceeded`, `policy_blocked`, and `crashed`. A reason
message is a one-line summary, not raw process output. Only absolute HTTPS PR
URLs without embedded credentials are accepted.

The strict consumer limit is 32 option labels, 100 characters per label,
64-character lowercase gate identifiers, 500-character questions and failure
messages, 500-character PR URLs, and 16 KiB per serialized JSONL line. The
producer caps questions and failure messages at 500 characters; consumers
reject raw overlong values. Unknown fields and versions are errors.

Never put prompts, file contents, credentials, tool output, or raw human
answers in events. Free text is deliberately composed, single-line, and
redacted for recognizable credential forms. The emitter is standalone and
uses only Node.js built-in modules.
