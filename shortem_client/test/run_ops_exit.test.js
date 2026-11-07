import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

test('runOps 는 close 만 기다리지 않는다', () => {
  const s = fs.readFileSync(new URL('../server/engine_bridge.js', import.meta.url), 'utf8');
  assert.match(s, /proc\.on\('exit', \(\) => setTimeout\(finish, EXIT_GRACE_MS\)/);
});

// 11-03 완성본 검사 멈춤(정민혜 1.0.52·1.0.54) — 산출물을 다 쓴 실행기가 끝나지 않아도(종료 정리에서 멈춤) 결과를 받는다
async function fakeEngine(code) {
  const os = await import('node:os');
  const path = await import('node:path');
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'runops-'));
  const d = path.join(root, 'eng', 'tools', 'calcopy', 'hybrid');
  fs.mkdirSync(d, { recursive: true });
  for (const p of ['tools', 'tools/calcopy', 'tools/calcopy/hybrid']) fs.writeFileSync(path.join(root, 'eng', p, '__init__.py'), '');
  fs.writeFileSync(path.join(d, 'runner_ops.py'), code);
  process.env.SHORTEM_ENGINE = path.join(root, 'eng');
  process.env.SHORTEM_PYTHON = process.env.SHORTEM_PYTHON || execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c', 'import sys;print(sys.executable)']).toString().trim();
  return path.join(root, 'job');
}

test('결과 파일을 쓴 실행기가 끝나지 않아도 결과를 받고 끈다', async () => {
  const job = await fakeEngine([
    'import json, os, time',
    'f = os.environ.get("SHORTEM_RESULT")',
    'if f: open(f, "w", encoding="utf-8").write(json.dumps({"check": {"ok": True}}))',
    'time.sleep(600)',
  ].join('\n'));
  const { runOps } = await import('../server/engine_bridge.js');
  const t0 = Date.now();
  const r = await runOps(job, [{ cmd: 'check' }], { timeoutMs: 30000 });
  assert.deepEqual(r, { check: { ok: true } });
  assert.ok(Date.now() - t0 < 15000, `${Date.now() - t0}ms`);
});

test('옛 엔진(stdout 마지막 줄)도 그대로 받는다', async () => {
  const job = await fakeEngine('import json\nprint(json.dumps({"check": {"ok": 1}}))\n');
  const { runOps } = await import('../server/engine_bridge.js');
  assert.deepEqual(await runOps(job, [{ cmd: 'check' }], { timeoutMs: 30000 }), { check: { ok: 1 } });
});
