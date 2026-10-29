// 원본 찾기 진행 줄(관제263 10-26 사장님 "한도 없이 원본을 찾고 있다고 5분에 한 번씩 계속 안내") — 서버 flow.finding_say 가 준 문구에
//   회원 PC 가 기다리는 동안 5분마다 'N분째'를 새로 채운다(shapeFlow). 서버를 다시 부르지 않아도 줄이 바뀌어야 한다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { freshDirs } from './helpers.js';

freshDirs('finding_line');
const { shapeFlow, findingLine } = await import('../server/flow_driver.js');

test('5분마다 N분째가 바뀐다 · 첫 5분은 분 없이', () => {
  const t0 = 1_700_000_000_000;
  const fd = { sec: 10, step: 300, base: '해외 원본 찾기 중', say0: '소재 2편의 원본을 함께 찾고 있어요 · 1편 후보 3개 / 2편 후보 0개',
    say: '소재 2편의 원본을 함께 찾고 있어요 · {m}분째 · 1편 후보 3개 / 2편 후보 0개', at: t0 };
  assert.equal(findingLine(fd, t0), fd.say0);
  assert.equal(findingLine(fd, t0 + 289_000), fd.say0);                                  // 299초
  assert.match(findingLine(fd, t0 + 291_000), /· 5분째 ·/);                              // 301초
  assert.match(findingLine(fd, t0 + 600_000), /· 10분째 ·/);
  const real = Date.now;
  try {
    Date.now = () => t0 + 900_000;
    const s = shapeFlow({ sid: 'abcdef012345', status: 'review', message: '해외 원본 찾기 중', finding: fd, asks: [] });
    assert.equal(s.message, '해외 원본 찾기 중 · 소재 2편의 원본을 함께 찾고 있어요 · 15분째 · 1편 후보 3개 / 2편 후보 0개');
    const off = shapeFlow({ sid: 'abcdef012345', status: 'review', message: '대본 쓰기 중', finding: null, asks: [] });
    assert.equal(off.message, '대본 쓰기 중');                                            // 찾기가 끝나면 서버 줄 그대로
  } finally { Date.now = real; }
});
