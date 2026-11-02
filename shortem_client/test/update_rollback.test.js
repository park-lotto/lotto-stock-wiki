// 단계 배포 되돌리기(관제 304) — 서버가 번호가 더 낮은 판을 주면 PC 가 받아서 바꾼다(claude_portal.update_target 의 rollback).
//   updater.js 를 고치지 않는다 — 판 높낮이 판단은 서버 한 곳이고, 이 시험은 그 전제를 지킨다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { freshDirs, withFake } from './helpers.js';

const root = freshDirs('update_rollback');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const T = path.join(root, 'Shortem');                       // 회수된 새 판 1.0.2 가 깔린 PC
const put = (rel, s) => { fs.mkdirSync(path.dirname(path.join(T, rel)), { recursive: true }); fs.writeFileSync(path.join(T, rel), s); };
put('tools/tools.manifest.json', '{}');
put('server/index.js', '// BAD');
put('engine/tools/calcopy/make.py', '# BAD');
put('app_version.json', '{"version":"1.0.2"}');
const OLD = path.join(root, 'stage');
for (const [rel, s] of [['server/index.js', '// GOOD'], ['engine/tools/calcopy/make.py', '# GOOD']]) {
  fs.mkdirSync(path.dirname(path.join(OLD, rel)), { recursive: true }); fs.writeFileSync(path.join(OLD, rel), s);
}
const zip = execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
  'import sys;sys.path.insert(0,sys.argv[1]);import publish_update as P;from pathlib import Path;sys.stdout.buffer.write(P.make_zip(Path(sys.argv[2]),"1.0.1"))',
  path.join(HERE, '..', '..', 'tools', 'claude_portal'), OLD]);
process.env.SHORTEM_TOOLS = path.join(T, 'tools');
const fake = await withFake({ update: { version: '1.0.1', zip } });
const { checkUpdate } = await import('../server/updater.js');
const { api } = await import('../server/api.js');
const { ENGINE_VERSION } = await import('../server/license.js');
const L = createRequire(import.meta.url)(path.join(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js'));
test.after(() => fake.close());
process.env.SHORTEM_MACHINE_ID = 'machine-rb';
await api.license();

test('회수된 판을 가진 PC 는 낮은 번호 판을 받아 엔진은 바로, 나머지는 다음 켤 때 바꾼다', async () => {
  assert.equal(ENGINE_VERSION, '1.0.2', '시험 전제: 지금 판이 더 높다');
  const r = await checkUpdate({ force: true });
  assert.deepEqual([r.update, r.ready, r.version], [true, true, '1.0.1']);
  assert.equal(fs.readFileSync(path.join(T, 'engine', 'tools', 'calcopy', 'make.py'), 'utf8'), '# GOOD', '엔진은 다음 편부터 옛 판');
  assert.equal(L.applyPending(T), '1.0.1');
  assert.equal(fs.readFileSync(path.join(T, 'server', 'index.js'), 'utf8'), '// GOOD');
  assert.equal(JSON.parse(fs.readFileSync(path.join(T, 'app_version.json'), 'utf8')).version, '1.0.1');
});
