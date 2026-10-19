// 5판 엔진 다리 — AI 요청 줄(엔진 client_llm 이 쓰는 꼴) 읽기·그림 싣기·답 쓰기(원자적)·잘못된 id 거절
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('bridge');
const { pending, requestContent, answer } = await import('../server/engine_bridge.js');
const { shapeSession } = await import('../server/make_flow.js');
const { homeDir } = await import('../server/paths.js');

function fakeRequest(id, parts) {
  const d = path.join(homeDir(), 'ai', 'r1test', id);
  fs.mkdirSync(d, { recursive: true });
  fs.writeFileSync(path.join(d, 'p01.jpg'), Buffer.from([0xff, 0xd8, 0xff, 0xd9]));
  fs.writeFileSync(path.join(d, 'request.json'), JSON.stringify({ id, tag: 'ocr0', tier: 'sonnet', prompt: '읽어라', parts, made_at: Date.now() / 1000 }));
  return d;
}

test('요청 목록 → 글 + 이미지 내용, 답은 tmp→이름 바꾸기로', () => {
  const id = '20261019-120000-ocr0-abcdef';
  const d = fakeRequest(id, [{ kind: 'text', text: '자막 0' }, { kind: 'image', file: 'p01.jpg' }]);
  const ps = pending();
  assert.equal(ps.length, 1);
  const c = requestContent(ps[0]);
  assert.equal(c[0].type, 'text');
  assert.match(c[0].text, /권장 모델: sonnet/);
  assert.match(c[0].text, /자막 0/);
  assert.equal(c[1].type, 'image');
  assert.equal(c[1].mimeType, 'image/jpeg');
  assert.deepEqual(answer(id, { items: [] }), { ok: true });
  assert.ok(fs.existsSync(path.join(d, 'answer.json')) && !fs.existsSync(path.join(d, 'answer.json.tmp')));
  assert.equal(pending().length, 0);
  assert.equal(answer(id, { items: [] }).ok, false);              // 이미 답함
});

test('잘못된 id·배열 답·경로 탈출 그림은 거절', () => {
  assert.equal(answer('../../x', {}).ok, false);
  const id = '20261019-120001-score-abcdef';
  fakeRequest(id, [{ kind: 'image', file: '../../../evil.jpg' }]);
  assert.equal(answer(id, [1, 2]).ok, false);
  const c = requestContent(pending()[0]);
  assert.equal(c.length, 1);                                       // 감옥 밖 그림은 싣지 않는다
  assert.match(c[0].text, /그림을 읽지 못함/);
});

test('세션 → need: 후보·사인·완성', () => {
  const c = shapeSession({ sid: 'abcdef012345', state: 'candidates', candidates: [{ n: 1, title: '주걱', total: 46, line: 'x', scores: {} }] });
  assert.equal(c.need, 'choose');
  assert.match(c.next, /step="choose"/);
  assert.equal(shapeSession({ sid: 'abcdef012345', state: 'candidates', candidates: [] }).need, 'retry');
  assert.equal(shapeSession({ sid: 'abcdef012345', state: 'working', topic: { state: 'plan_review' }, files: [{ name: '계획.md' }] }).need, 'approve');
  const done = shapeSession({ sid: 'abcdef012345', state: 'final_review', files: [{ name: 'final.mp4', path: 'C:/x/final.mp4' }] });
  assert.equal(done.need, 'done');
  assert.equal(done.video, 'C:/x/final.mp4');
  assert.ok(shapeSession({ error: '거절', code: 403 }).fail);
});
