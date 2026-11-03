import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

test('다른 창이 끝낸 편은 디스크 상태로 본다 — 거짓 멈춤 경보·바쁨 없음(11-03 삼현정 228분)', async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'stall-'));
  process.env.SHORTEM_HOME = home;
  process.env.SHORTEM_STALL_MS = '1000';
  const D = await import('../server/flow_driver.js?' + Date.now());
  const sid = 'abcdef123456';
  const f = path.join(D.flowRoot(), sid, 'flow.json');
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, JSON.stringify({ sid, status: 'execute', movedAt: Date.now() - 3600000 }));
  D.loadFlow(sid);                                              // 이 창 메모리 = execute
  assert.equal(D.anyFlowBusy(), true);
  fs.writeFileSync(f, JSON.stringify({ sid, status: 'done', movedAt: Date.now() - 3600000 }));     // 다른 창이 끝냄
  assert.equal(D.flowStall(), null);
  assert.equal(D.anyFlowBusy(), false);
});
