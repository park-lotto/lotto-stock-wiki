// 제작 실행기 — job 한 개를 working 동안 이어 돌린다(전이 판단은 engine/next_step.js 만).
//   단계 진입마다 임대 확인: 잃었으면 다시 받고, 못 받으면 그 단계 앞에서 멈춘다(state 저장 → resume 으로 재개).
//   도구 호출은 최대 SHORTEM_WAIT_SEC(기본 45초)만 기다리고 진행 상태를 돌려준다 — 렌더는 뒤에서 계속 돈다.
import { Lease } from './lease.js';
import { api } from './api.js';
import { fetchJobAssets, clearCache } from './assets.js';
import { audit } from './audit.js';
import { loadJob, saveJob, newJobId, jobDir } from './jobs.js';
import { nextStep, runOne, FLOW, outOf } from './engine/next_step.js';
import fs from 'node:fs';

const leases = new Map();     // job_id → Lease
const running = new Map();    // job_id → Promise
let licCache = null;

export const waitBudgetMs = () => Number(process.env.SHORTEM_WAIT_SEC || 45) * 1000;

function leaseFor(job) {
  let l = leases.get(job.job_id);
  if (!l) { l = new Lease(job.job_id, { stepName: () => (FLOW[(jobsInFlight.get(job.job_id) || job).cur] || FLOW.setup).name }); leases.set(job.job_id, l); }
  return l;
}

export function makeCtx(overrides = {}) {
  return {
    async license() {
      if (licCache && Date.now() - licCache.at < 10 * 60000) return licCache.v;
      const v = await api.license();
      licCache = { at: Date.now(), v };
      return v;
    },
    async ensureLease(job) { const l = leaseFor(job); if (!l.active) await l.acquire(); return l; },
    leaseId(job) { return leaseFor(job).id; },
    async releaseLease(job) { const l = leases.get(job.job_id); if (l) { await l.release(); leases.delete(job.job_id); } },
    fetchAssets: fetchJobAssets,
    clearCache,
    debug: process.env.SHORTEM_DEBUG ? (step, e) => process.stderr.write(`[shortem] ${step}: ${e.stack || e}\n${e.detail || ''}\n`) : null,
    ...overrides,
  };
}

export function resetLicenseCache() { licCache = null; }

async function loop(job, ctx) {
  while (job.status === 'working') {
    // 단계 진입 전 임대 확인(setup 은 자체에서 받는다)
    if (job.cur !== 'setup' && job.cur !== 'done') {
      const l = leases.get(job.job_id);
      if (l && l.lost && l.lostReason === 'lease_lost') {
        // 마이페이지 강제 해제 등으로 서버가 임대를 거둬 갔다 — 몰래 다시 받지 않고 이 단계 앞에서 멈춘다(재개는 resume)
        job.status = 'failed';
        job.fail = { where: (FLOW[job.cur] || FLOW.setup).name, why: '작업 임대가 해제되어 이 단계 앞에서 멈췄습니다', fix: '이 기기에서 이어 하려면 같은 job_id 로 step="resume" 을 부르세요', retry_ok: true };
        audit('lease_stop', { job: job.job_id, step: job.fail.where, code: 'lease_lost' });
        saveJob(job);
        break;
      }
      if (!l || !l.active) {
        try { await ctx.ensureLease(job); }
        catch (e) {
          job.status = 'failed';
          job.fail = { where: (FLOW[job.cur] || FLOW.setup).name, why: e.code === 'busy_other_device' ? (e.msg || '다른 기기에서 작업 중입니다') : '라이선스 임대가 끊겨 이 단계 앞에서 멈췄습니다', fix: '인터넷·다른 기기 작업을 확인하고 같은 job_id 로 step="resume" 을 부르면 이어서 합니다', retry_ok: true };
          audit('lease_stop', { job: job.job_id, step: job.fail.where, code: e.code || 'error' });
          saveJob(job);
          break;
        }
      }
    }
    await runOne(job, ctx);
    if (job.cancel_requested) { job.status = 'cancelled'; saveJob(job); }
  }
  if (job.status === 'failed' || job.status === 'cancelled') { await ctx.releaseLease(job); }
  return job;
}

function kick(job, ctx) {
  if (running.has(job.job_id)) return running.get(job.job_id);
  const p = loop(job, ctx).finally(() => running.delete(job.job_id));
  running.set(job.job_id, p);
  return p;
}

async function waitFor(p, ms) {
  let t;
  await Promise.race([p, new Promise(r => { t = setTimeout(r, ms); })]);
  clearTimeout(t);
}

// shortem_make 본체. 반환 = 가르기 전 응답(outOf)
export async function make({ step, job_id, profile_id, source, payload }, ctx = makeCtx(), { waitMs = waitBudgetMs() } = {}) {
  let job;
  if (step === 'setup' && !job_id) {
    job = { job_id: newJobId(), created: Date.now(), cur: 'setup', status: 'working', step_started: Date.now(), profile_id: profile_id || null };
    if (source) job.pending_source = source;
    fs.mkdirSync(jobDir(job.job_id), { recursive: true });
    saveJob(job);
    audit('job_new', { job: job.job_id, profile: profile_id || '' });
  } else {
    if (!job_id) return { hints: ['job_id 가 필요합니다 — 새로 시작하려면 step="setup"'] };
    const live = running.has(job_id) ? null : loadJob(job_id);
    job = running.has(job_id) ? jobsInFlight.get(job_id) : live;
    if (!job) return { hints: ['그런 작업이 없습니다 — shortem_job list 로 확인하세요'] };
    if (step === 'source_pick' && source && !payload) payload = { source };
    if (step === 'resume' && !running.has(job_id)) { const old = leases.get(job_id); if (old) old.stopTimer(); leases.delete(job_id); }
    if (!running.has(job_id)) {
      const r = await nextStep(job, step, payload, ctx);
      if (!r.accepted) { const o = outOf(job, r.hints); return o; }
      saveJob(job);
    }
  }
  jobsInFlight.set(job.job_id, job);
  const p = kick(job, ctx);
  await waitFor(p, waitMs);
  return outOf(job);
}

const jobsInFlight = new Map();   // 돌고 있는 job 객체(같은 객체를 응답에 쓴다)

export function current(job_id) { return running.has(job_id) ? jobsInFlight.get(job_id) : loadJob(job_id); }

export async function cancel(job_id, ctx = makeCtx()) {
  const job = current(job_id);
  if (!job) return null;
  if (job.status === 'done') return job;
  job.status = 'cancelled';
  job.cancel_requested = true;
  job.fail = { where: (FLOW[job.cur] || FLOW.setup).name, why: '사용자가 멈췄습니다', fix: '새로 만들려면 step="setup"', retry_ok: false };
  await ctx.releaseLease(job);
  saveJob(job);
  audit('job_cancel', { job: job_id });
  return job;
}

// 시험용: 돌고 있는 것 끝날 때까지
export async function settle(job_id) { const p = running.get(job_id); if (p) await p; }
export function _leases() { return leases; }
