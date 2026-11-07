import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';

test('다른 창 프로그램이 같은 편 진행 고리를 쥐고 있으면 돌지 않는다(11-03 김유선 busy·stale 번갈아)', async () => {
  freshDirs('pumplock');
  const D = await import('../server/flow_driver.js');
  const sid = 'aaaabbbbcccc';
  const dir = path.join(D.flowRoot(), sid);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'flow.json'), JSON.stringify({ sid, status: 'retry' }));
  fs.writeFileSync(path.join(dir, 'pump.lock'), JSON.stringify({ pid: process.ppid }));       // 살아 있는 남(부모 프로세스)
  const f = D.retryFlow(sid);
  await f.running;
  assert.equal(f.status, 'retry');                                                      // 서버에 보내지 않았다
  assert.ok(fs.existsSync(path.join(dir, 'pump.lock')));                                // 남의 잠금은 그대로
});
