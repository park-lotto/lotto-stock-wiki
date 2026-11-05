import test from 'node:test';
import assert from 'node:assert/strict';

test('멈춘 편은 상태 칸이 review 로 남아도 바쁜 편으로 치지 않는다(11-03 강태경 벤치마킹 막힘)', async () => {
  const { flowBusy } = await import('../server/flow_driver.js');
  assert.equal(flowBusy({ status: 'review', cancelled: true }), false);
  assert.equal(flowBusy({ status: 'execute', cancelled: true, busy: true }), true);      // 실행기가 끝나는 중이면 기다린다
  assert.equal(flowBusy({ status: 'review' }), true);
  assert.equal(flowBusy({ status: 'done' }), false);
  assert.equal(flowBusy(null), false);
});
