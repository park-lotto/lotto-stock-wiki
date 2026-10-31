// 10-31 실사고: 시트 27장 14MB → 응답 18.6MB → Claude Code 가 16MB 에서 연결을 끊었다. 응답 하나는 16MB 아래, 그림은 하나도 안 사라진다.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { requestContent } from '../server/engine_bridge.js';

const LIMIT = 16 * 1024 * 1024;
function req(id, n, size = 540 * 1024) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ai-size-'));
  const parts = [];
  for (let i = 0; i < n; i++) { fs.writeFileSync(path.join(dir, `s${i}.jpg`), Buffer.alloc(size, 1)); parts.push({ kind: 'image', file: `s${i}.jpg` }); }
  return { id, dir, req: { tier: 'opus', prompt: '본다', tag: 'sheet_x', parts } };
}
const bytes = c => Buffer.byteLength(JSON.stringify(c));
const shown = (c, n) => { const t = c.filter(x => x.type === 'text').map(x => x.text).join('\n'); return Array.from({ length: n }, (_, i) => t.includes(`s${i}.jpg`)).every(Boolean); };

test('시트 27장(실사고 크기): 16MB 아래 + 넘친 그림은 경로로 전부 남는다', () => {
  const c = requestContent(req('a', 27));
  assert.ok(bytes(c) < LIMIT, String(bytes(c)));
  assert.ok(shown(c, 27));
  assert.match(c[0].text, /Read 로 직접 여세요/);
});

test('요청 5건을 한 응답에 묶어도 예산을 함께 쓴다', () => {
  const budget = { left: 12 * 1024 * 1024 };
  const c = [1, 2, 3, 4, 5].flatMap(i => requestContent(req('r' + i, 10), 40, budget));
  assert.ok(bytes(c) < LIMIT, String(bytes(c)));
});

test('그림 한 장이 예산보다 커도 끊기지 않는다', () => {
  const c = requestContent(req('b', 1, 13 * 1024 * 1024));
  assert.ok(bytes(c) < LIMIT);
  assert.ok(shown(c, 1));
});

test('41장째도 버리지 않는다', () => {
  const c = requestContent(req('c', 45, 1024));
  assert.ok(shown(c, 45));
});
