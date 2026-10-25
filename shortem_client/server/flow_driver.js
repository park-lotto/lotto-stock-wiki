// 볼케이노형 제작 고리(관제 234, 2026-10-21 사장님 "볼케이노처럼 단계별로 착착") — 서버 지시서(POST /api/claude/step)를 따라 돈다.
//   서버가 do 를 주면 실행기(엔진 hybrid/runner_ops)가 돌리고, review 를 주면 회원 Claude 에게 AI 요청(shortem_ai)으로 넘기고,
//   답이 다 모이면 다시 서버로. 판단은 서버 한 곳 — 여기는 나르기만 한다(노하우 0).
//   진행 안내 = 서버 message 한 줄("OO 완료 → 다음 OO") 그대로.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { api, ApiError } from './api.js';
import { runOps, aiRootDir, dataDir } from './engine_bridge.js';
import { refreshCookies } from './logins.js';
import { ensureDir, jail } from './paths.js';

export const FLOW_SID_RE = /^[0-9a-f]{12}$/;
const flows = new Map();   // sid → { st, busy, waiters }
const flowRoot = () => ensureDir(dataDir(), 'flow');
const stFile = sid => path.join(flowRoot(), sid, 'flow.json');

function save(f) {
  const p = stFile(f.sid);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = p + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(f));
  fs.renameSync(tmp, p);
}

export function loadFlow(sid) {
  if (!FLOW_SID_RE.test(String(sid || ''))) return null;
  if (flows.has(sid)) return flows.get(sid);
  try {
    const f = JSON.parse(fs.readFileSync(stFile(sid), 'utf8'));
    f.busy = false;                                   // 디스크에서 다시 읽은 편은 돌던 고리가 없다(프로그램을 다시 켰다)
    if (f.status === 'wait_user' && f.approved === 'sent') f.approved = false;
    flows.set(sid, f); return f;
  } catch { return null; }
}
export const isFlowSid = sid => !!loadFlow(sid);

function reqId(tag) {
  const d = new Date(); const p = n => String(n).padStart(2, '0');
  const t = `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}-${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`;
  return `${t}-${String(tag).replace(/[^0-9A-Za-z가-힣_.-]+/g, '_').slice(0, 40)}-${crypto.randomBytes(3).toString('hex')}`;
}

// 서버 review 하나 → AI 요청 폴더(engine_bridge.pending 이 읽는 꼴 — shortem_ai 가 그대로 넘긴다)
function postReview(f, rv) {
  const jobDir = path.join(flowRoot(), f.sid, 'job');
  const id = reqId(rv.id);
  const d = ensureDir(aiRootDir(), path.join('flow_' + f.sid, id));
  const parts = [];
  let n = 0;
  for (const s of rv.show || []) {
    if (s.text) { parts.push({ kind: 'text', text: String(s.text) }); continue; }
    if (s.file) {
      try {
        const src = jail(jobDir, s.file);
        const name = `p${String(n++).padStart(2, '0')}${path.extname(src) || '.jpg'}`;
        fs.copyFileSync(src, path.join(d, name));
        parts.push({ kind: 'image', file: name });
      } catch { parts.push({ kind: 'text', text: '(그림을 준비하지 못함)' }); }
    }
  }
  const req = { id, tag: rv.id, tier: rv.model || 'opus', prompt: rv.ask, parts, need: rv.need || [], made_at: Date.now() / 1000 };
  fs.writeFileSync(path.join(d, 'request.json.tmp'), JSON.stringify(req));
  fs.renameSync(path.join(d, 'request.json.tmp'), path.join(d, 'request.json'));
  return { rid: rv.id, dir: d, need: rv.need || [] };
}

// 답 모으기 — 모양이 틀리면(필요 칸 없음) error.json 으로 다시 묻는다(두 번까지)
function collect(f) {
  const out = {};
  for (const q of f.asks || []) {
    const a = path.join(q.dir, 'answer.json');
    if (!fs.existsSync(a)) return null;
    let j = null;
    try { j = JSON.parse(fs.readFileSync(a, 'utf8')); } catch { j = null; }
    const miss = j && typeof j === 'object' ? (q.need || []).filter(k => !(k in j)) : ['JSON 객체'];
    if (miss.length && (q.bad || 0) < 2) {
      q.bad = (q.bad || 0) + 1;
      fs.renameSync(a, path.join(q.dir, `answer.bad${q.bad}.json`));
      fs.writeFileSync(path.join(q.dir, 'error.json'), JSON.stringify({ why: `답에 칸이 없다: ${miss.join(', ')}` }));
      save(f);
      return null;
    }
    out[q.rid] = j || {};
  }
  for (const q of f.asks || []) { try { fs.writeFileSync(path.join(q.dir, 'done'), ''); } catch { /* 이미 */ } }
  return out;
}

// 서버 응답 하나를 먹는다 → 다음 할 일(실행기면 바로 돌린다)
async function absorb(f, res) {
  f.payload = res.next_payload || f.payload;
  f.status = res.status;
  f.message = res.message || f.message;
  f.stage = res.stage || f.stage;
  f.asks = null;
  f.wait = null;
  if (res.status === 'execute') { f.do = res.do || []; save(f); return 'run'; }
  if (res.status === 'review' || res.status === 'reject') { f.asks = (res.review || []).map(rv => postReview(f, rv)); save(f); return 'ask'; }
  if (res.status === 'wait_user') { f.wait = res.wait; f.approved = false; save(f); return 'user'; }   // 새 사인 요청(길이 고친 뒤 다시 사인 등) — 앞 사인 표시를 지운다(10-21 실측: 두 번째 사인을 안 묻고 wait 만 돌았다)
  if (res.status === 'done') { f.video = res.video; f.title = res.title; f.note = res.note; save(f); return 'end'; }
  f.fail = { why: res.why || res.message || '멈췄습니다', fix: res.fix || '', retry_ok: !!res.retry_ok, server_stop: true };
  save(f);
  return 'end';
}

async function send(f, body) {
  try { return await api.step({ ...body, payload: f.payload }); }
  catch (e) {
    if (e instanceof ApiError && ['network', 'http_502', 'http_503', 'http_504'].includes(e.code)) {   // 서버가 잠깐 안 받으면 한 번 더(진행 중 편은 payload 가 PC 에 있다)
      await new Promise(r => setTimeout(r, 5000));
      return api.step({ ...body, payload: f.payload });
    }
    throw e;
  }
}

// 막힐 때(AI 답·회원 사인)까지 고리를 돈다 — 실행기 일은 기다려서 끝낸다
async function pump(f) {
  if (f.busy) return;
  f.busy = true;
  try {
    for (let guard = 0; guard < 200; guard++) {
      let res;
      if (f.status === 'execute') {
        const measure = await runOps(path.join(flowRoot(), f.sid, 'job'), f.do || []);
        res = await send(f, { step: 'go', measure });
      } else if (f.status === 'review' || f.status === 'reject') {
        const replies = collect(f);
        if (!replies) break;                        // 회원 Claude 답을 기다린다
        res = await send(f, { step: 'go', replies });
      } else if (f.status === 'retry') {
        res = await send(f, { step: 'retry' });
      } else if (f.approved === true && f.status === 'wait_user') {
        f.approved = 'sent';
        res = await send(f, { step: 'approve' });
      } else break;
      if ((await absorb(f, res)) === 'end') break;
    }
  } catch (e) {
    f.fail = { why: e instanceof ApiError ? (e.msg || e.code) : '진행이 멈췄습니다', fix: '잠시 뒤 shortem_make(step="retry") 로 이어 가세요', retry_ok: true };
    f.status = 'error';
    save(f);
  } finally { f.busy = false; save(f); }
}

export async function startFlow({ preset, video, product }) {
  await refreshCookies();
  const res = await api.step({ step: 'start', preset, source: { kind: 'youtube', url: video, ...(product ? { product: String(product).slice(0, 200) } : {}) } });
  const f = { sid: res.sid, preset, video, created: Date.now() };
  flows.set(f.sid, f);
  await absorb(f, res);
  f.running = pump(f);
  return f;
}

export function approveFlow(sid) { const f = loadFlow(sid); if (!f) return null; f.approved = true; save(f); f.running = pump(f); return f; }
export function retryFlow(sid) {
  const f = loadFlow(sid); if (!f) return null;
  if (f.status === 'error') { f.fail = null; f.status = f.do ? 'execute' : (f.asks ? 'review' : f.status); }
  else if (f.fail && f.fail.server_stop && f.fail.retry_ok) { f.fail = null; f.status = 'retry'; }   // 서버가 '다시 시도하면 이어 간다'고 한 멈춤(받기 실패 등)
  f.running = pump(f);
  return f;
}

function progressLine(f) {
  try {
    const p = JSON.parse(fs.readFileSync(path.join(flowRoot(), f.sid, 'job', 'progress.json'), 'utf8'));
    const what = String(p.what || '').slice(0, 40);
    if (!what) return '';
    return p.n && p.m ? `${what} ${p.n}/${p.m}` : `${what} 중`;
  } catch { return ''; }
}

// MCP 응답 꼴 — 회원에게는 message 한 줄만(세부 금지). need 로 다음 할 일.
export function shapeFlow(f) {
  const doing = f.status === 'execute' ? progressLine(f) : '';   // 실행기 진행 신호('원본 후보 조사 3/8') — 회원이 멈춘 줄 모르게(10-26)
  const base = { sid: f.sid, message: doing ? `${f.message} · ${doing}` : f.message, ...(doing ? { doing } : {}), ...(f.stage ? { stage: f.stage.text, step: f.stage.no, step_total: f.stage.total } : {}) };
  if (f.fail) return { ...base, need: 'fail', fail: { why: f.fail.why, fix: f.fail.fix || '', retry_ok: !!f.fail.retry_ok }, ...(f.fail.retry_ok ? { next: `shortem_make(step="retry", sid="${f.sid}")` } : {}) };
  if (f.status === 'done') return { ...base, need: 'done', video: f.video, title: f.title, note: f.note || undefined };
  if (f.status === 'wait_user' && f.wait && f.wait.kind === 'approve' && f.approved !== 'sent' && f.approved !== true) {
    return { ...base, need: 'approve', script: f.wait.script, next: `고객에게 script(제목·대본 줄)를 그대로 보여 주고 사인을 받으면 shortem_make(step="approve", sid="${f.sid}")`,
      hints: ['사인 전에는 목소리 합성·렌더를 하지 않습니다(고객 키 비용)'] };
  }
  if ((f.status === 'review' || f.status === 'reject') && f.asks && f.asks.some(q => !fs.existsSync(path.join(q.dir, 'answer.json')))) {
    return { ...base, need: 'ai', next: `shortem_ai(action="list") 로 요청을 받아 하나씩 답한 뒤(answer), shortem_make(step="wait", sid="${f.sid}") 를 부르세요`,
      hints: ['판정 요청입니다 — 고객에게 묻지 말고 바로 답하세요'] };
  }
  return { ...base, need: 'wait', next: `shortem_make(step="wait", sid="${f.sid}")`, hints: ['만드는 중입니다 — 같은 wait 를 다시 부르면 이어서 기다립니다. 셸·sleep 으로 기다리지 마세요'] };
}

// 기다리기 — 상태가 바뀌거나(답 필요·사인·완성·실패) waitMs 가 지날 때까지
export async function waitFlow(sid, waitMs) {
  const f = loadFlow(sid);
  if (!f) return null;
  if (!f.busy && !f.fail && f.status !== 'done') f.running = pump(f);
  const t0 = Date.now();
  while (Date.now() - t0 < waitMs) {
    const s = shapeFlow(f);
    if (s.need !== 'wait') return s;
    if (!f.busy && (f.status === 'review' || f.status === 'reject')) f.running = pump(f);   // 답이 다 왔으면 이어 간다
    await new Promise(r => setTimeout(r, 500));
  }
  return shapeFlow(f);
}
