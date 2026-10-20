#!/usr/bin/env node
// 숏템 연결기(launcher) — Claude Desktop(.mcpb)과 Claude Code(플러그인) 공용. 한 벌만 둔다.
// 하는 일: 설치팩이 깐 폴더에서 server/index.js 를 찾아 동봉 node 로 실행(stdio 그대로 연결).
// 설치 폴더가 없으면: "설치팩을 먼저 설치하세요" 도구 1개만 내는 최소 MCP 서버로 돈다.
// 규칙: 서버 응답·인자 문자열을 실행 파일 경로로 쓰지 않는다(경로는 아래 고정 규칙으로만 정한다).
'use strict';
const fs = require('fs');
const path = require('path');
const os = require('os');
const { spawn } = require('child_process');

const LAUNCHER_VERSION = '1.0.0';

function installHome() {
  // 1) 설치 프로그램이 등록한 환경변수(윈도: 사용자 환경변수, 맥: postinstall 이 남김)
  //    ★SHORTEM_HOME 은 서버 쪽 '사용자 자료 폴더(~/.shortem)' 이름이라 설치 폴더에는 SHORTEM_INSTALL 을 쓴다
  const fromEnv = process.env.SHORTEM_INSTALL;
  if (fromEnv && fs.existsSync(manifestPath(fromEnv))) return fromEnv;
  // 2) 기본 설치 경로(설계 §3-2 · §3-4)
  if (process.platform === 'win32') {
    const base = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
    return path.join(base, 'Shortem');
  }
  if (process.platform === 'darwin') {
    return path.join(os.homedir(), 'Library', 'Application Support', 'Shortem');
  }
  return path.join(os.homedir(), '.local', 'share', 'Shortem');
}

function manifestPath(home) {
  return path.join(home, 'tools', 'tools.manifest.json');
}

function nodeExe(home) {
  return process.platform === 'win32'
    ? path.join(home, 'tools', 'node', 'node.exe')
    : path.join(home, 'tools', 'node', 'bin', 'node');
}

function readInstallInfo(home) {
  try { return JSON.parse(fs.readFileSync(path.join(home, 'install.json'), 'utf8')); } catch (_) { return null; }
}

function problem(home) {
  const server = path.join(home, 'server', 'index.js');
  const node = nodeExe(home);
  if (!fs.existsSync(manifestPath(home))) return 'not_installed';
  if (!fs.existsSync(server)) return 'server_missing';
  if (!fs.existsSync(node)) return 'node_missing';
  const info = readInstallInfo(home);
  if (process.platform === 'darwin' && info && info.arch && info.arch !== process.arch && info.arch === 'arm64') {
    // arm64 설치팩을 Intel 맥에 깐 경우(반대 방향 x64→Apple Silicon 은 Rosetta 로 돈다)
    if (os.cpus().every((c) => !/Apple/i.test(c.model))) return 'arch_mismatch';
  }
  return null;
}

const MESSAGES = {
  not_installed: '숏템 실행 도구가 이 컴퓨터에 아직 없습니다. 이 도구(shortem_setup)를 install: true 로 부르면 숏템 서버에서 바로 받아 깝니다(약 1GB, 설치 프로그램·관리자 권한 필요 없음). 라이선스 키가 설정에 없으면 license_key 로 함께 주세요.',
  server_missing: '숏템 설치 폴더가 손상됐습니다(서버 파일 없음). 이 도구를 install: true 로 다시 부르면 새로 받아 깝니다.',
  node_missing: '숏템 설치 폴더가 손상됐습니다(실행 도구 없음). 이 도구를 install: true 로 다시 부르면 새로 받아 깝니다.',
  arch_mismatch: '이 맥(Intel)과 다른 종류(Apple Silicon용) 설치팩이 깔렸습니다. 페이지에서 \'맥 Intel(x64)\' 설치팩을 받아 다시 설치해 주세요.',
};

function runServer(home) {
  // 서버 계약(shortem_client/server/tools_paths.js): 실행 도구 폴더 = SHORTEM_TOOLS, 그 안 tools.manifest.json
  const env = Object.assign({}, process.env, {
    SHORTEM_INSTALL: home,
    SHORTEM_TOOLS: path.join(home, 'tools'),
    SHORTEM_LAUNCHER: LAUNCHER_VERSION,
  });
  const child = spawn(nodeExe(home), [path.join(home, 'server', 'index.js')], {
    stdio: 'inherit',
    env,
    windowsHide: true,
  });
  const forward = (sig) => { try { child.kill(sig); } catch (_) { /* 이미 끝남 */ } };
  process.on('SIGINT', () => forward('SIGINT'));
  process.on('SIGTERM', () => forward('SIGTERM'));
  child.on('error', (err) => {
    process.stderr.write(`[shortem-launcher] 서버 시작 실패: ${err.code || err.message}\n`);
    process.exit(1);
  });
  child.on('exit', (code, signal) => {
    if (signal) process.exit(1);
    process.exit(code == null ? 1 : code);
  });
}

// ── exe 없이 까기(사장님 10-20 "인증서 없이 스타터킷처럼 바로") ───────────────
//   연결 파일이 키만 들고 서버(/api/claude/install, 판단 = claude_portal.install_info)에서 설치 묶음을 받아 직접 푼다.
//   브라우저로 받지 않으니 '인터넷에서 받은 파일' 표시(Zone.Identifier)가 없고 서명 안 된 exe 를 두 번 누를 일이 없다
//   (10-20 실측: node 로 받은 파일엔 :$DATA 하나뿐). 묶음 내용 = 설치 exe 와 같은 설치 폴더(installer/win/build_win.py make_pack_zip).
//   ★주소 허용 규칙은 server/api.js 와 같은 뜻(SHORTEM_BASE origin + SHORTEM_ASSET_HOSTS) — 설치 전이라 그 파일을 못 부른다.
const https = require('https');
const crypto = require('crypto');
const { execFile } = require('child_process');
// 오래 걸리는 단계(풀기·확인)는 비동기 — 동기로 돌리면 그동안 진행률 질문에 답을 못 한다(10-20 시험에서 진행 단계가 '끝'만 보였다)
const run = (cmd, args, opts) => new Promise((res, rej) => execFile(cmd, args, Object.assign({ windowsHide: true, maxBuffer: 16 << 20 }, opts), (e, out, err) => (e ? rej(new Error(String(err || e.message).trim().slice(-300))) : res(out))));

const baseUrl = () => String(process.env.SHORTEM_BASE || 'https://shoppingshorts.duckdns.org').replace(/\/+$/, '');
function allowedOrigins() {
  const out = new Set([new URL(baseUrl()).origin]);
  for (const h of String(process.env.SHORTEM_ASSET_HOSTS || '').split(',').map((x) => x.trim()).filter(Boolean)) {
    try { out.add(new URL(h.includes('://') ? h : 'https://' + h).origin); } catch (_) { /* 무시 */ }
  }
  return out;
}
function packPlat() {
  if (process.platform === 'win32') return 'win-x64';
  if (process.platform === 'darwin') return process.arch === 'arm64' ? 'mac-arm64' : 'mac-x64';
  return null;
}
function readKey(arg) {
  const k = String(arg || process.env.SHORTEM_LICENSE || '').trim();
  if (k) return k;
  try { return fs.readFileSync(path.join(process.env.SHORTEM_HOME || path.join(os.homedir(), '.shortem'), 'license'), 'utf8').trim(); } catch (_) { return ''; }
}

function get(url, { key, file, onData, hops = 0 } = {}) {
  return new Promise((resolve, reject) => {
    const u = new URL(url, baseUrl() + '/');
    const local = /^(127\.0\.0\.1|localhost)$/.test(u.hostname);       // 시험 서버(shortem_client/test/fake_server.js)
    if (u.protocol !== 'https:' && !local) return reject(new Error('https 주소가 아닙니다'));
    if (!allowedOrigins().has(u.origin)) return reject(new Error('허용하지 않은 주소입니다: ' + u.origin));
    const mod = u.protocol === 'https:' ? https : require('http');
    const req = mod.get(u, { headers: key ? { Authorization: 'Bearer ' + key } : {}, timeout: 60000 }, (res) => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode) && res.headers.location && hops < 3) {
        res.resume();
        return resolve(get(new URL(res.headers.location, u).href, { key: null, file, onData, hops: hops + 1 }));
      }
      if (!file) {
        let b = '';
        res.setEncoding('utf8');
        res.on('data', (c) => { b += c; if (b.length > 1 << 20) req.destroy(new Error('응답이 너무 큽니다')); });
        res.on('end', () => { try { resolve(JSON.parse(b)); } catch (_) { reject(new Error('서버 응답을 읽지 못했습니다(' + res.statusCode + ')')); } });
        return;
      }
      if (res.statusCode !== 200) { res.resume(); return reject(new Error('받기 실패 ' + res.statusCode)); }
      const h = crypto.createHash('sha256');
      const out = fs.createWriteStream(file);
      let n = 0;
      res.on('data', (c) => { h.update(c); n += c.length; if (onData) onData(n); });
      res.pipe(out);
      out.on('finish', () => resolve({ bytes: n, sha256: h.digest('hex') }));
      out.on('error', reject);
      res.on('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('서버 응답이 없습니다')));
    req.on('error', reject);
  });
}

function desktopDir() {
  for (const n of ['Desktop', '바탕 화면', 'OneDrive/Desktop', 'OneDrive/바탕 화면']) {
    const d = path.join(os.homedir(), n);
    if (fs.existsSync(d)) return d;
  }
  return null;
}

async function unpack(zip, dst) {
  fs.mkdirSync(dst, { recursive: true });
  if (process.platform === 'win32') {
    const tar = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32', 'tar.exe');   // 윈도 10 1803+ 내장(bsdtar, zip 읽음)
    await run(tar, ['-xf', zip, '-C', dst], { timeout: 30 * 60 * 1000 });
  } else {
    await run('/usr/bin/ditto', ['-x', '-k', zip, dst], { timeout: 30 * 60 * 1000 });
  }
}

const job = { phase: 'idle', got: 0, size: 0, version: '', error: '' };

async function installPack(home, key, saveKey) {
  const plat = packPlat();
  if (!plat) throw new Error('이 컴퓨터 종류(' + process.platform + ')는 아직 지원하지 않습니다');
  job.phase = 'asking';
  const info = await get('/api/claude/install?plat=' + plat, { key });
  if (!info || info.ok === false) throw new Error((info && (info.msg || info.code)) || '서버가 설치를 거절했습니다');
  if (!info.ready) throw new Error('설치 묶음이 아직 서버에 준비되지 않았습니다 — 잠시 뒤 다시 해 주세요');
  if (!/^\d+\.\d+\.\d+$/.test(String(info.version)) || !/^[0-9a-f]{64}$/.test(String(info.sha256))) throw new Error('서버 응답이 올바르지 않습니다');
  job.version = info.version;
  job.size = Number(info.size) || 0;
  const parent = path.dirname(home);
  fs.mkdirSync(parent, { recursive: true });
  const zip = path.join(parent, 'Shortem.download.part');
  job.phase = 'downloading';
  const got = await get(info.url, { key: null, file: zip, onData: (n) => { job.got = n; } });
  if (got.sha256 !== info.sha256 || (job.size && got.bytes !== job.size)) {
    try { fs.unlinkSync(zip); } catch (_) {}
    throw new Error('받은 묶음 확인값이 다릅니다 — 다시 시도해 주세요');
  }
  job.phase = 'unpacking';
  const fresh = home + '.new';
  fs.rmSync(fresh, { recursive: true, force: true });
  await unpack(zip, fresh);
  if (!fs.existsSync(manifestPath(fresh)) || !fs.existsSync(path.join(fresh, 'server', 'index.js'))) throw new Error('풀린 묶음이 덜 찼습니다');
  job.phase = 'placing';
  let old = null;
  if (fs.existsSync(home)) { old = home + '.old-' + Date.now(); fs.renameSync(home, old); }
  try { fs.renameSync(fresh, home); } catch (e) { if (old) fs.renameSync(old, home); throw e; }
  job.phase = 'checking';
  const args = [path.join(home, 'postinstall.js'), '--home', home, '--version', info.version];
  const desk = desktopDir();
  if (desk) args.push('--desktop', desk);
  await run(nodeExe(home), args, { timeout: 10 * 60 * 1000 });   // 실행 도구 sha256 대조·시작.md
  if (saveKey) {   // 키를 도구 인자로만 받았으면 설치본의 주인 함수(server/license.js saveLicense)로 저장
    const lic = require('url').pathToFileURL(path.join(home, 'server', 'license.js')).href;
    await run(nodeExe(home), ['--input-type=module', '-e', `const m=await import(${JSON.stringify(lic)});m.saveLicense(process.env.SHORTEM_K)`],
      { timeout: 60000, env: Object.assign({}, process.env, { SHORTEM_K: key }) });
  }
  try { fs.unlinkSync(zip); } catch (_) {}
  if (old) { try { fs.rmSync(old, { recursive: true, force: true }); } catch (_) { /* 다음에 */ } }
  job.phase = 'done';
}

// 진행 중·끝이면 그 상태, install 요청이면 시작, 아니면 null(종전 안내)
function installStatus(home, args) {
  if (job.phase === 'done') return { ok: true, text: `숏템 설치를 마쳤습니다(${job.version}). Claude 를 완전히 껐다 켜면 숏템 도구가 모두 보입니다.` };
  if (job.phase !== 'idle' && job.phase !== 'failed') {
    const pct = job.size ? Math.floor((job.got / job.size) * 100) : 0;
    const what = { asking: '서버에 확인하는 중', downloading: `받는 중 ${Math.round(job.got / 1e6)}/${Math.round(job.size / 1e6)}MB (${pct}%)`,
      unpacking: '푸는 중', placing: '자리 잡는 중', checking: '실행 도구 확인하는 중' }[job.phase] || job.phase;
    return { ok: true, text: `숏템 설치 진행 중 — ${what}. 30초쯤 뒤 이 도구를 다시 불러 진행을 확인하세요.` };
  }
  if (!(args && args.install)) return null;
  const key = readKey(args.license_key);
  if (!key) return { ok: false, text: '라이선스 키가 필요합니다. 숏템메이커 \'클로드형\' 페이지에서 키(SHORTEM-L1. 로 시작)를 복사해 license_key 로 주세요.' };
  job.phase = 'asking'; job.error = ''; job.got = 0;
  installPack(home, key, !!(args.license_key && !process.env.SHORTEM_LICENSE)).catch((e) => {
    job.phase = 'failed';
    job.error = String((e && e.message) || e).slice(0, 300);
    process.stderr.write('[shortem-launcher] 설치 실패: ' + job.error + '\n');
  });
  return { ok: true, text: '숏템 설치를 시작했습니다(약 1GB). 30초쯤 뒤 이 도구를 다시 불러 진행을 확인하세요.' };
}

// ── 설치 전용 최소 MCP(stdio, 줄 단위 JSON-RPC) ───────────────────────────
function runFallback(reason, home) {
  const msg = MESSAGES[reason] || MESSAGES.not_installed;
  const tool = {
    name: 'shortem_setup',
    title: '숏템 준비 점검',
    description: '숏템 준비 점검·설치. 실행 도구가 없으면 install: true 로 불러 숏템 서버에서 받아 깝니다(진행 중이면 다시 불러 진행률 확인).',
    inputSchema: { type: 'object', properties: { selftest: { type: 'boolean' }, install: { type: 'boolean' },
      license_key: { type: 'string', description: '설정에 키가 없을 때만' } }, additionalProperties: false },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  };
  const send = (obj) => process.stdout.write(JSON.stringify(obj) + '\n');
  const reply = (id, result) => send({ jsonrpc: '2.0', id, result });
  const error = (id, code, message) => send({ jsonrpc: '2.0', id, error: { code, message } });
  process.stderr.write(`[shortem-launcher] 설치팩 없음(${reason}) — 안내 전용으로 동작. 찾은 경로: ${home}\n`);

  let buf = '';
  process.stdin.setEncoding('utf8');
  process.stdin.on('data', (chunk) => {
    buf += chunk;
    let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl).trim();
      buf = buf.slice(nl + 1);
      if (!line) continue;
      let req;
      try { req = JSON.parse(line); } catch (_) { error(null, -32700, 'Parse error'); continue; }
      const { id, method, params } = req;
      if (id === undefined || id === null) continue; // 알림은 답하지 않는다
      if (method === 'initialize') {
        reply(id, {
          protocolVersion: (params && params.protocolVersion) || '2025-06-18',
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: 'shortem', title: '숏템', version: LAUNCHER_VERSION },
          instructions: msg,
        });
      } else if (method === 'ping') {
        reply(id, {});
      } else if (method === 'tools/list') {
        reply(id, { tools: [tool] });
      } else if (method === 'tools/call') {
        const name = params && params.name;
        if (name !== 'shortem_setup') { error(id, -32602, `알 수 없는 도구: ${name}`); continue; }
        const st = ['not_installed', 'server_missing', 'node_missing'].includes(reason) ? installStatus(home, params && params.arguments) : null;
        if (st || job.phase === 'failed') {
          const failed = !st && job.phase === 'failed';
          const text = failed ? `숏템 설치가 멈췄습니다: ${job.error} — install: true 로 다시 부르면 처음부터 다시 받습니다.` : st.text;
          reply(id, { content: [{ type: 'text', text }], structuredContent: { ok: !failed && st.ok, phase: job.phase, text }, isError: failed || !st.ok });
          continue;
        }
        reply(id, {
          content: [{ type: 'text', text: msg }],
          structuredContent: { ok: false, fail: { where: '설치', why: msg, fix: '설치팩 설치 후 Claude 다시 시작', retry_ok: true } },
          isError: true,
        });
      } else if (method === 'resources/list') {
        reply(id, { resources: [] });
      } else if (method === 'prompts/list') {
        reply(id, { prompts: [] });
      } else {
        error(id, -32601, `Method not found: ${method}`);
      }
    }
  });
  process.stdin.on('end', () => process.exit(0));
}

// 켤 때 자동 업데이트 — 바꾸기 쪽(관제 234 5판). 받기는 서버(server/updater.js)가 지난번에 <설치>/_update/<판>/ 에 풀어 두었다.
//   서버를 띄우기 전에 server·engine 을 새 판으로 바꾼다. 하나라도 실패하면 되돌리고 그대로 예전 판으로 뜬다.
function applyPending(home) {
  const up = path.join(home, '_update');
  const pend = path.join(up, 'pending.json');
  let p;
  try { p = JSON.parse(fs.readFileSync(pend, 'utf8')); } catch (_) { return null; }
  if (!/^\d+\.\d+\.\d+$/.test(String(p.version)) || p.dir !== p.version) { try { fs.unlinkSync(pend); } catch (_) {} return null; }
  const src = path.join(up, p.dir);
  const old = path.join(up, 'old-' + Date.now());
  const moved = [];
  try {
    fs.mkdirSync(old, { recursive: true });
    for (const d of ['server', 'engine']) {
      if (!fs.existsSync(path.join(src, d))) throw new Error('덜 찬 업데이트: ' + d);
      if (fs.existsSync(path.join(home, d))) { fs.renameSync(path.join(home, d), path.join(old, d)); moved.push(d); }
      // 서버 node_modules 는 묶음에 있다(빌드가 만든 server/ 통째)
      fs.renameSync(path.join(src, d), path.join(home, d));
    }
    fs.copyFileSync(path.join(src, 'app_version.json'), path.join(home, 'app_version.json'));
    fs.unlinkSync(pend);
    fs.rmSync(src, { recursive: true, force: true });
    try { fs.rmSync(old, { recursive: true, force: true }); } catch (_) { /* 다음에 */ }
    return p.version;
  } catch (e) {
    for (const d of moved) {                      // 되돌리기
      try { fs.rmSync(path.join(home, d), { recursive: true, force: true }); fs.renameSync(path.join(old, d), path.join(home, d)); } catch (_) {}
    }
    try { fs.unlinkSync(pend); } catch (_) {}
    process.stderr.write('[숏템] 업데이트 적용 실패 — 예전 판으로 시작합니다: ' + e.message + '\n');
    return null;
  }
}

function main() {
  const home = installHome();
  if (!process.argv.includes('--where') && fs.existsSync(path.join(home, '_update', 'pending.json'))) applyPending(home);
  if (process.argv.includes('--where')) {
    process.stdout.write(JSON.stringify({ home, node: nodeExe(home), problem: problem(home) }) + '\n');
    return;
  }
  const p = problem(home);
  if (p) runFallback(p, home);
  else runServer(home);
}

if (require.main === module) main();
else module.exports = { applyPending, installHome, installPack, installStatus, job };   // 시험(shortem_client/test/update.test.js)이 바꾸기만 부른다
