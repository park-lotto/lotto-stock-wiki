// 켤 때 자동 업데이트(관제 234 5판) — 받기(server/updater.js) → 다음 켤 때 바꾸기(installer/mcpb/launcher.js applyPending) · 실패 되돌리기
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { freshDirs, withFake } from './helpers.js';

const root = freshDirs('update');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const T = path.join(root, 'Shortem');                       // 가짜 설치 폴더(예전 판)
const put = (rel, s) => { fs.mkdirSync(path.dirname(path.join(T, rel)), { recursive: true }); fs.writeFileSync(path.join(T, rel), s); };
put('tools/tools.manifest.json', '{}');
put('server/index.js', '// OLD');
put('engine/tools/calcopy/make.py', '# OLD');
put('app_version.json', '{"version":"1.0.0"}');
const NEW = path.join(root, 'stage');                      // 새 판 빌드 폴더 → 서버 publish_update 와 같은 묶기(make_zip)
for (const [rel, s] of [['server/index.js', '// NEW'], ['server/node_modules/x/index.js', 'x'], ['engine/tools/calcopy/make.py', '# NEW']]) {
  fs.mkdirSync(path.dirname(path.join(NEW, rel)), { recursive: true }); fs.writeFileSync(path.join(NEW, rel), s);
}
const zip = execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
  'import sys;sys.path.insert(0,sys.argv[1]);import publish_update as P;from pathlib import Path;sys.stdout.buffer.write(P.make_zip(Path(sys.argv[2]),"1.0.1"))',
  path.join(HERE, '..', '..', 'tools', 'claude_portal'), NEW]);
process.env.SHORTEM_TOOLS = path.join(T, 'tools');
const fake = await withFake({ update: { version: '1.0.1', zip } });
const { checkUpdate } = await import('../server/updater.js');
const { api } = await import('../server/api.js');
const L = createRequire(import.meta.url)(path.join(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js'));
test.after(() => fake.close());
process.env.SHORTEM_MACHINE_ID = 'machine-upd';
await api.license();

test('새 판을 받아 대기 폴더에 풀고, 다음에 켤 때 바꾼다(돌고 있는 예전 판은 그대로)', async () => {
  const r = await checkUpdate({ force: true });
  assert.deepEqual([r.update, r.ready, r.version], [true, true, '1.0.1']);
  assert.equal(fs.readFileSync(path.join(T, 'server', 'index.js'), 'utf8'), '// OLD', '받기만 했을 땐 예전 판 그대로');
  assert.equal(L.applyPending(T), '1.0.1');
  assert.equal(fs.readFileSync(path.join(T, 'server', 'index.js'), 'utf8'), '// NEW');
  assert.equal(fs.readFileSync(path.join(T, 'engine', 'tools', 'calcopy', 'make.py'), 'utf8'), '# NEW');
  assert.ok(fs.existsSync(path.join(T, 'server', 'node_modules', 'x', 'index.js')));
  assert.equal(JSON.parse(fs.readFileSync(path.join(T, 'app_version.json'), 'utf8')).version, '1.0.1');
  assert.ok(!fs.existsSync(path.join(T, '_update', 'pending.json')));
});

test('덜 찬 업데이트는 되돌리고 예전 판으로 뜬다', () => {
  const up = path.join(T, '_update', '9.9.9');
  fs.mkdirSync(path.join(up, 'server'), { recursive: true });
  fs.writeFileSync(path.join(up, 'server', 'index.js'), '// BROKEN');
  fs.writeFileSync(path.join(up, 'app_version.json'), '{"version":"9.9.9"}');
  fs.writeFileSync(path.join(T, '_update', 'pending.json'), JSON.stringify({ version: '9.9.9', dir: '9.9.9' }));
  assert.equal(L.applyPending(T), null);
  assert.equal(fs.readFileSync(path.join(T, 'server', 'index.js'), 'utf8'), '// NEW', '서버가 예전(현재) 판 그대로');
  assert.ok(fs.existsSync(path.join(T, 'engine', 'tools', 'calcopy', 'make.py')));
});
