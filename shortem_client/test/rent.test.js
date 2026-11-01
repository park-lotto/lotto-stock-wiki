// 편마다 프리셋 빌리기(관제 234 5판) — 파이썬으로 잠근 꾸러미를 풀고, 엔진 도는 동안만 두고, 끝나면 지운다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { freshDirs, withFake } from './helpers.js';

const root = freshDirs('rent');
const PRESET = 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정';
const zipOf = files => execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c',
  'import sys,io,json,zipfile\nb=io.BytesIO()\nz=zipfile.ZipFile(b,"w",zipfile.ZIP_DEFLATED)\n[z.writestr(k,v) for k,v in json.loads(sys.argv[1]).items()]\nz.close()\nsys.stdout.buffer.write(b.getvalue())',
  JSON.stringify(files)]);
const FILES = { [`${PRESET}/frame.json`]: JSON.stringify({ layers: [{ kind: 'bg' }] }), [`${PRESET}/manifest.json`]: '{"slug":"sseolpulda"}',
  'channel/sseolpulda/뜯기/abc/뜯기.json': '{"자막":"'.padEnd(5000, '가') + '"}' };
const rent = { zip: zipOf(FILES), preset_path: PRESET };
const fake = await withFake({ rent });
const { rentPreset, sweep } = await import('../server/preset_rent.js');
const { api } = await import('../server/api.js');
test.after(() => fake.close());
process.env.SHORTEM_MACHINE_ID = 'machine-rent';
await api.license();

const engine = name => { const d = path.join(root, name); fs.mkdirSync(d, { recursive: true }); return d; };
const leaseOf = () => [...fake.state.customers.values()][0].lease;

test('빌리기: 풀린 파일 = 꾸러미 원본 · 다 쓰면 channel 통째로 지우고 작업 권한 반납', async () => {
  const E = engine('e1');
  const r = await rentPreset({ engineRoot: E, profileId: 'cp_sseol01' });
  assert.equal(r.presetPath, PRESET);
  for (const [k, v] of Object.entries(FILES)) assert.equal(fs.readFileSync(path.join(E, k), 'utf8'), v, k);
  assert.ok(leaseOf(), '빌리는 동안 작업 권한이 살아 있다');
  await assert.rejects(rentPreset({ engineRoot: E, profileId: 'cp_sseol01' }), e => e.code === 'busy');
  await r.release();
  assert.equal(fs.existsSync(path.join(E, 'channel')), false, '끝나면 남김없이 지운다');
  assert.equal(leaseOf(), null, '작업 권한 반납');
  assert.ok(!fs.readdirSync(process.env.SHORTEM_HOME, { recursive: true }).some(n => /\.zip$|뜯기/.test(String(n))), '꾸러미·풀린 파일이 홈에 남지 않는다');
});

test('개발 PC(표식 없는 진짜 channel)는 빌리지 않고 지우지도 않는다', async () => {
  const E = engine('dev');
  fs.mkdirSync(path.join(E, 'channel', 'mine'), { recursive: true });
  fs.writeFileSync(path.join(E, 'channel', 'mine', 'a.json'), '{}');
  const before = fake.state.rents;
  const r = await rentPreset({ engineRoot: E, profileId: 'cp_sseol01' });
  assert.equal(r.dev, true);
  await r.release();
  assert.equal(sweep(E), false);
  assert.ok(fs.existsSync(path.join(E, 'channel', 'mine', 'a.json')));
  assert.equal(fake.state.rents, before);
});

test('등급 없음·열쇠 틀림·바깥 경로 → 실패하고 아무것도 안 남는다', async () => {
  for (const [why, patch, code] of [['등급', { deny: true }, 'not_entitled'], ['열쇠', { tamper: true }, /authenticate/],
    ['바깥 경로', { zip: zipOf({ 'channel/../evil.txt': 'x' }) }, /바깥 경로/]]) {
    const E = engine('bad_' + why.replace(/\s/g, ''));
    Object.assign(rent, patch);
    await assert.rejects(rentPreset({ engineRoot: E, profileId: 'cp_sseol01' }), e => (code instanceof RegExp ? code.test(e.message) : e.code === code), why);
    for (const k of Object.keys(patch)) delete rent[k];
    rent.zip = zipOf(FILES);
    assert.equal(fs.existsSync(path.join(E, 'channel')), false, why);
    assert.equal(fs.existsSync(path.join(root, 'evil.txt')) || fs.existsSync(path.join(E, 'evil.txt')), false, why);
    assert.equal(leaseOf(), null, why + ' — 작업 권한도 반납');
  }
});

test('프로그램이 죽어 남은 빌린 channel 은 다음에 켤 때 지운다(표식 있는 것만)', () => {
  const E = engine('stale');
  fs.mkdirSync(path.join(E, 'channel', 'x'), { recursive: true });
  fs.writeFileSync(path.join(E, 'channel', '.rented'), 'm1');
  assert.equal(sweep(E), true);
  assert.equal(fs.existsSync(path.join(E, 'channel')), false);
});
