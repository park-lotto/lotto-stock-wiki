// 숏폼 만들기 흐름(관제 234 5판) — 프리셋 고르기 → 후보 소재 → 고객 사인 → 완성.
//   단계 판단은 엔진(calcopy_make) 한 곳. 여기는 엔진 세션 JSON 을 Claude 가 따라 하기 쉬운 꼴(need·다음 할 일)로 옮기기만 한다.
//   하이쿠도 따라오게: 응답마다 need 하나와 그 need 에 맞는 도구 호출 한 줄(next)을 준다.
import fs from 'node:fs';
import path from 'node:path';
import { startRun, waitRun, getRun, activeRuns, pending, SID_RE } from './engine_bridge.js';
import { homeDir, writeFileIn } from './paths.js';

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
    const files = S.files || [];
    const fin = files.find(f => f.name === 'final.mp4');
    return { ...base, need: 'done', video: fin && fin.path, files: files.map(f => f.name), hints: ['완성본 경로를 고객에게 알려 주세요'] };
  }
  return { ...base, need: 'wait', topic_state: t.state, next: `shortem_make(step="status", sid="${S.sid}")` };
}

// 프로필 → 엔진 팩 파일(~/.shortem/packs/<프로필>.json) — 팩 내용은 서버(channel_profile.pack_for)가 만든 것을 그대로 쓴다
export function packFileFor(profile) {
  if (process.env.SHORTEM_DEV_PACK) return process.env.SHORTEM_DEV_PACK;
  if (!profile || !profile.pack) return null;
  const rel = path.join('packs', `${String(profile.profile_id).replace(/[^0-9A-Za-z_-]/g, '_')}.json`);
  writeFileIn(homeDir(), rel, JSON.stringify({ 1: profile.pack }));
  return path.join(homeDir(), rel);
}

async function go(args, opts) {
  const r = startRun(args, opts);
  const out = await waitRun(r, waitMs());
  if (out) return shapeSession(out);
  return r.done ? shapeSession({ error: '엔진 결과 없음' }) : aiNeed(r.runId);
}

export async function makeStep({ step, sid, n, run_id, profile, topic }) {
  if (step === 'wait') {
    const r = getRun(run_id) || activeRuns()[0];
    if (!r) return { hints: ['기다릴 작업이 없습니다 — shortem_make(step="status", sid=…) 로 보세요'] };
    const out = await waitRun(r, waitMs());
    return out ? shapeSession(out) : (r.done ? shapeSession({ error: '엔진 결과 없음' }) : aiNeed(r.runId));
  }
  if (step === 'start') {
    if (!profile) return { hints: ['프로필이 없습니다 — shortem_presets refresh=true 로 내 채널을 받으세요'] };
    if (!profile.preset_path) return { hints: ['이 프로필의 프리셋을 찾지 못했습니다 — 숏템 웹 설정에서 프리셋을 다시 저장하세요'] };
    const args = ['start', '--preset', profile.preset_path, '--pack', '1', ...(topic ? ['--topic', String(topic).slice(0, 200)] : [])];
    return go(args, { packFile: packFileFor(profile) });
  }
  if (!SID_RE.test(String(sid || ''))) return { hints: ['sid 가 필요합니다(start 응답의 sid)'] };
  if (step === 'choose') {
    if (!Number.isInteger(n) || n < 1) return { hints: ['고른 후보 번호 n 이 필요합니다'] };
    return go(['choose', sid, String(n)], { packFile: packFileFor(profile) });
  }
  if (step === 'approve') return go(['approve', sid, '--by', '고객'], { packFile: packFileFor(profile) });
  if (step === 'status') return go(['status', sid], { packFile: packFileFor(profile) });
  return { hints: ['모르는 단계입니다'] };
}

export function aiList(limit = 3) {
  return pending().slice(0, limit);
}

export const haveActive = () => activeRuns().length > 0 || fs.existsSync(path.join(homeDir(), 'ai'));
