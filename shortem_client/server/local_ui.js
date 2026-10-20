// 회원 PC 설정·편집 화면(관제 234 5판, 사장님 10-19 "PC 에서 수정을 볼 수 있게 / 저장도 로컬 / 보여주기식 말고").
//   127.0.0.1 에만 열고(밖에서 못 들어온다), 켤 때마다 새 접속 토큰(쿠키)·호스트 검사(남의 웹페이지가 못 부른다).
//   미리보기 = 엔진 렌더러 그 자체(out/scene-style-ui-showcase.html 의 sceneStyle.load) + 엔진이 만든 입력(preview_request.py).
//   설정 = local_settings 한 곳(Claude 의 shortem_settings 와 같은 파일) — 화면은 3초마다 다시 읽어 Claude 가 바꾼 것도 보인다.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import { homeDir, workDir, jail } from './paths.js';
import { engineRoot, engineTool } from './engine_bridge.js';
import { readSettings, packFor, savePack, select, resetPack, catalog, PID_RE } from './local_settings.js';
import { rentPreset } from './preset_rent.js';
import { makeStep } from './make_flow.js';
import { openLogin, status as loginStatus, PLATFORMS } from './logins.js';
import { deliverStatus, linkTelegram, confirmTelegram, setDeliver, deliverFinal } from './deliver.js';
import { keyStatuses, saveKey } from './engine/voice.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const STATIC_OK = /^(out|shopping_shorts\/static)\/[0-9A-Za-z가-힣_.\-/]+\.(html|js|css|woff2?|ttf|otf|png|jpe?g|webp|gif|svg|json)$/;
const TYPES = { html: 'text/html; charset=utf-8', js: 'text/javascript; charset=utf-8', css: 'text/css; charset=utf-8', json: 'application/json',
  woff: 'font/woff', woff2: 'font/woff2', ttf: 'font/ttf', otf: 'font/otf', png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg',
  webp: 'image/webp', gif: 'image/gif', svg: 'image/svg+xml', mp4: 'video/mp4' };
let ui = null;   // {server, port, token, url}

function presets() {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), 'profiles.json'), 'utf8')).presets || []; } catch { return []; }
}

// 완성본 목록 — make_flow 가 완성본 옆에 남긴 표식(<영상>.json: sid·소재 폴더·프리셋)
export function videos() {
  const dir = path.join(workDir(), '완성본');
  let names = [];
  try { names = fs.readdirSync(dir).filter(n => n.endsWith('.mp4')); } catch { return []; }
  return names.map(n => {
    let meta = {};
    try { meta = JSON.parse(fs.readFileSync(path.join(dir, n + '.json'), 'utf8')); } catch { /* 표식 없는 옛 완성본 */ }
    let at = 0;
    try { at = fs.statSync(path.join(dir, n)).mtimeMs; } catch { /* 없음 */ }
    return { name: n, at, sid: meta.sid || null, preset: meta.preset || null, title: meta.title || n.replace(/_[0-9a-f]{12}\.mp4$/, '') };
  }).sort((a, b) => b.at - a.at);
}

function send(res, code, body, type = 'application/json; charset=utf-8', extra = {}) {
  const b = Buffer.isBuffer(body) ? body : Buffer.from(typeof body === 'string' ? body : JSON.stringify(body));
  res.writeHead(code, { 'Content-Type': type, 'Content-Length': b.length, 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...extra });
  res.end(b);
}

async function readBody(req) {
  const ch = [];
  let n = 0;
  for await (const d of req) { n += d.length; if (n > 200000) return null; ch.push(d); }
  try { return JSON.parse(Buffer.concat(ch).toString('utf8') || '{}'); } catch { return null; }
}

function cookieOk(req, token) {
  const m = String(req.headers.cookie || '').match(/(?:^|;\s*)st=([0-9a-f]{32})/);
  return !!m && crypto.timingSafeEqual(Buffer.from(m[1]), Buffer.from(token));
}

function serveFile(req, res, file, type) {
  let st;
  try { st = fs.statSync(file); } catch { return send(res, 404, { error: '없음' }); }
  const range = String(req.headers.range || '').match(/^bytes=(\d*)-(\d*)$/);
  if (range && type === TYPES.mp4) {
    const start = range[1] ? +range[1] : 0, end = range[2] ? Math.min(+range[2], st.size - 1) : st.size - 1;
    if (start > end) return send(res, 416, { error: '범위' });
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${st.size}`, 'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1 });
    return fs.createReadStream(file, { start, end }).pipe(res);
  }
  res.writeHead(200, { 'Content-Type': type, 'Content-Length': st.size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache', 'X-Content-Type-Options': 'nosniff' });
  fs.createReadStream(file).pipe(res);
}

async function preview({ preset, patch, video }) {
  if (!PID_RE.test(String(preset || ''))) return { error: '프리셋을 고르세요' };
  let presetPath = process.env.SHORTEM_DEV_PRESET || null;
  if (!presetPath) {
    try { presetPath = (await rentPreset({ engineRoot: engineRoot(), presetId: preset, kind: 'ui' })).presetPath; }
    catch (e) { return { error: e.msg || e.message || '프리셋을 받지 못했습니다', code: e.code }; }
  }
  if (!presetPath) return { error: '개발 PC 입니다 — SHORTEM_DEV_PRESET 에 엔진 프리셋 경로를 주세요' };
  const base = await packFor(preset);
  const pack = patch ? JSON.parse(JSON.stringify(Object.assign({}, base))) : base;
  if (patch) for (const [k, v] of Object.entries(patch)) pack[k] = (v && typeof v === 'object' && !Array.isArray(v)) ? { ...(pack[k] || {}), ...v } : v;
  let topicDir = null;
  const v = video ? videos().find(x => x.name === video) : null;
  if (v && v.sid) {
    try { topicDir = JSON.parse(fs.readFileSync(path.join(workDir(), '완성본', v.name + '.json'), 'utf8')).topic_dir || null; } catch { topicDir = null; }
  }
  const r = await engineTool('preview', { preset: presetPath, pack, ...(topicDir ? { topic_dir: topicDir } : {}) });
  return r.error ? { error: r.error } : { snapshot: r.snapshot, context: r.context, applied: r.applied, title: r.title };
}

async function route(req, res, token, port) {
  const host = String(req.headers.host || '');
  if (host !== `127.0.0.1:${port}` && host !== `localhost:${port}`) return send(res, 403, { error: '이 PC 화면에서만 열 수 있습니다' });
  const u = new URL(req.url, `http://${host}`);
  if (u.pathname === '/' && req.method === 'GET') {
    const t = u.searchParams.get('t') || '';
    if (t.length === 32 && crypto.timingSafeEqual(Buffer.from(t.padEnd(32, '0').slice(0, 32)), Buffer.from(token))) {
      return send(res, 302, '', 'text/plain', { Location: '/', 'Set-Cookie': `st=${token}; HttpOnly; SameSite=Strict; Path=/` });
    }
    if (!cookieOk(req, token)) return send(res, 403, '숏템 Claude 에서 shortem_settings(action="open") 으로 다시 여세요', 'text/plain; charset=utf-8');
    return serveFile(req, res, path.join(HERE, 'ui', 'index.html'), TYPES.html);
  }
  if (!cookieOk(req, token)) return send(res, 403, { error: '접속 토큰이 없습니다' });
  if (u.pathname.startsWith('/r/') && req.method === 'GET') {      // 엔진 렌더러 정적 파일(화면·글꼴만)
    const rel = decodeURIComponent(u.pathname.slice(3));
    if (!STATIC_OK.test(rel) || rel.includes('..')) return send(res, 404, { error: '없음' });
    const file = path.resolve(engineRoot(), rel);
    if (!file.startsWith(path.resolve(engineRoot()) + path.sep)) return send(res, 404, { error: '없음' });
    return serveFile(req, res, file, TYPES[rel.split('.').pop().toLowerCase()] || 'application/octet-stream');
  }
  if (u.pathname.startsWith('/v/') && req.method === 'GET') {      // 완성본 보기
    const name = decodeURIComponent(u.pathname.slice(3));
    if (!videos().some(v => v.name === name)) return send(res, 404, { error: '없음' });
    return serveFile(req, res, path.join(workDir(), '완성본', name), TYPES.mp4);
  }
  // 렌더러 편집기 쪽 '내 로고' 목록(미리보기에는 안 쓰인다) — 서버를 부르지 않게 빈 목록
  if (u.pathname === '/api/produce/scene-style/logo' && req.method === 'GET') return send(res, 200, { items: [] });
  if (!u.pathname.startsWith('/api/')) return send(res, 404, { error: '없음' });
  if (req.method === 'POST' && req.headers['x-shortem-ui'] !== '1') return send(res, 403, { error: '화면에서만 바꿀 수 있습니다' });
  if (u.pathname === '/api/state' && req.method === 'GET') {
    const s = readSettings();
    const list = presets();
    const cur = s.current && list.some(p => p.id === s.current) ? s.current : (list[0] && list[0].id) || null;
    let cat = null, pack = null, err = null;
    try { cat = await catalog(); pack = cur ? await packFor(cur) : null; } catch (e) { err = String(e.message || e); }
    const changed = cur ? ((s.channels[cur] || {}).pack || {}) : {};
    return send(res, 200, { presets: list, current: cur, pack, changed, catalog: cat && { ...cat, default_pack: undefined, preset_defaults: undefined }, videos: videos(), error: err, logins: loginStatus(), deliver: deliverStatus(), keys: keyStatuses(),
      stamp: (s.channels[cur] || {}).updated || 0 });
  }
  const body = await readBody(req);
  if (!body) return send(res, 400, { error: '요청 모양이 다릅니다' });
  if (u.pathname === '/api/select') return send(res, 200, { ok: select(body.preset) });
  if (u.pathname === '/api/save') return send(res, 200, await savePack(body.preset, body.patch));
  if (u.pathname === '/api/reset') { if (PID_RE.test(String(body.preset || ''))) resetPack(body.preset); return send(res, 200, { ok: true }); }
  if (u.pathname === '/api/preview') return send(res, 200, await preview(body));
  if (u.pathname === '/api/login') return send(res, 200, PLATFORMS[body.platform] ? await openLogin(body.platform) : { ok: false, why: '모르는 곳입니다' });
  // 완성본 받기(텔레그램·구글 드라이브) — 판단은 deliver.js. 봇 토큰은 이 화면에만 넣는다(채팅에 붙여 넣지 않게)
  const km = u.pathname.match(/^\/api\/key\/([a-z_]{2,20})$/);
  if (km) return send(res, 200, saveKey(km[1], body.key));   // 회원 본인 키(목록 = voice.js KEY_SERVICES)
  if (u.pathname === '/api/deliver/link') return send(res, 200, await linkTelegram(body.token));
  if (u.pathname === '/api/deliver/confirm') return send(res, 200, await confirmTelegram());
  if (u.pathname === '/api/deliver/set') return send(res, 200, { ok: true, deliver: setDeliver(body) });
  if (u.pathname === '/api/deliver/test') {
    const v = videos().find(x => x.name === body.video) || videos()[0];
    if (!v) return send(res, 200, { error: '보낼 완성본이 아직 없습니다' });
    return send(res, 200, { ok: true, video: v.name, result: await deliverFinal(path.join(workDir(), '완성본', v.name), { title: v.title, force: true }) });
  }
  if (u.pathname === '/api/restyle') {   // 완성본을 지금 설정으로 다시(엔진 calcopy_make.restyle) — AI 판독이 필요하면 Claude 가 이어 받는다
    const v = videos().find(x => x.name === body.video);
    if (!v || !v.sid) return send(res, 200, { error: '이 영상은 다시 만들 수 없습니다(옛 영상)' });
    const o = await makeStep({ step: 'restyle', sid: v.sid, preset: v.preset || readSettings().current });
    return send(res, 200, o.need === 'done' ? { ok: true, done: true } : o.need === 'ai' || o.need === 'wait' ? { ok: true, running: true, need: o.need }
      : { error: (o.fail && o.fail.why) || (o.hints || []).join(' ') || '다시 만들지 못했습니다' });
  }
  return send(res, 404, { error: '없음' });
}

export async function startUi() {
  if (ui) return ui;
  const token = crypto.randomBytes(16).toString('hex');
  const server = http.createServer((req, res) => {
    route(req, res, token, server.address().port).catch(e => { try { send(res, 500, { error: String(e && e.message || e) }); } catch { /* 이미 보냄 */ } });
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(Number(process.env.SHORTEM_UI_PORT || 0), '127.0.0.1', resolve); });
  server.unref();
  const port = server.address().port;
  ui = { server, port, token, url: `http://127.0.0.1:${port}/?t=${token}` };
  return ui;
}

export async function stopUi() { if (ui) { await new Promise(r => ui.server.close(r)); ui = null; } }

// 고객 기본 브라우저로 열기(윈도우 start · 맥 open) — 실패해도 주소는 Claude 가 알려 준다
export function openBrowser(url) {
  if (process.env.SHORTEM_NO_BROWSER === '1') return false;
  try {
    const p = process.platform === 'win32' ? spawn('cmd', ['/c', 'start', '""', url], { shell: false, windowsHide: true, detached: true, stdio: 'ignore' })
      : spawn(process.platform === 'darwin' ? 'open' : 'xdg-open', [url], { detached: true, stdio: 'ignore' });
    p.unref();
    return true;
  } catch { return false; }
}
