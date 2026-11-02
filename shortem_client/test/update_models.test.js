// 판독 모델은 설치 폴더 models/ 로(engine/ 은 연결기가 통째로 바꾼다) · 같은 판을 다시 받지 않는다 — 11-02 306MB 묶음 수리
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { freshDirs, withFake } from './helpers.js';

const root = freshDirs('update_models');
const HERE = path.dirname(fileURLToPath(import.meta.url));
const T = path.join(root, 'Shortem');
const at = (...p) => path.join(T, ...p);
const put = (rel, s) => { fs.mkdirSync(path.dirname(at(rel)), { recursive: true }); fs.writeFileSync(at(rel), s); };
const version = v => put('app_version.json', JSON.stringify({ version: v }));
const NEW = path.join(root, 'stage');
for (const [rel, s] of [['server/index.js', '// NEW'], ['engine/tools/calcopy/make.py', '# NEW']]) {
  fs.mkdirSync(path.dirname(path.join(NEW, rel)), { recursive: true }); fs.writeFileSync(path.join(NEW, rel), s);
}
// 모델을 뺀 판 — 묶기는 publish_update.make_zip 그대로
const zip = execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
  'import sys;sys.path.insert(0,sys.argv[1]);import publish_update as P;from pathlib import Path;P.MODELS_LAST="1.0.0";sys.stdout.buffer.write(P.make_zip(Path(sys.argv[2]),"1.0.1"))',
  path.join(HERE, '..', '..', 'tools', 'claude_portal'), NEW]);
put('tools/tools.manifest.json', '{}');
put('server/index.js', '// OLD');
put('engine/tools/calcopy/make.py', '# OLD');
version('1.0.0');
process.env.SHORTEM_TOOLS = at('tools');
const fake = await withFake({ update: { version: '1.0.1', zip } });
const { checkUpdate, adoptModels } = await import('../server/updater.js');
const { api } = await import('../server/api.js');
const L = createRequire(import.meta.url)(path.join(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js'));
test.after(() => fake.close());
process.env.SHORTEM_MACHINE_ID = 'machine-models';
await api.license();

let gets = 0;
const realFetch = globalThis.fetch;
globalThis.fetch = (u, o) => { if (String(u).includes('/__blob/update')) gets++; return realFetch(u, o); };
const clean = () => {
  fs.rmSync(at('_update'), { recursive: true, force: true });
  fs.rmSync(at('models'), { recursive: true, force: true });
  fs.rmSync(at('engine', 'models'), { recursive: true, force: true });
  version('1.0.0');
  gets = 0;
};

test('engine/models 를 가진 회원이 모델 없는 판을 받아도 모델이 남는다(받기 → 연결기 바꾸기)', async () => {
  clean();
  put('engine/models/a.onnx', 'AAAA');
  const r = await checkUpdate({ force: true });
  assert.deepEqual([r.ready, r.version], [true, '1.0.1']);
  assert.equal(fs.readFileSync(at('models', 'a.onnx'), 'utf8'), 'AAAA');
  assert.equal(L.applyPending(T), '1.0.1');
  assert.ok(!fs.existsSync(at('engine', 'models')), '연결기가 engine 을 통째로 바꾼다');
  assert.equal(fs.readFileSync(at('models', 'a.onnx'), 'utf8'), 'AAAA');
});

test('켜진 옛 프로그램 — 다른 연결기가 이미 바꾼 판을 다시 받지 않는다', async () => {
  clean();
  await checkUpdate({ force: true });
  assert.equal(gets, 1);
  assert.equal(L.applyPending(T), '1.0.1');     // 설치 폴더는 1.0.1, 이 프로세스의 ENGINE_VERSION 은 1.0.0 그대로
  const r = await checkUpdate({ force: true });
  assert.equal(r.update, false);
  assert.equal(gets, 1);
  assert.ok(!fs.existsSync(at('_update', 'pending.json')));
});

test('풀어 둔 판의 표시만 없어졌으면 받지 않고 다시 건다', async () => {
  clean();
  await checkUpdate({ force: true });
  fs.unlinkSync(at('_update', 'pending.json'));
  const r = await checkUpdate({ force: true });
  assert.equal(r.reused, true);
  assert.equal(gets, 1);
  assert.equal(JSON.parse(fs.readFileSync(at('_update', 'pending.json'), 'utf8')).version, '1.0.1');
});

test('만드는 중 표시가 숨어 있어도 다시 받지 않는다', async () => {
  clean();
  await checkUpdate({ force: true });
  fs.renameSync(at('_update', 'pending.json'), at('_update', 'pending.hold.json'));
  await checkUpdate({ force: true });
  assert.equal(gets, 1);
  assert.ok(!fs.existsSync(at('_update', 'pending.json')), '숨긴 표시를 되살리면 제작 중 판이 바뀐다');
});

test('반쯤 풀린 폴더는 믿지 않고 다시 받는다', async () => {
  clean();
  put('_update/1.0.1/server/index.js', '// 끊김');
  put('_update/1.0.1/engine/tools/calcopy/make.py', '# 끊김');
  put('_update/1.0.1/app_version.json', '{}');
  await checkUpdate({ force: true });
  assert.equal(gets, 1);
  assert.equal(fs.readFileSync(at('_update', '1.0.1', 'server', 'index.js'), 'utf8'), '// NEW');
});

test('모델을 못 옮겼으면 모델 없는 판을 걸지 않는다', async () => {
  clean();
  put('engine/models/a.onnx', 'AAAA');
  put('models', 'x');                            // 폴더 자리에 파일 — 복사 실패
  await assert.rejects(checkUpdate({ force: true }), /판독 모델/);
  assert.ok(!fs.existsSync(at('_update', 'pending.json')));
  assert.ok(!fs.existsSync(at('_update', '1.0.1')));
  assert.equal(fs.readFileSync(at('engine', 'models', 'a.onnx'), 'utf8'), 'AAAA');
  fs.rmSync(at('models'));
});

test('옮기기는 크기가 다르면 다시, 같으면 건너뛴다', () => {
  clean();
  put('engine/models/a.onnx', 'AAAA');
  put('models/a.onnx', 'A');
  assert.deepEqual(adoptModels(T), []);
  assert.equal(fs.readFileSync(at('models', 'a.onnx'), 'utf8'), 'AAAA');
  assert.ok(!fs.existsSync(at('models', 'a.onnx.tmp')));
  assert.deepEqual(adoptModels(path.join(root, '없는폴더')), []);
});
