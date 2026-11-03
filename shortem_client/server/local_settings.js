// 내 채널 설정 = PC 로컬 파일 하나(~/.shortem/settings.json, 관제 234 5판 사장님 "저장도 로컬").
//   설정 화면(local_ui)·고객 Claude(shortem_settings)·엔진 제작(make_flow)이 모두 이 파일만 읽고 쓴다 — 판단 주인 한 곳.
//   값 검사는 엔진(preview_request.py check)이 한다. 여기는 깊게 합치고 저장만 한다.
import fs from 'node:fs';
import path from 'node:path';
import { homeDir, writeFileIn, jail } from './paths.js';
import { engineTool } from './engine_bridge.js';
import { api } from './api.js';
import { keyStatus } from './engine/voice.js';

const FILE = 'settings.json';
export const PID_RE = /^p_[0-9a-f]{10}$/;

export function readSettings() {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), FILE), 'utf8')); } catch { return { current: null, channels: {} }; }
}
const writeSettings = s => writeFileIn(homeDir(), FILE, JSON.stringify(s, null, 1));   // 임시 파일→이름 바꾸기(화면·Claude 가 동시에 써도 반쯤 쓴 파일을 안 읽는다)

let catCache = null;
export async function catalog() {
  if (catCache) return catCache;
  const r = await engineTool('catalog');
  if (r.error) throw new Error(r.error);
  catCache = r.catalog;
  return catCache;
}

export function useCatalog(c) { catCache = c; }   // 시험용 — 엔진을 띄우지 않고 표를 넣는다

function merge(base, over) {
  if (Array.isArray(over) || over === null || typeof over !== 'object') return over;
  const out = { ...(base && typeof base === 'object' && !Array.isArray(base) ? base : {}) };
  for (const [k, v] of Object.entries(over)) out[k] = merge(out[k], v);
  return out;
}

// ★기본값은 그 프리셋의 원본 영상에 맞춘다 — 모든 프리셋(사장님 10-20). 엔진 기본 팩 ← 프리셋 기본값(엔진 preview_request.preset_defaults 가
//   빌드 때 만든 표) ← 회원이 바꾼 칸. 회원이 안 바꾼 칸은 프리셋 값을 따른다(프리셋 기본값이 바뀌면 같이 바뀐다)
export async function packFor(pid) {
  const s = readSettings();
  const own = (s.channels[pid] || {}).pack;
  const cat = await catalog();
  return merge(merge(cat.default_pack, (cat.preset_defaults || {})[pid] || {}), own || {});
}

// patch 를 합쳐 검사 → 통과하면 저장. 반환 {ok, pack} 또는 {ok:false, errors}
export async function savePack(pid, patch, { select = true } = {}) {
  if (!PID_RE.test(String(pid || ''))) return { ok: false, errors: ['프리셋 id 모양이 아닙니다'] };
  const pack = merge(await packFor(pid), patch || {});
  const r = await engineTool('check', { pack });
  if (r.error) return { ok: false, errors: [r.error] };
  if (r.errors.length) return { ok: false, errors: r.errors };
  const s = readSettings();
  const prev = (s.channels[pid] || {}).pack || {};
  s.channels[pid] = { pack: merge(prev, patch || {}), updated: Date.now() };   // 고객이 바꾼 칸만 남긴다(기본값이 바뀌면 따라간다)
  if (select) { s.current = pid; s.current_at = Date.now(); }
  writeSettings(s);
  return { ok: true, pack };
}

export function select(pid) {
  if (!PID_RE.test(String(pid || ''))) return false;
  const s = readSettings();
  s.current = pid; s.current_at = Date.now();
  writeSettings(s);
  return true;
}

// 기본값으로 — 지우지 않고 빈 칸 + 시각(서버·다른 화면과 맞출 때 '되돌림'도 최근 것으로 전해지게, 관제 266)
export function resetPack(pid) {
  const s = readSettings();
  s.channels[pid] = { pack: {}, updated: Date.now() };
  writeSettings(s);
}

// 서버 '내 채널 설정'(웹 /claude/studio)과 맞추기(관제 266) — 이 PC 설정을 보내고, 서버가 합친 결과(프리셋마다 더 최근 것)를 그대로 쓴다.
//   합치는 판단은 서버 claude_studio.sync_merge 한 곳. 서버에 못 닿으면(키 없음·오프라인) 이 PC 설정 그대로 간다.
// 받은 결과에 합칠 때도 서버 sync_merge 와 같은 규칙(프리셋마다 더 최근에 바꾼 쪽) — 서버 저장 관문이 이 PC 칸을 거절하면(서버 엔진이 아직 모르는 칸
//   caption_scale·name_style 등, 관문 차이) 서버는 옛 칸을 돌려준다. 그대로 쓰면 회원이 방금 바꾼 칸이 사라졌다(#1958 이성택·#1041 최일환 목소리 되돌아감).
export function mergeChannels(server, local) {
  const out = { ...(server || {}) };
  for (const [pid, ch] of Object.entries(local || {})) {
    if (!out[pid] || Number((ch || {}).updated || 0) > Number(out[pid].updated || 0)) out[pid] = ch;
  }
  return out;
}

let lastSync = 0;
export async function syncFromServer({ force = false } = {}) {
  if (!force && Date.now() - lastSync < 30000) return { skipped: true };
  lastSync = Date.now();
  const s = readSettings();
  let r;
  try { r = await api.studio({ current: s.current || null, current_at: s.current_at || 0, channels: s.channels || {} }); }
  catch (e) { return { ok: false, why: (e && e.code) || 'network' }; }
  const got = (r && r.settings) || null;
  if (!got || typeof got.channels !== 'object') return { ok: false, why: 'bad_reply' };
  // 꾸민 모양(looks) = 이 PC 저장(saveLook, 사장님 11-01 '로컬로') + 웹에서 꾸민 프리셋은 받아 온다
  const next = { ...s, current: got.current || s.current || null, current_at: got.current_at || 0, channels: mergeChannels(got.channels, s.channels),
    looks: { ...((got.looks && typeof got.looks === 'object') ? got.looks : {}), ...(s.looks || {}) } };   // 이 PC 에서 꾸민 것이 먼저
  if (JSON.stringify(next) !== JSON.stringify(s)) writeSettings(next);
  return { ok: true };
}

// 완성본 고치기 지시함(이 PC) — Claude 는 shortem_inbox 로 읽고 처리한다
export function addRequest(target, text) {
  const t = String(text || '').trim().slice(0, 4000);
  if (!t || !target || typeof target !== 'object') return { ok: false, error: '지시 내용을 받지 못했습니다' };
  const s = readSettings();
  const q = { id: `l_${Date.now().toString(36)}`, at: Date.now(), state: '대기', target, text: t };
  s.requests = [...(s.requests || []), q].slice(-100);
  writeSettings(s);
  return { ok: true, request: q };
}
export function setRequest(id, state, note) {
  const s = readSettings();
  const q = (s.requests || []).find(x => x.id === id);
  if (!q) return null;
  q.state = state; q.note = String(note || '').slice(0, 1000);
  writeSettings(s);
  return q;
}

// 그림 로고 저장 — packs 옆 logos/<pid>.png (렌더는 styles.member_frame 이 같은 자리를 읽는다)
export function saveLogo(pid, dataUrl) {
  const m = /^data:image\/png;base64,([A-Za-z0-9+/=]+)$/.exec(String(dataUrl || ''));
  if (!PID_RE.test(String(pid || '')) || !m) return { ok: false, error: 'PNG 그림만 올릴 수 있습니다' };
  writeFileIn(homeDir(), path.join('logos', `${pid}.png`), Buffer.from(m[1], 'base64'));
  return { ok: true, file: `${pid}.png` };
}

// 꾸민 모양 저장 — 검사는 엔진 한 곳(워커 'look' = scene_style.validate_snapshot), 서버 save_look 과 같은 검사
const LOOK_MAX = 400000;
export async function saveLook(pid, snapshot) {
  if (!PID_RE.test(String(pid || '')) || !snapshot || typeof snapshot !== 'object') return { ok: false, error: '꾸민 모양을 받지 못했습니다' };
  if (JSON.stringify(snapshot).length > LOOK_MAX) return { ok: false, error: '꾸민 모양이 너무 큽니다' };
  const r = await engineTool('look', { snapshot });
  if (r.error || r.invalid) return { ok: false, error: r.invalid || r.error };
  const s = readSettings();
  s.looks = { ...(s.looks || {}), [pid]: { snapshot: r.snapshot, updated: Date.now() } };
  writeSettings(s);
  return { ok: true };
}

// 목소리 회사 — 엔진 voices.provider_of 와 같은 판단(CS #142). 모르면 null
export function providerOf(t) {
  const v = String((t || {}).voice_id || '');
  const p = (t || {}).provider;
  return ({ fishaudio: 'fish', fish_audio: 'fish', eleven: 'elevenlabs' })[p] || p || (v.startsWith('tc_') ? 'typecast' : v.startsWith('kr-') ? 'elevenlabs' : v.startsWith('fs-') ? 'fish' : null);
}

const VOICE_KEYS = ['voice_id', 'name', 'provider', 'preset_id', 'emotion'];
export const VOICE_SERVICES = ['typecast', 'elevenlabs', 'fish'];      // 목소리 키는 이 셋 중 하나면 된다(사장님 11-03)
// 프리셋 목소리 회사 키가 없을 때 그 회사 기본 성우(사장님 11-03): 일레븐 = 미나·표현(숏템메이커 typecast_tts.FALLBACK_VOICE) ·
//   피쉬 = 추천 여자 성우 일반여성2(voice_presets fs-ilban2-stable — 사장님 11-03 지정). 타입캐스트 = 프리셋에 세팅한 성우
//   (숏템메이커 기본 필재는 숏클에서 금지 — engine/voices 사장님 10-20). 타입캐스트가 아닌 프리셋에서 타입캐스트 키만 있으면 썰템쇼 프리셋 성우(박창수).
export const DEFAULT_VOICES = {
  elevenlabs: { voice_id: 'kr-mina-expressive', name: '미나', provider: 'elevenlabs' },
  fish: { voice_id: 'fs-ilban2-stable', name: '일반여성2', provider: 'fish' },
  typecast: { voice_id: 'tc_6059dad0b83880769a50502f', name: '박창수', provider: 'typecast' },
};
// (판단 주인 — 이 프리셋에서 엔진이 쓸 회원 목소리 칸) 순서:
//   ① 회원이 이 프리셋 목소리를 정했으면 그대로(설정 화면 소리 단계·shortem_settings — 회원 요청이 이긴다)
//   ② 프리셋 목소리 회사 키가 있으면 프리셋 목소리(사장님이 세팅한 기본값)
//   ③ 회원이 다른 프리셋에서 고른 목소리 중 키가 있는 것(지금 채널 먼저) — #1186·#953·#1846
//   ④ 키가 있는 회사의 기본 성우(DEFAULT_VOICES, 일레븐 → 피쉬 → 타입캐스트) — 처음 세팅에 일레븐 키만 있는 회원(사장님 11-03 '셋 중 하나만')
//   반환 = 팩 member.tts 에 넣을 칸(빈 객체 = 프리셋 목소리). hasKey(회사) 는 키 파일 판정(engine/voice.keyStatus).
export function memberVoice(settings, pid, presetTts, hasKey) {
  const ch = (settings || {}).channels || {};
  const own = ((ch[pid] || {}).pack || {}).tts || {};
  if (own.voice_id) return own;
  if (hasKey(providerOf(presetTts) || 'typecast')) return own;
  const other = [(settings || {}).current, ...Object.keys(ch)].filter(p => p && p !== pid)
    .map(p => ((ch[p] || {}).pack || {}).tts).find(t => t && t.voice_id && hasKey(providerOf(t)));
  const pick = other || DEFAULT_VOICES[['elevenlabs', 'fish', 'typecast'].find(k => hasKey(k))];
  return pick ? { ...Object.fromEntries(VOICE_KEYS.filter(k => pick[k] != null).map(k => [k, pick[k]])), ...own } : own;
}

// 지금 채널에서 엔진이 실제로 쓸 목소리 {voice_id, provider…} — 시작 점검(키·목소리 시험·일레븐 요금제)이 이것 하나만 본다(엔진 팩 packFile 과 같은 memberVoice).
//   채널을 안 골랐으면 키가 있는 회사 기본 성우, 키도 없으면 null.
export async function engineVoice(hasKey = s => keyStatus(s).present, settings = readSettings()) {
  const pid = (settings || {}).current;
  let presetTts = null;
  if (pid) { try { presetTts = (await packFor(pid)).tts || null; } catch { /* 프리셋 표 못 읽음 */ } }
  const t = pid ? memberVoice(settings, pid, presetTts, hasKey) : {};
  if (t.voice_id) return t;
  if (presetTts && presetTts.voice_id) return presetTts;
  return DEFAULT_VOICES[['elevenlabs', 'fish', 'typecast'].find(k => hasKey(k))] || null;
}

// 시작 점검이 볼 목소리 회사 — 지금 채널에서 엔진이 쓸 목소리(memberVoice)의 회사. 프리셋 목소리를 모르면(채널 안 고름) null = 셋 중 아무 키
export function voiceServiceFor(settings, presetTts, hasKey) {
  const pid = (settings || {}).current;
  if (!pid) return null;
  const t = memberVoice(settings, pid, presetTts, hasKey);
  return providerOf(t.voice_id ? t : presetTts) || null;
}

// 엔진 팩 파일(~/.shortem/packs/<pid>.json = {"1": 합친 팩}) — 만들 때마다 지금 설정으로 새로 쓴다(웹에서 바꾼 것도 먼저 받는다)
export async function packFile(pid, { hasKey = s => keyStatus(s).present } = {}) {
  await syncFromServer({ force: true });
  const rel = path.join('packs', `${pid}.json`);
  const st = readSettings();
  const web = { look: ((st.looks || {})[pid] || {}).snapshot || null };   // 엔진이 읽는 웹 설정(꾸민 모양) — 팩 검사 밖 칸. 감정은 팩 tts.emotion
  const full = await packFor(pid);
  const member = { ...((st.channels[pid] || {}).pack || {}) };      // member = 회원이 바꾼 칸만(엔진 styles.member_frame) — 기본값이 판을 덮지 않게
  const tts = memberVoice(st, pid, full.tts, hasKey);
  if (Object.keys(tts).length) member.tts = tts;
  writeFileIn(homeDir(), rel, JSON.stringify({ 1: tts.voice_id ? { ...full, tts: { ...full.tts, ...tts } } : full, member, web }));
  return path.join(homeDir(), rel);
}
