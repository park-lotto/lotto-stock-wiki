import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hold-'));
process.env.SHORTEM_HOME = home;
process.env.SHORTEM_INSTALL = home;
const { holdPending, sweep } = await import('../server/preset_rent.js');

test('만드는 중엔 판 교체 표시를 숨기고, 반납이나 다음 켜기 때 되돌린다', () => {
  const up = path.join(home, '_update');
  fs.mkdirSync(up);
  const pend = path.join(up, 'pending.json');
  fs.writeFileSync(pend, '{"version":"1.0.33"}');
  holdPending(true);
  assert.equal(fs.existsSync(pend), false);          // 연결기가 engine 을 바꾸지 못한다
  holdPending(false);
  assert.equal(fs.existsSync(pend), true);
  holdPending(true);
  sweep(path.join(home, 'engine'));                  // 프로그램이 죽어 숨김이 남은 경우
  assert.equal(fs.existsSync(pend), true);
});

test('다른 프로그램이 제작 중이면 지우지도 교체를 풀지도 않고, 주인이 죽으면 다시 쓴다', async () => {
  const { spawn } = await import('node:child_process');
  const { renting } = await import('../server/preset_rent.js');
  const other = spawn(process.execPath, ['-e', 'setTimeout(()=>{},60000)']);
  fs.writeFileSync(path.join(home, 'rent.lock'), String(other.pid));
  const pend = path.join(home, '_update', 'pending.json');
  holdPending(true);
  assert.equal(renting(), true);
  assert.equal(sweep(path.join(home, 'engine')), false);
  assert.equal(fs.existsSync(pend), false);            // 표시가 숨겨진 채로 남는다
  other.kill();
  await new Promise(r => other.on('exit', r));
  assert.equal(renting(), false);
  sweep(path.join(home, 'engine'));
  assert.equal(fs.existsSync(pend), true);
});
