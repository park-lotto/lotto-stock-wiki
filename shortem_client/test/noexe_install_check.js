// exe 없이 까는 길 끝까지 시험(사장님 10-20 "인증서 없이 스타터킷처럼 바로") — 저장해 두고 판마다 돌린다.
//   빈 폴더 = 고객 PC(LOCALAPPDATA·USERPROFILE 을 그 안으로) → 연결 파일(installer/mcpb/launcher.js)만 띄워
//   shortem_setup {install:true, license_key} → 진행률을 부르며 기다림 → 다시 띄웠을 때 진짜 숏템 서버 도구가 뜨는가.
//   실행: node test/noexe_install_check.js --zip <dist>/shortem-win-x64-<판>.zip [--sha <sha256>] [--dir <없는 폴더>]
//   출력: JSON 한 줄(ok·걸린 초·도구 이름·설치 폴더 크기). 하나라도 어긋나면 rc=1.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { startFakeServer, makeKey } from './fake_server.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LAUNCHER = path.resolve(HERE, '..', '..', 'installer', 'mcpb', 'launcher.js');
const arg = (n, d) => { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : d; };

const zip = arg('--zip');
if (!zip || !fs.existsSync(zip)) { console.error('--zip <설치 묶음> 이 필요합니다'); process.exit(2); }
const dir = path.resolve(arg('--dir', path.join(os.tmpdir(), 'shortem_noexe_' + Date.now())));
if (fs.existsSync(dir)) { console.error('없는 폴더를 주세요: ' + dir); process.exit(2); }
fs.mkdirSync(path.join(dir, 'Desktop'), { recursive: true });

let sha = arg('--sha');
if (!sha) {
  const h = (await import('node:crypto')).createHash('sha256');
  for await (const c of fs.createReadStream(zip)) h.update(c);
  sha = h.digest('hex');
}
const srv = await startFakeServer({ install: { file: zip, size: fs.statSync(zip).size, sha256: sha, version: '1.0.0' } });
const key = makeKey(12, Math.floor(Date.now() / 1000) + 86400, 1);
const env = { ...process.env, LOCALAPPDATA: path.join(dir, 'AppData', 'Local'), USERPROFILE: dir, HOME: dir,
  SHORTEM_HOME: path.join(dir, '.shortem'), SHORTEM_BASE: srv.url, SHORTEM_INSTALL: '', SHORTEM_LICENSE: '' };

// 연결 파일 하나를 띄워 줄 단위 JSON-RPC 로 묻는다
function mcp() {
  const p = spawn(process.execPath, [LAUNCHER], { env, stdio: ['pipe', 'pipe', 'pipe'] });
  let buf = ''; const wait = new Map(); let seq = 0;
  p.stdout.setEncoding('utf8');
  p.stdout.on('data', (c) => {
    buf += c; let nl;
    while ((nl = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, nl); buf = buf.slice(nl + 1);
      try { const m = JSON.parse(line); if (m.id != null && wait.has(m.id)) { wait.get(m.id)(m); wait.delete(m.id); } } catch { /* 로그 줄 */ }
    }
  });
  p.stderr.on('data', () => {});
  const ask = (method, params = {}) => new Promise((r, j) => {
    const id = ++seq; wait.set(id, r);
    setTimeout(() => { if (wait.has(id)) { wait.delete(id); j(new Error('응답 없음: ' + method)); } }, 120000);
    p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  });
  return { ask, stop: () => { try { p.stdin.end(); p.kill(); } catch { /* 끝 */ } } };
}

const t0 = Date.now();
const out = { dir };
const a = mcp();
await a.ask('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'check', version: '1' } });
const first = await a.ask('tools/list');
out.before_tools = first.result.tools.map((t) => t.name);
const call = (args) => a.ask('tools/call', { name: 'shortem_setup', arguments: args }).then((m) => m.result.structuredContent || {});
let st = await call({ install: true, license_key: key });
out.start = st.text;
const seen = new Set();
while (!['done', 'failed'].includes(st.phase)) {
  await new Promise((r) => setTimeout(r, 3000));
  st = await call({});
  seen.add(st.phase);
  if (Date.now() - t0 > 40 * 60 * 1000) { st = { phase: 'failed', text: '40분 넘음' }; break; }
}
out.phases = [...seen];
out.end = st.text;
a.stop();
const home = path.join(env.LOCALAPPDATA, 'Shortem');
out.installed = fs.existsSync(path.join(home, 'tools', 'tools.manifest.json'));
out.license_saved = fs.existsSync(path.join(env.SHORTEM_HOME, 'license'));
out.desktop_start_md = fs.existsSync(path.join(dir, 'Desktop', '숏템작업', '시작.md'));
out.leftover = fs.readdirSync(path.dirname(home)).filter((n) => n !== 'Shortem');   // .part·.new·.old 남으면 안 된다
out.install_seconds = Math.round((Date.now() - t0) / 1000);

// 다시 켜기 = 진짜 숏템 서버로 뜨는가
if (out.installed) {
  const b = mcp();
  const init = await b.ask('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'check', version: '1' } });
  out.after_server = init.result && init.result.serverInfo;
  const l = await b.ask('tools/list');
  out.after_tools = (l.result.tools || []).map((t) => t.name);
  b.stop();
}
await srv.close();
out.ok = st.phase === 'done' && out.installed && out.license_saved && out.leftover.length === 0
  && (out.after_tools || []).includes('shortem_make') && (out.after_tools || []).length > 1;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
