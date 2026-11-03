import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

test('엔진을 바꾸면 떠 있는 설정 검사 워커를 새로 띄운다(11-03 김만기 옛 워커가 새 칸 거절)', async () => {
  process.env.SHORTEM_ENGINE = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
  const B = await import('../server/engine_bridge.js');
  const a = await B.engineTool('check', { pack: {} }, { timeoutMs: 120000 });
  assert.ok(!a.error, JSON.stringify(a).slice(0, 300));
  const pid1 = B.workerPid();
  assert.ok(pid1);
  assert.equal(B.resetEngineWorker(), true);
  const b = await B.engineTool('check', { pack: {} }, { timeoutMs: 120000 });
  assert.ok(!b.error);
  assert.notEqual(B.workerPid(), pid1);
  B.resetEngineWorker();
});
