// 숏클 실시간 연결(관제 304, 2026-11-02) — 회원 프로그램 쪽. 가짜 서버로 왕복을 실제 함수로 재현한다:
//   회원 report → 이벤트 조회 → 관리자 send → 회원 pull → 도구 응답 hints → 전달 표시.
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { Client } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import { freshDirs, withFake } from './helpers.js';

freshDirs('live');
const fake = await withFake();
const { pullLive, reportLive, withTeam, inboxFile, seenFile, outboxFile, TEAM_MAX_EACH } = await import('../server/live.js');
const { shape, TEAM_HINT, TEAM_MAX } = await import('../server/firewall.js');
const { startFlow, flowStall, waitFlow } = await import('../server/flow_driver.js');
const REPO = path.resolve(process.cwd(), '..', '..');
const HOOK = path.join(REPO, 'installer', 'plugin', 'shortem', 'hooks', 'live.js');
const body = r => JSON.parse(r.content[0].text);
const sleep = ms => new Promise(r => setTimeout(r, ms));
const reset = () => { for (const f of [inboxFile(), seenFile(), outboxFile()]) fs.rmSync(f, { force: true }); fake.live.events.length = 0; fake.live.msgs.length = 0; fake.live.down = false; };

test.after(() => fake.close());

test('받은 메시지는 파일에 남고, 다음 도구 응답 hints 맨 앞에 한 번만 실린다', async () => {
  reset();
  const m = fake.liveSend(12, '목소리 키를 다시 넣어 주세요');
  await pullLive();
  assert.equal(JSON.parse(fs.readFileSync(inboxFile(), 'utf8'))[0].text, '목소리 키를 다시 넣어 주세요');
  await pullLive();                                       // 받았다고 알린다(got)
  assert.ok(m.delivered_at, '서버에 도착 표시');
  const a = shape(withTeam({ need: 'wait', hints: ['기다리세요'] }));
  assert.deepEqual(a.hints, [TEAM_HINT + '목소리 키를 다시 넣어 주세요', '기다리세요']);
  assert.equal(a.need, 'wait');
  assert.deepEqual(shape(withTeam({ need: 'wait', hints: ['기다리세요'] })).hints, ['기다리세요'], '두 번 전달하지 않는다');
  await sleep(100);
  assert.ok(m.read_at, '전달되면 서버가 안다');
  await pullLive();
  assert.equal(JSON.parse(fs.readFileSync(inboxFile(), 'utf8')).length, 0, '서버가 안 뒤엔 비운다');
});

test('긴 메시지도 방화벽에서 안 잘리고, 힌트가 많아도 맨 앞이라 안 빠진다', async () => {
  reset();
  const long = '가'.repeat(TEAM_MAX - TEAM_HINT.length);
  fake.liveSend(12, long);
  await pullLive();
  const s = shape(withTeam({ hints: Array.from({ length: 20 }, (_, i) => '안내 ' + i) }));
  assert.equal(s.hints[0], TEAM_HINT + long);
  assert.equal(s.hints.length, 12);
  assert.ok(s.hints.slice(1).every(h => h.length <= 200));
  assert.equal(shape({ hints: ['나'.repeat(500)] }).hints[0].length, 200, '다른 힌트 길이 상한은 그대로');
});

test('규격 숫자 지우기·내부 경로 가리기는 팀 메시지에도 안전하다', async () => {
  reset();
  fake.liveSend(12, '1234 번 확인 C:\\Users\\x\\.shortem\\license');
  await pullLive();
  const s = shape(withTeam({ hints: [] }), new Set([1234]));
  assert.match(s.hints[0], /1234/, '우리가 쓴 숫자는 지우지 않는다');
  assert.doesNotMatch(s.hints[0], /license/);
});

test('한 응답에 다 못 실으면 다음 응답으로 넘긴다', async () => {
  reset();
  for (let i = 0; i < TEAM_MAX_EACH + 2; i++) fake.liveSend(12, '말' + i);
  await pullLive();
  assert.equal(shape(withTeam({})).hints.length, TEAM_MAX_EACH);
  assert.equal(shape(withTeam({})).hints.length, 2);
  assert.equal(shape(withTeam({})).hints, undefined);
});

test('서버가 꺼져 있어도 도구 응답은 안 깨지고, 못 보낸 보고는 다음 신호에 다시 간다', async () => {
  reset();
  fake.live.down = true;
  await pullLive();
  assert.deepEqual(shape(withTeam({ need: 'wait' })), { need: 'wait' });
  const r = await reportLive({ kind: 'error', text: '끊겼다', sid: 'a'.repeat(12), stage: '렌더' });
  assert.equal(r.ok, false);
  assert.equal(fake.live.events.length, 0);
  assert.equal(JSON.parse(fs.readFileSync(outboxFile(), 'utf8')).length, 1);
  fake.live.down = false;
  await pullLive();
  assert.equal(fake.live.events.length, 1);
  assert.equal(fake.live.events[0].text, '끊겼다');
  assert.equal(JSON.parse(fs.readFileSync(outboxFile(), 'utf8')).length, 0);
});

test('진행 고리가 터지면 서버에 error 로 알린다', async () => {
  reset();
  let n = 0;
  fake.state.stepHandler = () => (++n === 1 ? { code: 200, json: { ok: true, sid: 'b'.repeat(12), status: 'reject', message: '판정', stage: { no: 2, total: 13, text: '소재 확인' }, review: [], next_payload: 'p1' } }
    : { code: 500, json: { ok: false, code: 'server_err', msg: '지시서 고장' } });
  await startFlow({ preset: 'p_0123456789', video: 'https://youtu.be/abcdefghijk' });
  const s = await waitFlow('b'.repeat(12), 3000);
  assert.equal(s.need, 'fail');
  await sleep(100);
  const e = fake.live.events.find(x => x.kind === 'error');
  assert.ok(e, '보고가 갔다');
  assert.equal(e.sid, 'b'.repeat(12));
  assert.equal(e.stage, '소재 확인');
  assert.match(e.text, /지시서 고장/);
});

test('회원 Claude 답을 20분 넘게 기다리면 멈춤을 한 번만 알린다', async () => {
  reset();
  fake.state.stepHandler = () => ({ code: 200, json: { ok: true, sid: 'c'.repeat(12), status: 'review', message: '판정', stage: { no: 5, total: 13, text: '제품 확인' }, review: [{ id: 'x', ask: '읽어라', need: [] }], next_payload: 'p2' } });
  await startFlow({ preset: 'p_0123456789', video: 'https://youtu.be/abcdefghijk' });
  assert.equal(flowStall(Date.now() + 19 * 60000), null);
  const s = flowStall(Date.now() + 21 * 60000);
  assert.equal(s.sid, 'c'.repeat(12));
  assert.equal(s.kind, 'stuck');
  assert.match(s.text, /답/);
  assert.equal(flowStall(Date.now() + 22 * 60000), null);
});

test('UserPromptSubmit 훅 — 저장된 미전달 메시지를 맥락으로 넣고, 한 번만', async () => {
  reset();
  fake.liveSend(12, '설정 화면에서 키를 확인해 주세요');
  await pullLive();
  const run = () => JSON.parse(execFileSync(process.execPath, [HOOK], { env: process.env, input: '{}' }).toString('utf8'));
  const a = run();
  assert.equal(a.hookSpecificOutput.hookEventName, 'UserPromptSubmit');
  assert.match(a.hookSpecificOutput.additionalContext, /숏클 팀 메시지: 설정 화면에서 키를 확인해 주세요/);
  assert.deepEqual(run(), {}, '두 번 넣지 않는다');
  assert.deepEqual(shape(withTeam({})), {}, '훅으로 전달됐으면 도구 응답에도 안 실린다');
  fs.rmSync(inboxFile(), { force: true });
  assert.deepEqual(run(), {}, '파일이 없어도 조용히 통과');
  fs.writeFileSync(inboxFile(), '{깨진 파일');
  assert.deepEqual(run(), {}, '깨진 파일이어도 회원 입력을 막지 않는다');
  fs.rmSync(inboxFile(), { force: true });
});

test('hooks.json 에 UserPromptSubmit 이 등록돼 있고 시작 훅은 그대로다', () => {
  const h = JSON.parse(fs.readFileSync(path.join(REPO, 'installer', 'plugin', 'shortem', 'hooks', 'hooks.json'), 'utf8')).hooks;
  assert.equal(h.SessionStart[0].hooks.length, 3);
  const c = h.UserPromptSubmit[0].hooks[0];
  assert.equal(c.type, 'command');
  assert.match(c.command, /hooks\/live\.js/);
});

test('허용 목록·설치 목록에 shortem_message 가 있다', () => {
  const skill = fs.readFileSync(path.join(REPO, 'installer', 'plugin', 'shortem', 'skills', 'make', 'SKILL.md'), 'utf8');
  assert.match(skill, /^allowed-tools:.*mcp__plugin_shortem_shortem__shortem_message/m);
  const man = JSON.parse(fs.readFileSync(path.join(REPO, 'installer', 'mcpb', 'manifest.json'), 'utf8'));
  assert.ok(man.tools.some(t => t.name === 'shortem_message'));
});

test('왕복 — 진짜 MCP 프로세스: shortem_message → 관리자 답장 → 신호 pull → 도구 응답 hints → 전달 표시', async () => {
  reset();
  const client = new Client({ name: 't', version: '1' });
  await client.connect(new StdioClientTransport({ command: process.execPath, args: [path.resolve('index.js')],
    env: { ...process.env, SHORTEM_INSTALL: '', SHORTEM_HB_MS: '150', SHORTEM_CLIENT: 'test' } }));   // SHORTEM_INSTALL 이 있으면 이 PC 설치본이 대신 뜬다
  try {
    const r = await client.callTool({ name: 'shortem_message', arguments: { text: '쿠팡 검색이 계속 막혀요', important: true } });
    assert.equal(body(r).info.sent, true);
    assert.equal(fake.live.events.length, 1);
    assert.equal(fake.live.events[0].kind, 'message');
    assert.equal(fake.live.events[0].level, 'important');
    assert.equal(fake.live.events[0].text, '쿠팡 검색이 계속 막혀요');

    const m = fake.liveSend(12, '다른 검색어로 해 보세요');
    for (let i = 0; i < 40 && !fs.existsSync(inboxFile()); i++) await sleep(50);
    for (let i = 0; i < 40 && !m.delivered_at; i++) await sleep(50);
    assert.ok(m.delivered_at, '신호가 받아 갔다');

    const j = await client.callTool({ name: 'shortem_job', arguments: { action: 'list' } });
    assert.equal(body(j).hints[0], TEAM_HINT + '다른 검색어로 해 보세요');
    for (let i = 0; i < 40 && !m.read_at; i++) await sleep(50);
    assert.ok(m.read_at, '서버에 전달 표시');

    const again = await client.callTool({ name: 'shortem_job', arguments: { action: 'list' } });
    assert.ok(!(body(again).hints || []).some(h => h.startsWith(TEAM_HINT)), '한 번만');
  } finally { await client.close(); }
});
