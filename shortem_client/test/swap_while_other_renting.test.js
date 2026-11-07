import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

test('다른 창 프로그램이 빌려 만드는 중(rent.lock 주인 살아 있음)이면 renting() — 업데이트 교체를 미룬다(11-03 김효준)', async () => {
  freshDirs('swaprent');
  const R = await import('../server/preset_rent.js');
  assert.equal(R.renting(), false);
  fs.writeFileSync(path.join(process.env.SHORTEM_HOME, 'rent.lock'), JSON.stringify({ pid: process.ppid, job: 'm1' }));
  assert.equal(R.renting(), true);
  fs.rmSync(path.join(process.env.SHORTEM_HOME, 'rent.lock'), { force: true });
  assert.equal(R.renting(), false);
});
