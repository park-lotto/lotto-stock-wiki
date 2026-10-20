// 하이브리드 라인(엔진 hybrid/customer.py — 집 PC 제작순서 그대로, 사장님 10-21) 응답 꼴: 진행은 stage 한 줄만, 사인·멈춤·다시 시도
import test from 'node:test';
import assert from 'node:assert/strict';
import { freshDirs } from './helpers.js';

freshDirs('hybrid_flow');
const { shapeSession } = await import('../server/make_flow.js');
const { shape } = await import('../server/firewall.js');

test('사인 자리 — 대본을 보여 주고 approve, 진행 한 줄은 단계 이름만', () => {
  const o = shapeSession({ sid: 'aaaaaaaaaaaa', need: 'approve', stage: '대본 확인을 기다립니다', step: 8, total: 12,
    script: { title: '이미도 주방템', lines: ['진짜 한 3년 묵은 얼룩이'] } });
  assert.equal(o.need, 'approve');
  assert.match(o.next, /step="approve", sid="aaaaaaaaaaaa"/);
  const s = shape(o);
  assert.equal(s.stage, '대본 확인을 기다립니다');
  assert.equal(s.step, 8);
  assert.equal(s.step_total, 12);
  assert.deepEqual(s.script.lines, ['진짜 한 3년 묵은 얼룩이']);
});

test('멈춤 — 이유·회원이 할 일만, 다시 시도 가능하면 retry', () => {
  const stop = shape(shapeSession({ sid: 'bbbbbbbbbbbb', need: 'fail', stage: '원본 영상 찾는 중', why: '원본 영상을 찾지 못했습니다', fix: '원본 주소를 알려 주세요', retry_ok: false }));
  assert.equal(stop.fail.why, '원본 영상을 찾지 못했습니다');
  assert.ok(!stop.next);
  const again = shape(shapeSession({ sid: 'cccccccccccc', need: 'fail', why: 'StageError: C:/x/y/customer.py 받기 실패', fix: '같은 단계를 한 번 더', retry_ok: true }));
  assert.match(again.next, /step="retry", sid="cccccccccccc"/);
  assert.ok(!/customer\.py|C:\//.test(JSON.stringify(again)), JSON.stringify(again));   // 내부 파일·경로는 안 보인다
});
