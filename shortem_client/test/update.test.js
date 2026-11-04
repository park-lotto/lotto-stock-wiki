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
for (const [rel, s] of [['server/index.js', '// NEW'], ['server/node_modules/x/index.js', 'x'], ['engine/tools/calcopy/make.py', '# NEW'],
  ['server/plugin_update/shortem/.claude-plugin/plugin.json', '{"name":"shortem","version":"1.0.0"}'], ['server/plugin_update/shortem/hooks/wake.js', '// NEW WAKE']]) {
  fs.mkdirSync(path.dirname(path.join(NEW, rel)), { recursive: true }); fs.writeFileSync(path.join(NEW, rel), s);
}
const zip = execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
  'import sys;sys.path.insert(0,sys.argv[1]);import publish_update as P;from pathlib import Path;sys.stdout.buffer.write(P.make_zip(Path(sys.argv[2]),"1.0.1"))',
  path.join(HERE, '..', '..', 'tools', 'claude_portal'), NEW]);
process.env.SHORTEM_TOOLS = path.join(T, 'tools');
put('claude-plugin/shortem/hooks/wake.js', '// OLD WAKE');
// 가짜 claude 명령(플러그인 갱신 알림) — 진짜 Claude Code 를 건드리지 않고 불린 인자만 적는다
const binDir = path.join(root, 'bin'), claudeLog = path.join(binDir, 'calls.txt');   // cmd 는 한글 경로를 글자로 못 받아 %~dp0(제 자리)로 쓴다
fs.mkdirSync(binDir, { recursive: true });
if (process.platform === 'win32') fs.writeFileSync(path.join(binDir, 'claude.cmd'), ['@echo %*>>"%~dp0calls.txt"', '@exit /b 0', ''].join('\r\n'));
else { fs.writeFileSync(path.join(binDir, 'claude'), ['#!/bin/sh', `echo "$@" >> "${claudeLog}"`, ''].join('\n')); fs.chmodSync(path.join(binDir, 'claude'), 0o755); }
process.env.PATH = binDir + path.delimiter + process.env.PATH;
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
  // 관제 325: 플러그인(훅)은 받자마자 새 판 — 다음 켤 때까지 기다리지 않는다
  assert.equal(fs.readFileSync(path.join(T, 'claude-plugin', 'shortem', 'hooks', 'wake.js'), 'utf8'), '// NEW WAKE');
  assert.equal(JSON.parse(fs.readFileSync(path.join(T, 'claude-plugin', 'shortem', '.claude-plugin', 'plugin.json'), 'utf8')).version, '1.0.1');
  assert.equal(fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'plugin_version.txt'), 'utf8'), '1.0.1');
  assert.match(fs.readFileSync(claudeLog, 'utf8'), /plugin update shortem@shortem/);
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

test('받자마자 엔진 적용 — 만드는 중이면 안 건드린다', async () => {
  const { applyDownloaded } = await import('../server/updater.js');
  const nodeFs = await import('node:fs'), nodeOs = await import('node:os'), nodePath = await import('node:path');
  const r = nodeFs.mkdtempSync(nodePath.join(nodeOs.tmpdir(), 'up-'));
  const d = nodePath.join(r, 'u'), h = nodePath.join(r, 'h');
  nodeFs.mkdirSync(nodePath.join(d, 'engine'), { recursive: true }); nodeFs.mkdirSync(nodePath.join(h, 'engine'), { recursive: true });
  nodeFs.writeFileSync(nodePath.join(d, 'engine', 'a.py'), 'new'); nodeFs.writeFileSync(nodePath.join(h, 'engine', 'a.py'), 'old');
  assert.equal(applyDownloaded(d, h, 1), false);
  assert.equal(nodeFs.readFileSync(nodePath.join(h, 'engine', 'a.py'), 'utf8'), 'old');
  assert.equal(applyDownloaded(d, h, 0), true);
  assert.equal(nodeFs.readFileSync(nodePath.join(h, 'engine', 'a.py'), 'utf8'), 'new');
  assert.ok(nodeFs.existsSync(nodePath.join(d, 'engine', 'a.py')));
});
