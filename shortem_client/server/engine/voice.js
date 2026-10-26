// 음성 — 고객 키(~/.shortem/keys/typecast, 값만 0600)로 타입캐스트 합성. 우리 서버는 키를 받지도 저장하지도 않는다.
//   API 모양 = shopping_shorts/typecast_tts.py(build_payload·synthesize)와 같다: POST /v1/text-to-speech/with-timestamps
//   (403·404 면 /v1/text-to-speech 한 번 더), 헤더 X-API-KEY, 본문 {voice_id,text,model,language,output:{audio_format,audio_tempo}}.
//   일 상한(편 수) · 줄 캐시(같은 글·목소리·빠르기면 다시 안 부른다) · 앞뒤 무음 자르기.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { homeDir, jail, writeFileIn } from '../paths.js';
import { runOk } from '../tools_paths.js';
import { probe } from './analyze.js';
import { keyPrint } from '../license.js';

const TC_TS = 'https://api.typecast.ai/v1/text-to-speech/with-timestamps';
const TC = 'https://api.typecast.ai/v1/text-to-speech';
export const DAILY_JOBS = () => Number(process.env.SHORTEM_TTS_DAILY || 10);

export function keyFile(service = 'typecast') {
  if (!/^[a-z0-9_]{2,20}$/.test(service)) throw new Error('잘못된 서비스 이름');
  return jail(homeDir(), 'keys/' + service);
}

export function readKey(service = 'typecast') {
  try { return fs.readFileSync(keyFile(service), 'utf8').trim(); } catch { return ''; }
}

// 회원이 넣는 키 목록 — 판단 한 곳(설정 화면·저장·엔진 환경변수가 이 표만 본다). 사장님 10-21: 미나 = 회원 일레븐랩스 키 · 쿠팡 = 회원 파트너스 키(없으면 회원 PC 크롬)
export const KEY_SERVICES = Object.freeze({
  typecast: { label: '목소리 키(타입캐스트)', where: 'typecast.ai ▸ 개발자 ▸ API 키', env: 'TYPECAST_API_KEY', need: '없으면 타입캐스트 목소리를 만들 수 없습니다' },
  elevenlabs: { label: '목소리 키(일레븐랩스)', where: 'elevenlabs.io ▸ 프로필 ▸ API Keys', env: 'ELEVENLABS_API_KEY', need: '미나 목소리 프리셋에 필요합니다' },
  fish: { label: '목소리 키(피쉬오디오)', where: 'fish.audio ▸ API ▸ API Keys', env: 'FISH_API_KEY', need: '피쉬오디오 목소리를 고르면 필요합니다' },
  coupang_access: { label: '쿠팡 파트너스 Access Key', where: '쿠팡 파트너스 ▸ 추가기능 ▸ 오픈API', env: 'COUPANG_ACCESS_KEY', need: '없으면 이 PC 크롬 창으로 쿠팡을 찾습니다' },
  coupang_secret: { label: '쿠팡 파트너스 Secret Key', where: '쿠팡 파트너스 ▸ 추가기능 ▸ 오픈API', env: 'COUPANG_SECRET_KEY', need: 'Access Key 와 짝으로 넣습니다' },
  vmake: { label: '자막 지우기 키(VMake)', where: 'VMake 개발자 화면 ▸ App Key 와 Secret 을 app_key:secret 꼴로', env: 'VMAKE_API_KEY', need: '원본 영상에 박힌 자막을 지울 때 필요합니다(엔진 vmake_clean — 없으면 그 단계에서 멈춥니다)' },
  vertex_sa: { label: '버텍스 AI 서비스 계정(JSON)', where: '구글 클라우드 ▸ IAM ▸ 서비스 계정 ▸ 키 ▸ JSON 내려받기(역할 Vertex AI User)', env: 'GOOGLE_APPLICATION_CREDENTIALS', file: true, json: true, need: 'AI 영상(Veo)·사진(Imagen)을 만들 때 씁니다 — 숏템메이커에 등록한 것을 그대로 가져올 수 있습니다' },
  speechmatics: { label: '받아쓰기 키(스피치매틱스)', where: 'speechmatics.com ▸ Settings ▸ API Keys', env: 'SPEECHMATICS_API_KEY', need: '있으면 원음·완성본 받아쓰기를 두 모델로 대조합니다(없으면 위스퍼만)' },
});

// 고객이 설정 화면에서 넣는 키(관제 234, 10-20: 키 넣는 화면이 없어 고객이 파일을 직접 만들어야 했다) — 값은 파일에만(0600), 응답엔 지문만
export function saveKey(service, value) {
  const svc = KEY_SERVICES[service];
  if (!svc) return { ok: false, why: '모르는 키입니다' };
  const k = String(value || '').trim();
  if (svc.json) {                                         // 버텍스 서비스 계정 = JSON 파일 통째(숏템메이커 vertex_route.validate_sa 와 같은 검사)
    let j = null;
    try { j = JSON.parse(k); } catch { return { ok: false, why: 'JSON 형식이 아닙니다 — 내려받은 키 파일(.json) 내용을 통째로 붙여 넣으세요' }; }
    if (k.length > 20000 || !j || j.type !== 'service_account') return { ok: false, why: '서비스 계정 키가 아닙니다(type 이 service_account 여야 합니다)' };
    for (const f of ['project_id', 'client_email', 'private_key']) if (!String(j[f] || '').trim()) return { ok: false, why: `키 파일에 ${f} 가 없습니다 — 다시 내려받아 주세요` };
    if (!j.private_key.includes('BEGIN PRIVATE KEY')) return { ok: false, why: 'private_key 모양이 이상합니다 — 파일 전체를 그대로 붙여 넣으세요' };
    writeFileIn(homeDir(), 'keys/' + service, k, 0o600);
    return { ok: true, ...keyStatus(service) };
  }
  if (k.length < 16 || k.length > 300 || /\s/.test(k)) return { ok: false, why: `키 모양이 아닙니다 — ${svc.where} 의 키 전체를 붙여 넣으세요` };
  writeFileIn(homeDir(), 'keys/' + service, k, 0o600);
  return { ok: true, ...keyStatus(service) };
}

export function keyStatus(service = 'typecast') {
  const k = readKey(service);
  if (!k) return { present: false };
  if ((KEY_SERVICES[service] || {}).json) { try { const j = JSON.parse(k); return { present: true, fp: `${j.project_id} · ${String(j.client_email || '').split('@')[0].slice(0, 4)}…` }; } catch { /* 아래 */ } }
  return { present: true, fp: keyPrint(k) };
}

// 화면용 — 키마다 이름·어디서 받나·지문(값은 없다)
export const keyStatuses = () => Object.fromEntries(Object.entries(KEY_SERVICES).map(([s, v]) => [s, { label: v.label, where: v.where, need: v.need, json: !!v.json, ...keyStatus(s) }]));
// 엔진 환경변수 — 넣은 키만(값은 출력하지 않는다)
// 파일로 쓰는 키(버텍스 서비스 계정)는 값 대신 파일 경로를 넘긴다(구글 라이브러리 GOOGLE_APPLICATION_CREDENTIALS 꼴)
export const keyEnv = () => Object.fromEntries(Object.entries(KEY_SERVICES).map(([s, v]) => [v.env, readKey(s) ? (v.file ? keyFile(s) : readKey(s)) : '']).filter(([, k]) => k));

function usage() {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), 'usage.json'), 'utf8')); } catch { return {}; }
}

// 오늘 이 job 으로 합성을 써도 되나(편 단위). 같은 job 재시도는 한 번만 센다.
export function claimDaily(jobId, now = new Date()) {
  const day = now.toISOString().slice(0, 10);
  const u = usage();
  const today = u.day === day ? u : { day, jobs: [] };
  if (today.jobs.includes(jobId)) return true;
  if (today.jobs.length >= DAILY_JOBS()) return false;
  today.jobs.push(jobId);
  writeFileIn(homeDir(), 'usage.json', JSON.stringify(today));
  return true;
}

async function post(url, key, body) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), 120000);
  try {
    return await fetch(url, { method: 'POST', headers: { 'X-API-KEY': key, 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: ctl.signal });
  } finally { clearTimeout(t); }
}

// 목소리 프리셋 이름 → 타입캐스트 voice_id(shopping_shorts/calcopy_frame/my_packs.json 에 적힌 4개). 서버가 voice_id 를 주면 그것이 우선.
const PRESET_VOICES = { 'tc-piljae-stable': 'tc_68257f68bc6e3c161ab5078d', 'tc-gunn-stable': 'tc_61c2f7741330d213c238cba6', 'tc-changsu-stable': 'tc_6059dad0b83880769a50502f', 'tc-yongsik-stable': 'tc_5feb2085cca1a479e73bac37' };
export function voiceIdOf(tts) {
  if (!tts) return null;
  if (typeof tts.voice_id === 'string' && /^tc_[0-9a-f]{8,}$/.test(tts.voice_id)) return tts.voice_id;
  if (typeof tts.voice === 'string' && /^tc_[0-9a-f]{8,}$/.test(tts.voice)) return tts.voice;
  return PRESET_VOICES[tts.voice || tts.preset_id] || null;
}

export class VoiceError extends Error {
  constructor(why, fix, retry = true) { super(why); this.why = why; this.fix = fix; this.retry = retry; this.code = 'voice'; }
}

async function synthOne(key, text, { voiceId, tempo, model }, outFile) {
  const body = { voice_id: voiceId, text, model: model || 'ssfm-v30', language: 'kor', output: { audio_format: 'mp3', ...(tempo ? { audio_tempo: Math.max(0.5, Math.min(2, tempo)) } : {}) } };
  let r;
  try { r = await post(TC_TS, key, body); } catch { throw new VoiceError('음성 서비스에 연결하지 못했습니다', '인터넷 연결을 확인하고 다시 시도하세요'); }
  let align = null, audio = null;
  if (r.status === 403 || r.status === 404) {
    try { r = await post(TC, key, body); } catch { throw new VoiceError('음성 서비스에 연결하지 못했습니다', '인터넷 연결을 확인하고 다시 시도하세요'); }
  } else if (r.ok) {
    const j = await r.json().catch(() => null);
    if (!j || !j.audio) throw new VoiceError('음성 응답이 비어 있습니다', '잠시 뒤 다시 시도하세요');
    audio = Buffer.from(j.audio, 'base64');
    if (Array.isArray(j.characters) && j.characters.length) align = { starts: j.characters.map(c => Number(c.start) || 0), ends: j.characters.map(c => Number(c.end) || 0) };
  }
  if (!audio) {
    if (r.status === 401) throw new VoiceError('타입캐스트 키가 맞지 않습니다', 'typecast.ai 개발자 화면에서 키를 확인해 ~/.shortem/keys/typecast 에 다시 넣으세요', false);
    if (r.status === 402) throw new VoiceError('타입캐스트 크레딧이 부족합니다', 'typecast.ai 에서 충전한 뒤 다시 시도하세요', false);
    if (r.status === 404) throw new VoiceError('고른 목소리를 찾지 못했습니다', '숏템 페이지에서 내 채널 목소리를 다시 골라 주세요', false);
    if (!r.ok) throw new VoiceError('음성을 만들지 못했습니다', '잠시 뒤 다시 시도하세요');
    const ct = r.headers.get('content-type') || '';
    if (ct.includes('json')) { const j = await r.json().catch(() => null); if (j && j.audio) audio = Buffer.from(j.audio, 'base64'); }
    else audio = Buffer.from(await r.arrayBuffer());
    if (!audio || !audio.length) throw new VoiceError('음성 응답이 비어 있습니다', '잠시 뒤 다시 시도하세요');
  }
  fs.writeFileSync(outFile, audio);
  return align;
}

// 앞뒤 무음 자르기 + 문장 안 긴 쉼 줄이기(copy_render._trim 과 같은 값) → wav
async function trim(src, dst) {
  const f = 'silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.02';
  const mid = 'silenceremove=stop_periods=-1:stop_duration=0.1:stop_threshold=-45dB:stop_silence=0.05';
  await runOk('ffmpeg', ['-v', 'error', '-y', '-i', src, '-af', `${f},areverse,${f},areverse,${mid}`, '-ar', '44100', '-ac', '1', dst], { timeoutMs: 120000 });
}

// lines = [문장…], tts = {voice_id, tempo, model}. 반환 [{file, dur, align}]
export async function synthLines(lines, tts, dir, { jobId } = {}) {
  const key = readKey('typecast');
  if (!key) throw new VoiceError('타입캐스트 키가 없습니다', '~/.shortem/keys/typecast 파일에 내 키를 넣어 주세요(숏템 페이지 안내)', false);
  const voiceId = voiceIdOf(tts);
  if (!voiceId) throw new VoiceError('내 채널 목소리가 정해지지 않았습니다', '숏템 페이지에서 내 채널 목소리를 골라 주세요', false);
  if (jobId && !claimDaily(jobId)) throw new VoiceError('오늘 음성 만들기 횟수를 다 썼습니다', '내일 다시 하거나 설정에서 하루 횟수를 늘려 주세요', false);
  fs.mkdirSync(dir, { recursive: true });
  const out = [];
  for (const text of lines) {
    const h = crypto.createHash('sha256').update([voiceId, tts.tempo || '', tts.model || '', text].join('|')).digest('hex').slice(0, 20);
    const mp3 = path.join(dir, h + '.mp3'), wav = path.join(dir, h + '.wav'), al = path.join(dir, h + '.align.json');
    if (!fs.existsSync(wav)) {
      const align = await synthOne(key, text, { voiceId, tempo: tts.tempo, model: tts.model }, mp3);
      if (align) fs.writeFileSync(al, JSON.stringify(align));
      await trim(mp3, wav);
    }
    let align = null;
    try { align = JSON.parse(fs.readFileSync(al, 'utf8')); } catch { /* 없음 */ }
    const p = await probe(wav);
    // 무음을 자르면 글자 시각이 앞당겨진다 — 비율로 맞춘다
    if (align && align.ends.length) {
      const s0 = align.starts[0] || 0, end = align.ends[align.ends.length - 1] || p.duration;
      const k = end > s0 ? p.duration / (end - s0) : 1;
      align = { starts: align.starts.map(x => Math.max(0, (x - s0) * k)), ends: align.ends.map(x => Math.max(0, (x - s0) * k)) };
    }
    out.push({ file: wav, dur: p.duration, align });
  }
  return out;
}
