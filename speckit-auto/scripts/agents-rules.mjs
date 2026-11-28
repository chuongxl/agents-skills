#!/usr/bin/env node
// Inserts, refreshes and validates the speckit-auto coding-rules block in AGENTS.md.
// Node builtins only. Only the text between the block markers is ever written; everything
// else in the file is preserved byte for byte.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const START = /^[ \t]*<!--[ \t]*speckit-auto:coding-rules:start(?:[ \t]+v(\d+))?[ \t]*-->[ \t]*$/gm;
const END = /^[ \t]*<!--[ \t]*speckit-auto:coding-rules:end[ \t]*-->[ \t]*$/gm;
const CLAUDE_IMPORT = /^[ \t]*@(?:\.\/)?AGENTS\.md[ \t]*$/m;
const TEMPLATE_URL = new URL('../assets/coding-rules.md', import.meta.url);
export const SUPPORTED_VERSIONS = new Set([1]);

// Deterministic, conservative catalog: a library is only drafted when it is both declared
// in a manifest and mapped here, so "unambiguous concern" never depends on a host's memory.
const CATALOG = new Map([
  ['date-fns', 'dates'],
  ['dayjs', 'dates'],
  ['luxon', 'dates'],
  ['moment', 'dates'],
  ['zod', 'validation'],
  ['ajv', 'validation'],
  ['joi', 'validation'],
  ['yup', 'validation'],
  ['axios', 'HTTP client'],
  ['ky', 'HTTP client'],
  ['got', 'HTTP client'],
  ['requests', 'HTTP client'],
  ['prisma', 'data access'],
  ['sequelize', 'data access'],
  ['typeorm', 'data access'],
  ['sqlalchemy', 'data access'],
  ['passport', 'auth'],
  ['jsonwebtoken', 'auth'],
  ['auth0', 'auth'],
  ['winston', 'logging'],
  ['pino', 'logging'],
  ['loguru', 'logging'],
  ['jest', 'testing'],
  ['vitest', 'testing'],
  ['pytest', 'testing'],
  ['p-retry', 'retry/backoff'],
  ['async-retry', 'retry/backoff'],
  ['papaparse', 'parsing'],
  ['csv-parse', 'parsing'],
]);

const ALLOWED_CONCERNS = new Set([
  'dates', 'validation', 'HTTP client', 'data access', 'auth', 'logging', 'testing',
  'retry/backoff', 'parsing',
]);

const MANIFESTS = [
  'package.json', 'pyproject.toml', 'go.mod', 'pom.xml', 'build.gradle', 'build.gradle.kts',
  'Cargo.toml', 'composer.json', 'Gemfile', 'pubspec.yaml',
];

function fail(message) {
  throw new Error(message);
}

const toLf = (text) => text.replace(/\r\n/g, '\n');

function markers(text) {
  return {
    starts: [...text.matchAll(START)],
    ends: [...text.matchAll(END)],
  };
}

/**
 * Parse the managed block in the ORIGINAL text. Never normalizes or trims.
 * Status: none | malformed | legacy | unsupported | newer | valid.
 */
export function parseBlock(text) {
  const { starts, ends } = markers(text);
  if (!starts.length && !ends.length) return { status: 'none', version: null, supported: false };
  if (starts.length !== 1 || ends.length !== 1 || ends[0].index <= starts[0].index) {
    return { status: 'malformed', version: null, supported: false };
  }

  const start = starts[0].index;
  const end = ends[0].index + ends[0][0].length;
  const body = text.slice(start, end);
  const version = starts[0][1] ? Number(starts[0][1]) : null;

  if (version === null) return { status: 'legacy', version: 0, start, end, body, supported: false };
  if (!SUPPORTED_VERSIONS.has(version)) {
    const status = version > Math.max(...SUPPORTED_VERSIONS) ? 'newer' : 'unsupported';
    return { status, version, start, end, body, supported: false };
  }
  return { status: 'valid', version, start, end, body, supported: true };
}

export function readTemplate(url = TEMPLATE_URL) {
  const block = toLf(fs.readFileSync(url, 'utf8')).trim();
  const { starts, ends } = markers(block);
  if (starts.length !== 1 || ends.length !== 1 || starts[0].index !== 0) {
    fail('coding-rules template must be exactly one marked block');
  }
  if (ends[0].index + ends[0][0].length !== block.length) {
    fail('coding-rules template must end with its end marker');
  }
  if (!starts[0][1]) fail('coding-rules template start marker must carry a version (vN)');
  return { block, version: Number(starts[0][1]) };
}

function eolBefore(text, index) {
  const crlf = text.lastIndexOf('\r\n', index);
  const lf = text.lastIndexOf('\n', index);
  if (lf === -1) {
    const firstCrlf = text.indexOf('\r\n');
    return firstCrlf !== -1 ? '\r\n' : '\n';
  }
  return crlf === lf - 1 ? '\r\n' : '\n';
}

const renderBlock = (block, eol) => block.replace(/\n/g, eol);

function appendGap(text, eol) {
  if (!text.length) return '';
  if (text.endsWith(`${eol}${eol}`)) return '';
  if (text.endsWith(eol)) return eol;
  return `${eol}${eol}`;
}

// Pure text transform. `text` is the current file content, or null when the file is absent.
export function upsertBlock(text, template) {
  const { version } = template;
  if (text === null) {
    return { action: 'created', text: `# AGENTS.md\n\n${template.block}\n`, previousVersion: null };
  }

  const p = parseBlock(text);
  if (p.status === 'malformed') {
    fail('AGENTS.md has a malformed speckit-auto coding-rules block (expected one start marker followed by one end marker); fix the markers by hand and re-run');
  }
  if (p.status === 'newer') return { action: 'newer', text, previousVersion: p.version };

  const eol = eolBefore(text, p.start ?? text.length);
  const block = renderBlock(template.block, eol);

  if (p.status === 'none') {
    return {
      action: 'appended',
      text: text + appendGap(text, eol) + block + eol,
      previousVersion: null,
    };
  }

  if (p.status === 'valid' && text.slice(p.start, p.end) === block) {
    return { action: 'unchanged', text, previousVersion: p.version };
  }

  // Splice only the managed slice. Prefix and suffix keep their original bytes.
  return {
    action: 'updated',
    text: text.slice(0, p.start) + block + text.slice(p.end),
    previousVersion: p.version,
  };
}

function regularFileOrAbsent(file) {
  let stat;
  try {
    stat = fs.lstatSync(file);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
  if (!stat.isFile()) fail(`${path.basename(file)} exists but is not a regular file; leaving it untouched`);
  return stat;
}

function writeAtomic(file, text, mode) {
  const tmp = `${file}.speckit-auto-${process.pid}.tmp`;
  try {
    fs.writeFileSync(tmp, text, { flag: 'wx', mode: mode ?? 0o644 });
    fs.renameSync(tmp, file);
  } catch (error) {
    fs.rmSync(tmp, { force: true });
    throw error;
  }
}

// CLAUDE.md is what Claude Code loads; `@AGENTS.md` makes it import the shared file.
function ensureClaudeImport(repo, dryRun) {
  const file = path.join(repo, 'CLAUDE.md');
  let stat;
  try {
    stat = fs.lstatSync(file);
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
    if (!dryRun) writeAtomic(file, '@AGENTS.md\n');
    return 'created';
  }
  if (stat.isSymbolicLink()) {
    let target = null;
    try {
      target = fs.realpathSync(file);
    } catch {
      return 'skipped';
    }
    return target === fs.realpathSync(path.join(repo, 'AGENTS.md')) ? 'unchanged' : 'skipped';
  }
  if (!stat.isFile()) return 'skipped';
  const text = fs.readFileSync(file, 'utf8');
  if (CLAUDE_IMPORT.test(toLf(text))) return 'unchanged';
  const eol = eolBefore(text, text.length);
  const head = text.replace(/\s+$/, '');
  if (!dryRun) writeAtomic(file, head ? `${head}${eol}${eol}@AGENTS.md${eol}` : `@AGENTS.md${eol}`, stat.mode & 0o777);
  return 'import_added';
}

export function parsePreferredLibraries(text) {
  if (text === null) return [];
  const lf = toLf(text);
  const heading = lf.match(/^##[ \t]+Preferred libraries[ \t]*$/m);
  if (!heading) return [];
  const rest = lf.slice(heading.index + heading[0].length);
  const next = rest.match(/^##[ \t]+/m);
  const section = next ? rest.slice(0, next.index) : rest;
  const rows = [];
  for (const line of section.split('\n')) {
    const cells = line.match(/^\|[ \t]*([^|]+?)[ \t]*\|[ \t]*([^|]+?)[ \t]*\|[ \t]*$/);
    if (!cells) continue;
    const concern = cells[1].trim();
    const library = cells[2].trim().replace(/^`|`$/g, '');
    if (!concern || !library || /^-+$/.test(concern) || concern.toLowerCase() === 'concern') continue;
    rows.push({ concern, library });
  }
  return rows;
}

function declaredTokens(repo) {
  const tokens = new Set();
  for (const name of MANIFESTS.concat(fs.readdirSync(repo).filter((f) => /^requirements.*\.txt$/.test(f)))) {
    const file = path.join(repo, name);
    let stat;
    try {
      stat = fs.lstatSync(file);
    } catch {
      continue;
    }
    if (!stat.isFile()) continue;
    const text = fs.readFileSync(file, 'utf8');
    let searchText = text;
    if (name === 'package.json' || name === 'composer.json') {
      try {
        const manifest = JSON.parse(text);
        searchText = JSON.stringify({
          ...(manifest.dependencies ?? {}),
          ...(manifest.optionalDependencies ?? {}),
          ...(manifest.require ?? {}),
        });
      } catch {
        searchText = '';
      }
    }
    for (const [library] of CATALOG) {
      const escaped = library.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      if (new RegExp(`(^|[^A-Za-z0-9_@./-])${escaped}([^A-Za-z0-9_@./-]|$)`, 'm').test(searchText)) {
        tokens.add(library);
      }
    }
  }
  return tokens;
}

export function draftLibraries(repo) {
  const declared = declaredTokens(repo);
  const rows = [];
  for (const [library, concern] of CATALOG) {
    if (!declared.has(library)) continue;
    if (rows.some((row) => row.concern === concern)) continue;
    rows.push({ concern, library });
    if (rows.length === 12) break;
  }
  return rows;
}

export function validateLibraries(rows, declared) {
  const violations = [];
  if (rows.length > 12) violations.push('table has more than 12 rows');
  for (const { concern, library } of rows) {
    if (!ALLOWED_CONCERNS.has(concern)) violations.push(`concern not allowed: ${concern}`);
    if (!CATALOG.has(library)) violations.push(`library is not in the unambiguous catalog: ${library}`);
    else if (CATALOG.get(library) !== concern) violations.push(`concern/library mismatch: ${concern} -> ${library}`);
    if (!declared.has(library)) violations.push(`library is not declared in a manifest: ${library}`);
  }
  return violations;
}

function librariesCommand(repo, subcommand, apply) {
  if (!repo) fail('--repo <path> is required');
  const file = path.join(repo, 'AGENTS.md');
  const stat = regularFileOrAbsent(file);
  const text = stat ? fs.readFileSync(file, 'utf8') : null;
  const existing = parsePreferredLibraries(text);

  if (subcommand === 'validate') {
    const violations = existing.length ? validateLibraries(existing, declaredTokens(repo)) : [];
    if (violations.length) fail(`Preferred libraries table is invalid: ${violations.join('; ')}`);
    return { ok: true, action: existing.length ? 'valid' : 'none', rows: existing };
  }

  if (subcommand !== 'draft') fail('usage: agents-rules.mjs libraries <draft|validate> --repo <path> [--apply]');
  if (existing.length) return { ok: true, action: 'existing', rows: existing };

  const rows = draftLibraries(repo);
  if (!rows.length) return { ok: true, action: 'none', rows: [] };
  const table = [
    '## Preferred libraries',
    '',
    '| Concern | Library |',
    '| --- | --- |',
    ...rows.map(({ concern, library }) => `| ${concern} | ${library} |`),
    '',
  ].join('\n');
  if (apply) {
    const eol = eolBefore(text ?? '', (text ?? '').length);
    const body = table.replace(/\n/g, eol);
    const base = text ?? '';
    fs.writeFileSync(file, base + appendGap(base, eol) + body, { flag: stat ? 'a' : 'w' });
  }
  return { ok: true, action: apply ? 'added' : 'draft', rows };
}

export function run({ repo, dryRun = false, claudeImport = false, template = readTemplate() }) {
  if (!repo) fail('--repo <path> is required');
  const root = path.resolve(repo);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) fail(`--repo is not a directory: ${repo}`);
  const file = path.join(root, 'AGENTS.md');
  const stat = regularFileOrAbsent(file);
  const current = stat ? fs.readFileSync(file, 'utf8') : null;
  const parsed = current === null ? { status: 'none', version: null, supported: false } : parseBlock(current);

  let result;
  try {
    result = upsertBlock(current, template);
  } catch {
    result = { action: 'malformed', text: current, previousVersion: parsed.version };
  }
  const changed = result.text !== current;
  if (changed && !dryRun && result.action !== 'malformed') {
    writeAtomic(file, result.text, stat ? stat.mode & 0o777 : undefined);
  }

  const report = {
    ok: true,
    action: result.action,
    changed,
    status: parsed.status,
    version: parsed.version,
    previous_version: parsed.version,
    supported: parsed.supported,
    dry_run: dryRun,
    file: 'AGENTS.md',
    template_version: template.version,
    rules: parsed.body ? { status: parsed.status, version: parsed.version, body: parsed.body } : null,
    preferred_libraries: parsePreferredLibraries(current),
  };
  if (claudeImport) {
    // In a dry run AGENTS.md may not exist yet, so a symlinked CLAUDE.md cannot be resolved.
    report.claude_md = dryRun && current === null && fs.existsSync(path.join(root, 'CLAUDE.md'))
      ? 'unknown'
      : ensureClaudeImport(root, dryRun);
  }
  return report;
}

function parseArgs(argv) {
  const [command, ...rest] = argv;
  if (!['apply', 'check', 'libraries'].includes(command)) {
    fail('usage: agents-rules.mjs <apply|check|libraries> --repo <path> [--claude-import]');
  }
  const options = {
    command,
    dryRun: command === 'check',
    claudeImport: false,
    repo: null,
    librariesCommand: null,
    applyLibraries: false,
  };
  for (let i = 0; i < rest.length; i += 1) {
    const arg = rest[i];
    if (arg === '--repo') {
      options.repo = rest[i + 1];
      i += 1;
    } else if (arg.startsWith('--repo=')) {
      options.repo = arg.slice('--repo='.length);
    } else if (arg === '--claude-import') {
      options.claudeImport = true;
    } else if (arg === '--apply') {
      options.applyLibraries = true;
    } else if (command === 'libraries' && !arg.startsWith('--')) {
      options.librariesCommand = arg;
    } else {
      fail(`unknown argument: ${arg}`);
    }
  }
  return options;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const options = parseArgs(process.argv.slice(2));
    const report = options.command === 'libraries'
      ? librariesCommand(options.repo ? path.resolve(options.repo) : null, options.librariesCommand, options.applyLibraries)
      : run(options);
    process.stdout.write(`${JSON.stringify(report)}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({ ok: false, error: error.message })}\n`);
    process.exitCode = 2;
  }
}
