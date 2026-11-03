// 임대(lease)·하트비트(계약 §2, 설계 §7-10). 판정 주인은 서버 claude_portal.lease — 여기는 부르기만 한다.
//   acquire(멱등) → heartbeat(heartbeat_every 초마다, 단계 이름만) → release.
//   하트비트 3회 연속 실패 또는 409 lease_lost → lost. lost 면 지금 단계까지만 끝내고 다음 단계 진입 때 다시 acquire.
import fs from 'node:fs';
import path from 'node:path';
import { api, ApiError } from './api.js';
import { audit } from './audit.js';
import { homeDir } from './paths.js';

export const STEP_NAMES = Object.freeze(['소재', '분석', '대본', '장면 계획', '음성', '렌더', '검사', '확인', '완료']);
const MAX_FAILS = 3;

// 이 PC 에서 받은 임대 장부(임대마다 파일 하나: pid·job·lease). 프로그램이 죽으면 반납을 못 해 서버에 임대가 최대 3분 남고,
//   서버는 같은 기기라도 다른 작업이면 그동안 busy_other_device 로 막는다(11-03 #811·#761 재시작 직후 2번 멈춤).
//   그래서 임대를 받기 전에 주인이 죽은 장부를 서버에 돌려준다 — 임대를 받는 곳(편 빌리기·제작·벤치마킹)이 모두 이 acquire 를 거친다.
//   서버 반납은 임대 번호·기기가 같을 때만 지우므로 다른 기기·살아 있는 프로그램의 임대는 건드리지 않는다.
const bookDir = () => path.join(homeDir(), 'leases');
const bookFile = id => path.join(bookDir(), String(id).replace(/[^\w-]/g, '') + '.json');
const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };
export async function freeDeadLeases() {
  let names = [];
  try { names = fs.readdirSync(bookDir()); } catch { return 0; }
  let n = 0;
  for (const name of names) {
    const f = path.join(bookDir(), name);
    let b = null;
    try { b = JSON.parse(fs.readFileSync(f, 'utf8')); } catch { /* 깨진 장부는 지운다 */ }
    if (b && b.pid && (b.pid === process.pid || alive(b.pid))) continue;
    if (b && b.lease) {
      try { await api.lease({ action: 'release', job_id: b.job, lease_id: b.lease }); n++; } catch { /* 못 돌려주면 서버 만료를 기다린다 */ }
    }
    try { fs.rmSync(f, { force: true }); } catch { /* 다음에 */ }
  }
  if (n) audit('lease_free_dead', { result: 'ok', n });
  return n;
}

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
    if (!this.id) await freeDeadLeases();
    const name = this.stepName();
    const r = await api.lease({ action: 'acquire', job_id: this.jobId, step_name: name, ...(this.id ? { lease_id: this.id } : {}) });
    this.id = r.lease_id;
    try { fs.mkdirSync(bookDir(), { recursive: true }); fs.writeFileSync(bookFile(this.id), JSON.stringify({ pid: process.pid, job: this.jobId, lease: this.id })); } catch { /* 장부 없이도 임대는 돈다 */ }
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
    try { fs.rmSync(bookFile(id), { force: true }); } catch { /* 다음 freeDeadLeases 가 치운다 */ }
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
