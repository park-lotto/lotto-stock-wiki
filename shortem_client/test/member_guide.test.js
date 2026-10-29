// 숏클 회원 지침(installer/common/CLAUDE_숏클.md) ↔ 회원 손발 대조(관제 290, 10-30 점검표 × 11개) — 지침이 시키는 일을 도구가 실제로 할 수 있나.
import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { freshDirs } from './helpers.js';
import { makeKey } from './fake_server.js';

freshDirs('member_guide');
const REPO = path.resolve(process.cwd(), '..', '..');
const GUIDE = path.join(REPO, 'installer', 'common', 'CLAUDE_숏클.md');
const skillTools = name => {
  const t = fs.readFileSync(path.join(REPO, 'installer', 'plugin', 'shortem', 'skills', name, 'SKILL.md'), 'utf8');
  return (t.match(/^allowed-tools:(.*)$/m) || ['', ''])[1].split(/\s+/).filter(Boolean).map(x => x.replace('mcp__plugin_shortem_shortem__', ''));
};

test('지침에 나오는 숏클 도구는 make 스킬이 다 쓸 수 있다(점검표 2·3·5)', () => {
  const named = [...new Set(fs.readFileSync(GUIDE, 'utf8').match(/shortem_[a-z]+/g))];
  const allowed = new Set(skillTools('make'));
  const miss = named.filter(n => !allowed.has(n));
  assert.deepEqual(miss, [], `make 스킬 허용 목록에 없는 도구: ${miss.join(', ')}`);
  assert.ok(!/Start-Sleep/.test(fs.readFileSync(GUIDE, 'utf8')), '지침이 막힌 셸(Start-Sleep)로 기다리라고 하면 안 된다');
});

test('make 단계에 대본 보기·줄 고치기·기다리기가 있다(점검표 6·10)', async () => {
  const src = fs.readFileSync(path.join(REPO, 'shortem_client', 'server', 'index.js'), 'utf8');
  for (const s of ['script', 'revise', 'pause']) assert.match(src, new RegExp(`step: z\\.enum\\(\\[[^\\]]*'${s}'`));
  const { pauseSec } = await import('../server/make_flow.js');
  assert.equal(pauseSec(999), 60);
  assert.equal(pauseSec(1), 5);
  assert.equal(pauseSec(undefined), 60);
});

test('새 프리셋 표시 — 처음 설치는 조용히, 그 뒤 처음 보는 것만 new(점검표 4)', async () => {
  const { newPresets } = await import('../server/index.js');
  assert.equal(newPresets(['p_a', 'p_b']).size, 0);
  assert.deepEqual([...newPresets(['p_a', 'p_b', 'p_c'])], ['p_c']);
  assert.equal(newPresets(['p_a', 'p_b', 'p_c']).size, 0);
});

test('완성본 받기 연결이 없으면 done 에 안내가 붙는다(점검표 13)', async () => {
  const { deliverSay } = await import('../server/make_flow.js');
  const d = deliverSay();
  assert.deepEqual(d.deliver.to, []);
  assert.match(d.hint, /연결/);
});

test('지울 후보 — 완성본·끝난 편만, 도는 편은 빼고, 고른 id 만 지운다(점검표 11)', async () => {
  const { cleanupCandidates, showCandidates, removeCandidates } = await import('../server/disk.js');
  const { dataDir } = await import('../server/engine_bridge.js');
  const fin = path.join(process.env.SHORTEM_WORK, '완성본');
  fs.mkdirSync(fin, { recursive: true });
  fs.writeFileSync(path.join(fin, 'a_123.mp4'), Buffer.alloc(30000));
  fs.writeFileSync(path.join(fin, 'a_123.mp4.json'), '{}');
  for (const [sid, st] of [['aaaaaaaaaaaa', 'done'], ['bbbbbbbbbbbb', 'execute']]) {
    const d = path.join(dataDir(), 'flow', sid, 'job');
    fs.mkdirSync(d, { recursive: true });
    fs.writeFileSync(path.join(d, 'big.bin'), Buffer.alloc(50000));
    fs.writeFileSync(path.join(dataDir(), 'flow', sid, 'flow.json'), JSON.stringify({ sid, status: st, title: sid }));
  }
  const c = cleanupCandidates();
  assert.deepEqual(c.map(x => x.label).sort(), ['a_123.mp4', 'aaaaaaaaaaaa']);
  assert.ok(!JSON.stringify(showCandidates(c)).includes(':\\'), '회원에게 경로를 내보내지 않는다');
  const flowOne = c.find(x => x.label === 'aaaaaaaaaaaa');
  assert.equal(removeCandidates([flowOne.id, 'deadbeef']).length, 1);
  assert.ok(!fs.existsSync(path.join(dataDir(), 'flow', 'aaaaaaaaaaaa')));
  assert.ok(fs.existsSync(path.join(dataDir(), 'flow', 'bbbbbbbbbbbb')), '도는 편은 그대로');
  assert.ok(fs.existsSync(path.join(fin, 'a_123.mp4')), '고르지 않은 완성본은 그대로');
});

test('대본 보기·줄 고치기 — 서버 대본을 보관하고 revise 를 서버로 보낸다(점검표 8·10)', async () => {
  const seen = [];
  const s = await new Promise(res => {
    const srv = http.createServer((req, rsp) => {
      let b = '';
      req.on('data', d => { b += d; });
      req.on('end', () => {
        const body = JSON.parse(b || '{}');
        seen.push(body);
        const script = { title: '제목', lines: ['첫 줄', '둘째 줄'], rows: [{ id: 'L1', text: '첫 줄' }, { id: 'L2', text: '둘째 줄' }] };
        const out = body.step === 'revise'
          ? { status: 'review', message: '대본 줄 고치기', script, review: [{ id: 'line_fix_x', ask: '고쳐라', need: ['lines'] }] }
          : { status: 'review', message: '장면 맞추기', script, review: [{ id: 'plan_look', ask: '봐라', need: ['ok'] }] };
        rsp.writeHead(200, { 'Content-Type': 'application/json' });
        rsp.end(JSON.stringify({ ...out, sid: 'cccccccccccc', next_payload: `v1.${seen.length}.x.y` }));
      });
    });
    srv.listen(0, '127.0.0.1', () => res(srv));
  });
  process.env.SHORTEM_BASE = `http://127.0.0.1:${s.address().port}`;
  process.env.SHORTEM_LICENSE = makeKey(12, Math.floor(Date.now() / 1000) + 86400, 1);
  const { makeStep } = await import('../server/make_flow.js');
  const { startFlow } = await import('../server/flow_driver.js');
  const f = await startFlow({ video: 'https://www.youtube.com/shorts/cNo91ddBwB8' });
  const v = await makeStep({ step: 'script', sid: f.sid });
  assert.deepEqual(v.script.rows.map(r => r.id), ['L1', 'L2']);
  const o = await makeStep({ step: 'revise', sid: f.sid, revise: 'L2 를 더 짧게' });
  const last = seen[seen.length - 1];
  assert.equal(last.step, 'revise');
  assert.equal(last.revise, 'L2 를 더 짧게');
  assert.equal(last.payload, 'v1.1.x.y');
  assert.equal(o.need, 'ai');
  s.close();
});
