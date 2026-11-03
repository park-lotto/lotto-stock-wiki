// 한 PC 에 숏클 서버가 여럿(정민혜 Claude 창 7개) — 작업 폴더·제작 잠금을 같이 쓴다. 두 번째 창부터 점검(setup)이 알린다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { freshDirs } from './helpers.js';

freshDirs('instances');
const { registerServer, otherServers, OTHERS_NOTICE } = await import('../server/instances.js');
const { homeDir } = await import('../server/paths.js');

test('살아 있는 다른 서버만 세고 주인이 죽은 장부는 치운다', async () => {
  registerServer();
  assert.deepEqual(otherServers(), [], '혼자면 알림 없음');
  const other = spawn(process.execPath, ['-e', 'setTimeout(()=>{},30000)'], { stdio: 'ignore' });
  try {
    registerServer(other.pid);
    const dead = path.join(homeDir(), 'servers', '999999.json');
    fs.writeFileSync(dead, JSON.stringify({ pid: 999999 }));
    assert.deepEqual(otherServers(), [other.pid]);
    assert.equal(fs.existsSync(dead), false);
    assert.match(OTHERS_NOTICE(1), /다른 Claude 창 1곳/);
  } finally { other.kill(); }
});
