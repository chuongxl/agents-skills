#!/usr/bin/env node
import { randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { TextDecoder } from 'node:util';
import { fileURLToPath } from 'node:url';

export const MAX_JSONL_LINE_BYTES = 16 * 1024;
export const STAGES = ['01-intake', '02-spec-design', '03-implement-review', '04-finish'];
export const REASON_CODES = [
  'review_loop_stuck',
  'tests_failing',
  'git_error',
  'budget_exceeded',
  'policy_blocked',
  'crashed',
];

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const ISSUE_KEY = /^[A-Z][A-Z0-9]*-\d+$/;
const GATE_ID = /^[a-z0-9][a-z0-9_-]{0,63}$/;
const OFFSET_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/;
const ISO_CALENDAR_DATE = /^(\d{4})-(\d{2})-(\d{2})T/;
const SECRET_PATTERNS = [
  /\bBearer\s+[A-Za-z0-9._~+/=-]{8,}/gi,
  /\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})\b/g,
  /\b(AWS_ACCESS_KEY_ID|password|passwd|token|api[_ -]?key|secret)\s*[:=]\s*\S+/gi,
  /\bAKIA[0-9A-Z]{16}\b/g,
];
const TYPES = {
  run_started: [],
  stage_started: ['stage'],
  stage_finished: ['stage'],
  gate_waiting: ['stage', 'gate', 'question', 'options'],
  gate_answered: ['stage', 'gate'],
  question_waiting: ['stage', 'question', 'options'],
  pr_opened: ['pr_url'],
  run_completed: [],
  run_failed: ['reason'],
};
const BASE_FIELDS = ['schema_version', 'run_id', 'issue_key', 'seq', 'ts', 'type'];

function fail(message) {
  throw new Error(message);
}

function isRecord(value) {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function exactKeys(value, allowed, label) {
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) fail(`${label}: unknown field "${key}"`);
  }
}

function text(value, label, max, { truncate = false } = {}) {
  if (typeof value !== 'string') fail(`${label} must be a string`);
  let result = value;
  if (truncate) result = [...result].slice(0, max).join('');
  if ([...result].length > max) fail(`${label} must be at most ${max} characters`);
  if (/[\u0000-\u001f\u007f\u2028\u2029]/u.test(result)) fail(`${label} must be single-line text`);
  const sanitized = sanitizeText(result);
  if (sanitized !== result) fail(`${label} contains recognizable credential material`);
  return result;
}

function sanitizeText(value) {
  let sanitized = value;
  for (const pattern of SECRET_PATTERNS) {
    pattern.lastIndex = 0;
    sanitized = sanitized.replace(pattern, (match, key) => (key ? `${key}=[REDACTED]` : '[REDACTED]'));
  }
  return sanitized;
}

function validateIsoTimestamp(value) {
  if (
    typeof value !== 'string' ||
    !OFFSET_ISO.test(value) ||
    !isValidCalendarDate(value) ||
    !Number.isFinite(Date.parse(value))
  ) {
    fail('ts must be a valid ISO timestamp with an explicit UTC offset');
  }
}

function isValidCalendarDate(value) {
  const date = ISO_CALENDAR_DATE.exec(value);
  if (!date) return false;
  const [year, month, day] = date.slice(1).map(Number);
  if (month < 1 || month > 12) return false;
  const leapYear = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysPerMonth = [31, leapYear ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  return day >= 1 && day <= daysPerMonth[month - 1];
}

function validateOptions(value, label) {
  if (!Array.isArray(value) || value.length > 32) fail(`${label} must contain at most 32 labels`);
  return value.map((option, index) => text(option, `${label}[${index}]`, 100));
}

export function validateRunEvent(value) {
  if (!isRecord(value)) fail('event must be an object');
  exactKeys(value, [...BASE_FIELDS, ...Object.values(TYPES).flat()], 'event');
  if (value.schema_version !== 1) fail('schema_version must be 1');
  if (typeof value.run_id !== 'string' || !UUID.test(value.run_id)) fail('run_id must be a UUID');
  if (value.issue_key !== undefined && (typeof value.issue_key !== 'string' || !ISSUE_KEY.test(value.issue_key))) {
    fail('issue_key must be a Jira issue key');
  }
  if (!Number.isSafeInteger(value.seq) || value.seq < 1) fail('seq must be a positive safe integer');
  validateIsoTimestamp(value.ts);
  if (typeof value.type !== 'string' || !Object.hasOwn(TYPES, value.type)) fail('type is not a supported run event');

  const payloadFields = TYPES[value.type];
  exactKeys(value, [...BASE_FIELDS, ...payloadFields], 'event');

  switch (value.type) {
    case 'run_started':
    case 'run_completed':
      break;
    case 'stage_started':
    case 'stage_finished':
    case 'gate_waiting':
    case 'gate_answered':
    case 'question_waiting':
      if (!STAGES.includes(value.stage)) fail('stage is not a supported stage');
      if (value.type === 'gate_waiting' || value.type === 'gate_answered') {
        if (typeof value.gate !== 'string' || !GATE_ID.test(value.gate)) fail('gate must be a safe identifier of at most 64 characters');
      }
      if (value.type === 'gate_waiting' && value.question !== undefined) text(value.question, 'question', 500);
      if (value.type === 'question_waiting') text(value.question, 'question', 500);
      if (value.options !== undefined) validateOptions(value.options, 'options');
      break;
    case 'pr_opened': {
      const url = text(value.pr_url, 'pr_url', 500);
      let parsed;
      try {
        parsed = new URL(url);
      } catch {
        fail('pr_url must be a valid HTTPS URL');
      }
      if (parsed.protocol !== 'https:' || !parsed.hostname || parsed.username || parsed.password) {
        fail('pr_url must be a valid HTTPS URL without credentials');
      }
      break;
    }
    case 'run_failed':
      if (!isRecord(value.reason)) fail('reason must be an object');
      exactKeys(value.reason, ['code', 'message'], 'reason');
      if (!REASON_CODES.includes(value.reason.code)) fail('reason.code is not a supported failure code');
      text(value.reason.message, 'reason.message', 500);
      break;
    default: {
      const exhaustive = value.type;
      fail(`unsupported event type: ${exhaustive}`);
    }
  }
  let serialized;
  try {
    serialized = JSON.stringify(value);
  } catch {
    fail('event cannot be serialized as JSON');
  }
  if (Buffer.byteLength(serialized, 'utf8') + 1 > MAX_JSONL_LINE_BYTES) {
    fail(`serialized line exceeds ${MAX_JSONL_LINE_BYTES} bytes`);
  }
  return value;
}

function validatePayload(raw) {
  if (!isRecord(raw)) fail('stdin event must be a JSON object');
  if (typeof raw.type !== 'string' || !Object.hasOwn(TYPES, raw.type)) fail('type is not a supported run event');
  const fields = TYPES[raw.type];
  exactKeys(raw, ['type', ...fields], 'stdin event');
  const result = { type: raw.type };
  if (fields.includes('stage')) result.stage = raw.stage;
  if (fields.includes('gate')) result.gate = raw.gate;
  if (fields.includes('question') && raw.question !== undefined) {
    if (typeof raw.question !== 'string') fail('question must be a string');
    result.question = [...sanitizeText(raw.question)].slice(0, 500).join('');
  }
  if (fields.includes('question') && raw.type === 'question_waiting' && raw.question === undefined) {
    fail('question is required for question_waiting');
  }
  if (fields.includes('options') && raw.options !== undefined) {
    if (!Array.isArray(raw.options) || raw.options.length > 32) fail('options must contain at most 32 labels');
    result.options = raw.options.map((option, index) => {
      if (typeof option !== 'string') fail(`options[${index}] must be a string`);
      return [...sanitizeText(option)].slice(0, 100).join('');
    });
  }
  if (fields.includes('pr_url')) result.pr_url = raw.pr_url;
  if (fields.includes('reason')) {
    if (!isRecord(raw.reason)) fail('reason must be an object');
    exactKeys(raw.reason, ['code', 'message'], 'reason');
    result.reason = {
      code: raw.reason.code,
      message: typeof raw.reason.message === 'string' ? [...sanitizeText(raw.reason.message)].slice(0, 500).join('') : raw.reason.message,
    };
  }
  return result;
}

function parseArgs(argv) {
  const [command, ...args] = argv;
  if (command !== 'init' && command !== 'emit') fail('usage: run-events.mjs init|emit [options]');
  const values = new Map();
  for (let i = 0; i < args.length; i += 2) {
    const key = args[i];
    const value = args[i + 1];
    if (!['--repo', '--worktree', '--run-id', '--issue-key'].includes(key) || !value || value.startsWith('--')) {
      fail(`invalid option or missing value: ${key}`);
    }
    if (values.has(key)) fail(`duplicate option: ${key}`);
    values.set(key, value);
  }
  const required = command === 'init' ? ['--repo', '--worktree', '--run-id'] : ['--worktree', '--run-id'];
  for (const key of required) if (!values.has(key)) fail(`${key} is required`);
  if (command === 'emit' && values.has('--issue-key')) fail('--issue-key is valid only with init');
  return { command, values };
}

function canonicalDirectory(value, label) {
  if (/[\u0000-\u001f\u007f]/u.test(value)) fail(`${label} contains control characters`);
  const resolved = path.resolve(value);
  let stat;
  try {
    stat = fs.statSync(resolved);
  } catch {
    fail(`${label} directory does not exist: ${resolved}`);
  }
  if (!stat.isDirectory()) fail(`${label} must be a directory`);
  return fs.realpathSync(resolved);
}

function parseEventFile(filePath) {
  let content;
  try {
    content = fs.readFileSync(filePath);
  } catch (error) {
    if (error.code === 'ENOENT') return [];
    throw error;
  }
  if (content.length === 0) return [];
  if (content.at(-1) !== 10) fail('events.jsonl has an incomplete final line');
  let decoded;
  try {
    decoded = new TextDecoder('utf-8', { fatal: true }).decode(content);
  } catch {
    fail('events.jsonl is not valid UTF-8');
  }
  const lines = decoded.split('\n');
  lines.pop();
  const sequenceByRun = new Map();
  const issueKeyByRun = new Map();
  const firstEventByRun = new Set();
  const eventCountByRun = new Map();
  const terminalRuns = new Set();
  const parsed = [];
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];
    if (!line) fail(`events.jsonl line ${index + 1} is empty`);
    if (Buffer.byteLength(line, 'utf8') + 1 > MAX_JSONL_LINE_BYTES) fail(`events.jsonl line ${index + 1} exceeds ${MAX_JSONL_LINE_BYTES} bytes`);
    let event;
    try {
      event = validateRunEvent(JSON.parse(line));
    } catch (error) {
      fail(`events.jsonl line ${index + 1}: ${error.message}`);
    }
    const expected = (sequenceByRun.get(event.run_id) ?? 0) + 1;
    if (event.seq !== expected) fail(`events.jsonl line ${index + 1}: duplicate or invalid sequence for run ${event.run_id}; expected ${expected}`);
    if (terminalRuns.has(event.run_id)) fail(`events.jsonl line ${index + 1}: event follows a terminal event`);
    if (!firstEventByRun.has(event.run_id)) {
      if (event.type !== 'run_started' || event.seq !== 1) fail(`events.jsonl line ${index + 1}: a run must start with run_started sequence 1`);
      firstEventByRun.add(event.run_id);
    } else if (event.type === 'run_started') {
      fail(`events.jsonl line ${index + 1}: duplicate run_started`);
    }
    if (expected === 2 && (event.type !== 'stage_started' || event.stage !== STAGES[0])) {
      fail(`events.jsonl line ${index + 1}: sequence 2 must start stage ${STAGES[0]}`);
    }
    if (event.type === 'run_completed' || event.type === 'run_failed') terminalRuns.add(event.run_id);
    eventCountByRun.set(event.run_id, expected);
    const priorIssueKey = issueKeyByRun.get(event.run_id);
    if (issueKeyByRun.has(event.run_id) && priorIssueKey !== event.issue_key) {
      fail(`events.jsonl line ${index + 1}: issue_key changed within a run`);
    }
    issueKeyByRun.set(event.run_id, event.issue_key);
    sequenceByRun.set(event.run_id, event.seq);
    parsed.push(event);
  }
  for (const [runId, count] of eventCountByRun) {
    if (count < 2) fail(`run ${runId} has incomplete initialization`);
  }
  return parsed;
}

function writeEvent(eventsPath, event) {
  validateRunEvent(event);
  const line = `${JSON.stringify(event)}\n`;
  const bytes = Buffer.from(line, 'utf8');
  if (bytes.length > MAX_JSONL_LINE_BYTES) fail(`serialized event exceeds ${MAX_JSONL_LINE_BYTES} bytes`);
  const descriptor = fs.openSync(eventsPath, 'a', 0o600);
  try {
    let offset = 0;
    while (offset < bytes.length) offset += fs.writeSync(descriptor, bytes, offset, bytes.length - offset);
    fs.fsyncSync(descriptor);
  } finally {
    fs.closeSync(descriptor);
  }
}

function atomicJsonWrite(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temporaryPath = `${filePath}.${process.pid}.${randomUUID()}.tmp`;
  let descriptor;
  try {
    descriptor = fs.openSync(temporaryPath, 'wx', 0o600);
    const bytes = Buffer.from(`${JSON.stringify(value)}\n`, 'utf8');
    let offset = 0;
    while (offset < bytes.length) offset += fs.writeSync(descriptor, bytes, offset, bytes.length - offset);
    fs.fsyncSync(descriptor);
    fs.closeSync(descriptor);
    descriptor = undefined;
    fs.renameSync(temporaryPath, filePath);
  } catch (error) {
    if (descriptor !== undefined) fs.closeSync(descriptor);
    try {
      fs.unlinkSync(temporaryPath);
    } catch {}
    throw error;
  }
}

function withLock(speckitPath, action) {
  const lockPath = path.join(speckitPath, '.run-events.lock');
  let descriptor;
  try {
    descriptor = fs.openSync(lockPath, 'wx', 0o600);
  } catch (error) {
    if (error.code === 'EEXIST') fail(`another producer may be writing events (lock exists at ${lockPath})`);
    throw error;
  }
  try {
    fs.writeSync(descriptor, `${process.pid}\n`);
    return action();
  } finally {
    fs.closeSync(descriptor);
    fs.unlinkSync(lockPath);
  }
}

function makeEvent(runId, issueKey, seq, payload) {
  const event = {
    schema_version: 1,
    run_id: runId,
    ...(issueKey === undefined ? {} : { issue_key: issueKey }),
    seq,
    ts: new Date().toISOString(),
    ...payload,
  };
  return validateRunEvent(event);
}

function readDiscovery(repoPath, runId) {
  const filePath = path.join(repoPath, '.speckit', 'runs', `${runId}.json`);
  try {
    const value = JSON.parse(fs.readFileSync(filePath, 'utf8'));
    if (!isRecord(value) || value.schema_version !== 1 || value.run_id !== runId) {
      fail(`invalid discovery record: ${filePath}`);
    }
    if (typeof value.worktree_path !== 'string' || typeof value.repo_path !== 'string') {
      fail(`invalid discovery record paths: ${filePath}`);
    }
    if (!path.isAbsolute(value.worktree_path) || !path.isAbsolute(value.repo_path) ||
      /[\u0000-\u001f\u007f]/u.test(value.worktree_path) || /[\u0000-\u001f\u007f]/u.test(value.repo_path)) {
      fail(`invalid discovery record paths: ${filePath}`);
    }
    if (value.issue_key !== undefined && (typeof value.issue_key !== 'string' || !ISSUE_KEY.test(value.issue_key))) {
      fail(`invalid discovery record issue_key: ${filePath}`);
    }
    exactKeys(value, ['schema_version', 'run_id', 'issue_key', 'repo_path', 'worktree_path', 'updated_at'], 'discovery record');
    validateIsoTimestamp(value.updated_at);
    return value;
  } catch (error) {
    if (error.code === 'ENOENT') return undefined;
    throw error;
  }
}

function init({ values }) {
  const repoPath = canonicalDirectory(values.get('--repo'), '--repo');
  const worktreePath = canonicalDirectory(values.get('--worktree'), '--worktree');
  const runId = values.get('--run-id');
  if (!UUID.test(runId)) fail('--run-id must be a UUID');
  const issueKey = values.get('--issue-key');
  if (issueKey !== undefined && !ISSUE_KEY.test(issueKey)) fail('--issue-key must be a Jira issue key');
  const speckitPath = path.join(worktreePath, '.speckit');
  fs.mkdirSync(speckitPath, { recursive: true });
  return withLock(speckitPath, () => {
    const eventsPath = path.join(speckitPath, 'events.jsonl');
    const allEvents = parseEventFile(eventsPath);
    const runEvents = allEvents.filter((event) => event.run_id === runId);
    const previous = runEvents.at(-1);
    const discoveryPath = path.join(repoPath, '.speckit', 'runs', `${runId}.json`);
    const previousDiscovery = readDiscovery(repoPath, runId);
    if (previousDiscovery && runEvents.length === 0) {
      fail(`discovery record exists but event history is missing for run ${runId}`);
    }
    if (previousDiscovery?.issue_key !== undefined && issueKey !== undefined && previousDiscovery.issue_key !== issueKey) {
      fail('issue_key does not match the existing discovery record');
    }
    if (runEvents.length === 0) {
      const started = makeEvent(runId, issueKey, 1, { type: 'run_started' });
      writeEvent(eventsPath, started);
      writeEvent(eventsPath, makeEvent(runId, issueKey, 2, { type: 'stage_started', stage: STAGES[0] }));
    } else {
      if (runEvents[0].type !== 'run_started') fail('existing run does not begin with run_started');
      if (issueKey !== undefined && issueKey !== runEvents[0].issue_key) fail('issue_key does not match the existing run');
      if (previous.type === 'run_completed' || previous.type === 'run_failed') {
        fail(`cannot resume terminal run ${runId}`);
      }
    }
    atomicJsonWrite(discoveryPath, {
      schema_version: 1,
      run_id: runId,
      ...((issueKey ?? previous?.issue_key) === undefined ? {} : { issue_key: issueKey ?? previous?.issue_key }),
      repo_path: repoPath,
      worktree_path: worktreePath,
      updated_at: new Date().toISOString(),
    });
  });
}

function readInput() {
  const chunks = [];
  let total = 0;
  const chunk = Buffer.alloc(4096);
  for (;;) {
    const count = fs.readSync(0, chunk, 0, chunk.length, null);
    if (count === 0) break;
    total += count;
    if (total > MAX_JSONL_LINE_BYTES) fail(`stdin event exceeds ${MAX_JSONL_LINE_BYTES} bytes`);
    chunks.push(Buffer.from(chunk.subarray(0, count)));
  }
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks)));
  } catch (error) {
    fail(`stdin must contain one JSON object: ${error.message}`);
  }
}

function emit({ values }) {
  const worktreePath = canonicalDirectory(values.get('--worktree'), '--worktree');
  const runId = values.get('--run-id');
  if (!UUID.test(runId)) fail('--run-id must be a UUID');
  const speckitPath = path.join(worktreePath, '.speckit');
  if (!fs.existsSync(speckitPath)) fail('run is not initialized; .speckit directory is missing');
  return withLock(speckitPath, () => {
    const eventsPath = path.join(speckitPath, 'events.jsonl');
    const events = parseEventFile(eventsPath);
    const runEvents = events.filter((event) => event.run_id === runId);
    if (runEvents.length === 0) fail(`run ${runId} has no initialized event history`);
    const latest = runEvents.at(-1);
    if (latest.type === 'run_completed' || latest.type === 'run_failed') fail(`run ${runId} is already terminal`);
    const payload = validatePayload(readInput());
    const issueKey = runEvents[0].issue_key;
    const event = makeEvent(runId, issueKey, latest.seq + 1, payload);
    writeEvent(eventsPath, event);
  });
}

export function runEventsCli(argv = process.argv.slice(2)) {
  const [major, minor] = process.versions.node.split('.').map(Number);
  if (major < 22 || (major === 22 && minor < 13)) fail('structured run events require Node.js >=22.13');
  const parsed = parseArgs(argv);
  if (parsed.command === 'init') return init(parsed);
  return emit(parsed);
}

// The skill directory is often a symlink; import.meta.url is the real path, so compare real paths.
const isMain = () => {
  try {
    return Boolean(process.argv[1]) && fs.realpathSync(process.argv[1]) === fs.realpathSync(fileURLToPath(import.meta.url));
  } catch {
    return false;
  }
};

if (isMain()) {
  try {
    runEventsCli();
  } catch (error) {
    process.stderr.write(`run-events: ${error.message}\n`);
    process.exitCode = 1;
  }
}
