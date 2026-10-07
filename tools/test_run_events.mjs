import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { validateRunEvent } from '../speckit-auto/scripts/run-events.mjs';

const fixtures = [
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":1,"ts":"2026-10-07T20:00:00+07:00","type":"run_started"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":2,"ts":"2026-10-07T20:00:01+07:00","type":"stage_started","stage":"01-intake"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":3,"ts":"2026-10-07T20:00:02+07:00","type":"stage_finished","stage":"01-intake"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":4,"ts":"2026-10-07T20:00:03+07:00","type":"gate_waiting","stage":"01-intake","gate":"worktree-review","question":"Review worktree","options":["Approve","Reject"]}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":5,"ts":"2026-10-07T20:00:04+07:00","type":"gate_answered","stage":"01-intake","gate":"worktree-review"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":6,"ts":"2026-10-07T20:00:05+07:00","type":"question_waiting","stage":"02-spec-design","question":"Choose a provider","options":["github-speckit","superpowers"]}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":7,"ts":"2026-10-07T20:00:06+07:00","type":"pr_opened","pr_url":"https://github.com/example/project/pull/18"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":8,"ts":"2026-10-07T20:00:07+07:00","type":"run_completed"}',
  '{"schema_version":1,"run_id":"123e4567-e89b-42d3-a456-426614174000","issue_key":"US-18","seq":9,"ts":"2026-10-07T20:00:08+07:00","type":"run_failed","reason":{"code":"tests_failing","message":"Focused tests failed"}}',
];

const helperPath = new URL('../speckit-auto/scripts/run-events.mjs', import.meta.url);

function run(args, input = '') {
  return spawnSync(process.execPath, [helperPath.pathname, ...args], {
    encoding: 'utf8',
    input,
  });
}

function makeWorkspace(t) {
  const root = fs.mkdtempSync(path.join(process.cwd(), 'tools', '.run-events-test-'));
  const repo = path.join(root, 'repo');
  const worktree = path.join(root, 'worktree');
  fs.mkdirSync(repo);
  fs.mkdirSync(worktree);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return { repo, worktree };
}

test('validates all nine serialized event contract fixtures', () => {
  for (const fixture of fixtures) assert.equal(validateRunEvent(JSON.parse(fixture)).type, JSON.parse(fixture).type);
});

test('rejects impossible calendar dates and accepts Gregorian leap days', () => {
  const event = JSON.parse(fixtures[0]);
  for (const ts of [
    '2026-02-31T20:00:00+07:00',
    '2025-02-29T20:00:00+07:00',
    '1900-02-29T20:00:00+07:00',
  ]) {
    assert.throws(() => validateRunEvent({ ...event, ts }), /timestamp/i);
  }
  for (const ts of ['2024-02-29T20:00:00+07:00', '2000-02-29T20:00:00+07:00']) {
    assert.equal(validateRunEvent({ ...event, ts }).ts, ts);
  }
});

test('rejects unknown reason codes, fields, and schema versions', () => {
  const base = JSON.parse(fixtures[8]);
  assert.throws(() => validateRunEvent({ ...base, reason: { code: 'unknown', message: 'No' } }), /reason\.code/);
  assert.throws(() => validateRunEvent({ ...base, extra: true }), /unknown field/);
  assert.throws(() => validateRunEvent({ ...base, schema_version: 2 }), /schema_version/);
});

test('keeps a maximum UTF-8 payload within the JSONL line limit', () => {
  const base = JSON.parse(fixtures[5]);
  const event = validateRunEvent({
    ...base,
    options: Array(32).fill('😀'.repeat(100)),
    question: '😀'.repeat(500),
  });
  assert.ok(Buffer.byteLength(JSON.stringify(event), 'utf8') + 1 <= 16 * 1024);
});

test('rejects metadata that is not an issue key and blocks overlapping writers', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174116';
  const invalid = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId, '--issue-key', 'US-18;touch nope']);
  assert.notEqual(invalid.status, 0);
  assert.match(invalid.stderr, /issue key/i);
  fs.mkdirSync(path.join(worktree, '.speckit'), { recursive: true });
  fs.writeFileSync(path.join(worktree, '.speckit', '.run-events.lock'), '999999\n');
  const locked = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.notEqual(locked.status, 0);
  assert.match(locked.stderr, /another producer|lock exists/i);
});

test('emits bounded Unicode and shell metacharacter text without executing it', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174111';
  const marker = path.join(repo, 'executed');
  const question = `What about 東京😀?; touch ${marker}`;
  const init = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId, '--issue-key', 'US-18']);
  assert.equal(init.status, 0, init.stderr);
  const emitted = run(
    ['emit', '--worktree', worktree, '--run-id', runId],
    JSON.stringify({ type: 'question_waiting', stage: '02-spec-design', question }),
  );
  assert.equal(emitted.status, 0, emitted.stderr);
  const lines = fs.readFileSync(path.join(worktree, '.speckit', 'events.jsonl'), 'utf8').trim().split('\n');
  const last = JSON.parse(lines.at(-1));
  assert.equal(last.question, question.slice(0, 500));
  assert.equal(fs.existsSync(marker), false);
});

test('caps oversized questions and rejects overlong consumer events', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174112';
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
  const emitted = run(
    ['emit', '--worktree', worktree, '--run-id', runId],
    JSON.stringify({ type: 'question_waiting', stage: '02-spec-design', question: 'x'.repeat(501) }),
  );
  assert.equal(emitted.status, 0, emitted.stderr);
  const last = fs
    .readFileSync(path.join(worktree, '.speckit', 'events.jsonl'), 'utf8')
    .trim()
    .split('\n')
    .at(-1);
  assert.equal(JSON.parse(last).question.length, 500);
  assert.throws(() => validateRunEvent(JSON.parse(last).question.length > 500 ? JSON.parse(last) : {
    ...JSON.parse(last),
    question: 'x'.repeat(501),
  }), /question/);
});

test('redacts recognizable credentials from bounded event text', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174113';
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
  const emitted = run(
    ['emit', '--worktree', worktree, '--run-id', runId],
    JSON.stringify({
      type: 'run_failed',
      reason: { code: 'crashed', message: 'Bearer abcdefghijklmnopqrstuvwxyz123456' },
    }),
  );
  assert.equal(emitted.status, 0, emitted.stderr);
  const event = JSON.parse(fs.readFileSync(path.join(worktree, '.speckit', 'events.jsonl'), 'utf8').trim().split('\n').at(-1));
  assert.match(event.reason.message, /REDACTED/);
  assert.doesNotMatch(event.reason.message, /abcdefghijklmnopqrstuvwxyz/);
});

test('resume preserves sequence and updates atomic discovery after a worktree move', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174114';
  const first = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId, '--issue-key', 'US-18']);
  assert.equal(first.status, 0, first.stderr);
  const movedWorktree = path.join(repo, 'worktree-moved');
  fs.renameSync(worktree, movedWorktree);
  const resumed = run(['init', '--repo', repo, '--worktree', movedWorktree, '--run-id', runId, '--issue-key', 'US-18']);
  assert.equal(resumed.status, 0, resumed.stderr);
  const emitted = run(
    ['emit', '--worktree', movedWorktree, '--run-id', runId],
    JSON.stringify({ type: 'stage_finished', stage: '01-intake' }),
  );
  assert.equal(emitted.status, 0, emitted.stderr);
  const events = fs
    .readFileSync(path.join(movedWorktree, '.speckit', 'events.jsonl'), 'utf8')
    .trim()
    .split('\n')
    .map((line) => JSON.parse(line));
  assert.deepEqual(events.map((event) => event.seq), [1, 2, 3]);
  assert.deepEqual(events.map((event) => event.type), ['run_started', 'stage_started', 'stage_finished']);
  const discovery = JSON.parse(fs.readFileSync(path.join(repo, '.speckit', 'runs', `${runId}.json`), 'utf8'));
  assert.equal(discovery.worktree_path, movedWorktree);
});

test('refuses to continue when an existing event file has invalid sequence data', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174115';
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
  fs.appendFileSync(
    path.join(worktree, '.speckit', 'events.jsonl'),
    `${JSON.stringify({ ...JSON.parse(fixtures[0]), run_id: runId })}\n`,
  );
  const resumed = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.notEqual(resumed.status, 0);
  assert.match(resumed.stderr, /sequence|duplicate/i);
});

test('refuses an existing JSONL line over the 16 KiB limit', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174117';
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
  fs.appendFileSync(path.join(worktree, '.speckit', 'events.jsonl'), `${'x'.repeat(16 * 1024)}\n`);
  const resumed = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.notEqual(resumed.status, 0);
  assert.match(resumed.stderr, /exceeds 16384 bytes/);
});
