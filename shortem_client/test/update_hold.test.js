// 제작 중 창을 닫아 표시가 숨은 채(pending.hold.json) 남아도 앱 판은 바뀌어야 한다(사건 #1507·#1517).
//   그 PC: _update/1.0.57 온전·engine_now=1.0.57·pending.json 없음·pending.hold.json={1.0.57} — 엔진만 새 판, 앱은 1.0.50 에 묶임.
//   숨김의 뜻은 '돌고 있는 제작 중엔 바꾸지 마라' — 제작 잠금(rent.lock) 주인이 살아 있을 때만 지킨다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { freshDirs, withFake } from './helpers.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const L = createRequire(import.meta.url)(path.join(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js'));
const root = freshDirs('update_hold');
const { applyUpdate } = await import('../server/supervisor.js');
const read = (f) => { try { return fs.readFileSync(f, 'utf8'); } catch { return null; } };
const lock = (pid) => fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'rent.lock'), JSON.stringify({ pid, job: 'm1' }));
const deadPid = () => Number(execFileSync(process.execPath, ['-e', 'console.log(process.pid)']).toString().trim());

function pc(name) {   // 1.0.50 이 깔리고 1.0.57 을 받아 둔 PC — 표시는 숨은 이름
  const H = path.join(root, name);
  const put = (rel, s) => { fs.mkdirSync(path.dirname(path.join(H, rel)), { recursive: true }); fs.writeFileSync(path.join(H, rel), s); };
  put('tools/tools.manifest.json', '{}');
  put('server/index.js', '// 1.0.50'); put('engine/tools/calcopy/make.py', '# 1.0.57'); put('app_version.json', '{"version":"1.0.50"}');
  put('_update/1.0.57/server/index.js', '// 1.0.57'); put('_update/1.0.57/engine/tools/calcopy/make.py', '# 1.0.57');
  put('_update/1.0.57/app_version.json', '{"version":"1.0.57"}');
  put('_update/pending.hold.json', JSON.stringify({ version: '1.0.57', dir: '1.0.57' }));
  return H;
}

const APPLY = { launcher: h => L.applyPending(h), supervisor: h => applyUpdate(h) };

for (const [who, apply] of Object.entries(APPLY)) {
  test(`${who}: 숨은 표시만 있고 제작 잠금 주인이 죽었으면 그 판으로 바꾼다`, () => {
    const H = pc(`dead_${who}`);
    lock(deadPid());
    assert.equal(apply(H), '1.0.57');
    assert.equal(read(path.join(H, 'server', 'index.js')), '// 1.0.57');
    assert.equal(JSON.parse(read(path.join(H, 'app_version.json'))).version, '1.0.57');
    assert.equal(fs.existsSync(path.join(H, '_update', 'pending.hold.json')), false);
  });

  test(`${who}: 제작 잠금 주인이 살아 있으면(다른 창이 만드는 중) 바꾸지 않는다`, async () => {
    const H = pc(`alive_${who}`);
    const maker = spawn(process.execPath, ['-e', 'setTimeout(()=>{},60000)'], { stdio: 'ignore' });
    await new Promise(r => setTimeout(r, 200));
    lock(maker.pid);
    try {
      assert.equal(apply(H), null);
      assert.equal(read(path.join(H, 'server', 'index.js')), '// 1.0.50');
      assert.ok(fs.existsSync(path.join(H, '_update', 'pending.hold.json')), '숨김 그대로');
    } finally { maker.kill(); fs.rmSync(path.join(process.env.SHORTEM_HOME, 'rent.lock'), { force: true }); }
  });
}

test('서버: 판 확인 때 아무도 안 만들면 숨은 표시를 되살린다(supervisor 바꾸기 신호가 pending.json 을 본다)', async () => {
  const H = pc('server');
  lock(deadPid());
  const stage = path.join(root, 'stage');
  for (const [rel, s] of [['server/index.js', '// 1.0.57'], ['engine/tools/calcopy/make.py', '# 1.0.57']]) {
    fs.mkdirSync(path.dirname(path.join(stage, rel)), { recursive: true }); fs.writeFileSync(path.join(stage, rel), s);
  }
  const zip = execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
    'import sys;sys.path.insert(0,sys.argv[1]);import publish_update as P;from pathlib import Path;sys.stdout.buffer.write(P.make_zip(Path(sys.argv[2]),"1.0.57"))',
    path.join(HERE, '..', '..', 'tools', 'claude_portal'), stage]);
  process.env.SHORTEM_TOOLS = path.join(H, 'tools');
  process.env.SHORTEM_INSTALL = H;
  const fake = await withFake({ update: { version: '1.0.57', zip } });
  try {
    const { checkUpdate } = await import('../server/updater.js');
    const { api } = await import('../server/api.js');
    process.env.SHORTEM_MACHINE_ID = 'machine-hold';
    await api.license();
    const r = await checkUpdate({ force: true });
    assert.deepEqual([r.update, r.ready, r.version], [true, true, '1.0.57']);
    assert.equal(JSON.parse(read(path.join(H, '_update', 'pending.json')) || '{}').version, '1.0.57', '표시가 보여야 supervisor 가 바꾼다');
    assert.equal(fs.existsSync(path.join(H, '_update', 'pending.hold.json')), false);
  } finally { fake.close(); }
});
