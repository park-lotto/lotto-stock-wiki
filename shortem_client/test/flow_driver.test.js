// 볼케이노형 고리(flow_driver, 관제 234 10-21) — 서버 지시서를 따라 돈다: do → 실행기 → measure, review → AI 요청 → 답 → replies, 사인 → approve.
//   가짜 지시서 서버(이 파일 안)로 고리만 본다. 실행기는 진짜 엔진 runner_ops(SHORTEM_ENGINE = 엔진 트랙)의 가벼운 명령(write_doc)으로.
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';
import { makeKey } from './fake_server.js';

freshDirs('flow_driver');
const ENGINE = process.env.SHORTEM_ENGINE || path.resolve(process.cwd(), '..', '..', '..', '칼카피숏템엔진');
const seen = [];

function server() {
  // 지시서: start → execute(write_doc) → review(판정 1건) → wait_user(사인) → done
  return new Promise(res => {
    const s = http.createServer((req, rsp) => {
      let b = '';
      req.on('data', d => { b += d; });
      req.on('end', () => {
        const body = JSON.parse(b || '{}');
        seen.push(body);
        const n = seen.length;
        const out = n === 1 ? { status: 'execute', message: '준비 확인 중', stage: { no: 1, total: 13, text: '준비 확인' }, do: [{ id: 'w', cmd: 'write_doc', files: { 'a.txt': '안녕' } }] }
          : n === 2 ? { status: 'review', message: '준비 확인 완료 → 원본 영상 찾기 중', stage: { no: 3, total: 13, text: '원본 영상 찾기' },
            review: [{ id: 'origin_read', model: 'opus', ask: '읽어라', show: [{ text: '제목: x' }, { file: 'doc/a.txt' }], need: ['celeb'] }] }
          : n === 3 || n === 4 ? { status: 'wait_user', message: '대본 확인', stage: { no: 9, total: 13, text: '대본 확인' }, wait: { kind: 'approve', script: { title: '제목', lines: [n === 3 ? '줄 하나' : '줄인 줄'] } } }
          : { status: 'done', message: '완성', stage: { no: 13, total: 13, text: '완성' }, video: path.join(ENGINE, 'README.md'), title: '제목' };
        rsp.writeHead(200, { 'Content-Type': 'application/json' });
        rsp.end(JSON.stringify({ ...out, sid: 'abcdef012345', next_payload: `v1.${n}.x.y` }));
      });
    });
    s.listen(0, '127.0.0.1', () => res(s));
  });
}

test('고리 — 실행기 결과·판정 답·사인이 서버로 차례로 간다', { skip: !fs.existsSync(path.join(ENGINE, 'tools', 'calcopy', 'hybrid', 'runner_ops.py')) }, async () => {
  const s = await server();
  process.env.SHORTEM_BASE = `http://127.0.0.1:${s.address().port}`;
  process.env.SHORTEM_LICENSE = makeKey(12, Math.floor(Date.now() / 1000) + 86400, 1);
  process.env.SHORTEM_ENGINE = ENGINE;
  const { startFlow, waitFlow, approveFlow, shapeFlow } = await import('../server/flow_driver.js');
  const { pending, answer } = await import('../server/engine_bridge.js');
  const f = await startFlow({ preset: 'p_0123456789', video: 'https://www.youtube.com/shorts/cNo91ddBwB8' });
  let o = await waitFlow(f.sid, 60000);
  assert.equal(seen[1].step, 'go');
  assert.equal(seen[1].payload, 'v1.1.x.y');                       // next_payload 그대로
  assert.equal(seen[1].measure.w.ok, true);                         // 실행기가 진짜로 돌았다
  assert.equal(o.need, 'ai', JSON.stringify(o));
  assert.match(o.message, /원본 영상 찾기/);
  const p = pending().find(x => x.req.tag === 'origin_read');
  assert.ok(p && p.req.parts.some(x => x.kind === 'image' || x.kind === 'text'));
  assert.equal(answer(p.id, { wrong: 1 }).ok, true);               // 칸 없는 답 → 다시 묻는다
  o = await waitFlow(f.sid, 3000);
  assert.equal(seen.length, 2, '틀린 꼴 답은 서버로 안 보낸다');
  const p2 = pending().find(x => x.req.tag === 'origin_read');
  assert.ok(p2 && p2.retry_why, '다시 묻는 이유가 붙는다');
  assert.equal(answer(p2.id, { celeb: '성시경' }).ok, true);
  o = await waitFlow(f.sid, 20000);
  assert.deepEqual(seen[2].replies, { origin_read: { celeb: '성시경' } });
  assert.equal(o.need, 'approve');
  assert.deepEqual(o.script.lines, ['줄 하나']);
  approveFlow(f.sid);
  o = await waitFlow(f.sid, 20000);
  assert.equal(seen[3].step, 'approve');
  // 길이를 고쳐 대본이 바뀌면 서버가 사인을 다시 묻는다 — 앞 사인으로 넘어가지 않고 다시 approve 를 요구해야 한다(10-21 실측 결함)
  assert.equal(o.need, 'approve', JSON.stringify(o));
  assert.deepEqual(o.script.lines, ['줄인 줄']);
  approveFlow(f.sid);
  o = await waitFlow(f.sid, 20000);
  assert.equal(seen[4].step, 'approve');
  assert.equal(o.need, 'done');
  assert.equal(shapeFlow(f).need, 'done');
  s.close();
});
