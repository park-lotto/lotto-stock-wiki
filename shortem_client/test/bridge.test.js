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
const { dataDir } = await import('../server/engine_bridge.js');

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

test('세션 → need: 후보·사인·완성', async () => {
  const c = shapeSession({ sid: 'abcdef012345', state: 'candidates', candidates: [{ n: 1, title: '주걱', total: 46, line: 'x', scores: {} }] });
  assert.equal(c.need, 'choose');
  assert.match(c.next, /step="choose"/);
  assert.equal(shapeSession({ sid: 'abcdef012345', state: 'candidates', candidates: [] }).need, 'retry');
  assert.equal(shapeSession({ sid: 'abcdef012345', state: 'working', topic: { state: 'plan_review' }, files: [{ name: '계획.md' }] }).need, 'approve');
  const { dataDir } = await import('../server/engine_bridge.js');
  const tdir = path.join(dataDir(), 'calcopy', 'topics', '7');
  fs.mkdirSync(tdir, { recursive: true });
  fs.writeFileSync(path.join(tdir, 'final.mp4'), 'x');
  const done = shapeSession({ sid: 'abcdef012345', state: 'final_review', topic_id: 7, topic: { name: '코팩 / 피지' } });
  assert.equal(done.need, 'done');
  assert.ok(done.video.endsWith('코팩_피지_abcdef012345.mp4') && fs.existsSync(done.video));   // 작업 폴더 완성본/ 에 복사
  assert.ok(shapeSession({ sid: 'abcdef012345', state: 'final_review', topic_id: 8 }).fail);      // 파일 없으면 실패로
  assert.ok(shapeSession({ error: '거절', code: 403 }).fail);
});

test('판정 요청은 지금 편 것만 — 이전 편·취소된 편은 내주지 않고 답도 거절(11-01 고객 창)', () => {
  const root = path.join(homeDir(), 'ai'); fs.rmSync(root, { recursive: true, force: true });
  const fl = path.join(dataDir(), 'flow');
  const mk = (sid, n, extra = {}) => {
    const id = `20261101-20000${n}-of-abcde${n}`; const d = path.join(root, 'flow_' + sid, id);
    fs.mkdirSync(d, { recursive: true });
    fs.writeFileSync(path.join(d, 'request.json'), JSON.stringify({ id, tag: 'of', tier: 'opus', prompt: 'x', parts: [], made_at: n }));
    fs.mkdirSync(path.join(fl, sid), { recursive: true });
    const p = path.join(fl, sid, 'flow.json');
    fs.writeFileSync(p, JSON.stringify({ sid, status: 'review', asks: [{ dir: d }], ...extra }));
    fs.utimesSync(p, n * 1000, n * 1000);
    return id;
  };
  const old = mk('aaaaaaaaaaaa', 1), now = mk('bbbbbbbbbbbb', 2);
  assert.deepEqual(pending().map(p => p.id), [now]);
  assert.equal(answer(old, { a: 1 }).ok, false);
  assert.equal(answer(now, { a: 1 }).ok, true);
  const c = mk('cccccccccccc', 3, { cancelled: true });
  assert.ok(!pending().some(p => p.id === c));
});

test('fable 자리는 페이블·아스트라 권고로 보인다(11-05)', async () => {
  const { tierLabel } = await import('../server/engine_bridge.js');
  assert.match(tierLabel('fable'), /페이블\(Claude\) 또는 아스트라\(코덱스\) 권고 — 필수 아님/);
  assert.equal(tierLabel('opus'), 'opus');
});
