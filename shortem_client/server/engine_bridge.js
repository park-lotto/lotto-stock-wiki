// 엔진 다리 — 고객 PC 의 칼카피 엔진(설치팩 동봉 파이썬 + 엔진 묶음)을 부른다(관제 234 5판).
//   판단은 엔진 한 곳(shopping_shorts/calcopy_make — 후보·고르기·검수·사인·만들기). 여기는 띄우고 JSON 을 읽기만 한다.
//   엔진 AI 는 고객 Claude: 엔진이 요청을 줄 폴더(~/.shortem/ai/<run>/<요청>)에 쓰고 기다린다 → shortem_ai 로 Claude 가 답한다.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { homeDir, ensureDir, jail } from './paths.js';
import { toolPath, toolsDir, devMode } from './tools_paths.js';
import { readKey } from './engine/voice.js';

export const SID_RE = /^[0-9a-f]{12}$/;
export const REQ_RE = /^[0-9]{8}-[0-9]{6}-[0-9A-Za-z가-힣_.-]{1,40}-[0-9a-f]{6}$/;

// 엔진 묶음 자리 — 설치본은 tools 옆 engine/, 개발은 SHORTEM_ENGINE(엔진 트랙 폴더)
export function engineRoot() {
  return path.resolve(process.env.SHORTEM_ENGINE || path.join(toolsDir(), '..', 'engine'));
}
function pythonExe() {
  if (process.env.SHORTEM_PYTHON) return process.env.SHORTEM_PYTHON;
  if (devMode()) return process.platform === 'win32' ? 'py' : 'python3';
  return toolPath('python');
}
export const packRoot = () => path.resolve(process.env.SHORTEM_PACK_ROOT || path.join(toolsDir(), '..', 'packs'));
const aiRoot = () => ensureDir(homeDir(), 'ai');
const dataDir = () => ensureDir(homeDir(), '창고');

function engineEnv(queue, packFile) {
  const env = { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8',
    CALCOPY_GEMINI_BACKEND: 'client', CALCOPY_CUSTOMER_MODE: '1', SHORTEM_LLM_QUEUE: queue,
    CALCOPY_DATA_DIR: dataDir(), CALCOPY_PACK_ROOT: packRoot(), CHANNEL_FIND_CACHE: ensureDir(homeDir(), 'cache', 'channel_find') };
  if (packFile) env.CALCOPY_PACKS = packFile;
  const tc = readKey('typecast');                        // 목소리 = 고객 본인 키(~/.shortem/keys) — 값은 출력하지 않는다
  if (tc) env.TYPECAST_API_KEY = tc;
  const sm = readKey('speechmatics');
  if (sm) { env.SPEECHMATICS_API_KEY = sm; env.SHORTEM_ASR = 'speechmatics'; }
  if (!devMode()) {                                      // 설치본: 동봉 도구만 PATH 에(ffmpeg·yt-dlp + 이 MCP 를 돌리는 동봉 node — 엔진 렌더러가 node 를 부른다)
    const dirs = ['ffmpeg', 'ytdlp'].map(t => { try { return path.dirname(toolPath(t)); } catch { return null; } }).filter(Boolean);
    dirs.push(path.dirname(process.execPath));
    env.PATH = [...new Set(dirs)].join(path.delimiter) + path.delimiter + (process.env.SystemRoot ? path.join(process.env.SystemRoot, 'System32') : '');
    try { env.PUPPETEER_EXECUTABLE_PATH = toolPath('chrome'); } catch { /* 자가점검이 알린다 */ }
  }
  return env;
}

const runs = new Map();   // runId → {proc, done, out, err, queue}

// make.py --json <args…> 를 뒤에서 띄운다. 도구 호출은 waitMs 만 기다린다(AI 요청이 생기면 바로 돌아간다).
export function startRun(args, { packFile } = {}) {
  const runId = 'r' + Date.now().toString(36) + crypto.randomBytes(3).toString('hex');
  const queue = ensureDir(aiRoot(), runId);
  const proc = spawn(pythonExe(), [path.join(engineRoot(), 'tools', 'calcopy', 'make.py'), '--json', ...args],
    { cwd: engineRoot(), env: engineEnv(queue, packFile), shell: false, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
  const r = { runId, queue, proc, done: false, out: [], err: '', code: null, started: Date.now() };
  proc.stdout.on('data', d => r.out.push(d));
  proc.stderr.on('data', d => { if (r.err.length < 200000) r.err += String(d); });
  proc.on('close', code => { r.done = true; r.code = code; });
  proc.on('error', e => { r.done = true; r.code = -1; r.err += String(e && e.message); });
  runs.set(runId, r);
  return r;
}

export function runResult(r) {
  if (!r.done) return null;
  const s = Buffer.concat(r.out).toString('utf8').trim().split('\n').filter(Boolean).pop() || '';
  try { return JSON.parse(s); } catch { return { error: '엔진 결과를 읽지 못했습니다', code: 'engine_output', tail: r.err.slice(-600) }; }
}

export const getRun = id => runs.get(id);
export const activeRuns = () => [...runs.values()].filter(r => !r.done);

export async function waitRun(r, waitMs) {
  const t0 = Date.now();
  while (Date.now() - t0 < waitMs) {
    if (r.done) return runResult(r);
    if (pending().length) return null;                   // AI 요청이 생겼다 — Claude 에게 넘긴다
    await new Promise(res => setTimeout(res, 400));
  }
  return r.done ? runResult(r) : null;
}

// 답을 기다리는 AI 요청 전부(오래된 순)
export function pending() {
  const out = [];
  let rootDirs = [];
  try { rootDirs = fs.readdirSync(aiRoot()); } catch { return out; }
  for (const run of rootDirs) {
    let reqs = [];
    try { reqs = fs.readdirSync(path.join(aiRoot(), run)); } catch { continue; }
    for (const id of reqs) {
      const d = path.join(aiRoot(), run, id);
      if (!REQ_RE.test(id) || fs.existsSync(path.join(d, 'done')) || fs.existsSync(path.join(d, 'answer.json'))) continue;
      let req;
      try { req = JSON.parse(fs.readFileSync(path.join(d, 'request.json'), 'utf8')); } catch { continue; }
      let err = null;
      try { err = JSON.parse(fs.readFileSync(path.join(d, 'error.json'), 'utf8')); } catch { /* 처음 */ }
      out.push({ run, id, dir: d, req, retry_why: err && err.why });
    }
  }
  return out.sort((a, b) => (a.req.made_at || 0) - (b.req.made_at || 0));
}

// 요청 하나 → MCP 내용(글 + 그림). 그림은 이미지 내용으로 바로 싣는다(어느 Claude 앱이든 본다).
export function requestContent(p, maxImages = 40) {
  const lines = [`[AI 요청 ${p.id}] 권장 모델: ${p.req.tier}${p.retry_why ? ` · 앞 답이 틀렸다: ${p.retry_why}` : ''}`,
    '아래 지시대로 JSON 객체 하나만 만들어 shortem_ai(action="answer", id, answer) 로 보내세요. 지어내지 마세요.', '', p.req.prompt];
  const content = [];
  let n = 0;
  for (const part of p.req.parts || []) {
    if (part.kind === 'text') { lines.push('', part.text); continue; }
    if (part.kind === 'image' && n < maxImages) {
      lines.push('', `(그림 ${part.file})`);
      try { content.push({ type: 'image', data: fs.readFileSync(jail(p.dir, part.file)).toString('base64'), mimeType: part.file.endsWith('.png') ? 'image/png' : 'image/jpeg' }); n++; }
      catch { lines.push('(그림을 읽지 못함)'); }
    }
  }
  return [{ type: 'text', text: lines.join('\n') }, ...content];
}

export function answer(id, obj) {
  if (!REQ_RE.test(String(id || ''))) return { ok: false, why: '요청 id 모양이 아닙니다' };
  const p = pending().find(x => x.id === id);
  if (!p) return { ok: false, why: '그 요청이 없거나 이미 답했습니다' };
  if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return { ok: false, why: 'answer 는 JSON 객체여야 합니다' };
  const tmp = jail(p.dir, 'answer.json.tmp');
  fs.writeFileSync(tmp, JSON.stringify(obj));
  fs.renameSync(tmp, jail(p.dir, 'answer.json'));        // 엔진이 쓰다 만 파일을 읽지 않게(10-19 실측 결함)
  return { ok: true };
}
