import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import {
  draftLibraries, parseBlock, parsePreferredLibraries, readTemplate, run, upsertBlock, validateLibraries,
} from '../speckit-auto/scripts/agents-rules.mjs';

const helper = fileURLToPath(new URL('../speckit-auto/scripts/agents-rules.mjs', import.meta.url));
const template = readTemplate();
const read = (file) => fs.readFileSync(new URL(`../${file}`, import.meta.url), 'utf8');

function repo(files = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'agents rules $(x) '));
  for (const [name, text] of Object.entries(files)) fs.writeFileSync(path.join(dir, name), text);
  return dir;
}
const agents = (dir) => fs.readFileSync(path.join(dir, 'AGENTS.md'), 'utf8');
const cli = (...args) => spawnSync(process.execPath, [helper, ...args], { encoding: 'utf8' });

test('template is one versioned block', () => {
  assert.equal(template.version, 1);
  assert.match(template.block, /^<!-- speckit-auto:coding-rules:start v1 -->\n/);
  assert.match(template.block, /\n<!-- speckit-auto:coding-rules:end -->$/);
  assert.match(template.block, /Reuse first/);
  assert.match(template.block, /No new dependency without approval/);
});

test('creates AGENTS.md when it is missing', () => {
  const dir = repo();
  const report = run({ repo: dir });
  assert.equal(report.action, 'created');
  assert.equal(report.changed, true);
  assert.equal(report.status, 'none');
  assert.equal(agents(dir), `# AGENTS.md\n\n${template.block}\n`);
});

test('appends without trimming existing content', () => {
  const original = '# Project\n\nUse pnpm.\n\n\n';
  const dir = repo({ 'AGENTS.md': original });
  assert.equal(run({ repo: dir }).action, 'appended');
  assert.equal(agents(dir), `${original}${template.block}\n`);
});

test('a second run changes nothing', () => {
  const dir = repo({ 'AGENTS.md': '# Project\n' });
  run({ repo: dir });
  const before = agents(dir);
  const report = run({ repo: dir });
  assert.equal(report.action, 'unchanged');
  assert.equal(report.changed, false);
  assert.equal(report.status, 'valid');
  assert.equal(report.supported, true);
  assert.ok(report.rules.body.includes('Reuse first'));
  assert.equal(agents(dir), before);
});

test('replaces only the block when it is older or was edited', () => {
  const old = '<!-- speckit-auto:coding-rules:start v0 -->\nold rules\n<!-- speckit-auto:coding-rules:end -->';
  const dir = repo({ 'AGENTS.md': `# Top\n\n${old}\n\n## Preferred libraries\n\n| Dates | date-fns |\n` });
  const report = run({ repo: dir });
  assert.equal(report.action, 'updated');
  assert.equal(report.previous_version, 0);
  assert.equal(report.status, 'unsupported');
  assert.equal(agents(dir), `# Top\n\n${template.block}\n\n## Preferred libraries\n\n| Dates | date-fns |\n`);

  const edited = agents(dir).replace('Reuse first', 'Reuse never');
  fs.writeFileSync(path.join(dir, 'AGENTS.md'), edited);
  assert.equal(run({ repo: dir }).action, 'updated');
  assert.match(agents(dir), /Reuse first/);
});

test('never downgrades a newer block', () => {
  const newer = '# Top\n\n<!-- speckit-auto:coding-rules:start v99 -->\nfuture\n<!-- speckit-auto:coding-rules:end -->\n';
  const dir = repo({ 'AGENTS.md': newer });
  const report = run({ repo: dir });
  assert.equal(report.action, 'newer');
  assert.equal(report.changed, false);
  assert.equal(report.status, 'newer');
  assert.equal(report.supported, false);
  assert.match(report.rules.body, /^<!-- speckit-auto:coding-rules:start v99 -->/);
  assert.equal(agents(dir), newer);
});

test('malformed markers stop without writing', () => {
  for (const text of [
    '<!-- speckit-auto:coding-rules:start v1 -->\nno end\n',
    'no start\n<!-- speckit-auto:coding-rules:end -->\n',
    `${template.block}\n\n${template.block}\n`,
    '<!-- speckit-auto:coding-rules:end -->\n<!-- speckit-auto:coding-rules:start v1 -->\n',
  ]) {
    const dir = repo({ 'AGENTS.md': text });
    assert.throws(() => upsertBlock(text, template), /malformed/);
    const report = run({ repo: dir });
    assert.equal(report.action, 'malformed');
    assert.equal(report.status, 'malformed');
    assert.equal(report.changed, false);
    assert.equal(agents(dir), text);
  }
});

test('parseBlock reports every supported state', () => {
  assert.equal(parseBlock('# Team\n').status, 'none');
  assert.equal(parseBlock('start only\n').status, 'none');
  assert.equal(parseBlock('<!-- speckit-auto:coding-rules:start v1 -->\n').status, 'malformed');
  const legacy = '<!-- speckit-auto:coding-rules:start -->\nx\n<!-- speckit-auto:coding-rules:end -->';
  assert.equal(parseBlock(legacy).status, 'legacy');
  const valid = parseBlock(template.block);
  assert.equal(valid.status, 'valid');
  assert.equal(valid.version, 1);
  assert.equal(valid.supported, true);
  assert.equal(valid.body, template.block);
  const newer = template.block.replace('start v1', 'start v2');
  assert.equal(parseBlock(newer).status, 'newer');
  assert.equal(parseBlock(newer).supported, false);
});

test('markers mentioned inline are not treated as a block', () => {
  const text = 'The block starts with `<!-- speckit-auto:coding-rules:start v1 -->` in AGENTS.md.\n';
  const result = upsertBlock(text, template);
  assert.equal(result.action, 'appended');
  assert.ok(result.text.startsWith(text));
});

test('CRLF files and a BOM are preserved', () => {
  const dir = repo({ 'AGENTS.md': '\uFEFF# Project\r\n\r\nUse pnpm.\r\n' });
  run({ repo: dir });
  const text = agents(dir);
  assert.ok(text.startsWith('\uFEFF# Project\r\n\r\nUse pnpm.\r\n\r\n<!-- speckit-auto'));
  assert.equal(text.replace(/\r\n/g, '').includes('\n'), false);
  assert.equal(run({ repo: dir }).action, 'unchanged');
});

test('mixed EOLs and trailing whitespace survive byte for byte', () => {
  const original = '# Project\r\nHard break.  \nSecond line.\r\n   \t\n\n';
  const result = upsertBlock(original, template);
  assert.ok(result.text.startsWith(original));
  assert.ok(result.text.includes('<!-- speckit-auto:coding-rules:start v1 -->'));

  const suffix = '\r\n\r\n## Team notes  \r\n';
  const input = `${template.block}${suffix}`;
  const updated = upsertBlock(input.replace('Reuse first', 'Reuse never'), template);
  assert.ok(updated.text.endsWith(suffix));
});

test('check reports the action and writes nothing', () => {
  const dir = repo();
  const result = cli('check', '--repo', dir, '--claude-import');
  assert.equal(result.status, 0);
  const report = JSON.parse(result.stdout);
  assert.equal(report.action, 'created');
  assert.equal(report.status, 'none');
  assert.equal(report.dry_run, true);
  assert.equal(report.claude_md, 'created');
  assert.deepEqual(fs.readdirSync(dir), []);
});

test('check exposes an unsupported block without failing', () => {
  const dir = repo({ 'AGENTS.md': '<!-- speckit-auto:coding-rules:start v99 -->\nfuture\n<!-- speckit-auto:coding-rules:end -->\n' });
  const result = cli('check', '--repo', dir);
  assert.equal(result.status, 0);
  const report = JSON.parse(result.stdout);
  assert.equal(report.action, 'newer');
  assert.equal(report.status, 'newer');
  assert.equal(report.supported, false);
  assert.equal(report.changed, false);
});

test('CLAUDE.md import is created, added once, or left alone', () => {
  const fresh = repo();
  assert.equal(run({ repo: fresh, claudeImport: true }).claude_md, 'created');
  assert.equal(fs.readFileSync(path.join(fresh, 'CLAUDE.md'), 'utf8'), '@AGENTS.md\n');
  assert.equal(run({ repo: fresh, claudeImport: true }).claude_md, 'unchanged');

  const existing = repo({ 'CLAUDE.md': '# Claude notes\n\nBe brief.\n' });
  assert.equal(run({ repo: existing, claudeImport: true }).claude_md, 'import_added');
  assert.equal(fs.readFileSync(path.join(existing, 'CLAUDE.md'), 'utf8'), '# Claude notes\n\nBe brief.\n\n@AGENTS.md\n');
  assert.equal(run({ repo: existing, claudeImport: true }).claude_md, 'unchanged');

  const linked = repo({ 'AGENTS.md': '# Project\n' });
  fs.symlinkSync('AGENTS.md', path.join(linked, 'CLAUDE.md'));
  assert.equal(run({ repo: linked, claudeImport: true }).claude_md, 'unchanged');
  assert.ok(fs.lstatSync(path.join(linked, 'CLAUDE.md')).isSymbolicLink());

  const untouched = repo();
  assert.equal(run({ repo: untouched }).claude_md, undefined);
  assert.equal(fs.existsSync(path.join(untouched, 'CLAUDE.md')), false);
});

test('a non-regular AGENTS.md is refused', () => {
  const dir = repo({ 'real.md': '# Real\n' });
  fs.symlinkSync('real.md', path.join(dir, 'AGENTS.md'));
  const result = cli('apply', '--repo', dir);
  assert.equal(result.status, 2);
  assert.equal(JSON.parse(result.stderr).ok, false);
  assert.equal(fs.readFileSync(path.join(dir, 'real.md'), 'utf8'), '# Real\n');
});

test('CLI rejects bad usage with exit 2', () => {
  assert.equal(cli('apply').status, 2);
  assert.equal(cli('frobnicate', '--repo', '.').status, 2);
  assert.equal(cli('apply', '--repo', repo(), '--force').status, 2);
  assert.equal(cli('libraries', '--repo', repo()).status, 2);
  assert.equal(cli('libraries', 'draft').status, 2);
});

test('preferred libraries are drafted from declared dependencies only', () => {
  const dir = repo({
    'package.json': JSON.stringify({
      dependencies: { 'date-fns': '^3', zod: '^3' },
      devDependencies: { jest: '^29' },
    }),
  });
  const rows = draftLibraries(dir);
  assert.deepEqual(rows, [
    { concern: 'dates', library: 'date-fns' },
    { concern: 'validation', library: 'zod' },
  ]);

  const result = cli('libraries', 'draft', '--repo', dir, '--apply');
  assert.equal(result.status, 0);
  assert.deepEqual(JSON.parse(result.stdout).rows, rows);
  const text = agents(dir);
  assert.match(text, /^## Preferred libraries\r?$/m);
  assert.match(text, /\| dates \| date-fns \|/);
  assert.deepEqual(parsePreferredLibraries(text), rows);
  assert.equal(cli('libraries', 'validate', '--repo', dir).status, 0);
});

test('preferred libraries validation rejects guessed and misclassified rows', () => {
  assert.deepEqual(
    validateLibraries([{ concern: 'dates', library: 'magic-parser' }], new Set(['magic-parser'])),
    ['library is not in the unambiguous catalog: magic-parser'],
  );
  assert.deepEqual(
    validateLibraries([{ concern: 'HTTP client', library: 'date-fns' }], new Set(['date-fns'])),
    ['concern/library mismatch: HTTP client -> date-fns'],
  );
  assert.deepEqual(
    validateLibraries([{ concern: 'dates', library: 'date-fns' }], new Set()),
    ['library is not declared in a manifest: date-fns'],
  );
  assert.ok(validateLibraries(Array.from({ length: 13 }, () => ({ concern: 'dates', library: 'date-fns' })), new Set()).some((v) => /more than 12/.test(v)));

  const dir = repo({ 'AGENTS.md': '## Preferred libraries\n\n| Concern | Library |\n| --- | --- |\n| dates | guessed-lib |\n' });
  const result = cli('libraries', 'validate', '--repo', dir);
  assert.equal(result.status, 2);
  assert.match(JSON.parse(result.stderr).error, /not declared/);
});

test('setup, pipeline and review instructions are wired to the validated rules', () => {
  const setup = read('speckit-auto/references/shared/integration-setup.md');
  assert.match(setup, /scripts\/agents-rules\.mjs apply/);
  assert.match(setup, /scripts\/agents-rules\.mjs libraries/);
  assert.match(setup, /"coding_rules"/);
  assert.match(setup, /chore\(agents\): add speckit-auto coding rules/);

  const entry = read('speckit-auto/SKILL.md');
  assert.match(entry, /scripts\/agents-rules\.mjs/);
  assert.match(entry, /assets\/coding-rules\.md/);
  assert.match(entry, /--coding-rules/);

  const intake = read('speckit-auto/references/pipeline/stage-01-intake.md');
  assert.match(intake, /agents-rules\.mjs check/);
  assert.match(intake, /status: valid/);
  const design = read('speckit-auto/references/pipeline/stage-02-spec-design.md');
  assert.match(design, /Reuse & dependencies/);
  const implement = read('speckit-auto/references/pipeline/stage-03-implement-review.md');
  assert.match(implement, /coding_rules/);
  assert.match(implement, /as the `coding_rules` input/);

  const review = read('speckit-code-review/SKILL.md');
  assert.match(review, /references\/reuse-dependencies\.md/);
  assert.match(review, /Optional `coding_rules`/);
  const reuse = read('speckit-code-review/references/reuse-dependencies.md');
  assert.match(reuse, /coding_rules/);
  assert.match(reuse, /Reuse & dependencies/);
});
