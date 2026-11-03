// 채널 벤치마킹 2판(관제 319 과제 8) — 회원 PC 는 서버 지시서 고리(startBenchFlow → absorb·pump)로 돈다.
//   시험 편 = 서버가 내는 회원 과제(meta.kind=member_task): 회원 PC 손이 임시 내 프리셋을 올리고(addMine) 과제 글에 그 id 를 채우고,
//   회원 Claude 가 답한 편 sid 의 결과 폴더(엔진 창고 밖)를 흐름 작업 폴더 안으로 옮겨 상대 경로로 바꾼다.
import test from 'node:test';
import assert from 'node:assert';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('bench_v2');
const { api } = await import('../server/api.js');
const { startBenchFlow, waitFlow, flowRoot, cancelFlow } = await import('../server/flow_driver.js');
const { pending, answer, dataDir } = await import('../server/engine_bridge.js');
const M = await import('../server/my_presets.js');
const keepStep = api.step;
test.after(() => { api.step = keepStep; });

test('startBenchFlow sends bench_start with channel', async () => {
  let sent;
  api.step = async b => { sent = b; return { sid: 'abcdefabcdef', status: 'execute', do: [{ id: 'bm_env', cmd: 'bm_env' }], next_payload: 'p' }; };
  const f = await startBenchFlow({ channel: 'https://www.youtube.com/@abc', name: 'n', n: 3, dryRun: true });
  assert.equal(sent.step, 'bench_start');
  assert.equal(sent.source.url, 'https://www.youtube.com/@abc');
  assert.equal(f.sid, 'abcdefabcdef');
});

const SID = '0123456789ab';
const ESID = 'feedfeedfeed';
const ASK = '## 회원 과제 — 시험 영상 1편\n- 만들기: shortem_make(step="start", preset="{preset_id}") 로 시작\n답: {"work_dir": "<sid>", "ok": true}';
const TASK = { id: 'bm_trial', model: 'opus', ask: ASK, need: ['work_dir', 'ok'],
  meta: { kind: 'member_task', tool: 'shortem_make', preset: { slug: 'my_t', style: 'frm', dir: 'channel/my_t/preset/frm' }, source: { channel: 'https://www.youtube.com/@abc' }, try: 0 } };
const W = () => path.join(flowRoot(), SID, 'job');
const sent = [];

test('회원 과제 review → 임시 내 프리셋을 올리고, 회원 Claude 과제 글에 그 id 가 들어간다', async () => {
  const pd = path.join(W(), 'channel', 'my_t', 'preset', 'frm');
  fs.mkdirSync(pd, { recursive: true });
  fs.writeFileSync(path.join(pd, 'manifest.json'), '{"slug":"my_t"}');
  fs.writeFileSync(path.join(pd, 'frame.json'), '{}');
  api.step = async b => { sent.push(b); return sent.length === 1 ? { sid: SID, status: 'review', message: '시험 영상 만들기 중', review: [TASK], next_payload: 'p1' }
    : { sid: SID, status: 'stop', why: '멈춤', fix: '다시', retry_ok: true, next_payload: 'p2' }; };
  const f = await startBenchFlow({ channel: 'https://www.youtube.com/@abc', name: '내 틀', n: 3 });
  const o = await waitFlow(f.sid, 2000);
  assert.equal(o.need, 'ai', JSON.stringify(o));
  const mine = M.listMine().filter(p => p.slug === 'my_t');
  assert.equal(mine.length, 1, '임시 내 프리셋 1개');
  assert.equal(mine[0].channel, 'https://www.youtube.com/@abc');
  assert.ok(fs.existsSync(path.join(M.myRoot(), 'my_t', 'preset', 'frm', 'frame.json')));
  const p = pending().find(x => x.req.tag === 'bm_trial');
  assert.ok(p, '회원 Claude 에게 과제가 갔다');
  assert.ok(p.req.prompt.includes(`shortem_make(step="start", preset="${mine[0].id}")`), p.req.prompt);
  assert.ok(!p.req.prompt.includes('{preset_id}'));
  assert.equal(p.req.meta.kind, 'member_task', '작업실 화면 표식(meta)은 그대로');
});

test('답한 편 sid 의 결과 폴더(W 밖)가 W 안으로 들어오고, 서버로 가는 work_dir 은 W 기준 상대 경로', async () => {
  const mk = path.join(dataDir(), 'calcopy', 'make');
  const out = path.join(mk, ESID, 'work', '7', '제작');
  fs.mkdirSync(path.join(out, '대조'), { recursive: true });
  for (const n of ['final.mp4', 'timeline.json', 'remake_log.json']) fs.writeFileSync(path.join(out, n), n);
  fs.writeFileSync(path.join(out, '대조', 'verdict.json'), '{}');
  fs.writeFileSync(path.join(mk, `${ESID}.json`), JSON.stringify({ sid: ESID, topic_id: 7 }));
  const p = pending().find(x => x.req.tag === 'bm_trial');
  assert.equal(answer(p.id, { work_dir: ESID, ok: true }).ok, true);
  await waitFlow(SID, 3000);
  const go = sent[1];
  assert.equal(go && go.step, 'go', JSON.stringify(sent));
  const wd = go.replies.bm_trial.work_dir;
  assert.equal(go.replies.bm_trial.ok, true);
  assert.equal(wd, `trial/t0_${ESID}`);
  assert.ok(!path.isAbsolute(wd));
  for (const n of ['final.mp4', 'timeline.json', 'remake_log.json', '대조/verdict.json']) assert.ok(fs.existsSync(path.join(W(), wd, n)), n);
});

test('없는 편 sid 를 답하면 ok:false 와 이유로 서버에 간다(조용히 넘어가지 않음)', async () => {
  sent.length = 0;
  const S2 = '0123456789ac';
  const pd = path.join(flowRoot(), S2, 'job', 'channel', 'my_t', 'preset', 'frm');
  fs.mkdirSync(pd, { recursive: true });
  fs.writeFileSync(path.join(pd, 'frame.json'), '{}');
  api.step = async b => { sent.push(b); return sent.length === 1 ? { sid: S2, status: 'review', message: 'x', review: [TASK], next_payload: 'q1' }
    : { sid: S2, status: 'stop', why: '멈춤', fix: '다시', retry_ok: false, next_payload: 'q2' }; };
  await startBenchFlow({ channel: 'https://www.youtube.com/@abc', name: '내 틀', n: 3 });
  const p = pending().find(x => x.req.tag === 'bm_trial');
  assert.equal(answer(p.id, { work_dir: 'aaaaaaaaaaaa', ok: true }).ok, true);
  await waitFlow(S2, 3000);
  const r = sent[1].replies.bm_trial;
  assert.equal(r.ok, false);
  assert.match(r.why, /편/);
});

test('과제 글에 프리셋 자리가 없으면 회원 Claude 에게 안 보이고 ok:false 로 바로 답한다', async () => {
  sent.length = 0;
  const S3 = '0123456789ad';
  const pd = path.join(flowRoot(), S3, 'job', 'channel', 'my_t', 'preset', 'frm');
  fs.mkdirSync(pd, { recursive: true });
  fs.writeFileSync(path.join(pd, 'frame.json'), '{}');
  api.step = async b => { sent.push(b); return sent.length === 1 ? { sid: S3, status: 'review', message: 'x', review: [{ ...TASK, ask: '자리 없는 글' }], next_payload: 'r1' }
    : { sid: S3, status: 'stop', why: '멈춤', fix: '다시', retry_ok: false, next_payload: 'r2' }; };
  await startBenchFlow({ channel: 'https://www.youtube.com/@abc', name: '내 틀', n: 3 });
  await waitFlow(S3, 3000);
  assert.equal(sent[1] && sent[1].replies.bm_trial.ok, false, JSON.stringify(sent));
  cancelFlow(S3);
});

test('멈추면(cancel) 끝 고리가 한 번 불리고, 임시본을 지우면 같은 이름의 원래 내 프리셋이 되살아난다', async () => {
  const src = path.join(flowRoot(), '_orig');
  fs.mkdirSync(path.join(src, 'channel', 'my_k', 'preset', 'frm'), { recursive: true });
  fs.writeFileSync(path.join(src, 'channel', 'my_k', 'preset', 'frm', 'frame.json'), '"원래"');
  const [orig] = M.addMine(src, { slug: 'my_k', name: '원래 틀', presets: [{ style: 'frm', sources: ['a'] }] }, '');
  const S4 = '0123456789ae';
  const pd = path.join(flowRoot(), S4, 'job', 'channel', 'my_k', 'preset', 'frm');
  fs.mkdirSync(pd, { recursive: true });
  fs.writeFileSync(path.join(pd, 'frame.json'), '"시험"');
  api.step = async () => ({ sid: S4, status: 'review', message: 'x', review: [{ ...TASK, meta: { ...TASK.meta, preset: { slug: 'my_k', style: 'frm', dir: 'channel/my_k/preset/frm' } } }], next_payload: 's1' });
  let ends = 0;
  await startBenchFlow({ channel: '', videos: ['https://youtu.be/abcdefghijk'], name: '원래 틀', n: 1, onEnd: () => { ends++; M.dropMine('my_k'); } });
  await waitFlow(S4, 500);
  assert.equal(M.listMine().find(p => p.slug === 'my_k').name, '원래 틀 시험');
  const c = cancelFlow(S4);
  await c.ended;
  assert.equal(ends, 1);
  const back = M.listMine().filter(p => p.slug === 'my_k');
  assert.deepEqual(back.map(p => [p.id, p.name]), [[orig.id, '원래 틀']]);
  assert.equal(fs.readFileSync(path.join(M.myRoot(), 'my_k', 'preset', 'frm', 'frame.json'), 'utf8'), '"원래"');
  assert.equal(fs.existsSync(path.join(M.myRoot(), '_keep', 'my_k')), false);
});
