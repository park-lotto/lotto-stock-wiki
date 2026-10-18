// 임대(lease)·하트비트(계약 §2, 설계 §7-10). 판정 주인은 서버 claude_portal.lease — 여기는 부르기만 한다.
//   acquire(멱등) → heartbeat(heartbeat_every 초마다, 단계 이름만) → release.
//   하트비트 3회 연속 실패 또는 409 lease_lost → lost. lost 면 지금 단계까지만 끝내고 다음 단계 진입 때 다시 acquire.
import { api, ApiError } from './api.js';
import { audit } from './audit.js';

export const STEP_NAMES = Object.freeze(['소재', '분석', '대본', '장면 계획', '음성', '렌더', '검사', '확인', '완료']);
const MAX_FAILS = 3;

export class Lease {
  constructor(jobId, { stepName = () => STEP_NAMES[0], hbMs } = {}) {
    this.jobId = jobId;
    this.stepName = stepName;
    this.id = null;
    this.lost = false;
    this.fails = 0;
    this.timer = null;
    this.hbMs = hbMs;
    this.lastError = null;
  }

  get active() { return !!this.id && !this.lost; }

  async acquire() {
    const name = this.stepName();
    const r = await api.lease({ action: 'acquire', job_id: this.jobId, step_name: name, ...(this.id ? { lease_id: this.id } : {}) });
    this.id = r.lease_id;
    this.lost = false;
    this.fails = 0;
    const every = Number(process.env.SHORTEM_HB_MS) || this.hbMs || (Number(r.heartbeat_every) || 60) * 1000;
    this.startTimer(every);
    audit('lease_acquire', { job: this.jobId, step: name, result: 'ok' });
    return r;
  }

  startTimer(every) {
    this.stopTimer();
    this.timer = setInterval(() => { this.heartbeat().catch(() => {}); }, every);
    if (this.timer.unref) this.timer.unref();
  }

  stopTimer() { if (this.timer) clearInterval(this.timer); this.timer = null; }

  async heartbeat() {
    if (!this.id || this.lost) return false;
    try {
      await api.lease({ action: 'heartbeat', job_id: this.jobId, lease_id: this.id, step_name: this.stepName() });
      this.fails = 0;
      return true;
    } catch (e) {
      this.lastError = e instanceof ApiError ? e.code : 'network';
      if (e instanceof ApiError && e.status === 409) {
        this.markLost('lease_lost');
      } else if (++this.fails >= MAX_FAILS) {
        this.markLost('heartbeat_fail');
      }
      return false;
    }
  }

  markLost(why) {
    if (this.lost) return;
    this.lost = true;
    this.lostReason = why;
    this.stopTimer();
    audit('lease_lost', { job: this.jobId, code: why });
  }

  async release() {
    this.stopTimer();
    const id = this.id;
    this.id = null;
    if (!id) return;
    try { await api.lease({ action: 'release', job_id: this.jobId, lease_id: id }); audit('lease_release', { job: this.jobId, result: 'ok' }); }
    catch { audit('lease_release', { job: this.jobId, result: 'fail' }); }
  }
}

// 단계 진입 전: 임대가 살아 있나 확인하고, 없거나 잃었으면 다시 받는다. 실패면 ApiError 를 던진다.
export async function ensureLease(lease) {
  if (lease.active) return lease;
  await lease.acquire();
  return lease;
}
