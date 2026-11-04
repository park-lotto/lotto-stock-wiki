// #4135~#4162(11-04 이성택 bdadce8082ac): 네트워크로 status 'error' 가 된 편을 retry 해도 매번 바로 같은 오류 — 서버에 요청 0건.
//   retryFlow 가 메모리에서만 상태를 바꾸고 저장하지 않아, pump 시작의 '디스크 최신 상태로 덮기'(1c7e4f4e0)가 error 로 되돌렸다.
//   retryFlow·recleanFlow 는 approveFlow 처럼 저장한 뒤 pump 를 부른다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

freshDirs('flow_retry_saved');
const { loadFlow, retryFlow, flowRoot } = await import('../server/flow_driver.js');

test('error 편 retry 는 디스크 상태까지 바꿔 pump 가 되돌리지 않는다', async () => {
  const sid = 'bbbbbbbbbb01';
  fs.mkdirSync(path.join(flowRoot(), sid), { recursive: true });
  // do 없이 asks 만 있는 편 — retry 하면 review(회원 Claude 답 대기)로 가야 한다(실행기는 안 돈다)
  fs.writeFileSync(path.join(flowRoot(), sid, 'flow.json'), JSON.stringify({ sid, preset: 'p_aaaaaaaaaa', status: 'error', asks: [{ id: 'q1', dir: path.join(flowRoot(), sid, 'q1') }],
    fail: { why: '서버에 연결하지 못했습니다', retry_ok: true }, movedAt: Date.now() }));
  loadFlow(sid);
  const f = retryFlow(sid);
  await f.running;
  const d = JSON.parse(fs.readFileSync(path.join(flowRoot(), sid, 'flow.json'), 'utf8'));
  assert.equal(d.status, 'review', '다시 시도가 error 로 되돌아갔다: ' + JSON.stringify(d.fail));
  assert.ok(!d.fail, '예전 오류 문구가 그대로 남았다');
});
