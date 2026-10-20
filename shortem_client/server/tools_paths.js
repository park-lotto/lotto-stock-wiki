// 실행 바이너리 고정(설계 §7-5). 부를 수 있는 것은 아래 이름뿐이고, 경로는 설치 폴더의
// tools.manifest.json 에 적힌 상대 경로 + sha256 대조로만 정한다. PATH 탐색은 개발 모드(SHORTEM_DEV_TOOLS=1)만.
//   ★서버 응답·payload 문자열이 argv[0] 이 되는 길은 없다 — run() 은 이름표(TOOL_NAMES)만 받는다.
import crypto from 'node:crypto';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';

export const TOOL_NAMES = Object.freeze(['ffmpeg', 'ffprobe', 'chrome', 'python', 'ytdlp']);
const EXE = process.platform === 'win32' ? '.exe' : '';

export function toolsDir() {
  if (process.env.SHORTEM_TOOLS) return path.resolve(process.env.SHORTEM_TOOLS);
  if (process.platform === 'win32') return path.join(process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local'), 'Shortem', 'tools');
  if (process.platform === 'darwin') return path.join(os.homedir(), 'Library', 'Application Support', 'Shortem', 'tools');
  return path.join(os.homedir(), '.local', 'share', 'Shortem', 'tools');
}

export const devMode = () => process.env.SHORTEM_DEV_TOOLS === '1';

function sha256File(p) {
  const h = crypto.createHash('sha256');
  const fd = fs.openSync(p, 'r');
  try {
    const buf = Buffer.allocUnsafe(1 << 20);
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
  } finally { fs.closeSync(fd); }
  return h.digest('hex');
}

function onPath(name) {
  const dirs = String(process.env.PATH || '').split(path.delimiter).filter(Boolean);
  const exts = process.platform === 'win32' ? ['.exe', '.cmd', ''] : [''];
  for (const d of dirs) for (const e of exts) {
    const p = path.join(d, name + e);
    try { if (fs.statSync(p).isFile()) return p; } catch { /* 없음 */ }
  }
  return null;
}

function devChrome() {
  const root = path.join(os.homedir(), '.cache', 'puppeteer', 'chrome-headless-shell');
  let vers = [];
  try { vers = fs.readdirSync(root); } catch { return null; }
  const key = v => v.replace(/^[^-]*-/, '').split('.').map(Number);
  vers.sort((a, b) => { const x = key(a), y = key(b); for (let i = 0; i < 4; i++) if ((x[i] || 0) !== (y[i] || 0)) return (y[i] || 0) - (x[i] || 0); return 0; });
  for (const v of vers) {
    for (const sub of fs.readdirSync(path.join(root, v))) {
      const p = path.join(root, v, sub, 'chrome-headless-shell' + EXE);
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
}

let cache = null;   // {resolved:{name:{path,version}}, problems:[...]}

// 설치 폴더 manifest 모양: {"version":"1.0.0","tools":{"ffmpeg":{"path":"ffmpeg/bin/ffmpeg.exe","sha256":"…","version":"…"}, …}}
export function resolveTools({ force = false } = {}) {
  if (cache && !force) return cache;
  const resolved = {}, problems = [];
  if (devMode()) {
    const map = { ffmpeg: onPath('ffmpeg'), ffprobe: onPath('ffprobe'), chrome: devChrome(), python: onPath('python') || onPath('python3'), ytdlp: onPath('yt-dlp') };
    for (const n of TOOL_NAMES) {
      if (map[n]) resolved[n] = { path: map[n], version: 'dev', verified: false };
      else problems.push({ tool: n, why: '개발 모드에서 찾지 못했습니다' });
    }
    cache = { resolved, problems, mode: 'dev', dir: null };
    return cache;
  }
  const dir = toolsDir();
  const manPath = path.join(dir, 'tools.manifest.json');
  let man = null;
  try { man = JSON.parse(fs.readFileSync(manPath, 'utf8')); } catch { /* 없음 */ }
  if (!man || typeof man.tools !== 'object') {
    for (const n of TOOL_NAMES) problems.push({ tool: n, why: '설치 목록(tools.manifest.json)이 없습니다' });
    cache = { resolved, problems, mode: 'install', dir };
    return cache;
  }
  for (const n of TOOL_NAMES) {
    const ent = man.tools[n];
    if (!ent || typeof ent.path !== 'string' || typeof ent.sha256 !== 'string') { problems.push({ tool: n, why: '설치 목록에 없습니다' }); continue; }
    const rel = ent.path.replace(/\\/g, '/');
    if (rel.split('/').includes('..') || path.isAbsolute(rel)) { problems.push({ tool: n, why: '설치 목록 경로가 올바르지 않습니다' }); continue; }
    const p = path.join(dir, ...rel.split('/'));
    if (!fs.existsSync(p)) { problems.push({ tool: n, why: '파일이 없습니다' }); continue; }
    let got;
    try { got = sha256File(p); } catch { problems.push({ tool: n, why: '파일을 읽지 못했습니다' }); continue; }
    if (got.toLowerCase() !== ent.sha256.toLowerCase()) { problems.push({ tool: n, why: '파일 지문이 설치본과 다릅니다' }); continue; }
    resolved[n] = { path: p, version: String(ent.version || ''), verified: true };
  }
  cache = { resolved, problems, mode: 'install', dir };
  return cache;
}

export function toolPath(name) {
  if (!TOOL_NAMES.includes(name)) throw new Error('허용되지 않은 실행 도구');
  const t = resolveTools().resolved[name];
  if (!t) { const e = new Error('실행 도구가 준비되지 않았습니다 — 설치팩을 다시 실행하세요'); e.code = 'tool_missing'; e.tool = name; throw e; }
  return t.path;
}

// 고정 바이너리만 실행. shell 없음. args 는 문자열 배열(널 문자 금지).
export function run(name, args, { timeoutMs = 30 * 60 * 1000, cwd, input, onStderr, env } = {}) {
  const exe = toolPath(name);
  if (!Array.isArray(args) || args.some(a => typeof a !== 'string' || a.includes('\0'))) return Promise.reject(new Error('잘못된 실행 인자'));
  return new Promise((resolve, reject) => {
    const child = spawn(exe, args, { shell: false, windowsHide: true, cwd, env: env || process.env, stdio: ['pipe', 'pipe', 'pipe'] });
    const out = [], err = [];
    let errLen = 0;
    const timer = setTimeout(() => { try { child.kill('SIGKILL'); } catch { /* 끝남 */ } }, timeoutMs);
    child.stdout.on('data', d => out.push(d));
    child.stderr.on('data', d => { if (errLen < 4 << 20) { err.push(d); errLen += d.length; } if (onStderr) onStderr(String(d)); });
    child.on('error', e => { clearTimeout(timer); reject(e); });
    child.on('close', code => {
      clearTimeout(timer);
      resolve({ code, stdout: Buffer.concat(out), stderr: Buffer.concat(err).toString('utf8') });
    });
    if (input != null) child.stdin.end(input); else child.stdin.end();
  });
}

export async function runOk(name, args, opts) {
  const r = await run(name, args, opts);
  if (r.code !== 0) {
    const e = new Error(`${name} 실행 실패`);
    e.code = 'tool_failed'; e.tool = name; e.detail = r.stderr.slice(-1500);   // detail 은 로컬 진단용 — 모델 응답에 안 싣는다
    throw e;
  }
  return r;
}
