#!/usr/bin/env node
// Inserts or refreshes the speckit-auto coding-rules block in a repository's AGENTS.md.
// Node builtins only. Only the text between the block markers is ever written; everything
// else in the file is preserved byte for byte.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const START = /^[ \t]*<!--[ \t]*speckit-auto:coding-rules:start(?:[ \t]+v(\d+))?[ \t]*-->[ \t]*$/gm;
const END = /^[ \t]*<!--[ \t]*speckit-auto:coding-rules:end[ \t]*-->[ \t]*$/gm;
const CLAUDE_IMPORT = /^[ \t]*@(?:\.\/)?AGENTS\.md[ \t]*$/m;
const TEMPLATE_URL = new URL('../assets/coding-rules.md', import.meta.url);

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

// Pure text transform. `text` is the current file content, or null when the file is absent.
export function upsertBlock(text, template) {
  const { block, version } = template;
  if (text === null) {
    return { action: 'created', text: `# AGENTS.md\n\n${block}\n`, previousVersion: null };
  }
  const bom = text.startsWith('\uFEFF') ? '\uFEFF' : '';
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const body = toLf(bom ? text.slice(1) : text);
  const { starts, ends } = markers(body);
  const out = (lf) => bom + (eol === '\n' ? lf : lf.replace(/\n/g, '\r\n'));

  if (starts.length === 0 && ends.length === 0) {
    const head = body.trimEnd();
    const next = head ? `${head}\n\n${block}\n` : `${block}\n`;
    return { action: 'appended', text: out(next), previousVersion: null };
  }
  if (starts.length !== 1 || ends.length !== 1 || ends[0].index < starts[0].index) {
    fail('AGENTS.md has a malformed speckit-auto coding-rules block (expected one start marker followed by one end marker); fix the markers by hand and re-run');
  }
  const from = starts[0].index;
  const to = ends[0].index + ends[0][0].length;
  const previousVersion = starts[0][1] ? Number(starts[0][1]) : 0;
  if (previousVersion > version) {
    return { action: 'newer', text, previousVersion };
  }
  if (body.slice(from, to) === block) {
    return { action: 'unchanged', text, previousVersion };
  }
  return { action: 'updated', text: out(body.slice(0, from) + block + body.slice(to)), previousVersion };
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
  const eol = text.includes('\r\n') ? '\r\n' : '\n';
  const head = text.replace(/\s+$/, '');
  if (!dryRun) writeAtomic(file, head ? `${head}${eol}${eol}@AGENTS.md${eol}` : `@AGENTS.md${eol}`, stat.mode & 0o777);
  return 'import_added';
}

export function run({ repo, dryRun = false, claudeImport = false, template = readTemplate() }) {
  if (!repo) fail('--repo <path> is required');
  const root = path.resolve(repo);
  if (!fs.existsSync(root) || !fs.statSync(root).isDirectory()) fail(`--repo is not a directory: ${repo}`);
  const file = path.join(root, 'AGENTS.md');
  const stat = regularFileOrAbsent(file);
  const current = stat ? fs.readFileSync(file, 'utf8') : null;
  const result = upsertBlock(current, template);
  const changed = result.text !== current;
  if (changed && !dryRun) writeAtomic(file, result.text, stat ? stat.mode & 0o777 : undefined);
  const report = {
    ok: true,
    action: result.action,
    changed,
    dry_run: dryRun,
    file: 'AGENTS.md',
    version: template.version,
    previous_version: result.previousVersion,
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
  if (command !== 'apply' && command !== 'check') fail('usage: agents-rules.mjs <apply|check> --repo <path> [--claude-import]');
  const options = { dryRun: command === 'check', claudeImport: false, repo: null };
  for (let i = 0; i < rest.length; i += 1) {
    const arg = rest[i];
    if (arg === '--repo') {
      options.repo = rest[i + 1];
      i += 1;
    } else if (arg.startsWith('--repo=')) {
      options.repo = arg.slice('--repo='.length);
    } else if (arg === '--claude-import') {
      options.claudeImport = true;
    } else {
      fail(`unknown argument: ${arg}`);
    }
  }
  return options;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.stdout.write(`${JSON.stringify(run(parseArgs(process.argv.slice(2))))}\n`);
  } catch (error) {
    process.stderr.write(`${JSON.stringify({ ok: false, error: error.message })}\n`);
    process.exitCode = 2;
  }
}
