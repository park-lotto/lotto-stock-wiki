// 11-05 박은숙 #6491: 유튜브 로그인 창이 남은 채 인스타그램을 열면 새 창 없이 '열림'만 돌려줘 회원이 인스타 창을 끝내 못 봤다.
//   이미 떠 있으면 그 크롬에 요청한 곳 창을 더 열고(add), 응답 문구가 '전용 크롬 창을 모두 닫으라'로 다르다.
import test from 'node:test';
import assert from 'node:assert/strict';
import { openPlan, loginOpenedText } from '../server/logins.js';

test('창 있는 전용 크롬이 있으면 add(요청한 곳을 그 크롬에 연다)', () => {
  assert.equal(openPlan([{ pid: 1, win: true }], { platform: 'youtube', done: false }), 'add');
  assert.equal(openPlan([{ pid: 1, win: true }], null), 'add');
});
test('창 없이 남은 크롬은 replace, 아무것도 없으면 new, 잴 수 없으면 앞 창 따라', () => {
  assert.equal(openPlan([{ pid: 1, win: false }], null), 'replace');
  assert.equal(openPlan([], null), 'new');
  assert.equal(openPlan(null, { done: false }), 'add');
  assert.equal(openPlan(null, null), 'new');
});
test('이미 떠 있던 크롬에 더 열었으면 모두 닫으라고 안내한다', () => {
  assert.match(loginOpenedText({ already: true }, '인스타그램'), /모두 닫아/);
  assert.doesNotMatch(loginOpenedText({}, '인스타그램'), /모두 닫아/);
});
test('맥이면 Cmd+Q 로 크롬을 끝내라고 안내한다(11-05 박상혁 #7756)', () => {
  assert.match(loginOpenedText({}, '인스타그램', 'darwin'), /Cmd\+Q/);
  assert.doesNotMatch(loginOpenedText({}, '인스타그램', 'win32'), /Cmd\+Q/);
});
test('맥 쿠키 읽기는 목 키체인을 쓰지 않는다(11-05 박상혁 #7788)', async () => {
  const { cookieLaunchOpts } = await import('../server/logins.js');
  assert.deepEqual(cookieLaunchOpts('c', 'd', 'darwin').ignoreDefaultArgs, ['--use-mock-keychain']);
  assert.equal(cookieLaunchOpts('c', 'd', 'win32').ignoreDefaultArgs, undefined);
});
