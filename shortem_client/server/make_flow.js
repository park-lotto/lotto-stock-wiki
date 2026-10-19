// 숏폼 만들기 흐름(관제 234 5판) — 프리셋 고르기 → 후보 소재 → 고객 사인 → 완성.
//   단계 판단은 엔진(calcopy_make) 한 곳. 여기는 엔진 세션 JSON 을 Claude 가 따라 하기 쉬운 꼴(need·다음 할 일)로 옮기기만 한다.
//   하이쿠도 따라오게: 응답마다 need 하나와 그 need 에 맞는 도구 호출 한 줄(next)을 준다.
import fs from 'node:fs';
import path from 'node:path';
import { startRun, waitRun, getRun, activeRuns, pending, SID_RE, dataDir, engineRoot } from './engine_bridge.js';
import { rentPreset } from './preset_rent.js';
import { refreshCookies } from './logins.js';
import { packFile as localPackFile, PID_RE } from './local_settings.js';
import { homeDir, writeFileIn, workDir, ensureDir } from './paths.js';

export const waitMs = () => Number(process.env.SHORTEM_WAIT_SEC || 45) * 1000;

function aiNeed(runId) {
  const n = pending().length;
  return { need: 'ai', ai_requests: n, run_id: runId,
    next: `shortem_ai(action="list") 로 요청을 받아 하나씩 답한 뒤(answer), shortem_make(step="wait", run_id="${runId}") 를 부르세요`,
    hints: [`엔진이 AI 판독 ${n}건을 기다립니다 — 사람에게 묻지 말고 바로 답하세요`] };
}

const cand = c => ({ n: c.n, title: c.title, total: c.total, line: c.line, scores: c.scores, made: c.made || 0 });

// 엔진 세션 → 응답
export function shapeSession(S) {
  if (!S || S.error) return { fail: { why: (S && S.error) || '엔진이 답하지 않았습니다', code: S && S.code, fix: '같은 단계를 한 번 더 부르세요. 또 실패하면 shortem_feedback 으로 알려 주세요' } };
  const base = { sid: S.sid, state: S.state, preset: S.preset };
  if (S.state === 'candidates') {
    const c = (S.candidates || []).map(cand);
    if (!c.length) return { ...base, need: 'retry', hints: ['점수가 난 후보가 없습니다 — 잠시 뒤 shortem_make(step="start") 를 다시 부르면 소재를 더 찾습니다'] };
    return { ...base, need: 'choose', candidates: c,
      next: `고객에게 후보를 보여 주고 고른 번호로 shortem_make(step="choose", sid="${S.sid}", n=<번호>)`,
      hints: ['후보를 표로 보여 주고 고객이 번호를 고르게 하세요(대신 고르지 마세요)'] };
  }
  const t = S.topic || {};
  if (S.state === 'failed' || S.state === 'stopped') return { ...base, fail: { why: S.error || `엔진이 ${t.state || S.state} 에서 멈췄습니다`, fix: '같은 단계를 다시 부르거나 다른 후보를 고르세요' } };
  if ((t.state || '') === 'plan_review') {
    const files = (S.files || []).map(f => f.name);
    return { ...base, need: 'approve', plan_files: files,
      next: `고객에게 대본·계획을 보여 주고 사인을 받으면 shortem_make(step="approve", sid="${S.sid}")`,
      hints: ['사인 전에는 목소리 합성·렌더를 하지 않습니다(고객 키 비용)'] };
  }
  if ((t.state || '') === 'final_review' || S.state === 'final_review') {
    // 완성본 = 엔진 소재 폴더(창고/calcopy/topics/<id>/final.mp4) → 고객이 보는 작업 폴더(바탕화면 숏템작업)에 한 벌 복사
    const src = S.topic_id != null ? path.join(dataDir(), 'calcopy', 'topics', String(S.topic_id), 'final.mp4') : null;
    let video = null;
    if (src && fs.existsSync(src)) {
      const name = `${String((t.name || 'shortem')).replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40)}_${S.sid}.mp4`;
      video = path.join(ensureDir(workDir(), '완성본'), name);
      if (!fs.existsSync(video) || fs.statSync(src).mtimeMs > fs.statSync(video).mtimeMs) fs.copyFileSync(src, video);   // 다시 만들기(restyle) 뒤엔 새 완성본으로
      try { fs.writeFileSync(video + '.json', JSON.stringify({ sid: S.sid, title: String(t.name || ''), preset: S.preset_id || null, topic_dir: path.dirname(src) })); } catch { /* 표식 없이도 영상은 본다 */ }
    }
    if (!video) return { ...base, fail: { why: '완성본 파일을 찾지 못했습니다', fix: 'shortem_make(step="status") 로 다시 보세요' } };
    return { ...base, need: 'done', video, hints: ['완성본 경로를 고객에게 알려 주세요(파일을 열어 보라고 안내)', `겉모습을 바꾸고 싶다고 하면 shortem_settings 로 바꾼 뒤 shortem_make(step="restyle", sid="${S.sid}") — 대본·재료는 그대로, 렌더만 다시`] };
  }
  return { ...base, need: 'wait', topic_state: t.state, next: `shortem_make(step="status", sid="${S.sid}")` };
}

// 프리셋 → 엔진 팩 파일 — 내용은 PC 로컬 설정(local_settings, 설정 화면·Claude 가 같이 고친 것) 한 곳
export async function packFileFor(presetId) {
  if (process.env.SHORTEM_DEV_PACK) return process.env.SHORTEM_DEV_PACK;
  return PID_RE.test(String(presetId || '')) ? localPackFile(presetId) : null;
}

const RENT_FAIL = { not_entitled: '이 프리셋은 지금 등급으로 쓸 수 없습니다 — 숏템 웹에서 등급을 확인하세요',
  not_ready: '이 프리셋을 지금 준비할 수 없습니다 — 잠시 뒤 다시 부르세요', busy: '앞 작업이 끝난 뒤 다시 부르세요',
  lease_lost: '작업 권한을 받지 못했습니다 — 다른 PC 에서 쓰는 중인지 확인하세요', no_key: '라이선스 키가 없습니다 — 숏템 설치를 다시 확인하세요' };

// 프리셋이 필요한 단계(start·choose·approve)는 그 편 동안만 서버에서 빌린다 — 판단은 서버(claude_portal.preset_rent)
async function go(args, opts, presetId) {
  if (presetId && !process.env.SHORTEM_DEV_PACK) {
    let rental;
    try { rental = await rentPreset({ engineRoot: engineRoot(), presetId }); }
    catch (e) { return { fail: { why: RENT_FAIL[e.code] || '프리셋을 받지 못했습니다', code: e.code || 'rent', fix: '잠시 뒤 같은 단계를 다시 부르세요' } }; }
    if (rental.presetPath && args[0] === 'start') args = args.map((a, i) => (args[i - 1] === '--preset' ? rental.presetPath : a));
    if (rental.dev && args.includes('rented')) return { fail: { why: '개발 PC 입니다 — SHORTEM_DEV_PRESET 에 엔진 프리셋 경로를 주세요', code: 'dev_preset' } };
    opts = { ...opts, onClose: rental.release };
  }
  if (['start', 'choose', 'approve', 'restyle'].includes(args[0])) await refreshCookies();   // 받기 전 최신 로그인 쿠키(유튜브 세션은 자주 돈다)
  const r = startRun(args, opts);
  const out = await waitRun(r, waitMs());
  if (out) return shapeSession(out);
  return r.done ? shapeSession({ error: '엔진 결과 없음' }) : aiNeed(r.runId);
}

const YT_CHANNEL = /^https:\/\/(www\.)?youtube\.com\/(@[^/?#]{1,80}|channel\/UC[0-9A-Za-z_-]{22})\/?$/;
const VIDEO = /^https:\/\/(www\.)?(youtube\.com\/(shorts\/|watch\?v=)[0-9A-Za-z_-]{11}|youtu\.be\/[0-9A-Za-z_-]{11}|tiktok\.com\/@[^/]{1,60}\/video\/[0-9]{8,25}|instagram\.com\/(reel|p)\/[0-9A-Za-z_-]{5,40})/;

// 고객이 준 해외 원본 채널 → 엔진이 읽는 원본 채널 목록 파일(~/.shortem/원본채널.json, 고객 채널만)
function originalsFile(channel) {
  const rel = '원본채널.json';
  writeFileIn(homeDir(), rel, JSON.stringify({ note: '고객이 준 해외 원본 채널(관제 234)', channels: [{ platform: 'youtube', url: channel }] }));
  return path.join(homeDir(), rel);
}

export async function makeStep({ step, sid, n, run_id, preset, topic, channel, video }) {
  if (step === 'wait') {
    const r = getRun(run_id) || activeRuns()[0];
    if (!r) return { hints: ['기다릴 작업이 없습니다 — shortem_make(step="status", sid=…) 로 보세요'] };
    const out = await waitRun(r, waitMs());
    return out ? shapeSession(out) : (r.done ? shapeSession({ error: '엔진 결과 없음' }) : aiNeed(r.runId));
  }
  if (step === 'start') {
    if (!preset) return { hints: ['고른 프리셋이 없습니다 — shortem_settings(action="open") 으로 설정 화면을 열어 프리셋을 고르세요'] };
    const devPath = process.env.SHORTEM_DEV_PRESET || '';   // 개발 PC: 빌리지 않고 엔진 폴더의 프리셋을 쓴다
    if (channel && !YT_CHANNEL.test(channel)) return { hints: ['채널 주소는 https://www.youtube.com/@이름 또는 /channel/UC… 꼴이어야 합니다(틱톡·인스타 채널은 아직 못 엽니다 — 영상 주소를 주세요)'] };
    if (video && !VIDEO.test(video)) return { hints: ['영상 주소는 유튜브 쇼츠·틱톡 영상·인스타 릴스 주소여야 합니다'] };
    const args = ['start', '--preset', devPath || 'rented', '--pack', '1',
      ...(topic ? ['--topic', String(topic).slice(0, 200)] : []), ...(video ? ['--ref', video] : [])];
    return go(args, { packFile: await packFileFor(preset), env: channel ? { CALCOPY_ORIGINALS_FILE: originalsFile(channel) } : {} }, devPath ? null : preset);
  }
  if (!SID_RE.test(String(sid || ''))) return { hints: ['sid 가 필요합니다(start 응답의 sid)'] };
  if (step === 'choose') {
    if (!Number.isInteger(n) || n < 1) return { hints: ['고른 후보 번호 n 이 필요합니다'] };
    return go(['choose', sid, String(n)], { packFile: await packFileFor(preset) }, devPathOr(preset));
  }
  if (step === 'approve') return go(['approve', sid, '--by', '고객'], { packFile: await packFileFor(preset) }, devPathOr(preset));
  if (step === 'restyle') return go(['restyle', sid, '--by', '고객'], { packFile: await packFileFor(preset) }, devPathOr(preset));
  if (step === 'status') return go(['status', sid], { packFile: await packFileFor(preset) });
  return { hints: ['모르는 단계입니다'] };
}

const devPathOr = p => (process.env.SHORTEM_DEV_PRESET ? null : p);

export function aiList(limit = 3) {
  return pending().slice(0, limit);
}

export const haveActive = () => activeRuns().length > 0 || fs.existsSync(path.join(homeDir(), 'ai'));
