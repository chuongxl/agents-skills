# Structured run events

speckit-auto records one UTF-8 JSON object per line at
`<worktree>/.speckit/events.jsonl`. The contract is versioned with
`schema_version: 1`; `run_id` is a UUID that stays stable across resumes and
changes for a fresh retry. Sequence numbers start at 1 and increase within one
run. Timestamps are ISO 8601 values with an explicit UTC offset.

Use Node.js 22.13 or later. The standalone emitter is
`scripts/run-events.mjs`:

```sh
node scripts/run-events.mjs init --repo <source-repo> --worktree <worktree> --run-id <uuid> [--issue-key <key>]
printf '%s\n' '{"type":"stage_finished","stage":"01-intake"}' |
  node scripts/run-events.mjs emit --worktree <worktree> --run-id <uuid>
```

The `emit` input is a JSON object containing `type` and only that event's
payload fields. The emitter adds identity, sequence, and timestamp fields.
Always pass arguments as an argument vector; never interpolate event content
into shell commands. It JSON-serializes data, appends one complete line, and
fails if validation or a write fails.

`init` writes `run_started` and `stage_started` (`01-intake`) once for a new
attempt. On resume it validates prior JSONL history, retains the next sequence,
and does not repeat start events. It atomically updates the source repository's
`.speckit/runs/<run_id>.json` discovery record, including the canonical
worktree path. A move updates this record without rewriting event history.
The emitter uses an exclusive lock and rejects overlapping writers rather
than risking duplicate sequence numbers; remove a lock only after confirming
its writer is no longer running.

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
