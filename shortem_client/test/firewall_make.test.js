// 만들기 흐름(make_flow) 응답이 응답 가르기(firewall.shape)를 지나도 고객이 다음 단계를 할 수 있나 — 10-20 라이브 시험 실사고:
//   sid·need·next 가 다 빠져 고객이 사인을 못 했다. 결과물로 판정: shape 뒤에 sid·need·next·후보·대본·완성본 경로가 남고, 내부 경로·모르는 칸은 빠진다.
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('fw_make');
const { shape } = await import('../server/firewall.js');
const { workDir, homeDir } = await import('../server/paths.js');

test('사인 단계: sid·need·next·대본이 남는다', () => {
  const s = shape({ sid: '841cc9cdf295', state: 'plan_review', need: 'approve', plan_files: ['대본_계획.md'],
    script: { title: '배달비 아까울 때', lines: ['불 앞에 서기 싫은 날', '전자레인지 하나로 파스타'] },
    next: 'shortem_make(step="approve", sid="841cc9cdf295")', hints: ['사인 전에는 목소리 합성·렌더를 하지 않습니다'],
    preset_path: 'channel/annapick/preset/x', merged_preset: path.join(homeDir(), 'x') });
  assert.equal(s.sid, '841cc9cdf295');
  assert.equal(s.need, 'approve');
  assert.match(s.next, /approve/);
  assert.deepEqual(s.script, { title: '배달비 아까울 때', lines: ['불 앞에 서기 싫은 날', '전자레인지 하나로 파스타'] });
  assert.equal(s.preset_path, undefined); assert.equal(s.merged_preset, undefined);
});

test('AI 요청·후보·완성본: run_id·후보 표·완성본 경로(작업 폴더/완성본)는 열고, 내부 경로는 가린다', () => {
  const ai = shape({ need: 'ai', ai_requests: 2, run_id: 'rmvg626oi3bede5', next: 'shortem_ai(action="list")' });
  assert.equal(ai.need, 'ai'); assert.equal(ai.run_id, 'rmvg626oi3bede5'); assert.equal(ai.ai_requests, 2);
  const ch = shape({ sid: 'aaaaaaaaaaaa', need: 'choose', candidates: [{ n: 1, title: '파스타 쿠커', total: 7.5, line: '귀찮을 때', scores: { x: 1 }, made: 0 }] });
  assert.deepEqual(ch.candidates, [{ n: 1, title: '파스타 쿠커', total: 7.5, line: '귀찮을 때', made: 0 }]);
  const v = path.join(workDir(), '완성본', '배달비_841cc9cdf295.mp4');
  const done = shape({ sid: '841cc9cdf295', need: 'done', video: v, hints: [`완성본: ${v}`, `엔진: ${path.join(homeDir(), 'engine', 'x.py')}`] });
  assert.equal(done.need, 'done'); assert.equal(done.video, v);
  assert.ok(!done.hints[1].includes(homeDir()), '내부 경로는 가린다');
  assert.equal(shape({ need: 'hack' }).need, undefined, '모르는 need 는 안 낸다');
  assert.equal(shape({ sid: '../../x' }).sid, undefined);
});
