// 숏템 작업실 탭(관제 291) — work_view 가 고객 PC 기록(flow.json · job/origin_foreign · AI 요청 폴더)을 화면 꼴로 옮기는지.
//   판정↔후보 짝 = 서버가 질문에 붙인 meta(mode·sub) 그대로, 표식 없는 이전 기록은 legacy, 그림은 감옥 밖으로 못 나간다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

const root = freshDirs('work_view');
const SID = 'abcdef123456';
const home = path.join(root, 'home');
const flowDir = path.join(home, '창고', 'flow', SID);
const of = path.join(flowDir, 'job', 'origin_foreign');
fs.mkdirSync(of, { recursive: true });
fs.writeFileSync(path.join(flowDir, 'flow.json'), JSON.stringify({ sid: SID, preset: 'p_x', status: 'wait_user', wait: { kind: 'approve', script: { title: '제목', lines: ['첫 줄'] } },
  stage: { no: 6, total: 13, text: '대본 사인' }, message: '대본을 확인해 주세요' }));
fs.writeFileSync(path.join(of, 'cands_lens.json'), JSON.stringify([{ n: 1, id: 'aaa111', platform: 'yt', title: '하나', views: 10 }, { n: 2, id: 'bbb222', platform: 'tiktok', title: '둘' }]));
fs.writeFileSync(path.join(of, 'thumb_aaa111.jpg'), 'x');
fs.writeFileSync(path.join(of, 'seed_15.jpg'), 'x');
const ask = (id, tag, meta, answer) => {
  const d = path.join(home, 'ai', 'flow_' + SID, id);
  fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(d, 'request.json'), JSON.stringify({ id, tag, made_at: 1, parts: [{ kind: 'image', file: 'p00.jpg' }], ...(meta ? { meta } : {}) }));
  if (answer) fs.writeFileSync(path.join(d, 'answer.json'), JSON.stringify(answer));
};
ask('r1', 's1:of_judge', { mode: 'lens', sub: '' }, { same: [2], why: '같은 촬영분' });
ask('r2', 'of_verify', { rows: ['bbb222'], sub: '' }, { same: [1] });
ask('r3', 'script_x', null, null);

const { flowView, flowList, viewFile } = await import('../server/work_view.js');

test('진행현황 — 사인 대기·AI 대기·단계 그대로, Claude 용 next/hints 는 안 낸다', () => {
  const v = flowView(SID);
  assert.equal(v.need, 'approve');
  assert.equal(v.step, 6);
  assert.equal(v.step_total, 13);
  assert.deepEqual(v.waiting_ai, ['script_x']);
  assert.equal(v.next, undefined);
  assert.equal(v.hints, undefined);
  assert.equal(flowList()[0].sid, SID);
});

test('원본 찾기 — 판정 답을 meta(mode·sub)로 후보에 짝짓고, 실제 장면 확인 행 표시', () => {
  const o = flowView(SID).origin[0];
  assert.equal(o.part, '');
  assert.equal(o.seeds.length, 1);
  const r = o.rounds[0];
  assert.equal(r.judged, true);
  assert.deepEqual(r.cands.map(c => c.same), [false, true]);
  assert.ok(r.cands[0].thumb.startsWith(`fl/${SID}/origin_foreign/thumb_aaa111.jpg`));
  assert.equal(r.cands[1].thumb, null);
  assert.deepEqual(o.verify[0].rows.map(x => x.ok), [true]);
});

test('표식 없는 이전 기록은 legacy(판정 끝남) — 짝을 지어내지 않는다', () => {
  fs.rmSync(path.join(home, 'ai', 'flow_' + SID, 'r1'), { recursive: true });
  ask('r4', 'of_judge', null, { same: [1] });
  const r = flowView(SID).origin[0].rounds[0];
  assert.equal(r.judged, false);
  assert.equal(r.legacy, true);
  assert.deepEqual(r.cands.map(c => c.same), [null, null]);
});

test('그림 — job·AI 폴더 안 jpg/png 만', () => {
  assert.ok(viewFile('fl', SID, 'origin_foreign/thumb_aaa111.jpg'));
  assert.equal(viewFile('fl', SID, '../flow.json'), null);
  assert.equal(viewFile('fl', SID, '../../x.jpg'), null);
  assert.equal(viewFile('fl', 'nope', 'a.jpg'), null);
  assert.equal(viewFile('zz', SID, 'a.jpg'), null);
});
