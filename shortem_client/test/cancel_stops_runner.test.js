// 편 멈춤(cancel) 직후 새 편 start 가 1/11 준비 확인에서 '준비 덜 됨'으로 멈췄다 — #2027 이용재(1.0.70), #502 정민혜(3분 뒤 풀림).
//   cancelFlow 는 표시만 바꾸고 돌던 실행기는 끝날 때까지 돌아, 그동안 프리셋 빌림(rent)이 남아 새 편 env 의 빌리기가 busy 였다.
//   이제 runOps 가 signal 을 받아 실행기를 끄고 바로 끝낸다 → runWithPreset finally 가 빌림을 바로 돌려준다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { freshDirs } from './helpers.js';

freshDirs('cancel_stops_runner');
const eng = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cancel-')), 'eng');
fs.mkdirSync(path.join(eng, 'tools', 'calcopy', 'hybrid'), { recursive: true });
for (const p of ['tools', 'tools/calcopy', 'tools/calcopy/hybrid']) fs.writeFileSync(path.join(eng, p, '__init__.py'), '');
fs.writeFileSync(path.join(eng, 'tools', 'calcopy', 'hybrid', 'runner_ops.py'), 'import time, os\nopen(os.environ["SHORTEM_RESULT"] + ".pid", "w").write(str(os.getpid()))\ntime.sleep(60)\n');
process.env.SHORTEM_ENGINE = eng;
process.env.SHORTEM_PYTHON = process.env.SHORTEM_PYTHON || execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c', 'import sys;print(sys.executable)']).toString().trim();
const { runOps } = await import('../server/engine_bridge.js');

const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };

test('멈춤 신호를 받으면 실행기를 끄고 바로 끝낸다(빌림이 바로 풀리게)', async () => {
  const job = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'cjob-')), 'job');
  const ac = new AbortController();
  const t0 = Date.now();
  const p = runOps(job, [{ id: 'env', cmd: 'env' }], { signal: ac.signal });
  let pidFile = null;
  for (let i = 0; i < 100 && !pidFile; i++) {
    await new Promise(r => setTimeout(r, 100));
    pidFile = fs.readdirSync(path.dirname(job)).find(n => n.endsWith('.json.pid'));
  }
  assert.ok(pidFile, '실행기가 떴다');
  const pid = Number(fs.readFileSync(path.join(path.dirname(job), pidFile), 'utf8'));
  ac.abort();
  const r = await p;
  assert.ok(Date.now() - t0 < 20000, '60초를 기다리지 않는다');
  assert.match(r.env.error, /멈췄다/);
  for (let i = 0; i < 50 && alive(pid); i++) await new Promise(res => setTimeout(res, 100));
  assert.equal(alive(pid), false, '실행기 프로세스가 꺼졌다');
});
