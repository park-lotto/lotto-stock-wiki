// 멈춘 응답의 수리판 신호(사장님 10-31)
import test from 'node:test';
import assert from 'node:assert/strict';
import { updateSignal } from '../server/make_flow.js';

const stop = { fail: { why: '멈춤' } };
const applied = async () => ({ applied: true, version: '1.0.13' });

test('멈췄고 수리판이 있으면 적용하고 다시 부르라고 알린다', async () => {
  const o = await updateSignal(stop, { isIdle: () => true, update: applied });
  assert.equal(o.fail.retry_ok, true);
  assert.match(o.hints[0], /1\.0\.13/);
});
test('돌고 있는 편이 있으면 덮지 않는다', async () => {
  let n = 0;
  const o = await updateSignal(stop, { isIdle: () => false, update: async () => { n++; return { applied: true, version: 'x' }; } });
  assert.equal(n, 0); assert.equal(o, stop);
});
test('이미 적용했거나 새 판이 없으면 응답을 바꾸지 않아 되풀이가 없다', async () => {
  assert.equal(await updateSignal(stop, { isIdle: () => true, update: async () => ({ applied: false, why: 'already' }) }), stop);
});
test('멈춘 응답이 아니면 확인하지 않는다', async () => {
  let n = 0; const ok = { need: 'wait' };
  assert.equal(await updateSignal(ok, { isIdle: () => true, update: async () => { n++; } }), ok);
  assert.equal(n, 0);
});
