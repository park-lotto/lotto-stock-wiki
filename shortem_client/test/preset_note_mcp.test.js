// 98 #160(10-26 잇템로그 회원 실측) — '잇템로그 스타일로'가 별칭으로 '외국인+한국제품반응'에 걸렸는데 응답엔 그 사실이 없고, 프리셋 목록은 p_… 번호뿐이라
//   회원 Claude 가 "다른 프리셋이 골라졌다"고 헷갈려 두 번 멈췄다. 판정: 별칭으로 찾았으면 preset_note 한 줄 · 목록은 이름(+별칭).
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import { freshDirs, withFake } from './helpers.js';

freshDirs('preset_note_mcp');
const PID = 'p_7777777777';
const fake = await withFake({ rent: { pid: PID, name: '외국인+한국제품반응', aliases: ['잇템로그'], deny: true, entitle: true } });
const SERVER = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'server', 'index.js');
const client = new Client({ name: 't', version: '1' });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [SERVER], env: { ...process.env }, stderr: 'ignore' }));
test.after(async () => { await client.close(); await fake.close(); });

test('별칭으로 고르면 "잇템로그 스타일 = 외국인+한국제품반응" 한 줄을 같이 준다', async () => {
  const r = await client.callTool({ name: 'shortem_make', arguments: { step: 'start', preset_name: '잇템로그 스타일로', video: 'https://www.youtube.com/shorts/NHwcwJCsOps' } });
  const s = r.structuredContent || {};
  assert.equal(s.preset_used, '외국인+한국제품반응', JSON.stringify(s));
  assert.match(s.preset_note || '', /잇템로그 스타일로.*=.*외국인\+한국제품반응/, JSON.stringify(s));
});

test('프리셋 목록은 번호가 아니라 이름(+별칭)', async () => {
  const r = await client.callTool({ name: 'shortem_presets', arguments: { refresh: true } });
  const ps = ((r.structuredContent || {}).info || {}).presets || [];
  const mine = ps.find(p => p.preset === '외국인+한국제품반응');
  assert.ok(mine, JSON.stringify(ps));
  assert.equal(mine.also, '잇템로그');
  assert.ok(!ps.some(p => /^p_[0-9a-f]{10}$/.test(p.preset)), JSON.stringify(ps));
});
