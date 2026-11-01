// 숏클 실시간 연결 회원 쪽(관제 304, 2026-11-02) — 판단은 서버 claude_live 한 곳. 여기는 나르고 저장만 한다.
//   받기: 신호(session.js, 1분)마다 pullLive → ~/.shortem/live_inbox.json 에 저장 → 다음 도구 응답(withTeam) hints 맨 앞
//         또는 회원이 말을 걸 때 UserPromptSubmit 훅(플러그인 hooks/live.js)이 맥락으로 넣는다.
//   전달 표시 = live_seen.txt 에 번호 한 줄씩 더 적기(이 프로그램·훅 둘 다 — 덮어쓰기 경합이 없게 inbox 는 이 프로그램만 쓴다).
//              다음 pull 이 서버에 got(저장함)·seen(맥락에 넣음)을 알리고, 서버가 안 것은 파일에서 지운다.
//   보내기: reportLive — 실패하면 live_outbox.json 에 두었다가 다음 신호에 다시 보낸다(끊겼을 때 나는 사고를 끊겨서 못 알리는 일이 없게).
//   회원에게는 아무것도 보이지 않는다 — 실패는 audit 에만.
import fs from 'node:fs';
import path from 'node:path';
import { api } from './api.js';
import { homeDir, writeFileIn } from './paths.js';
import { TEAM_HINT } from './firewall.js';
import { audit } from './audit.js';

export const TEAM_MAX_EACH = 5;        // 한 응답에 싣는 메시지 수 — 나머지는 다음 응답에
const OUTBOX_MAX = 20;
export const inboxFile = () => path.join(homeDir(), 'live_inbox.json');
export const seenFile = () => path.join(homeDir(), 'live_seen.txt');
export const outboxFile = () => path.join(homeDir(), 'live_outbox.json');

function readJson(file) {
  try { const v = JSON.parse(fs.readFileSync(file, 'utf8')); return Array.isArray(v) ? v : []; }
  catch (e) { if (e.code !== 'ENOENT') audit('live_file', { result: path.basename(file) }); return []; }
}
const writeJson = (name, v) => writeFileIn(homeDir(), name, JSON.stringify(v));
const seenIds = () => {
  try { return new Set(fs.readFileSync(seenFile(), 'utf8').split('\n').map(Number).filter(n => Number.isInteger(n) && n > 0)); }
  catch { return new Set(); }
};
function markSeen(ids) {
  fs.mkdirSync(homeDir(), { recursive: true });
  fs.appendFileSync(seenFile(), ids.map(i => i + '\n').join(''));
}

let warned = false;
const quietFail = e => { if (!warned) { warned = true; audit('live_fail', { result: String((e && (e.code || e.message)) || e).slice(0, 80) }); } };

async function flushOutbox() {
  const box = readJson(outboxFile());
  if (!box.length) return;
  const left = [...box];
  while (left.length) {
    try { await api.liveReport(left[0]); left.shift(); }
    catch (e) { if (e && e.status >= 400 && e.status < 500) { left.shift(); continue; } break; }   // 서버가 거절한 것은 다시 보내도 같다
  }
  writeJson('live_outbox.json', left);
}

// 신호마다 — 밀린 보고 보내기 → 서버에 알리기 + 새 메시지 받기
export async function pullLive() {
  try {
    await flushOutbox();
    const box = readJson(inboxFile());
    const seen = seenIds();
    const r = await api.livePull({ got: box.map(m => m.id), seen: [...seen] });
    warned = false;
    const keep = box.filter(m => !seen.has(m.id));          // 서버가 받은 것(seen)은 이제 지운다
    const have = new Set(box.map(m => m.id));
    const fresh = (r.messages || []).filter(m => !have.has(m.id) && !seen.has(m.id)).map(m => ({ id: m.id, ts: m.ts, sid: m.sid || '', text: String(m.text || '') }));
    if (fresh.length || keep.length !== box.length) writeJson('live_inbox.json', [...keep, ...fresh]);
    if (seen.size) writeFileIn(homeDir(), 'live_seen.txt', [...seenIds()].filter(i => !seen.has(i)).map(i => i + '\n').join(''));
  } catch (e) { quietFail(e); }
}

// 모든 도구 응답의 공통 지점(index.js reply) — 아직 안 건넨 메시지를 hints 맨 앞에. 파일이 깨져도 응답은 그대로 나간다
export function withTeam(o) {
  try {
    const seen = seenIds();
    const todo = readJson(inboxFile()).filter(m => !seen.has(m.id)).slice(0, TEAM_MAX_EACH);
    if (!todo.length) return o;
    markSeen(todo.map(m => m.id));
    pullLive();                                             // 전달됐다고 서버에 바로 알린다
    return { ...(o || {}), hints: [...todo.map(m => TEAM_HINT + m.text), ...((o && o.hints) || [])] };
  } catch (e) { quietFail(e); return o; }
}

// 회원 쪽 사건 보내기 — 절대 던지지 않는다. 결과 {ok}
export async function reportLive({ kind, text, level = 'info', sid = '', stage = '' }) {
  const body = { kind, level, text: String(text || '').slice(0, 2000), ...(sid ? { sid } : {}), ...(stage ? { stage: String(stage).slice(0, 60) } : {}) };
  try {
    const r = await api.liveReport(body);
    return { ok: true, id: r.id };
  } catch (e) {
    if (!(e && e.status >= 400 && e.status < 500)) {         // 끊김·서버 오류만 다시 보낸다
      try { writeJson('live_outbox.json', [...readJson(outboxFile()), body].slice(-OUTBOX_MAX)); } catch (x) { quietFail(x); }
    }
    quietFail(e);
    return { ok: false, code: e && e.code, msg: e && e.msg };
  }
}
