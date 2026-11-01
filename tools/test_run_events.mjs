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

const readSkill = (file) => fs.readFileSync(new URL(`../speckit-auto/${file}`, import.meta.url), 'utf8');

const skillVersion = readSkill('SKILL.md').match(/version: "([0-9]+\.[0-9]+\.[0-9]+)"/)?.[1];
const escapeRe = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const versionPattern = (value) => new RegExp(escapeRe(value));

test('entry documents run identity, runtime, and progressive event loading', () => {
  const entry = readSkill('SKILL.md');
  assert.match(entry, /--run-id <uuid>/);
  assert.match(entry, /Node\.js >=22\.13/);
  assert.ok(skillVersion, 'SKILL.md must declare metadata.version');
  assert.match(entry, versionPattern(`version: "${skillVersion}"`));
  assert.match(entry, /run-events\.md.*first event initialization/);
  assert.match(entry, /exactly three files/);
});

test('intake initializes the exact producer CLI and refreshes discovery after moves', () => {
  const intake = readSkill('references/pipeline/stage-01-intake.md');
  assert.match(intake, /run-events\.md/);
  assert.match(intake, /init.*run_started.*stage_started/s);
  assert.match(intake, /git worktree move.*init.*discovery/s);
  assert.match(intake, /source_repo_path.*event_helper_path.*run_id/s);
  assert.match(intake, /stage_finished.*01-intake/s);
  assert.match(intake, /\.speckit\/.*git-ignored/s);
});

test('all later stages explicitly emit entry, success boundaries, and classified exits', () => {
  for (const [file, stage] of [
    ['stage-02-spec-design.md', '02-spec-design'],
    ['stage-03-implement-review.md', '03-implement-review'],
    ['stage-04-finish.md', '04-finish'],
  ]) {
    const text = readSkill(`references/pipeline/${file}`);
    assert.match(text, new RegExp(`stage_started.*${stage}`));
    assert.match(text, new RegExp(`stage_finished.*${stage}`));
    assert.match(text, /run_failed/);
  }
  assert.match(readSkill('references/pipeline/stage-03-implement-review.md'), /review_loop_stuck/);
  assert.match(readSkill('references/shared/commit.md'), /run_failed.*git_error/s);
});

test('named gates and questions preserve default, YOLO, and request-change semantics', () => {
  const design = readSkill('references/pipeline/stage-02-spec-design.md');
  const finish = readSkill('references/pipeline/stage-04-finish.md');
  for (const gate of ['spec-approval', 'plan-approval', 'implementation-start']) {
    assert.ok(design.includes(gate), `missing ${gate}`);
  }
  assert.ok(finish.includes('implementation-approval'));
  for (const text of [design, finish]) {
    assert.match(text, /gate_waiting/);
    assert.match(text, /gate_answered/);
    assert.match(text, /question_waiting/);
    assert.match(text, /Request changes.*not.*run_failed/s);
  }
  assert.match(design, /github-speckit.*superpowers/s);
  assert.match(design, /YOLO.*no.*gate_waiting/s);
  const rules = readSkill('references/shared/operating-rules.md');
  assert.match(rules, /question_waiting.*before.*ask/s);
  assert.match(rules, /stage_started.*after.*response/s);
  assert.match(rules, /raw.*answers/);
});

test('completion follows required spec push and only confirmed PR URLs are emitted', () => {
  const finish = readSkill('references/pipeline/stage-04-finish.md');
  assert.match(finish, /completion commit.*push/s);
  assert.match(finish, /actual.*HTTPS.*PR URL.*pr_opened/s);
  const finalReport = finish.slice(finish.indexOf('## Final Report'));
  assert.match(finalReport, /Only after all required commits, the spec completion push, and execution-report updates\s+succeed, emit/);
  const successBoundary = finalReport.indexOf('{type: "stage_finished", stage: "04-finish"}');
  const terminalSuccess = finalReport.indexOf('{type: "run_completed"}');
  assert.ok(successBoundary > finalReport.indexOf('spec completion push'));
  assert.ok(terminalSuccess > successBoundary, 'terminal success must follow the final pushed-stage boundary');
  assert.match(finish, /write.*error.*never.*run_completed/s);
});

test('documented JSON stdin invocation is executable and uses only Node builtins', (t) => {
  const docs = readSkill('references/shared/run-events.md');
  const example = docs.match(/```sh\n(node --input-type=module - "\$event_helper_path" "\$worktree_path" "\$run_id" <<'NODE'\n([\s\S]*?)\nNODE)\n```/);
  assert.ok(example, 'missing exact shell-safe Node emit example');
  assert.doesNotMatch(docs, /echo .*type|printf.*type/);
  assert.match(example[2], /JSON\.stringify\(payload\)/);
  assert.match(example[2], /spawnSync\(process\.execPath/);
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174118';
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
  const result = spawnSync(process.execPath, ['--input-type=module', '-', helperPath.pathname, worktree, runId], {
    encoding: 'utf8', input: example[2],
  });
  assert.equal(result.status, 0, result.stderr);
  const event = JSON.parse(fs.readFileSync(path.join(worktree, '.speckit', 'events.jsonl'), 'utf8').trim().split('\n').at(-1));
  assert.equal(event.type, 'stage_finished');
  assert.equal(event.stage, '01-intake');
});

test('documented init, emit, and confirmed-PR shell examples preserve argument data', (t) => {
  const docs = readSkill('references/shared/run-events.md');
  const examples = [...docs.matchAll(/```sh\n([\s\S]*?)\n```/g)].map((match) => match[1]);
  assert.equal(examples.length, 4);
  const { repo, worktree } = makeWorkspace(t);
  const hostileWorktree = path.join(repo, "worktree ' 東京;$(touch injected)");
  fs.renameSync(worktree, hostileWorktree);
  const runId = '123e4567-e89b-42d3-a456-426614174119';
  const prUrl = 'https://github.com/example/project/pull/18?note=$(touch%20injected)&label=東京';
  const env = {
    ...process.env,
    event_helper_path: helperPath.pathname,
    source_repo_path: repo,
    worktree_path: hostileWorktree,
    run_id: runId,
    issue_key: 'US-18',
    pr_url: prUrl,
  };
  for (const example of examples) {
    const result = spawnSync('bash', ['-c', example], { encoding: 'utf8', env, cwd: repo });
    assert.equal(result.status, 0, result.stderr);
  }
  const eventsPath = path.join(hostileWorktree, '.speckit', 'events.jsonl');
  const events = fs.readFileSync(eventsPath, 'utf8').trim().split('\n').map(JSON.parse);
  assert.deepEqual(events.map((event) => event.type), [
    'run_started', 'stage_started', 'stage_finished', 'pr_opened',
  ]);
  assert.deepEqual(events.map((event) => event.seq), [1, 2, 3, 4]);
  assert.ok(events.every((event) => event.issue_key === 'US-18'));
  assert.equal(events.at(-1).pr_url, prUrl);
  assert.equal(fs.existsSync(path.join(repo, 'injected')), false);
  const beforeFailure = fs.readFileSync(eventsPath, 'utf8');
  fs.writeFileSync(path.join(hostileWorktree, '.speckit', '.run-events.lock'), `${process.pid} ${Date.now()}\n`);
  const failed = spawnSync('bash', ['-c', examples[1]], { encoding: 'utf8', env, cwd: repo });
  assert.notEqual(failed.status, 0);
  assert.match(failed.stderr, /another producer|lock exists/i);
  assert.equal(fs.readFileSync(eventsPath, 'utf8'), beforeFailure);
});

test('documented identities and badges agree, and manual event paths are covered', () => {
  const root = fs.readFileSync(new URL('../README.md', import.meta.url), 'utf8');
  assert.ok(skillVersion, 'SKILL.md must declare metadata.version');
  assert.match(root, new RegExp(`speckit-auto.*--run-id <uuid>.*v${versionPattern(skillVersion).source}`));
  const readme = readSkill('README.md');
  assert.match(readme, versionPattern(`version-${skillVersion}-blue`));
  assert.match(readme, versionPattern(`**Version**: ${skillVersion}`));
  const cases = fs.readFileSync(new URL('../test-case/speckit-auto/test-cases.md', import.meta.url), 'utf8');
  for (const scenario of [
    'Default happy path', 'YOLO happy path', 'Request changes', 'Resume and move', 'Fresh retry',
    'Failed event write', 'Manual questions', 'Terminal exits', 'PR confirmation', 'PR publish gate',
    'Completion push failure',
  ]) assert.ok(cases.includes(scenario), `missing manual case ${scenario}`);
});

function run(args, input = '') {
  return spawnSync(process.execPath, [helperPath.pathname, ...args], {
    encoding: 'utf8',
    input,
  });
}

test('the CLI runs when invoked through a symlinked skill directory', (t) => {
  const root = fs.mkdtempSync(path.join(process.cwd(), 'tools', '.run-events-link-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const link = path.join(root, 'speckit-auto');
  fs.symlinkSync(path.dirname(path.dirname(helperPath.pathname)), link);
  const result = spawnSync(process.execPath, [path.join(link, 'scripts', 'run-events.mjs')], { encoding: 'utf8' });
  assert.match(result.stderr, /usage: run-events\.mjs/);
  assert.notEqual(result.status, 0);
});

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
  // A live owner, not a dead pid: the emitter reclaims locks whose owner is provably gone.
  fs.writeFileSync(path.join(worktree, '.speckit', '.run-events.lock'), `${process.pid} ${Date.now()}\n`);
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

test('reclaims a lock whose owner is dead, and refuses one whose owner is alive or unreadable', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174113';
  const lockPath = path.join(worktree, '.speckit', '.run-events.lock');
  fs.mkdirSync(path.join(worktree, '.speckit'), { recursive: true });

  // Owner is dead and the lock is older than the staleness window: reclaimed automatically.
  fs.writeFileSync(lockPath, `999999 ${Date.now() - 60_000}\n`);
  const reclaimed = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.equal(reclaimed.status, 0, reclaimed.stderr);
  assert.equal(fs.existsSync(lockPath), false);

  // Owner is dead but the lock is fresh: not yet reclaimable, and the reason is reported.
  fs.writeFileSync(lockPath, `999999 ${Date.now()}\n`);
  const fresh = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.notEqual(fresh.status, 0);
  assert.match(fresh.stderr, /dead pid/i);

  // No readable owner: never reclaimed automatically, because the writer may be alive.
  fs.writeFileSync(lockPath, '');
  const ownerless = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.notEqual(ownerless.status, 0);
  assert.match(ownerless.stderr, /no readable owner/i);
  assert.equal(fs.existsSync(lockPath), true);

  // The documented manual recovery clears an owner-less lock.
  const cleared = run(['unlock', '--worktree', worktree]);
  assert.equal(cleared.status, 0, cleared.stderr);
  assert.equal(fs.existsSync(lockPath), false);
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
});

test('unlock refuses a lock whose owner is running and clears a dead one', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const lockPath = path.join(worktree, '.speckit', '.run-events.lock');
  fs.mkdirSync(path.join(worktree, '.speckit'), { recursive: true });

  fs.writeFileSync(lockPath, `${process.pid} ${Date.now()}\n`);
  const live = run(['unlock', '--worktree', worktree]);
  assert.notEqual(live.status, 0);
  assert.match(live.stderr, /running process/i);
  assert.equal(fs.existsSync(lockPath), true);

  fs.writeFileSync(lockPath, `999999 ${Date.now() - 60_000}\n`);
  const dead = run(['unlock', '--worktree', worktree]);
  assert.equal(dead.status, 0, dead.stderr);
  assert.match(dead.stdout, /removed stale lock/i);
  assert.equal(fs.existsSync(lockPath), false);

  const missing = run(['unlock', '--worktree', worktree]);
  assert.equal(missing.status, 0, missing.stderr);
  assert.match(missing.stdout, /no lock is present/i);
});

test('a successful write is not turned into a failure by lock cleanup', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174114';
  const lockPath = path.join(worktree, '.speckit', '.run-events.lock');
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);

  // A racing cleaner removes the lock between the write and the release. The event must
  // still be recorded and the command must still succeed.
  const racing = spawnSync(process.execPath, ['-e', `
    const fs = require('node:fs');
    const { spawnSync } = require('node:child_process');
    const helper = ${JSON.stringify(helperPath.pathname)};
    const lock = ${JSON.stringify(lockPath)};
    const timer = setInterval(() => { try { fs.unlinkSync(lock); } catch {} }, 1);
    const result = spawnSync(process.execPath, [helper, 'emit', '--worktree', ${JSON.stringify(worktree)}, '--run-id', '${runId}'],
      { input: JSON.stringify({ type: 'stage_finished', stage: '01-intake' }), encoding: 'utf8' });
    clearInterval(timer);
    process.stdout.write(JSON.stringify({ status: result.status, stderr: result.stderr }));
  `], { encoding: 'utf8' });
  const outcome = JSON.parse(racing.stdout);
  assert.equal(outcome.status, 0, outcome.stderr);
  const events = fs.readFileSync(path.join(worktree, '.speckit', 'events.jsonl'), 'utf8').trim().split('\n').map(JSON.parse);
  assert.ok(events.some((event) => event.type === 'stage_finished'));
});

test('completes an interrupted initialization instead of failing every run in the file', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runA = '123e4567-e89b-42d3-a456-426614174201';
  const runB = '223e4567-e89b-42d3-a456-426614174202';
  const eventsPath = path.join(worktree, '.speckit', 'events.jsonl');
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runA]).status, 0);

  // A producer that died between the two initialization appends left one record.
  const lines = fs.readFileSync(eventsPath, 'utf8').trim().split('\n');
  fs.writeFileSync(eventsPath, `${lines[0]}\n`);

  // The interrupted run is completed, not rejected.
  const completed = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runA]);
  assert.equal(completed.status, 0, completed.stderr);
  const repaired = fs.readFileSync(eventsPath, 'utf8').trim().split('\n').map(JSON.parse);
  assert.equal(repaired.filter((event) => event.run_id === runA).length, 2);
  assert.equal(repaired.at(-1).type, 'stage_started');

  // An unrelated run in the same worktree is not blocked by the repaired run.
  const fresh = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runB]);
  assert.equal(fresh.status, 0, fresh.stderr);
  const emitted = run(
    ['emit', '--worktree', worktree, '--run-id', runB],
    JSON.stringify({ type: 'stage_finished', stage: '01-intake' }),
  );
  assert.equal(emitted.status, 0, emitted.stderr);
});

test('refuses to emit into a run that was never initialized, without corrupting the file', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174203';
  const eventsPath = path.join(worktree, '.speckit', 'events.jsonl');
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);

  const lines = fs.readFileSync(eventsPath, 'utf8').trim().split('\n');
  fs.writeFileSync(eventsPath, `${lines[0]}\n`);

  // Sequence 2 must be stage_started; emitting anything else there would write a record
  // that no later read can accept.
  const refused = run(
    ['emit', '--worktree', worktree, '--run-id', runId],
    JSON.stringify({ type: 'stage_finished', stage: '01-intake' }),
  );
  assert.notEqual(refused.status, 0);
  assert.match(refused.stderr, /not initialized/i);
  assert.equal(fs.readFileSync(eventsPath, 'utf8').trim().split('\n').length, 1);

  // The run is still recoverable through init.
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);
});

test('repairs an interrupted trailing record instead of rejecting the whole file', (t) => {
  const { repo, worktree } = makeWorkspace(t);
  const runId = '123e4567-e89b-42d3-a456-426614174204';
  const eventsPath = path.join(worktree, '.speckit', 'events.jsonl');
  assert.equal(run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]).status, 0);

  // A write that was cut short leaves a final line without its terminating newline.
  const content = fs.readFileSync(eventsPath, 'utf8');
  fs.writeFileSync(eventsPath, content.slice(0, content.length - 5));

  const repaired = run(['init', '--repo', repo, '--worktree', worktree, '--run-id', runId]);
  assert.equal(repaired.status, 0, repaired.stderr);
  const after = fs.readFileSync(eventsPath, 'utf8');
  assert.ok(after.endsWith('\n'), 'the repaired file must end with a complete record');
  assert.ok(after.length >= content.length - 5);
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
