#!/usr/bin/env node
// tools.manifest.json 쓰기 — 판단 주인 하나(윈도 build_win.py · 맥 build_mac.sh 가 둘 다 이것을 부른다).
// 서버 계약(shortem_client/server/tools_paths.js resolveTools):
//   <설치 폴더>/tools/tools.manifest.json · tools.<이름>.path = tools 폴더 기준 상대 경로 · 이름표 ffmpeg·ffprobe·chrome·python·ytdlp (+node)
//   files[] = 실행 파일·라이브러리 전부의 sha256(설치 검증·자가점검용)
// 쓰는 법: node write_manifest.js --stage <Shortem 폴더> --plat win-x64|darwin-arm64|darwin-x64 --version 1.0.0 --lock <tools.lock.json>
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function arg(n) { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : undefined; }
const stage = path.resolve(arg('--stage'));
const plat = arg('--plat');
const version = arg('--version');
const lock = JSON.parse(fs.readFileSync(arg('--lock'), 'utf8'));
if (!stage || !plat || !version) { console.error('인자 부족: --stage --plat --version --lock'); process.exit(2); }

const WIN = plat.startsWith('win');
// 이름표 → [tools 기준 경로, lock 안 출처 이름]
const MAP = WIN ? {
  node: ['node/node.exe', 'node'],
  ffmpeg: ['ffmpeg/ffmpeg.exe', 'ffmpeg'],
  ffprobe: ['ffmpeg/ffprobe.exe', 'ffmpeg'],
  chrome: ['chrome-headless-shell/chrome-headless-shell.exe', 'chrome-headless-shell'],
  python: ['python/python.exe', 'python'],
  ytdlp: ['yt-dlp/yt-dlp.exe', 'yt-dlp'],
} : {
  node: ['node/bin/node', 'node'],
  ffmpeg: ['ffmpeg/ffmpeg', 'ffmpeg'],
  ffprobe: ['ffmpeg/ffprobe', 'ffmpeg'],
  chrome: ['chrome-headless-shell/chrome-headless-shell', 'chrome-headless-shell'],
  python: ['python/bin/python3', 'python'],
  ytdlp: ['yt-dlp/yt-dlp', 'yt-dlp'],
};

function sourceOf(name) {
  const p = lock[plat] || {};
  if (p[name]) return p[name];
  if (!WIN && name === 'ffmpeg') return lock.mac_ffmpeg_build && lock.mac_ffmpeg_build.ffmpeg;   // 맥 ffmpeg 는 소스 빌드
  if (!WIN && name === 'yt-dlp') return lock.mac_python_extra && lock.mac_python_extra['yt-dlp']; // 맥 yt-dlp 는 동봉 파이썬 패키지
  return null;
}

function sha256(p) { return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'); }

const BIN_EXT = new Set(['.exe', '.dll', '.pyd', '.dat', '.pak', '.bin', '.node', '.dylib', '.so']);
const MACHO = new Set(['feedface', 'feedfacf', 'cefaedfe', 'cffaedfe', 'cafebabe', 'bebafeca']);
function isBinary(p) {
  if (BIN_EXT.has(path.extname(p).toLowerCase())) return true;
  try {
    const fd = fs.openSync(p, 'r'); const b = Buffer.alloc(4); fs.readSync(fd, b, 0, 4, 0); fs.closeSync(fd);
    return MACHO.has(b.toString('hex'));
  } catch (_) { return false; }
}

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isSymbolicLink()) continue;          // 링크는 대상 파일이 따로 기록된다
    if (e.isDirectory()) walk(p, out);
    else if (e.isFile()) out.push(p);
  }
  return out;
}

const tdir = path.join(stage, 'tools');
const tools = {};
for (const [name, [rel, src]] of Object.entries(MAP)) {
  const p = path.join(tdir, ...rel.split('/'));
  if (!fs.existsSync(p)) { console.error(`없음: tools/${rel}`); process.exit(3); }
  const s = sourceOf(src) || {};
  tools[name] = {
    path: rel,
    sha256: sha256(p),
    version: String(s.version || ''),
    source_url: s.url || null,
    source_sha256: s.sha256 || null,
    ...(s.md5_b64 ? { source_md5_b64: s.md5_b64 } : {}),
  };
}
const files = walk(tdir).filter(isBinary).sort().map((p) => {
  const rel = path.relative(tdir, p).split(path.sep).join('/');
  return { path: rel, sha256: sha256(p), size: fs.statSync(p).size, tool: rel.split('/')[0] };
});
const man = {
  schema: 1,
  product: 'shortem',
  version,
  platform: WIN ? 'win32' : 'darwin',
  arch: plat.split('-')[1],
  created: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
  python_packages: Object.fromEntries(Object.entries(lock.python_packages || {}).filter(([k]) => k !== 'requirements')),
  tools,
  files,
};
fs.writeFileSync(path.join(tdir, 'tools.manifest.json'), JSON.stringify(man, null, 2) + '\n', 'utf8');
console.log(JSON.stringify({ ok: true, tools: Object.keys(tools).length, files: files.length }));
