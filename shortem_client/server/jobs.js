// job 저장소 — <작업폴더>/jobs/<job_id>/state.json. 쓰기는 경로 감옥 안만.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { workDir, jail, writeFileIn, ensureDir } from './paths.js';

export const JOB_RE = /^j_[0-9a-z]{6,40}$/;

export function newJobId() {
  return 'j_' + Date.now().toString(36) + crypto.randomBytes(4).toString('hex');
}

export function jobDir(id) {
  if (!JOB_RE.test(String(id))) throw Object.assign(new Error('잘못된 job id'), { code: 'bad_job' });
  return jail(workDir(), 'jobs/' + id);
}

export function loadJob(id) {
  try { return JSON.parse(fs.readFileSync(path.join(jobDir(id), 'state.json'), 'utf8')); } catch { return null; }
}

export function saveJob(job) {
  job.updated = Date.now();
  ensureDir(workDir(), 'jobs/' + job.job_id);
  writeFileIn(workDir(), `jobs/${job.job_id}/state.json`, JSON.stringify(job, null, 1));
  return job;
}

export function listJobs(limit = 30) {
  let names = [];
  try { names = fs.readdirSync(jail(workDir(), 'jobs')).filter(n => JOB_RE.test(n)); } catch { return []; }
  return names.map(loadJob).filter(Boolean).sort((a, b) => (b.updated || 0) - (a.updated || 0)).slice(0, limit);
}

export function outDir() { return ensureDir(workDir(), 'out'); }
