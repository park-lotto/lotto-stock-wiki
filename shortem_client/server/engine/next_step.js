// ★하나뿐인 전이·판정 주인 — nextStep(job, step, payload, ctx).
//   단계 9개(계약 §8): 소재 → 분석 → 대본 → 장면 계획 → 음성 → 렌더 → 검사 → 확인 → 완료
//   내부 상태: setup → source_pick(사람) → analyze → script(사람, 방향 힌트 반려 ≤5) → plan(선검수 승인 전 TTS 0)
//            → voice → render → check → review(사람) → done
//   규칙: status 가 'working' 인 동안 runner 가 nextStep 을 계속 부른다. 사람 자리는 입력이 없으면 need_input 으로 선다.
//   서버는 명령을 내리지 않는다 — 여기 전이는 전부 로컬 판단이다.
import fs from 'node:fs';
import path from 'node:path';
import { STEP_NAMES } from '../lease.js';
import { jobDir, outDir, saveJob } from '../jobs.js';
import { assetFile } from '../assets.js';
import { audit } from '../audit.js';
import { normalizeFrame, framesAt, captionLayer } from './frame.js';
import { checkSource, fetchSource, SourceError } from './source.js';
import { analyze } from './analyze.js';
import { rulesFrom, scriptNeed, lintScript } from './script_lint.js';
import { plan, timeline, titleLinesOf } from './plan.js';
import { synthLines, readKey, VoiceError } from './voice.js';
import { renderVideo } from './render.js';
import { checkVideo, failHints } from './check.js';

export const FLOW = Object.freeze({
  setup: { name: '소재' }, source_pick: { name: '소재', human: true }, analyze: { name: '분석' },
  script: { name: '대본', human: true }, plan: { name: '장면 계획', human: true }, voice: { name: '음성' },
  render: { name: '렌더' }, check: { name: '검사' }, review: { name: '확인', human: true }, done: { name: '완료' },
});
export const MAX_SCRIPT_TRIES = 5;
const ACCEPTS = ['youtube', 'local_video', 'text'];

const stepName = cur => (FLOW[cur] || FLOW.setup).name;
const failOf = (where, why, fix, retry_ok = true) => ({ where, why, fix, retry_ok });

function go(job, next) { job.cur = next; job.status = 'working'; job.step_started = Date.now(); delete job.need; delete job.hints; delete job.fail; }
function wait(job, need, hints) { job.status = 'need_input'; job.need = need; job.hints = hints || []; delete job.fail; }
function stop(job, fail, status = 'failed') { job.status = status; job.fail = fail; delete job.need; }

// 자산표 → 렌더 재료
function fontsOf(job) {
  const out = {};
  for (const [id, a] of Object.entries(job.assets || {})) {
    if (a.kind !== 'font') continue;
    const file = assetFile(job.assets, id);
    if (file) out[id.replace(/^font:/, '')] = { file, ext: a.ext || 'ttf' };
  }
  return out;
}
function specOf(job, title, firstEnd) {
  const fonts = fontsOf(job);
  // 채널명·글꼴 바꾸기(프리셋+옵션 합치기)는 서버 assets_for 가 이미 했다 — 여기서 다시 하지 않는다(판단 한 곳)
  return normalizeFrame(job.bundle && job.bundle.frame, { title, firstSpanEnd: firstEnd, fonts: new Set(Object.keys(fonts)) });
}
function corpusOf(job) { const i = job.source_info || {}; return [i.title, i.text, i.transcript].filter(Boolean).join('\n'); }
function dataOf(job) {
  const i = job.source_info || {};
  return { source_kind: i.kind, source_title: i.title || '', source_text: i.text || '', transcript: i.transcript || '' };
}
function outName(job) {
  const t = String((job.script && job.script.title) || '숏템').split('\n')[0].replace(/[\\/:*?"<>|\r\n\t]/g, '').replace(/\s+/g, '_').slice(0, 30) || '숏템';
  const d = new Date(job.created || Date.now());
  const ymd = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
  return `${ymd}_${t}_${job.job_id.slice(-6)}.mp4`;
}

// 완료 정리 — 규격(frame·rules)·자산표·계획 수치 삭제, 결과 요약만. 렌더 임시(틀 그림·필터 그래프)도 지운다.
export function finalize(job) {
  const keep = { job_id: job.job_id, created: job.created, updated: job.updated, profile_id: job.profile_id, profile_version: job.profile_version,
    cur: 'done', status: 'done', title: job.script && job.script.title, final: job.final, verdict: { pass: !!(job.verdict && job.verdict.pass) }, mark: job.mark, times: job.times };
  for (const sub of ['render', 'voice']) { try { fs.rmSync(path.join(jobDir(job.job_id), sub), { recursive: true, force: true }); } catch { /* 없음 */ } }
  for (const k of Object.keys(job)) delete job[k];
  Object.assign(job, keep);
  return job;
}

const handlers = {
  async setup(job, input, ctx) {
    let lic;
    try { lic = await ctx.license(); } catch (e) {
      if (e.code === 'revoked' || e.code === 'expired') ctx.clearCache(e.code);
      return stop(job, failOf('소재', e.msg || '라이선스를 확인하지 못했습니다', e.code === 'device_limit' ? '숏템 마이페이지에서 기기를 교체하세요' : e.code === 'network' ? '인터넷 연결을 확인하고 다시 시도하세요' : '숏템 페이지에서 라이선스 키를 확인하세요', ['network', 'rate_limited'].includes(e.code)));
    }
    const profiles = lic.profiles || [];
    const pid = job.profile_id || (profiles[0] && profiles[0].profile_id);
    const prof = profiles.find(p => p.profile_id === pid);
    if (!prof) return stop(job, failOf('소재', '내 채널(프로필)이 없습니다', '숏템 페이지에서 프리셋을 고르고 내 채널 옵션을 저장하세요', false));
    job.profile_id = prof.profile_id;
    job.profile_version = prof.version;
    try { await ctx.ensureLease(job); } catch (e) {
      return stop(job, failOf('소재', e.msg || '작업 임대를 받지 못했습니다', e.code === 'busy_other_device' ? '다른 기기 작업이 끝나거나 3분 뒤 다시 시도하세요' : '잠시 뒤 다시 시도하세요'));
    }
    try {
      const got = await ctx.fetchAssets({ profileId: prof.profile_id, jobId: job.job_id, leaseId: ctx.leaseId(job) });
      job.bundle = got.bundle;
      job.assets = got.table;
      job.mark = (got.bundle.license && got.bundle.license.mark) || '';
      job.asset_stats = got.stats;
    } catch (e) {
      return stop(job, failOf('소재', e.msg || '이번 편 자산을 받지 못했습니다', e.code === 'not_entitled' ? '숏템 페이지에서 구매한 프리셋인지 확인하세요' : '잠시 뒤 다시 시도하세요', e.code !== 'not_entitled'));
    }
    go(job, 'source_pick');
  },

  async source_pick(job, input) {
    const raw = (input && input.source) || job.pending_source;
    if (!raw) return wait(job, { kind: 'source', accepts: ACCEPTS, ask: '소재를 주세요 — 유튜브 주소(source.kind=youtube, url), 내 PC 영상(local_video, path), 또는 글(text, text)' });
    delete job.pending_source;
    let src;
    try { src = checkSource(raw); } catch (e) {
      if (e instanceof SourceError) return wait(job, { kind: 'source', accepts: ACCEPTS, ask: '소재를 다시 주세요' }, [e.why + ' — ' + e.fix]);
      throw e;
    }
    job.source = src;
    try {
      const got = await fetchSource(src, jobDir(job.job_id));
      job.video = got.video;
      job.source_info = got.info;
    } catch (e) {
      if (e instanceof SourceError) return wait(job, { kind: 'source', accepts: ACCEPTS, ask: '소재를 다시 주세요' }, [e.why + ' — ' + e.fix]);
      throw e;
    }
    go(job, 'analyze');
  },

  async analyze(job) {
    try { job.analysis = await analyze(job.video); }
    catch { return wait(job, { kind: 'source', accepts: ACCEPTS, ask: '이 영상은 읽을 수 없습니다 — 다른 소재를 주세요' }, ['영상 파일을 열지 못했습니다']); }
    job.script_tries = 0;
    go(job, 'script');
  },

  async script(job, input) {
    const rules = rulesFrom(job.bundle && job.bundle.rules);
    const spec = specOf(job, '', 1.5);
    const tLines = titleLinesOf(spec) || rules.title_lines;
    const need = scriptNeed(rules, tLines);
    if (!input || (!input.lines && !input.title)) return wait(job, need);
    const r = lintScript(input, rules, corpusOf(job), tLines);
    if (!r.ok) {
      job.script_tries = (job.script_tries || 0) + 1;
      job.script_draft = { title: r.title, lines: r.lines };
      if (job.script_tries >= MAX_SCRIPT_TRIES) {
        const bad = (r.hints.map(h => (h.match(/^(\d+)번 줄/) || [])[1]).find(Boolean)) || '1';
        wait(job, need, r.hints);
        job.status = 'failed';
        job.fail = failOf('대본', '방향 힌트로 다섯 번 고쳐도 기준에 맞지 않았습니다', `칸 ${bad}을 직접 써 주세요(사람이 고친 대본을 step='script' 로 다시 주면 이어서 합니다)`);
        return;
      }
      return wait(job, need, r.hints);
    }
    job.script = { title: r.title, lines: r.lines };
    delete job.script_draft;
    delete job.plan; delete job.plan_ok; delete job.tl; delete job.voice;
    go(job, 'plan');
  },

  async plan(job, input) {
    if (!job.plan) {
      const spec = specOf(job, job.script.title, 1.5);
      const mode = (((job.bundle.options || {}).text || {}).caption || {}).mode;
      job.plan = plan(spec, job.script, { mode });
      job.silent = !readKey('typecast');
    }
    const need = { kind: 'plan_ok', scenes: job.plan.scenes.length, voice: job.silent ? 'silent' : 'typecast', length: job.plan.lines.reduce((a, l) => a + l.est, 0) > 40 ? '길게' : job.plan.lines.length > 4 ? '보통' : '짧게',
      ask: `장면 ${job.plan.scenes.length}개 계획됨 — 진행할까요? (payload {approve:true} 면 음성·렌더로, {approve:false} 면 대본으로 돌아갑니다)` };
    const hints = job.silent ? ['타입캐스트 키가 없어 목소리 없이(배경음만) 만듭니다 — 목소리를 넣으려면 ~/.shortem/keys/typecast 에 키를 넣고 다시 승인하세요'] : [];
    if (!input || input.approve == null) return wait(job, need, hints);
    if (input.approve === false) { delete job.plan; go(job, 'script'); job.script_tries = 0; return; }
    job.silent = !readKey('typecast');
    job.plan_ok = true;
    go(job, 'voice');
  },

  async voice(job, input, ctx) {
    const lines = job.script.lines;
    if (job.silent) { job.voice = lines.map(() => null); return go(job, 'render'); }
    try {
      const tts = ((job.bundle.options || {}).tts) || {};
      job.voice = await synthLines(lines, tts, path.join(jobDir(job.job_id), 'voice'), { jobId: job.job_id });
      audit('voice', { job: job.job_id, n: lines.length, result: 'ok' });
    } catch (e) {
      if (e instanceof VoiceError) return stop(job, failOf('음성', e.why, e.fix, e.retry));
      throw e;
    }
    go(job, 'render');
  },

  async render(job, input, ctx) {
    const firstEnd = job.voice && job.voice[0] ? job.voice[0].dur : job.plan.lines[0].est;
    const spec = specOf(job, job.script.title, firstEnd);
    const tl = timeline(job.plan, job.voice, job.analysis, spec);
    job.tl = tl;
    const assets = Object.entries(job.assets || {});
    const bgmId = assets.find(([, a]) => a.kind === 'bgm');
    const o = job.bundle.options || {};
    const bgm = bgmId ? { file: assetFile(job.assets, bgmId[0]), gain_db: o.bgm && o.bgm.gain_db != null ? Number(o.bgm.gain_db) : -20 } : null;
    const sfxFiles = assets.filter(([, a]) => a.kind === 'sfx').map(([id, a]) => ({ id, file: assetFile(job.assets, id), name: a.name }));
    const opener = sfxFiles.find(s => /opener|오프너|두둥/i.test(s.name)) || null;
    const rest = sfxFiles.filter(s => s !== opener);
    const sfx = [];
    if (opener) sfx.push({ file: opener.file, t: 0, gain: 0.5 });
    if (rest.length) tl.lines.forEach((l, k) => { if (k > 0 && l.t1 - l.t0 >= 1) sfx.push({ file: rest[(k - 1) % rest.length].file, t: l.t0, gain: 0.3 }); });
    const comment = `shortem:${job.mark || 'nomark'}:${job.job_id}`;
    job.render = await renderVideo({ spec, tl, src: job.video, title: job.script.title, fonts: fontsOf(job), voice: job.voice, bgm, sfx: sfx.filter(s => s.file), dir: path.join(jobDir(job.job_id), 'render'), comment,
      onProgress: (k, a, b) => { job.sub = `${a}/${b}`; } });
    delete job.sub;
    go(job, 'check');
  },

  async check(job) {
    const silent = !!(job.render && job.render.audio && job.render.audio.silent);
    // 자막 칸 기대 수 = 그 장면 시각의 틀에 자막 층이 있는 장면 수(훅 카드처럼 자막 없는 틀은 빼고) — 계획·틀에서 센다(렌더 결과로 세지 않는다)
    const spec = specOf(job, job.script.title, job.tl.lines[0] ? job.tl.lines[0].t1 - job.tl.lines[0].t0 : 1.5);
    const expectCaptions = job.tl.scenes.filter(s => captionLayer(framesAt(spec, s.t0 + 1e-3).layers)).length;
    const v = await checkVideo(job.render.file, { tl: job.tl, render: job.render, rules: job.bundle.rules, silent, expectCaptions });
    job.verdict = v;
    fs.writeFileSync(path.join(jobDir(job.job_id), 'verdict.json'), JSON.stringify(v, null, 1));
    const od = outDir();
    if (!v.pass) {
      fs.writeFileSync(path.join(od, 'FAILED.json'), JSON.stringify({ job_id: job.job_id, at: new Date().toISOString(), where: '검사', problems: failHints(v.items) }, null, 1));
      job.cur = 'render';   // 다시 시도 = 렌더부터
      return stop(job, failOf('검사', '완성본이 검사 기준에 못 미쳐 최종본을 만들지 않았습니다', '같은 job_id 로 step="resume" 을 부르면 다시 렌더합니다'));
    }
    const final = path.join(od, outName(job));
    fs.copyFileSync(job.render.file, final);
    job.final = final;
    go(job, 'review');
  },

  async review(job, input) {
    if (!input || input.ok == null) return wait(job, { kind: 'review', video: job.final, verdict: '통과', ask: '완성본을 열어 보고 괜찮으면 payload {ok:true}, 고칠 게 있으면 {ok:false, redo:"script"|"plan"|"render"} 로 주세요' });
    if (input.ok === true) return go(job, 'done');
    const redo = ['script', 'plan', 'render'].includes(input.redo) ? input.redo : 'script';
    if (redo === 'script') { job.script_tries = 0; delete job.plan; }
    if (redo === 'plan') { delete job.plan; delete job.plan_ok; }
    go(job, redo);
  },

  async done(job, input, ctx) {
    await ctx.releaseLease(job);
    audit('job_done', { job: job.job_id, result: 'ok' });
    finalize(job);
  },
};

// step = 모델이 부른 단계(내부 이름) 또는 'status'/'resume'. payload = 사람 자리 입력.
//   반환 {accepted, hints?} — accepted 면 runner 가 working 동안 이어 돈다.
export async function nextStep(job, step, payload, ctx) {
  if (step === 'status') return { accepted: false };
  if (job.status === 'done' || job.status === 'cancelled') return { accepted: false, hints: ['이 작업은 이미 끝났습니다 — 새로 만들려면 step="setup"'] };
  // 실패에서 다시: resume 또는 같은 단계
  if (job.status === 'failed') {
    if (!(job.fail && job.fail.retry_ok)) return { accepted: false, hints: ['이 실패는 다시 시도로 풀리지 않습니다 — fail.fix 를 먼저 해 주세요'] };
    if (step !== 'resume' && step !== job.cur) return { accepted: false, hints: [`지금은 '${stepName(job.cur)}' 단계입니다 — step="resume" 또는 step="${job.cur}" 로 부르세요`] };
    go(job, job.cur);
    if (payload) job.input = payload;
    return { accepted: true };
  }
  if (job.status === 'need_input') {
    if (step !== job.cur) return { accepted: false, hints: [`지금은 '${stepName(job.cur)}' 단계 입력을 기다립니다 — step="${job.cur}" 로 부르세요`] };
    job.status = 'working';
    job.input = payload || {};
    return { accepted: true };
  }
  if (job.status === 'working') return { accepted: step === 'resume' || step === job.cur || step === 'setup', running: true };
  return { accepted: false };
}

// 한 칸 돌리기(runner 가 부른다) — 지금 상태의 처리기를 한 번
export async function runOne(job, ctx) {
  const h = handlers[job.cur];
  if (!h) { stop(job, failOf('완료', '알 수 없는 단계입니다', '새로 시작하세요', false)); return; }
  const input = job.input; delete job.input;
  const t0 = Date.now();
  const before = job.cur;
  try {
    await h(job, input, ctx);
  } catch (e) {
    audit('step_error', { job: job.job_id, step: stepName(before), code: e.code || 'error' });
    if (ctx.debug) ctx.debug(before, e);
    stop(job, failOf(stepName(before), stepWhy(before), '같은 job_id 로 step="resume" 을 부르면 이 단계부터 다시 합니다'));
    job.cur = before;
  }
  job.times = job.times || {};
  const tn = stepName(before);
  job.times[tn] = (job.times[tn] || 0) + (Date.now() - t0);
  if (job.job_id) saveJob(job);
}

function stepWhy(cur) {
  return { source_pick: '소재를 준비하다 멈췄습니다', analyze: '영상을 분석하다 멈췄습니다', voice: '음성을 만들다 멈췄습니다', render: '렌더하다 멈췄습니다', check: '검사하다 멈췄습니다' }[cur] || '진행하다 멈췄습니다';
}

// 모델로 나갈 응답(가르기 전) — firewall.shape 가 다시 거른다
export function outOf(job, extraHints) {
  const name = stepName(job.cur);
  const o = { job_id: job.job_id, progress: { name, status: job.status, elapsed_sec: Math.round((Date.now() - (job.step_started || job.created || Date.now())) / 1000) } };
  if (job.status === 'need_input' && job.need) {
    o.need = job.need;
    if (job.need.kind === 'script') o.data = dataOf(job);
  }
  const hints = [...(job.hints || []), ...(extraHints || [])];
  if (job.status === 'working') hints.push(`'${name}' 단계 진행 중입니다 — 잠시 뒤 같은 job_id 로 step="status" 를 다시 부르세요`);
  if (job.status === 'done' && job.final) hints.push('완성본이 작업 폴더 out/ 에 있습니다');
  if (hints.length) o.hints = hints;
  if (job.fail) o.fail = job.fail;
  if (job.status === 'failed' && job.need && job.need.kind === 'script') { o.need = job.need; o.data = dataOf(job); }
  return o;
}

export { STEP_NAMES };
