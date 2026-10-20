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
import { deliverInBackground } from './deliver.js';

export const waitMs = () => Number(process.env.SHORTEM_WAIT_SEC || 45) * 1000;

function aiNeed(runId) {
  const n = pending().length;
  // 물을 것이 없는데 아직 도는 중(목소리·렌더) — 'AI 0건에 답하라'고 하면 Claude 가 헤매다 셸 sleep 으로 기다렸다(10-20 회원 한 줄 실시험)
  if (!n) return { need: 'wait', run_id: runId, ...liveStage(), next: `shortem_make(step="wait", run_id="${runId}")`,
    hints: ['아직 만드는 중입니다(목소리·렌더는 몇 분 걸립니다) — 같은 wait 를 다시 부르면 끝날 때까지 이어서 기다립니다. 셸·sleep 으로 기다리지 마세요'] };
  return { need: 'ai', ai_requests: n, run_id: runId, ...liveStage(),
    next: `shortem_ai(action="list") 로 요청을 받아 하나씩 답한 뒤(answer), shortem_make(step="wait", run_id="${runId}") 를 부르세요`,
    hints: [`엔진이 AI 판독 ${n}건을 기다립니다 — 사람에게 묻지 말고 바로 답하세요`] };
}

const cand = c => ({ n: c.n, title: c.title, total: c.total, line: c.line, scores: c.scores, made: c.made || 0 });

// 고객이 사인하기 전에 볼 대본(제목·줄) — 엔진이 쓴 소재 폴더 대본.json 의 final(관제 234, 10-20: 파일 이름만 줘서 고객이 대본을 못 봤다)
function scriptOf(S) {
  if (S.topic_id == null) return undefined;
  try {
    const d = JSON.parse(fs.readFileSync(path.join(dataDir(), 'calcopy', 'topics', String(S.topic_id), '대본.json'), 'utf8'));
    const f = d.final || {};
    return { title: String(f.title || d.title || ''), lines: (f.lines || []).map(l => String(l.text || '')) };
  } catch { return undefined; }
}

// 엔진 세션 → 응답
// 엔진 오류 글 → 고객용(경로·내부 파일 이름·벤치 경로를 지우고 짧게) — 숏템 내부를 설명하지 않는다(관제 234)
export function cleanWhy(msg) {
  return String(msg || '').replace(/[A-Za-z]:[\\/][^\s'"]*/g, '…').replace(/(?:^|[\s'"(])\/[^\s'"]+/g, ' …')
    .replace(/channel\/[^\s'"]+/g, '프리셋').replace(/[\w가-힣.-]+\.(?:py|json|js|md|mp4|wav)/g, '파일')
    .replace(/Traceback[\s\S]*/, '').replace(/\s+/g, ' ').trim().slice(0, 160) || '엔진이 멈췄습니다';
}

// 하이브리드 라인(집 PC 제작순서 그대로 — 엔진 hybrid/customer.py, 사장님 10-21 재정비)의 응답 → MCP 응답. 진행은 stage 한 줄만(볼케이노처럼, 세부 금지)
const stageOf = o => (o && o.stage ? { stage: String(o.stage), step: o.step, step_total: o.total } : {});
function shapeHybrid(o) {
  const base = { sid: o.sid, ...stageOf(o) };
  if (o.need === 'approve') return { ...base, need: 'approve', script: o.script,
    next: `고객에게 script(제목·대본 줄)를 그대로 보여 주고 사인을 받으면 shortem_make(step="approve", sid="${o.sid}")`,
    hints: ['사인 전에는 목소리 합성·렌더를 하지 않습니다(고객 키 비용)'] };
  if (o.need === 'done') {
    const src = o.video && fs.existsSync(o.video) ? o.video : null;
    if (!src) return { ...base, fail: { why: '완성본 파일을 찾지 못했습니다', fix: 'shortem_make(step="status") 로 다시 보세요' } };
    const name = `${String(o.title || 'shortem').replace(/[\\/:*?"<>|\s]+/g, '_').slice(0, 40)}_${o.sid}.mp4`;
    const video = path.join(ensureDir(workDir(), '완성본'), name);
    if (!fs.existsSync(video) || fs.statSync(src).mtimeMs > fs.statSync(video).mtimeMs) fs.copyFileSync(src, video);
    try { fs.writeFileSync(video + '.json', JSON.stringify({ sid: o.sid, title: String(o.title || ''), line: 'hybrid' })); } catch { /* 표식 없이도 영상은 본다 */ }
    deliverInBackground(video, { title: String(o.title || '') });
    return { ...base, need: 'done', video, hints: ['완성본 경로를 고객에게 알려 주세요'] };
  }
  if (o.need === 'fail') return { ...base, fail: { why: cleanWhy(o.why), fix: o.fix || '', retry_ok: !!o.retry_ok },
    ...(o.retry_ok ? { next: `shortem_make(step="retry", sid="${o.sid}")` } : {}) };
  return { ...base, need: 'wait', next: `shortem_make(step="status", sid="${o.sid}")` };
}
const isHybridSid = sid => SID_RE.test(String(sid || '')) && fs.existsSync(path.join(dataDir(), 'hybrid', String(sid), 'piece.json'));
// 지금 도는 하이브리드 편의 진행 한 줄(엔진 progress.json 한 곳)
function liveStage() {
  try {
    const root = path.join(dataDir(), 'hybrid');
    const d = fs.readdirSync(root).map(n => path.join(root, n, 'progress.json')).filter(f => fs.existsSync(f))
      .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs)[0];
    return d ? stageOf(JSON.parse(fs.readFileSync(d, 'utf8'))) : {};
  } catch { return {}; }
}

export function shapeSession(S) {
  if (S && typeof S.need === 'string' && S.sid && !S.state) return shapeHybrid(S);
  if (!S || S.error) return { fail: { why: cleanWhy((S && S.error) || '엔진이 답하지 않았습니다'), code: S && S.code, fix: '같은 단계를 한 번 더 부르세요. 또 실패하면 shortem_feedback 으로 알려 주세요' } };
  const base = { sid: S.sid, state: S.state };   // 내부 프리셋 경로(벤치 채널 이름이 들어 있다)는 내보내지 않는다
  if (S.state === 'candidates') {
    const c = (S.candidates || []).map(cand);
    if (!c.length) return { ...base, need: 'retry', hints: ['점수가 난 후보가 없습니다 — 잠시 뒤 shortem_make(step="start") 를 다시 부르면 소재를 더 찾습니다'] };
    return { ...base, need: 'choose', candidates: c,
      next: `고객에게 후보를 보여 주고 고른 번호로 shortem_make(step="choose", sid="${S.sid}", n=<번호>)`,
      hints: ['후보를 표로 보여 주고 고객이 번호를 고르게 하세요(대신 고르지 마세요)'] };
  }
  const t = S.topic || {};
  if (S.state === 'failed' || S.state === 'stopped') return { ...base, fail: { why: cleanWhy(S.error || '만들기가 멈췄습니다'), fix: '같은 단계를 다시 부르거나 다른 후보를 고르세요' } };
  if ((t.state || '') === 'plan_review' || S.state === 'plan_review') {
    const files = (S.files || []).map(f => f.name);
    return { ...base, need: 'approve', plan_files: files, script: scriptOf(S),
      next: `고객에게 script(제목·대본 줄)를 그대로 보여 주고 사인을 받으면 shortem_make(step="approve", sid="${S.sid}")`,
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
      deliverInBackground(video, { title: String(t.name || '') });   // 텔레그램·구글 드라이브(켜 둔 곳만, 이미 보낸 것은 건너뜀) — deliver.js
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
    const line = hybridLine(rental.presetPath);                  // 이 프리셋이 집 PC 제작 라인(하이브리드)이면 그 입구로
    if (line && args[0] === 'start') {
      const ref = args[args.indexOf('--ref') + 1];
      if (!args.includes('--ref') || !ref) { await rental.release(); return { hints: ['이 프리셋은 연예인 쇼핑 쇼츠 주소로 만듭니다 — 고객에게 영상 주소를 받아 shortem_make(step="start", video=…) 로 부르세요'] }; }
      args = ['hybrid', 'start', '--ref', ref, '--version', line.version];
    }
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
    if (devPath && hybridLine(devPath)) {            // 개발 PC: 엔진 폴더 프리셋이 하이브리드면 빌리지 않고 그 입구로
      if (!video) return { hints: ['이 프리셋은 연예인 쇼핑 쇼츠 주소로 만듭니다 — 고객에게 영상 주소를 받아 shortem_make(step="start", video=…) 로 부르세요'] };
      return go(['hybrid', 'start', '--ref', video, '--version', hybridLine(devPath).version], { packFile: await packFileFor(preset) }, null);
    }
    const args = ['start', '--preset', devPath || 'rented', '--pack', '1',
      ...(topic ? ['--topic', String(topic).slice(0, 200)] : []), ...(video ? ['--ref', video] : [])];
    return go(args, { packFile: await packFileFor(preset), env: channel ? { CALCOPY_ORIGINALS_FILE: originalsFile(channel) } : {} }, devPath ? null : preset);
  }
  if (!SID_RE.test(String(sid || ''))) return { hints: ['sid 가 필요합니다(start 응답의 sid)'] };
  if (step === 'choose') {
    if (!Number.isInteger(n) || n < 1) return { hints: ['고른 후보 번호 n 이 필요합니다'] };
    return go(['choose', sid, String(n)], { packFile: await packFileFor(preset) }, devPathOr(preset));
  }
  if (isHybridSid(sid)) {   // 하이브리드 편 — 사인·이어 하기·상태(엔진 hybrid 입구). 이어 하기·사인은 기술 꾸러미가 필요해 다시 빌린다
    if (step === 'approve') return go(['hybrid', 'approve', sid], { packFile: await packFileFor(preset) }, devPathOr(preset));
    if (step === 'retry') return go(['hybrid', 'resume', sid], { packFile: await packFileFor(preset) }, devPathOr(preset));
    if (step === 'status') return go(['hybrid', 'status', sid], { packFile: await packFileFor(preset) }, devPathOr(preset));
    if (step === 'restyle') return { hints: ['이 프리셋은 다시 만들기를 아직 못 합니다 — 설정을 바꾼 뒤 같은 영상 주소로 새로 만들어 주세요'] };
  }
  if (step === 'approve') return go(['approve', sid, '--by', '고객'], { packFile: await packFileFor(preset) }, devPathOr(preset));
  if (step === 'restyle') return go(['restyle', sid, '--by', '고객'], { packFile: await packFileFor(preset) }, devPathOr(preset));
  if (step === 'status') return go(['status', sid], { packFile: await packFileFor(preset) });
  return { hints: ['모르는 단계입니다'] };
}

const devPathOr = p => (process.env.SHORTEM_DEV_PRESET ? null : p);

// 빌린 프리셋 폴더의 line.json — 주인 = 엔진 트랙 channel/<slug>/preset/<틀>/line.json(사장님 10-21 재정비). 개발 PC 는 SHORTEM_DEV_PRESET 폴더
export function hybridLine(presetPath) {
  const rel = presetPath || process.env.SHORTEM_DEV_PRESET;
  if (!rel) return null;
  try {
    const j = JSON.parse(fs.readFileSync(path.join(engineRoot(), ...String(rel).split('/'), 'line.json'), 'utf8'));
    return j && j.line === 'hybrid' && j.version ? j : null;
  } catch { return null; }
}

export function aiList(limit = 3) {
  return pending().slice(0, limit);
}

export const haveActive = () => activeRuns().length > 0 || fs.existsSync(path.join(homeDir(), 'ai'));
