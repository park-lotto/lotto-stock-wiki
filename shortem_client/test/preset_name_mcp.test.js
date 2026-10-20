// 회원 한 줄 요청을 준비 점검 없이 바로(프리셋 목록 캐시 없음) — 10-20 실시험에서 "쓸 수 있는 프리셋: 없음"으로 멈췄다.
//   판정: start(preset_name) 가 서버에서 목록을 받아 그 프리셋을 골라 저장한다(settings.json current).
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import { freshDirs, withFake } from './helpers.js';

freshDirs('preset_name_mcp');
const PID = 'p_4444444444';
const fake = await withFake({ rent: { pid: PID, name: '연예인상품+후기형', deny: true } });   // 빌리기는 거절 — 고르기까지만 본다
const SERVER = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'server', 'index.js');
const client = new Client({ name: 't', version: '1' });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [SERVER], env: { ...process.env }, stderr: 'ignore' }));
test.after(async () => { await client.close(); await fake.close(); });

test('준비 점검 없이 한 줄 요청 → 목록을 받아 그 프리셋으로 고른다', async () => {
  assert.ok(!fs.existsSync(path.join(process.env.SHORTEM_HOME, 'profiles.json')));
  const r = await client.callTool({ name: 'shortem_make', arguments: { step: 'start', preset_name: '연예인상품 후기형', video: 'https://www.youtube.com/watch?v=dL1t0o9k2Gk' } });
  const s = r.structuredContent || {};
  assert.ok(!(s.hints || []).some(h => /찾지 못했습니다/.test(h)), JSON.stringify(s));
  assert.equal(JSON.parse(fs.readFileSync(path.join(process.env.SHORTEM_HOME, 'settings.json'), 'utf8')).current, PID);
});
