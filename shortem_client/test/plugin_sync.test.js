import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'ps-'));
process.env.SHORTEM_HOME = path.join(tmp, 'home');
fs.mkdirSync(process.env.SHORTEM_HOME, { recursive: true });
const { syncPlugin } = await import('../server/plugin_sync.js');

function src() {
  const s = path.join(tmp, 'src');
  fs.mkdirSync(path.join(s, 'shortem', '.claude-plugin'), { recursive: true });
  fs.mkdirSync(path.join(s, 'shortem', 'hooks'), { recursive: true });
  fs.writeFileSync(path.join(s, 'shortem', '.claude-plugin', 'plugin.json'), JSON.stringify({ name: 'shortem', version: '1.0.0' }));
  fs.writeFileSync(path.join(s, 'shortem', 'hooks', 'hooks.json'), '{}');
  return s;
}

test('새 판이면 덮고 버전을 올려 Claude 에 갱신을 알린다, 같은 판이면 다시 안 한다', () => {
  const calls = [];
  const installRoot = path.join(tmp, 'install');
  const r = syncPlugin({ version: '1.2.3', installRoot, src: src(), run: a => { calls.push(a.join(' ')); return true; } });
  assert.equal(r.done, true);
  assert.deepEqual(calls, ['plugin marketplace update shortem', 'plugin update shortem@shortem']);
  const pj = JSON.parse(fs.readFileSync(path.join(installRoot, 'claude-plugin', 'shortem', '.claude-plugin', 'plugin.json'), 'utf8'));
  assert.equal(pj.version, '1.2.3');
  assert.equal(syncPlugin({ version: '1.2.3', installRoot, src: src(), run: () => { throw new Error('안 불려야 한다'); } }).why, 'same');
});

test('실패하면 표시를 안 남겨 다음에 다시 하고 알린다', () => {
  const seen = [];
  const r = syncPlugin({ version: '1.2.4', installRoot: path.join(tmp, 'install'), src: src(), run: () => false, report: t => seen.push(t) });
  assert.equal(r.done, false);
  assert.equal(seen.length, 1);
  assert.notEqual(fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'plugin_version.txt'), 'utf8').trim(), '1.2.4');
});
