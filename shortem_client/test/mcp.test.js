// MCP 겉면 — stdio 로 띄워 도구 9개(5판: shortem_ai·shortem_settings·shortem_login 추가)·설명·annotations·셸 도구 없음·키 값 비노출 확인
import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import { freshDirs, withFake } from './helpers.js';

freshDirs('mcp');
const fake = await withFake();
const SERVER = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'server', 'index.js');
const client = new Client({ name: 't', version: '1' });
await client.connect(new StdioClientTransport({ command: process.execPath, args: [SERVER], env: { ...process.env }, stderr: 'ignore' }));
test.after(async () => { await client.close(); await fake.close(); });

test('도구 9개 · 고정 설명 · annotations · 셸 실행 도구 없음', async () => {
  const { tools } = await client.listTools();
  assert.deepEqual(tools.map(t => t.name).sort(), ['shortem_ai', 'shortem_feedback', 'shortem_job', 'shortem_login', 'shortem_make', 'shortem_presets', 'shortem_profile', 'shortem_settings', 'shortem_setup']);
  const by = Object.fromEntries(tools.map(t => [t.name, t]));
  assert.equal(by.shortem_presets.annotations.readOnlyHint, true);
  assert.equal(by.shortem_profile.annotations.readOnlyHint, true);
  assert.equal(by.shortem_make.annotations.destructiveHint, false);
  assert.equal(by.shortem_make.annotations.idempotentHint, false);   // start 는 매번 새 세션
  assert.equal(by.shortem_job.annotations.destructiveHint, true);
  assert.ok(!tools.some(t => /shell|exec|command|run_/i.test(t.name)));
  for (const t of tools) for (const n of ['1462', '1006', '93.2', '-7.4', '1080', '1920']) assert.ok(!t.description.includes(n), `${t.name} 설명에 규격 숫자 ${n}`);
});

test('setup: 라이선스 확인·기기 등록, 키 값은 응답에 없음', async () => {
  const r = await client.callTool({ name: 'shortem_setup', arguments: {} });
  const s = r.structuredContent;
  assert.equal(s.info.license.ok, true);
  assert.equal(s.info.license.device.slot, 1);
  assert.ok(!JSON.stringify(r).includes(process.env.SHORTEM_LICENSE));
  const p = await client.callTool({ name: 'shortem_presets', arguments: {} });
  assert.equal(p.structuredContent.info.profiles.length, 3);
  const bad = await client.callTool({ name: 'shortem_make', arguments: { step: 'rm -rf' } });
  assert.equal(bad.isError, true);
  const fb = await client.callTool({ name: 'shortem_feedback', arguments: { kind: 'bug', text: '시험' } });
  assert.equal(fb.structuredContent.info.sent, true);
});
