// 완성본 보내기(사장님 10-20 "완성본은 텔레그램으로 받고 구글드라이브에 자동으로 저장") — 판단은 이 파일 한 곳.
//   부르는 곳: make_flow(완성본을 작업 폴더에 새로 복사한 직후) · local_ui(연결·시험 보내기).
//   텔레그램 = 고객 본인 봇(BotFather 토큰, 서버 부담 0·우리 토큰 노출 없음). 50MB 넘으면 영상 대신 알림 글만(봇 올리기 한도).
//   구글 드라이브 = 'Google Drive 데스크톱' 이 만든 '내 드라이브' 폴더에 복사 → 그 앱이 올린다(구글 로그인 창·앱 검수·경고 없음).
//   ★쓰기 뿌리(paths.jail: ~/.shortem · 작업 폴더) 밖에 쓰는 유일한 곳 — 찾아낸 '내 드라이브/숏템완성본' 만 허용한다(고객이 경로를 적지 않는다).
//   설정 ~/.shortem/deliver.json(0600) · 보낸 기록 <완성본>.sent.json(같은 완성본을 두 번 보내지 않는다, 다시 만들면 다시 보낸다).
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { homeDir, writeFileIn } from './paths.js';
import { audit } from './audit.js';

const TG = () => String(process.env.SHORTEM_TELEGRAM_API || 'https://api.telegram.org').replace(/\/+$/, '');   // 시험만 바꾼다
const TOKEN_RE = /^\d{5,15}:[A-Za-z0-9_-]{30,60}$/;
export const TG_MAX = 50 * 1000 * 1000;   // 봇 API 올리기 한도 50MB(넉넉히 10진)
const DRIVE_SUB = '숏템완성본';

export function readDeliver() {
  try { return JSON.parse(fs.readFileSync(path.join(homeDir(), 'deliver.json'), 'utf8')); } catch { return {}; }
}
function saveDeliver(d) { writeFileIn(homeDir(), 'deliver.json', JSON.stringify(d), 0o600); }

// 화면에 보일 상태(토큰 값은 내보내지 않는다)
export function deliverStatus() {
  const d = readDeliver();
  const t = d.telegram || {};
  const root = driveRoot();
  return { telegram: { linked: !!(t.token && t.chat_id), bot: t.bot || null, waiting: !!(t.token && !t.chat_id), on: t.on !== false },
    drive: { found: !!root, folder: root ? path.join(root, DRIVE_SUB) : null, on: !!(d.drive && d.drive.on) } };
}

// 'Google Drive 데스크톱' 의 내 드라이브 — 윈도: 드라이브 글자 뿌리의 '내 드라이브'/'My Drive' · 맥: ~/Library/CloudStorage/GoogleDrive-*/My Drive
export function driveRoot() {
  if (process.env.SHORTEM_DRIVE_ROOT) return fs.existsSync(process.env.SHORTEM_DRIVE_ROOT) ? process.env.SHORTEM_DRIVE_ROOT : null;   // 시험
  const names = ['내 드라이브', 'My Drive'];
  if (process.platform === 'win32') {
    for (const L of 'GHIJKLMNOPQRSTUVWXYZDEF') {
      for (const n of names) { const p = `${L}:\\${n}`; try { if (fs.statSync(p).isDirectory()) return p; } catch { /* 없음 */ } }
    }
    return null;
  }
  if (process.platform === 'darwin') {
    const cs = path.join(os.homedir(), 'Library', 'CloudStorage');
    let dirs = [];
    try { dirs = fs.readdirSync(cs).filter(n => n.startsWith('GoogleDrive-')); } catch { return null; }
    for (const d of dirs) for (const n of names) { const p = path.join(cs, d, n); try { if (fs.statSync(p).isDirectory()) return p; } catch { /* 없음 */ } }
  }
  return null;
}

async function tg(token, method, body) {
  const r = await fetch(`${TG()}/bot${token}/${method}`, body instanceof FormData ? { method: 'POST', body } : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body || {}) });
  let j = null;
  try { j = await r.json(); } catch { /* 아래 */ }
  if (!j || !j.ok) { const e = new Error((j && j.description) || `텔레그램 응답 ${r.status}`); e.code = 'telegram'; throw e; }
  return j.result;
}

// ① 토큰 받기 → 봇 이름 확인. 고객은 이어서 그 봇에게 아무 말이나 보낸다
export async function linkTelegram(token) {
  const t = String(token || '').trim();
  if (!TOKEN_RE.test(t)) return { ok: false, why: '봇 토큰 모양이 아닙니다 — 텔레그램 @BotFather 가 준 "숫자:글자" 전체를 붙여 넣으세요' };
  let me;
  try { me = await tg(t, 'getMe'); } catch (e) { return { ok: false, why: '이 토큰으로 봇을 찾지 못했습니다: ' + e.message }; }
  const d = readDeliver();
  d.telegram = { token: t, bot: me.username || me.first_name || '', chat_id: null, on: true };
  saveDeliver(d);
  audit('deliver_link', { result: 'telegram_token' });
  return { ok: true, bot: d.telegram.bot, next: `텔레그램에서 @${d.telegram.bot} 을 찾아 "시작"(또는 아무 말)을 보낸 뒤 '확인'을 누르세요` };
}

// ② 봇이 받은 마지막 개인 대화 = 받을 곳
export async function confirmTelegram() {
  const d = readDeliver();
  const t = (d.telegram || {}).token;
  if (!t) return { ok: false, why: '먼저 봇 토큰을 넣으세요' };
  let ups;
  try { ups = await tg(t, 'getUpdates', { limit: 50, allowed_updates: ['message'] }); } catch (e) { return { ok: false, why: e.message }; }
  const m = [...(ups || [])].reverse().map(u => u.message).find(x => x && x.chat && x.chat.type === 'private');
  if (!m) return { ok: false, why: `아직 받은 말이 없습니다 — 텔레그램에서 @${d.telegram.bot} 에게 아무 말이나 보낸 뒤 다시 누르세요` };
  d.telegram.chat_id = m.chat.id;
  saveDeliver(d);
  try { await tg(t, 'sendMessage', { chat_id: m.chat.id, text: '숏템 연결됨 — 완성본이 나오면 여기로 보내 드립니다.' }); } catch { /* 연결은 됐다 */ }
  return { ok: true };
}

export function setDeliver({ telegram, drive } = {}) {
  const d = readDeliver();
  if (typeof telegram === 'boolean' && d.telegram) d.telegram.on = telegram;
  if (typeof drive === 'boolean') d.drive = { on: drive };
  if (telegram === null) delete d.telegram;
  saveDeliver(d);
  return deliverStatus();
}

const sentPath = video => video + '.sent.json';
function readSent(video) { try { return JSON.parse(fs.readFileSync(sentPath(video), 'utf8')); } catch { return {}; } }

// 완성본이 나올 때 부른다(기다리지 않는다 — 완성 응답을 늦추지 않게). 같은 영상이 보내는 중이면 또 걸지 않는다
const inflight = new Set();
export function deliverInBackground(video, opts) {
  if (inflight.has(video)) return;
  inflight.add(video);
  deliverFinal(video, opts).catch(e => audit('deliver', { result: 'error', code: String(e.message || e).slice(0, 80) })).finally(() => inflight.delete(video));
}

// 완성본 한 편 보내기 — 같은 파일(크기·수정 시각)이면 이미 보낸 곳은 건너뛴다. force = 시험 보내기
export async function deliverFinal(video, { title = '', force = false } = {}) {
  const st = fs.statSync(video);
  const stamp = `${st.size}:${Math.floor(st.mtimeMs)}`;
  const prev = readSent(video);
  const done = prev.stamp === stamp && !force ? prev : { stamp };
  const d = readDeliver();
  const out = { telegram: done.telegram || null, drive: done.drive || null };
  const name = path.basename(video);

  if (d.drive && d.drive.on && !(done.drive && done.drive.ok)) {
    const root = driveRoot();
    if (!root) out.drive = { ok: false, why: '구글 드라이브 데스크톱(내 드라이브 폴더)을 찾지 못했습니다' };
    else {
      try {
        const dir = path.join(root, DRIVE_SUB);
        fs.mkdirSync(dir, { recursive: true });
        fs.copyFileSync(video, path.join(dir, name));
        out.drive = { ok: true, at: Date.now() };
      } catch (e) { out.drive = { ok: false, why: String(e.message || e).slice(0, 200) }; }
    }
  }

  const t = d.telegram || {};
  if (t.token && t.chat_id && t.on !== false && !(done.telegram && done.telegram.ok)) {
    const cap = [`🎬 ${title || name}`, out.drive && out.drive.ok ? `구글 드라이브 '${DRIVE_SUB}' 에도 저장했습니다` : ''].filter(Boolean).join('\n').slice(0, 1000);
    try {
      if (st.size <= TG_MAX) {
        const fd = new FormData();
        fd.append('chat_id', String(t.chat_id));
        fd.append('caption', cap);
        fd.append('supports_streaming', 'true');
        fd.append('video', new Blob([fs.readFileSync(video)], { type: 'video/mp4' }), name);
        await tg(t.token, 'sendVideo', fd);
        out.telegram = { ok: true, at: Date.now(), as: 'video' };
      } else {
        await tg(t.token, 'sendMessage', { chat_id: t.chat_id, text: `${cap}\n(영상이 ${Math.round(st.size / 1e6)}MB 라 텔레그램 봇 한도 50MB 를 넘어 파일은 PC 의 숏템작업/완성본 에 있습니다)` });
        out.telegram = { ok: true, at: Date.now(), as: 'notice' };
      }
    } catch (e) { out.telegram = { ok: false, why: String(e.message || e).slice(0, 200) }; }
  }
  try { fs.writeFileSync(sentPath(video), JSON.stringify({ stamp, ...out })); } catch { /* 기록 없이도 보냈다 */ }
  audit('deliver', { result: `tg:${out.telegram ? (out.telegram.ok ? 'ok' : 'fail') : '-'} drive:${out.drive ? (out.drive.ok ? 'ok' : 'fail') : '-'}` });
  return out;
}
