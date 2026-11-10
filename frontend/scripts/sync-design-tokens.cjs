#!/usr/bin/env node
// Copies the Console at Rest shared values into src/styles/tokens.css.
// Usage: node scripts/sync-design-tokens.cjs <path to the console-at-rest checkout>
// The copy is byte-for-byte under one stamp line; never edit tokens.css by hand.
const { execFileSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const source = process.argv[2];
if (!source) {
  console.error(
    'usage: node scripts/sync-design-tokens.cjs <path to the console-at-rest checkout>',
  );
  process.exit(2);
}

const tokens = fs.readFileSync(path.join(source, 'tokens.css'), 'utf8');
const rulebook = fs.readFileSync(path.join(source, 'RULEBOOK.md'), 'utf8');
const version = /^Version (\d+\.\d+)/m.exec(rulebook);
if (!version) throw new Error('No "Version X.Y" line in RULEBOOK.md');
const dirty = execFileSync(
  'git',
  ['-C', source, 'status', '--porcelain', '--', 'tokens.css', 'RULEBOOK.md'],
  { encoding: 'utf8' },
).trim();
if (dirty) {
  throw new Error(
    `tokens.css or RULEBOOK.md has uncommitted changes in ${source}: commit them first, so the stamp names a commit that holds these values.`,
  );
}
const commit = execFileSync('git', ['-C', source, 'rev-parse', '--short', 'HEAD'], {
  encoding: 'utf8',
}).trim();

const stamp = `/* Synced from console-at-rest v${version[1]} @ ${commit}. Do not edit: run scripts/sync-design-tokens.cjs. */\n`;
const target = path.join(__dirname, '..', 'src', 'styles', 'tokens.css');
fs.writeFileSync(target, stamp + tokens);
console.log(`tokens.css synced (v${version[1]} @ ${commit})`);
