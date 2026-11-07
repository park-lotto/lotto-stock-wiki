import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

test('설치본에서 표식 없는 channel 은 반납 찌꺼기 — 개발 PC 로 오판하지 않고 지운다(11-03 김효준 판 없음 3번)', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'rent-'));
  process.env.SHORTEM_HOME = path.join(home, 'h');
  const eng = path.join(home, 'engine');
  fs.mkdirSync(path.join(eng, 'channel', 'x'), { recursive: true });
  delete process.env.SHORTEM_ENGINE;
  delete process.env.SHORTEM_DEV_TOOLS;
  const R = await import('../server/preset_rent.js?' + Date.now());
  delete process.env.SHORTEM_INSTALL;
  const dev = await R.rentPreset({ engineRoot: eng, presetId: 'p1' });          // 개발(설치본 아님) = 진짜 파일로 본다
  assert.equal(dev.dev, true);
  assert.ok(fs.existsSync(path.join(eng, 'channel', 'x')));
  process.env.SHORTEM_INSTALL = path.join(home, 'inst');
  const r = await R.rentPreset({ engineRoot: eng, presetId: 'p1' }).catch(e => ({ err: e }));   // 서버가 없어 빌리기는 실패해도 된다
  assert.notEqual(r.dev, true);
  assert.equal(fs.existsSync(path.join(eng, 'channel', 'x')), false);
  delete process.env.SHORTEM_INSTALL;
});
