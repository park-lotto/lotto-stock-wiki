// 디스크가 모자랄 때 지울 후보(숏클 지침 4③ "지울 후보를 보여 주고 고르게 한다 · 회원 파일은 답이 없어도 지우지 않는다") — 판단은 이 파일 한 곳.
//   후보 = 작업 폴더 완성본(영상+표식) · 끝난 편 작업 폴더(창고/flow/<sid>, 다 만들었거나 멈춘 편). 도는 편·다른 파일은 후보가 아니다.
//   지우기는 회원이 고른 id 만(shortem_setup remove) — 경로는 다시 찾아 jail 안에서만 지운다(받은 경로를 믿지 않는다).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { workDir, jail } from './paths.js';
import { dataDir } from './engine_bridge.js';

function sizeOf(p) {
  let n = 0;
  let st;
  try { st = fs.lstatSync(p); } catch { return 0; }
  if (st.isSymbolicLink()) return 0;
  if (!st.isDirectory()) return st.size;
  for (const e of fs.readdirSync(p)) n += sizeOf(path.join(p, e));
  return n;
}
const idOf = p => crypto.createHash('sha1').update(p).digest('hex').slice(0, 8);
const mb = n => Math.round(n / 1e5) / 10;
const days = ms => Math.floor((Date.now() - ms) / 86400000);

function finals() {
  const dir = path.join(workDir(), '완성본');
  let names = [];
  try { names = fs.readdirSync(dir).filter(n => n.toLowerCase().endsWith('.mp4')); } catch { return []; }
  return names.map(n => {
    const p = jail(workDir(), path.join('완성본', n));
    const st = fs.statSync(p);
    const side = ['.json', '.sent.json'].map(x => p + x).filter(x => fs.existsSync(x));
    return { id: idOf(p), kind: '완성본', label: n, bytes: st.size + side.reduce((a, x) => a + sizeOf(x), 0), age_days: days(st.mtimeMs), paths: [p, ...side], root: workDir() };
  });
}

function flowDirs() {
  const root = path.join(dataDir(), 'flow');
  let sids = [];
  try { sids = fs.readdirSync(root); } catch { return []; }
  const out = [];
  for (const sid of sids) {
    let f = {};
    try { f = JSON.parse(fs.readFileSync(path.join(root, sid, 'flow.json'), 'utf8')); } catch { continue; }
    if (!(f.status === 'done' || f.fail)) continue;            // 도는 편·사인 기다리는 편은 지우지 않는다
    const p = jail(dataDir(), path.join('flow', sid));
    out.push({ id: idOf(p), kind: f.status === 'done' ? '끝난 편 작업 폴더' : '멈춘 편 작업 폴더', label: String(f.title || sid).slice(0, 40),
      bytes: sizeOf(p), age_days: days(Number(f.created) || fs.statSync(p).mtimeMs), paths: [p], root: dataDir() });
  }
  return out;
}

// 큰 것부터 — 회원에게 보일 칸만(경로는 내보내지 않는다)
export function cleanupCandidates(limit = 20) {
  return [...flowDirs(), ...finals()].filter(c => c.bytes > 0).sort((a, b) => b.bytes - a.bytes).slice(0, limit);
}
export const showCandidates = list => list.map(({ id, kind, label, bytes, age_days }) => ({ id, kind, label, size_mb: mb(bytes), age_days }));

// 회원이 고른 id 만 지운다 — 후보를 지금 다시 찾아 맞는 것만(없는 id 는 건너뜀)
export function removeCandidates(ids) {
  const want = new Set((ids || []).map(String));
  const done = [];
  for (const c of [...flowDirs(), ...finals()]) {
    if (!want.has(c.id)) continue;
    for (const p of c.paths) {
      const rel = path.relative(c.root, p);
      fs.rmSync(jail(c.root, rel), { recursive: true, force: true });
    }
    done.push({ id: c.id, label: c.label, size_mb: mb(c.bytes) });
  }
  return done;
}
