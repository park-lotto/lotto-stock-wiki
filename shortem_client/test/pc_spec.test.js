import test from 'node:test';
import assert from 'node:assert/strict';

test('느린 PC 판정과 고객에게 할 말(사장님 11-04 — 느릴 때마다 사양 때문임을 설명)', async () => {
  const { pcSpec } = await import('../server/selftest.js');
  const c = n => Array.from({ length: n }, () => ({ model: 'AMD Ryzen 5 7430U' }));
  const slow = pcSpec(c(4), 16e9);
  assert.equal(slow.slow, true);
  assert.match(slow.say, /4스레드/);
  const ok = pcSpec(c(16), 32e9);
  assert.equal(ok.slow, false);
  assert.equal(ok.say, undefined);
  assert.equal(pcSpec(c(8), 8e9).slow, true);          // 메모리 8GB 도 느린 PC
});
