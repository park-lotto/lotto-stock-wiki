// 판 바꾸기가 중간에 실패해도 받은 판(_update/<판>/)은 그대로 남아야 한다(사건 #1397).
//   그 PC: 멈춘 실행기가 <설치>/engine 을 현재 폴더로 쥐어 engine 이름 바꾸기가 실패 → 되돌리기가 방금 옮긴 새 server 를 지워
//   _update/1.0.55 에 engine 만 남고, 앱은 1.0.54 그대로·엔진만 1.0.55 가 됐다. 바꾸는 곳은 연결기 applyPending·supervisor.applyUpdate 두 벌.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { freshDirs } from './helpers.js';
import { applyUpdate } from '../server/supervisor.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const L = createRequire(import.meta.url)(path.join(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js'));
const root = freshDirs('update_swap_busy');
const read = (f) => { try { return fs.readFileSync(f, 'utf8'); } catch { return null; } };

function pc(name, { appVersion = true } = {}) {   // 1.0.54 가 깔리고 1.0.55 를 받아 둔 PC
  const H = path.join(root, name);
  const put = (rel, s) => { fs.mkdirSync(path.dirname(path.join(H, rel)), { recursive: true }); fs.writeFileSync(path.join(H, rel), s); };
  put('server/index.js', '// 1.0.54'); put('engine/tools/calcopy/make.py', '# 1.0.54'); put('app_version.json', '{"version":"1.0.54"}');
  put('_update/1.0.55/server/index.js', '// 1.0.55'); put('_update/1.0.55/engine/tools/calcopy/make.py', '# 1.0.55');
  if (appVersion) put('_update/1.0.55/app_version.json', '{"version":"1.0.55"}');
  put('_update/pending.json', JSON.stringify({ version: '1.0.55', dir: '1.0.55' }));
  return H;
}

const APPLY = { launcher: h => L.applyPending(h), supervisor: h => applyUpdate(h) };

for (const [who, apply] of Object.entries(APPLY)) {
  test(`${who}: 바꾸다 실패하면 옛 판으로 되돌리고 받은 판은 server·engine 둘 다 남긴다`, () => {
    const H = pc(`fail_${who}`, { appVersion: false });                  // 마지막 단계(app_version 복사)에서 실패
    assert.equal(apply(H), null);
    assert.equal(read(path.join(H, 'server', 'index.js')), '// 1.0.54');
    assert.equal(read(path.join(H, 'engine', 'tools', 'calcopy', 'make.py')), '# 1.0.54');
    assert.equal(read(path.join(H, '_update', '1.0.55', 'server', 'index.js')), '// 1.0.55', '새 server 를 지우면 다시 바꿀 수 없다');
    assert.equal(read(path.join(H, '_update', '1.0.55', 'engine', 'tools', 'calcopy', 'make.py')), '# 1.0.55');
  });

  test(`${who}: 실행기가 engine 폴더를 쥐고 있어도 server 는 새 판으로 바뀐다`, { skip: process.platform !== 'win32' && '현재 폴더가 이름 바꾸기를 막는 건 Windows' }, async () => {
    const H = pc(`busy_${who}`);
    const hold = spawn(process.execPath, ['-e', 'setTimeout(()=>{},60000)'], { cwd: path.join(H, 'engine', 'tools'), stdio: 'ignore' });
    await new Promise(r => setTimeout(r, 300));
    try {
      assert.equal(apply(H), '1.0.55');
      assert.equal(read(path.join(H, 'server', 'index.js')), '// 1.0.55');
      assert.equal(read(path.join(H, 'engine', 'tools', 'calcopy', 'make.py')), '# 1.0.55', '못 옮기면 자리에 덮는다');
      assert.equal(JSON.parse(read(path.join(H, 'app_version.json'))).version, '1.0.55');
      assert.equal(fs.existsSync(path.join(H, '_update', 'pending.json')), false);
    } finally { hold.kill(); }
  });

  test(`${who}: 다른 창이 먼저 표시(pending.json)를 지워도 바꾼 판을 되돌리지 않는다`, () => {
    const H = pc(`race_${who}`);
    const pend = path.join(H, '_update', 'pending.json');
    const orig = fs.copyFileSync;
    fs.copyFileSync = (a, b, ...r) => { const x = orig(a, b, ...r); if (String(b).endsWith('app_version.json')) fs.rmSync(pend, { force: true }); return x; };
    try { assert.equal(apply(H), '1.0.55'); } finally { fs.copyFileSync = orig; }
    assert.equal(read(path.join(H, 'server', 'index.js')), '// 1.0.55');
    assert.equal(read(path.join(H, 'engine', 'tools', 'calcopy', 'make.py')), '# 1.0.55');
  });
}
