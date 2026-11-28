import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { readTemplate, run, upsertBlock } from '../speckit-auto/scripts/agents-rules.mjs';

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
  assert.equal(agents(dir), `# AGENTS.md\n\n${template.block}\n`);
});

test('appends to an existing file and keeps its content', () => {
  const original = '# Project\n\nUse pnpm.\n\n\n';
  const dir = repo({ 'AGENTS.md': original });
  assert.equal(run({ repo: dir }).action, 'appended');
  assert.equal(agents(dir), `# Project\n\nUse pnpm.\n\n${template.block}\n`);
});

test('a second run changes nothing', () => {
  const dir = repo({ 'AGENTS.md': '# Project\n' });
  run({ repo: dir });
  const before = agents(dir);
  const report = run({ repo: dir });
  assert.equal(report.action, 'unchanged');
  assert.equal(report.changed, false);
  assert.equal(agents(dir), before);
});

test('replaces only the block when it is older or was edited', () => {
  const old = '<!-- speckit-auto:coding-rules:start v0 -->\nold rules\n<!-- speckit-auto:coding-rules:end -->';
  const dir = repo({ 'AGENTS.md': `# Top\n\n${old}\n\n## Preferred libraries\n\n| Dates | date-fns |\n` });
  const report = run({ repo: dir });
  assert.equal(report.action, 'updated');
  assert.equal(report.previous_version, 0);
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
    assert.throws(() => run({ repo: dir }), /malformed/);
    assert.equal(agents(dir), text);
  }
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

test('check reports the action and writes nothing', () => {
  const dir = repo();
  const result = cli('check', '--repo', dir, '--claude-import');
  assert.equal(result.status, 0);
  const report = JSON.parse(result.stdout);
  assert.equal(report.action, 'created');
  assert.equal(report.dry_run, true);
  assert.equal(report.claude_md, 'created');
  assert.deepEqual(fs.readdirSync(dir), []);
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
});

test('setup, pipeline and review instructions are wired to the block', () => {
  const setup = read('speckit-auto/references/shared/integration-setup.md');
  assert.match(setup, /scripts\/agents-rules\.mjs/);
  assert.match(setup, /"coding_rules"/);
  assert.match(setup, /chore\(agents\): add speckit-auto coding rules/);

  const entry = read('speckit-auto/SKILL.md');
  assert.match(entry, /scripts\/agents-rules\.mjs/);
  assert.match(entry, /assets\/coding-rules\.md/);

  assert.match(read('speckit-auto/references/pipeline/stage-01-intake.md'), /speckit-auto:coding-rules/);
  const design = read('speckit-auto/references/pipeline/stage-02-spec-design.md');
  assert.match(design, /Reuse & dependencies/);
  assert.match(read('speckit-auto/references/pipeline/stage-03-implement-review.md'), /coding_rules/);

  const review = read('speckit-code-review/SKILL.md');
  assert.match(review, /references\/reuse-dependencies\.md/);
  const reuse = read('speckit-code-review/references/reuse-dependencies.md');
  assert.match(reuse, /speckit-auto:coding-rules:start/);
  assert.match(reuse, /Reuse & dependencies/);
});
