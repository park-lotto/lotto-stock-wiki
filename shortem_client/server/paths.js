// 숏템 로컬 MCP — 폴더 자리와 경로 감옥(설계 §7-5).
//   쓰기는 두 뿌리 안만: SHORTEM_HOME(~/.shortem) · SHORTEM_WORK(바탕화면/숏템작업).
//   `..`·심링크·뿌리 밖 절대경로는 거부한다. 판단은 jail() 한 곳.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

export function homeDir() {
  return path.resolve(process.env.SHORTEM_HOME || path.join(os.homedir(), '.shortem'));
}

function desktopDir() {
  const h = os.homedir();
  for (const name of ['Desktop', '바탕 화면', 'OneDrive/Desktop', 'OneDrive/바탕 화면']) {
    const p = path.join(h, name);
    try { if (fs.statSync(p).isDirectory()) return p; } catch { /* 없음 */ }
  }
  return h;
}

export function workDir() {
  return path.resolve(process.env.SHORTEM_WORK || path.join(desktopDir(), '숏템작업'));
}

export class JailError extends Error {
  constructor(msg) { super(msg); this.code = 'jail'; }
}

// root 안의 상대 경로 rel 을 절대 경로로. rel 에 `..`·절대경로·널 문자가 있거나,
// 뿌리부터 이미 있는 단계 중 하나라도 심링크(또는 정션)면 거부.
export function jail(root, rel = '') {
  const base = path.resolve(root);
  const r = String(rel ?? '');
  if (r.includes('\0')) throw new JailError('경로에 쓸 수 없는 글자가 있습니다');
  if (path.isAbsolute(r) || /^[a-zA-Z]:/.test(r) || r.startsWith('\\\\')) throw new JailError('작업 폴더 밖 절대 경로는 쓸 수 없습니다');
  const parts = r.split(/[\\/]+/).filter(Boolean);
  if (parts.some(p => p === '..')) throw new JailError('상위 폴더(..)로는 나갈 수 없습니다');
  const full = path.resolve(base, ...parts);
  const relCheck = path.relative(base, full);
  if (relCheck.startsWith('..') || path.isAbsolute(relCheck)) throw new JailError('작업 폴더 밖으로는 쓸 수 없습니다');
  // 뿌리 자체와 그 아래 이미 있는 단계마다 심링크 검사
  let cur = base;
  const chain = [base, ...parts.map((_, i) => path.resolve(base, ...parts.slice(0, i + 1)))];
  for (cur of chain) {
    let st;
    try { st = fs.lstatSync(cur); } catch { break; }   // 아직 없는 단계부터는 새로 만든다
    if (st.isSymbolicLink()) throw new JailError('링크(바로가기) 폴더로는 쓸 수 없습니다');
  }
  return full;
}

// 절대 경로 p 가 root 안인가(읽기·검사용). 심링크도 실경로로 따져 본다.
export function inside(root, p) {
  const base = path.resolve(root);
  const full = path.resolve(p);
  const rel = path.relative(base, full);
  if (rel.startsWith('..') || path.isAbsolute(rel)) return false;
  try {
    const real = fs.realpathSync(full), realBase = fs.realpathSync(base);
    const r2 = path.relative(realBase, real);
    return !(r2.startsWith('..') || path.isAbsolute(r2));
  } catch { return true; }   // 아직 없는 파일 — 글자 경로로는 안쪽
}

export function ensureDir(root, rel = '') {
  const p = jail(root, rel);
  fs.mkdirSync(p, { recursive: true });
  return p;
}

// 감옥 안에만 쓰는 쓰기. mode 는 키 파일(0600)용.
export function writeFileIn(root, rel, data, mode) {
  const p = jail(root, rel);
  fs.mkdirSync(path.dirname(p), { recursive: true });
  jail(root, path.relative(path.resolve(root), path.dirname(p)));   // 만든 뒤 다시 확인(경합 방지)
  const tmp = p + '.tmp' + process.pid;
  fs.writeFileSync(tmp, data, mode ? { mode } : undefined);
  fs.renameSync(tmp, p);
  if (mode) { try { fs.chmodSync(p, mode); } catch { /* 윈도는 무시 */ } }
  return p;
}

export function rmIn(root, rel) {
  const p = jail(root, rel);
  if (path.resolve(p) === path.resolve(root)) throw new JailError('뿌리 폴더는 지울 수 없습니다');
  fs.rmSync(p, { recursive: true, force: true });
}
