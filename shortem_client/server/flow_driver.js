// 단계형 제작 고리(관제 234, 2026-10-21 사장님 "외부 사례처럼 단계별로 착착") — 서버 지시서(POST /api/claude/step)를 따라 돈다.
//   서버가 do 를 주면 실행기(엔진 hybrid/runner_ops)가 돌리고, review 를 주면 회원 Claude 에게 AI 요청(shortem_ai)으로 넘기고,
//   답이 다 모이면 다시 서버로. 판단은 서버 한 곳 — 여기는 나르기만 한다(노하우 0).
//   진행 안내 = 서버 message 한 줄("OO 완료 → 다음 OO") 그대로.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { api, ApiError } from './api.js';
import { runOps, aiRootDir, dataDir, engineRoot } from './engine_bridge.js';
import { rentPreset } from './preset_rent.js';
import { packFile, PID_RE } from './local_settings.js';
import { refreshCookies } from './logins.js';
import { setupPassed } from './selftest.js';
import { resolveTools } from './tools_paths.js';
import { ensureDir, jail } from './paths.js';
import { packFor } from './local_settings.js';
import { reportLive } from './live.js';

export const FLOW_SID_RE = /^[0-9a-f]{12}$/;
const flows = new Map();   // sid → { st, busy, waiters }
export const flowRoot = () => ensureDir(dataDir(), 'flow');
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
export const anyFlowBusy = () => [...flows.values()].some(f => f.busy || f.status === 'execute' || f.status === 'review');   // 돌고 있는 편이 있으면 엔진을 덮지 않는다

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
  const req = { id, tag: rv.id, tier: rv.model || 'opus', prompt: rv.ask, parts, need: rv.need || [], made_at: Date.now() / 1000, ...(rv.meta ? { meta: rv.meta } : {}) };   // meta = 작업실 화면이 판정을 후보에 짝짓는 표식(work_view)
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
  f.finding = res.finding ? { ...res.finding, at: Date.now() } : null;
  f.movedAt = Date.now();
  if (res.script) f.script = res.script;   // 지금 대본(제목·줄 id·문장) — 회원이 보자고 하면 그대로(step='script'), 고칠 줄은 reviseFlow   // 원본 찾기 진행 줄(서버 flow.finding_say) — 기다리는 동안 'N분째'를 시계로 채운다
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

// 실행기 일은 그 편 프리셋(판 설정·벤치 자료 꾸러미)을 빌린 채로 — 렌더·계획·준비 점검이 판 설정을 읽는다(10-29 회원 실측:
//   빌리지 않아 렌더가 판 파일 없음 SystemExit 로 조용히 죽고 '같은 원인 3번'으로 멈췄다). 빌림 판단은 서버 claude_portal.preset_rent 한 곳.
const COOKIE_EVERY_MS = 20 * 60 * 1000;   // 한 편이 30~50분 — 유튜브 세션이 도는 사이 끊기지 않게 일 사이마다 새로 뽑는다(사장님 11-02 "중간에 안끊기게")
let cookiesAt = 0;
async function runWithPreset(f) {
  if (Date.now() - cookiesAt > COOKIE_EVERY_MS) { cookiesAt = Date.now(); await refreshCookies(); }
  const job = path.join(flowRoot(), f.sid, 'job');
  let rental = null;
  if (f.preset) {
    try { rental = await rentPreset({ engineRoot: engineRoot(), presetId: f.preset }); }
    catch (e) {
      const why = '프리셋을 받지 못했다: ' + String((e && (e.code || e.message)) || e).slice(0, 120);
      return Object.fromEntries((f.do || []).map(d => [String(d.id || d.cmd), { error: why }]));
    }
  }
  // 박힌 글자 방식(사장님 10-30 — 회원이 설정에서 바꿈: 자동·지우기·흐림) — 회원 설정 text.orig_text 를 실행기에(vmake_clean.style_mode 가 읽는다)
  let textMode = '';
  try { const pk = f.preset ? await packFor(f.preset) : null; textMode = String((pk && pk.text && pk.text.orig_text) || ''); } catch { /* 설정 못 읽음 = 판 칸 그대로 */ }
  try {
    const member = PID_RE.test(String(f.preset || '')) ? { SHORTEM_MEMBER_PACK: await packFile(f.preset) } : {};   // 꾸미기 값 → 렌더(엔진 styles.member_frame)
    return await runOps(job, f.do || [], { env: { ...member, ...(f.restyling ? { SHORTEM_RESTYLE: '1' } : {}), ...(/^(vmake|blur)$/.test(textMode) ? { SHORTEM_TEXT_MODE: textMode } : {}) } }); }
  finally { if (rental) await rental.release(); }
}

const PUMP_MAX = 200;
// 막힐 때(AI 답·회원 사인)까지 고리를 돈다 — 실행기 일은 기다려서 끝낸다
async function pump(f) {
  if (f.busy) return;
  f.busy = true;
  let guard = 0;
  try {
    for (; guard < PUMP_MAX; guard++) {
      if (f.cancelled) break;
      let res;
      if (f.status === 'execute') {
        const measure = await runWithPreset(f);
        res = await send(f, { step: 'go', measure });
      } else if (f.status === 'review' || f.status === 'reject') {
        const replies = collect(f);
        if (!replies) break;                        // 회원 Claude 답을 기다린다
        res = await send(f, { step: 'go', replies });
      } else if (f.status === 'reclean') {
        res = await send(f, { step: 'reclean' });
      } else if (f.status === 'retry') {
        res = await send(f, { step: 'retry' });
      } else if (f.approved === true && f.status === 'wait_user') {
        f.approved = 'sent';
        res = await send(f, { step: 'approve' });
      } else break;
      if (f.cancelled) break;
      if ((await absorb(f, res)) === 'end') break;
    }
    if (guard >= PUMP_MAX) reportLive({ kind: 'stuck', sid: f.sid, stage: f.stage && f.stage.text, text: `진행 고리가 ${PUMP_MAX}번을 넘었다(같은 단계를 도는 중일 수 있다)` });
  } catch (e) {
    f.fail = { why: e instanceof ApiError ? (e.msg || e.code) : '진행이 멈췄습니다', fix: '잠시 뒤 다시 시도해 주세요', retry_ok: true };
    f.status = 'error';
    save(f);
    reportLive({ kind: 'error', sid: f.sid, stage: f.stage && f.stage.text, text: `진행 고리 멈춤: ${e instanceof ApiError ? `${e.code} ${e.msg}` : String((e && e.message) || e)}` });   // 서버는 이 편이 끊긴 걸 모른다(관제 304)
  } finally { f.busy = false; save(f); }
}

// 움직임 없는 편(관제 304) — 신호마다 본다. 사용 한도·창 닫힘으로 회원 Claude 가 사라지면 서버에서 안 보이는 멈춤이다. 그 움직임당 한 번만 알린다
export const STALL_MS = () => Number(process.env.SHORTEM_STALL_MS) || 20 * 60 * 1000;
function lastMove(f) {
  let t = f.movedAt || 0;
  try { t = Math.max(t, fs.statSync(path.join(flowRoot(), f.sid, 'job', 'progress.json')).mtimeMs); } catch { /* 진행 파일 없음 */ }
  return t;
}
export function flowStall(now = Date.now()) {
  for (const f of flows.values()) {
    if (f.cancelled || f.fail || !['execute', 'review', 'reject', 'wait_user'].includes(f.status)) continue;
    const moved = lastMove(f);
    if (!moved || now - moved < STALL_MS() || f.stallSaid === moved) continue;
    f.stallSaid = moved;
    const min = Math.round((now - moved) / 60000);
    return { kind: 'stuck', sid: f.sid, stage: f.stage && f.stage.text,
      text: f.status === 'execute' ? `실행기 일이 ${min}분째 안 끝난다` : `회원 Claude 답을 ${min}분째 기다린다(사용 한도·창 닫힘일 수 있다)` };
  }
  return null;
}

// 지금 돌고 있는 편 — 숏클은 한 번에 한 편(이 프로그램이 켜진 뒤 움직인 편만 본다)
export function liveFlow() {
  for (const f of flows.values()) {
    if (!f.cancelled && !f.fail && f.status !== 'done' && (f.busy || f.status === 'review' || f.status === 'reject')) return f;
  }
  return null;
}

// 작업 목록 — 편은 job 이 아니라 flow 에 있다(shortem_job list 가 비어 보이던 뿌리)
export function listFlows() {
  let names = [];
  try { names = fs.readdirSync(flowRoot()); } catch { return []; }
  return names.map(loadFlow).filter(Boolean).map(f => ({ sid: f.sid, preset: f.preset, status: f.cancelled ? 'cancelled' : f.fail ? 'stopped' : f.status, step: f.stage || '' }));
}

export function cancelFlow(sid) {
  const f = loadFlow(sid); if (!f) return null;
  if (f.status === 'done') return f;
  f.cancelled = true;
  f.fail = { why: '사용자가 멈췄습니다', fix: '새로 만들려면 영상 주소로 다시 시작해 주세요', retry_ok: false };
  save(f);
  return f;
}

// 완성본은 두고 지우기부터 렌더만 다시 — 대본·재료·목소리 그대로
export function recleanFlow(sid) {
  const f = loadFlow(sid); if (!f || f.busy) return f;
  f.fail = null; f.cancelled = false; f.status = 'reclean';
  f.running = pump(f);
  return f;
}

export async function startFlow({ preset, video, product }) {
  const live = liveFlow();
  if (live) throw new ApiError(409, { code: 'busy_flow', msg: `이미 만들고 있는 편이 있어요. 끝난 뒤 시작하거나 먼저 멈춰 주세요(shortem_job action="cancel", sid="${live.sid}")` });
  if (resolveTools().mode !== 'dev' && !setupPassed()) throw new ApiError(409, { code: 'need_setup', msg: '준비 점검을 먼저 끝내야 만들 수 있어요. shortem_setup 을 불러 전부 통과시킨 뒤 다시 시작하세요' });
  await refreshCookies();
  const res = await api.step({ step: 'start', preset, source: { kind: /tiktok.com/.test(video) ? 'tiktok' : (/instagram.com/.test(video) ? 'instagram' : 'youtube'), url: video, ...(product ? { product: String(product).slice(0, 200) } : {}) } });   // url '' = 서버가 소재 창고에서 고른다
  const f = { sid: res.sid, preset, video: video || '', created: Date.now() };
  flows.set(f.sid, f);
  await absorb(f, res);
  f.running = pump(f);
  return f;
}

// 회원이 대본을 보고 고칠 곳을 말함(숏클 지침 3-1) — 서버가 어느 단계에서든 그 줄만 고친다(flow.ph_member_revise). 돌던 일이 끝난 뒤에만 보낸다(순번 어긋남 방지)
export async function reviseFlow(sid, text) {
  const f = loadFlow(sid);
  if (!f) return null;
  if (f.busy) return { busy: true };
  if (!f.script) return { no_script: true };
  f.busy = true;
  try {
    f.fail = null;
    const res = await send(f, { step: 'revise', revise: String(text || '').slice(0, 500) });
    await absorb(f, res);
  } catch (e) {
    f.fail = { why: e instanceof ApiError ? (e.msg || e.code) : '고치기를 보내지 못했습니다', fix: '잠시 뒤 같은 요청을 다시 해 주세요', retry_ok: false };
    save(f);
  } finally { f.busy = false; }
  f.running = pump(f);
  return f;
}

// 완성본 다시 만들기 — 대본·재료는 그대로, 지금 회원 설정으로 렌더만 다시(주인 = 실행기 render, 프리셋 빌림·회원 값은 runWithPreset 그대로)
export async function restyleFlow(sid) {
  const f = loadFlow(sid);
  if (!f) return { error: '이 편 기록이 없습니다' };
  if (f.busy) return { error: '지금 만드는 중입니다' };
  const job = path.join(flowRoot(), f.sid, 'job');
  const v = fs.readdirSync(job).find(n => fs.existsSync(path.join(job, n, 'render', 'final.mp4')));
  if (!v) return { error: '다시 만들 재료가 없습니다' };
  f.do = [{ id: 'restyle', cmd: 'render', version: v }];
  f.restyling = true;
  const m = await runWithPreset(f).finally(() => { f.restyling = false; });
  const r = m.restyle || Object.values(m)[0] || {};
  if (r.error || r.ok === false) return { error: String(r.error || '다시 만들지 못했습니다').slice(0, 300) };
  if (f.video) fs.copyFileSync(path.join(job, v, 'render', 'final.mp4'), f.video);
  return { ok: true, video: f.video };
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
    return p.n && p.m ? `${what} ${p.n}/${p.m}` : (/중$/.test(what) ? what : `${what} 중`);   // '만드는 중 중' 겹침(10-26 잇템로그 회원 실측)
  } catch { return ''; }
}

// 원본 찾기가 길어질 때 진행 줄(사장님 10-26 "5분에 한 번씩 계속 안내") — 문구는 서버(flow.finding_say)가 준 그대로, 여기는 {m} 에 5분 단위 분만 채운다(flow.finding_line 과 같은 셈)
export function findingLine(fd, now = Date.now()) {
  const sec = Number(fd.sec || 0) + Math.max(0, (now - Number(fd.at || now)) / 1000);
  const step = Number(fd.step || 300);
  const m = Math.floor(sec / step) * step / 60;
  return m <= 0 ? String(fd.say0 || '') : String(fd.say || '').replace('{m}', String(m));
}

// MCP 응답 꼴 — 회원에게는 message 한 줄만(세부 금지). need 로 다음 할 일.
export function shapeFlow(f) {
  const doing = f.status === 'execute' ? progressLine(f) : '';   // 실행기 진행 신호('원본 후보 조사 3/8') — 회원이 멈춘 줄 모르게(10-26)
  const head = f.finding && !f.fail ? `${f.finding.base} · ${findingLine(f.finding)}` : f.message;
  const base = { sid: f.sid, message: doing ? `${head} · ${doing}` : head, ...(doing ? { doing } : {}), ...(f.stage ? { stage: f.stage.text, step: f.stage.no, step_total: f.stage.total } : {}) };
  if (f.fail) return { ...base, need: 'fail', fail: { why: f.fail.why, fix: f.fail.fix || '', retry_ok: !!f.fail.retry_ok }, ...(f.fail.retry_ok ? { next: `shortem_make(step="retry", sid="${f.sid}")` } : {}) };
  if (f.status === 'done') return { ...base, need: 'done', video: f.video, title: f.title, note: f.note || undefined };
  if (f.status === 'wait_user' && f.wait && f.wait.kind === 'approve' && f.approved !== 'sent' && f.approved !== true) {
    return { ...base, need: 'approve', script: f.wait.script, next: `고객에게 묻지 말고 대본을 네가 확인한 뒤 바로 shortem_make(step="approve", sid="${f.sid}")`,
      hints: ['고객 사인을 기다리지 않습니다. 네가 확인하고 바로 진행하세요'] };
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
  if (!f.busy && !f.fail && !f.cancelled && f.status !== 'done') f.running = pump(f);
  const t0 = Date.now();
  while (Date.now() - t0 < waitMs) {
    const s = shapeFlow(f);
    if (s.need !== 'wait') return s;
    if (!f.busy && (f.status === 'review' || f.status === 'reject')) f.running = pump(f);   // 답이 다 왔으면 이어 간다
    await new Promise(r => setTimeout(r, 500));
  }
  return shapeFlow(f);
}
