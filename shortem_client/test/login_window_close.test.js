// #4511·#4512·#4591(11-04 김효준): 로그인 창을 닫아도 계정 연결 '안 됨'. openLogin 이 '처음 띄운 크롬 프로세스의 종료'에서 쿠키를 한 번 읽었는데,
//   그 프로세스는 바로 끝나는 경우가 있다 — 같은 프로필 크롬이 떠 있으면 넘기고 0.2초 만에 끝남(이 PC 실측 code 21) · 관리자 권한이면 권한을 낮춰 다시 뜸.
//   판단 주인 = waitLoginClosed: 창이 닫혔나 = 전용 프로필에 창 있는 크롬이 없음(한 번 보인 뒤). 못 재는 PC 만 옛 exit 방식.
import test from 'node:test';
import assert from 'node:assert/strict';

const { waitLoginClosed } = await import('../server/logins.js');
const seq = list => { let i = 0; return async () => list[Math.min(i++, list.length - 1)]; };
const fast = { sleep: async () => {}, every: 1 };

test('처음 프로세스가 바로 끝나도 창이 닫힐 때까지 기다린다(넘김·권한 낮춤)', async () => {
  const killed = [];
  const why = await waitLoginClosed({ ...fast, exited: Promise.resolve(), isExited: () => true,
    procs: seq([[], [{ pid: 1, win: true }], [{ pid: 1, win: true }], [{ pid: 1, win: false }]]), kill: async ps => killed.push(...ps) });
  assert.equal(why, 'closed');
  assert.deepEqual(killed.map(p => p.pid), [1], '창 없이 남은 크롬은 치워야 쿠키 읽기가 프로필을 연다');
});

test('창이 끝내 안 뜨고 크롬도 없으면 포기(무한 대기 금지)', async () => {
  let t = 0;
  const why = await waitLoginClosed({ ...fast, exited: Promise.resolve(), isExited: () => true, procs: async () => [], clock: () => (t += 1000), goneMs: 30000 });
  assert.equal(why, 'gone');
});

test('창을 잴 수 없는 PC 는 옛 방식(프로세스 종료)', async () => {
  const why = await waitLoginClosed({ ...fast, exited: Promise.resolve(), isExited: () => true, procs: async () => null });
  assert.equal(why, 'exit');
});
