// 가짜 숏템 서버 — 계약(docs/superpowers/specs/2026-10-18-숏템MCP-api.md) 모양 그대로 응답한다.
//   실제 자산: 이 PC 트랙의 shopping_shorts/static/fonts 글꼴 · assets/sfx_packs 효과음 · assets/bgm_lib 곡.
//   틀: .tracks/칼카피숏템엔진/channel/*/preset/**/frame.json (읽기만) — sources·bench 원값은 원래 frame.json 에 없고 manifest 에 있다.
//   단독 실행: node test/fake_server.js [port] → 주소·시험 키를 출력.
import crypto from 'node:crypto';
import fs from 'node:fs';
import http from 'node:http';
import { execFileSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const TRACK = path.resolve(HERE, '..', '..');                      // .tracks/숏템MCP
export const ENGINE = path.resolve(TRACK, '..', '칼카피숏템엔진');
const SS = path.join(TRACK, 'shopping_shorts');
const SECRET = 'fake-secret-for-tests';
const STEP_NAMES = ['소재', '분석', '대본', '장면 계획', '음성', '렌더', '검사', '확인', '완료'];

export const PROFILES = [
  { profile_id: 'cp_sseol01', name: '내 채널 · 썰', preset_id: 'sseolpulda/A_흰바탕창/창아래_검정', version: 3, frame: 'channel/sseolpulda/preset/A_흰바탕창/창아래_검정/frame.json' },
  { profile_id: 'cp_item01', name: '내 채널 · 아이템', preset_id: 'itemhome/검정띠2줄', version: 1, frame: 'channel/itemhome/preset/검정띠2줄/frame.json' },
  { profile_id: 'cp_bang01', name: '내 채널 · 게시글', preset_id: 'banggu/게시글형', version: 1, frame: 'channel/banggu/preset/게시글형/frame.json' },
];

export function makeKey(cid, exp, kv) {
  const sig = crypto.createHmac('sha256', SECRET).update(`${cid}|${exp}|${kv}`).digest('hex').slice(0, 32);
  return `SHORTEM-L1.${cid}.${exp}.${kv}.${sig}`;
}

function parseKey(auth) {
  const m = String(auth || '').match(/^Bearer (SHORTEM-L1\.(\d+)\.(\d+)\.(\d+)\.([0-9a-f]{32}))$/);
  if (!m) return null;
  const [, key, cid, exp, kv, sig] = m;
  const want = crypto.createHmac('sha256', SECRET).update(`${cid}|${exp}|${kv}`).digest('hex').slice(0, 32);
  if (want !== sig) return { bad: true };
  return { key, cid: +cid, exp: +exp, kv: +kv };
}

// 글꼴 family → 파일(라이브 장면꾸미기 화면의 @font-face 등록표가 기준)
function fontTable() {
  const html = fs.readFileSync(path.join(ENGINE, 'out', 'scene-style-ui-showcase.html'), 'utf8');
  const out = {};
  for (const m of html.matchAll(/@font-face\s*\{[^}]*?font-family:\s*"?([A-Za-z0-9_-]+)"?;[^}]*?src:\s*url\("([^"]+)"\)/g)) {
    const rel = m[2].replace(/^\.\.\//, '');
    const p = path.join(TRACK, ...rel.split('/'));
    if (!out[m[1]] && fs.existsSync(p)) out[m[1]] = p;
  }
  return out;
}

const sha = b => crypto.createHash('sha256').update(b).digest('hex');

function framesLayers(f) { return f.frames ? f.frames.flatMap(x => x.layers) : f.layers; }

export async function startFakeServer({ port = 0, ttl = 180, heartbeatEvery = 60, devicesMax = 2, blobTtl = 6 * 3600, fonts: fontOverride, rent, update, install } = {}) {
  const FT = fontTable();
  const state = { customers: new Map(), blobs: new Map(), log: [], feedback: [], leaseSeq: 0, assetsCalls: 0, blobTtl };
  const cust = cid => { if (!state.customers.has(cid)) state.customers.set(cid, { kv: 1, revoked: false, devices: [], lease: null }); return state.customers.get(cid); };

  // 프로필별 번들·자산(참조하는 것만)
  function bundleFor(pid, cid) {
    const prof = PROFILES.find(p => p.profile_id === pid);
    if (!prof) return null;
    const frame = JSON.parse(fs.readFileSync(path.join(ENGINE, prof.frame), 'utf8'));
    delete frame.made_from;
    const families = new Set(framesLayers(frame).filter(l => l.kind === 'text' && typeof l.font === 'string' && l.font !== '$per_video').map(l => l.font));
    if (fontOverride) fontOverride.forEach(f => families.add(f));
    if (framesLayers(frame).some(l => l.kind === 'text' && l.font === '$per_video')) families.add('CcPretendard-Bold');
    const assets = [];
    const add = (id, kind, file) => { const b = fs.readFileSync(file); assets.push({ id, kind, sha256: sha(b), size: b.length, name: path.basename(file), file }); };
    for (const fam of families) if (FT[fam]) add('font:' + fam, 'font', FT[fam]);
    for (const n of ['opener.wav', 'pop.wav', 'whoosh.wav']) add('sfx:팩01/' + n, 'sfx', path.join(SS, 'assets', 'sfx_packs', '팩01', n));
    add('bgm:qiuqiu', 'bgm', path.join(SS, 'assets', 'bgm_lib', 'qiuqiu.mp3'));
    const mark = crypto.createHmac('sha256', SECRET).update(`${cid}|${pid}`).digest('hex').slice(0, 12);
    const bundle = {
      preset_id: prof.preset_id, profile_version: prof.version, license: { cid, issued: Math.floor(Date.now() / 1000), mark },
      frame,
      rules: { script: { slots: [{ role: '훅', length: '짧게' }, { role: '상황', length: '보통' }, { role: '전개', length: '보통' }, { role: '반전', length: '보통' }, { role: '반응', length: '짧게' }], line_max: 38, title_line_max: 14, speech: 'banmal' }, check: { lufs: [-16.5, -11.5] } },
      options: { brand: { channel_name: '내 채널' }, text: { caption: { mode: 'single' } }, tts: { provider: 'typecast', voice_id: 'tc_68257f68bc6e3c161ab5078d', name: '필재', tempo: 1.2 }, sfx_pack: '팩01', bgm: { track: 'qiuqiu', gain_db: -21 } },
    };
    return { bundle, assets };
  }

  function sign(asset) {
    const tok = crypto.randomBytes(16).toString('hex');
    state.blobs.set(tok, { file: asset.file, exp: Date.now() + state.blobTtl * 1000 });
    return tok;
  }

  const send = (res, code, obj) => { res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(obj)); };
  const fail = (res, code, c, msg, extra = {}) => send(res, code, { ok: false, code: c, msg, ...extra });

  function auth(req, res) {
    const k = parseKey(req.headers.authorization);
    if (!k) { fail(res, 401, 'no_key', '라이선스 키가 없습니다'); return null; }
    if (k.bad) { fail(res, 401, 'bad_key', '라이선스 키가 올바르지 않습니다'); return null; }
    if (k.exp < Date.now() / 1000) { fail(res, 401, 'expired', '라이선스가 만료되었습니다'); return null; }
    const c = cust(k.cid);
    if (c.revoked || k.kv !== c.kv) { fail(res, 403, 'revoked', '회수된 라이선스입니다'); return null; }
    const fp = String(req.headers['x-shortem-device'] || '');
    if (!/^[0-9a-f]{64}$/.test(fp)) { fail(res, 403, 'device_unknown', '기기 지문이 없습니다'); return null; }
    return { ...k, c, fp };
  }

  async function body(req) { const ch = []; for await (const d of req) ch.push(d); try { return JSON.parse(Buffer.concat(ch).toString('utf8') || '{}'); } catch { return null; } }

  const server = http.createServer(async (req, res) => {
    const u = new URL(req.url, 'http://x');
    state.log.push({ method: req.method, route: u.pathname, at: Date.now() });
    try {
      if (u.pathname === '/api/claude/license' && req.method === 'GET') {
        const a = auth(req, res); if (!a) return;
        let dev = a.c.devices.find(d => d.fp === a.fp), now = false;
        if (!dev) {
          if (a.c.devices.length >= devicesMax) return fail(res, 403, 'device_limit', '기기 2대가 이미 등록되어 있습니다 — 마이페이지에서 기기 교체');
          let name = ''; try { name = decodeURIComponent(String(req.headers['x-shortem-device-name'] || '')); } catch { name = ''; }
          dev = { fp: a.fp, name: name.slice(0, 40) || 'PC', slot: a.c.devices.length + 1 }; a.c.devices.push(dev); now = true;
        }
        return send(res, 200, { ok: true, cid: a.cid, plan: 'claude', expires: a.exp, device: { id: a.fp.slice(0, 12), name: dev.name, slot: dev.slot, registered_now: now },
          devices_used: a.c.devices.length, devices_max: devicesMax, entitled_presets: PROFILES.map(p => p.preset_id),
          presets: rent && rent.pid ? [{ id: rent.pid, name: rent.name || '제품비하인드썰형', desc: '' }] : [],
          profiles: PROFILES.map(({ frame, ...p }) => p), min_engine: '1.0.0', min_installer: '1.0.0', server_time: Math.floor(Date.now() / 1000) });
      }
      if (u.pathname === '/api/claude/lease' && req.method === 'POST') {
        const a = auth(req, res); if (!a) return;
        if (!a.c.devices.find(d => d.fp === a.fp)) return fail(res, 403, 'device_unknown', '등록되지 않은 기기입니다');
        const b = await body(req); if (!b) return fail(res, 400, 'bad_request', '본문이 JSON 이 아닙니다');
        if (b.step_name != null && !STEP_NAMES.includes(b.step_name)) return fail(res, 400, 'bad_request', '단계 이름이 목록 밖입니다');
        const L = a.c.lease, live = L && L.exp > Date.now();
        if (b.action === 'acquire') {
          if (live && L.fp !== a.fp) { const dn = (a.c.devices.find(d => d.fp === L.fp) || {}).name || '다른 PC'; return fail(res, 409, 'busy_other_device', `다른 기기(${dn})에서 작업 중입니다 — 끝나거나 3분 뒤 다시 시도하세요`, { retry_after: Math.ceil((L.exp - Date.now()) / 1000) }); }
          if (live && L.fp === a.fp && L.job_id === b.job_id) { L.exp = Date.now() + ttl * 1000; L.step = b.step_name; return send(res, 200, { ok: true, lease_id: L.lease_id, ttl, heartbeat_every: heartbeatEvery }); }
          a.c.lease = { lease_id: 'ls_' + (++state.leaseSeq) + crypto.randomBytes(3).toString('hex'), fp: a.fp, job_id: b.job_id, exp: Date.now() + ttl * 1000, step: b.step_name };
          return send(res, 200, { ok: true, lease_id: a.c.lease.lease_id, ttl, heartbeat_every: heartbeatEvery });
        }
        if (b.action === 'heartbeat') {
          if (!live || L.lease_id !== b.lease_id || L.fp !== a.fp) return fail(res, 409, 'lease_lost', '작업 임대가 끝났습니다');
          L.exp = Date.now() + ttl * 1000; L.step = b.step_name; return send(res, 200, { ok: true, ttl });
        }
        if (b.action === 'release') { if (L && L.lease_id === b.lease_id && L.fp === a.fp) a.c.lease = null; return send(res, 200, { ok: true }); }
        return fail(res, 400, 'bad_request', 'action 이 올바르지 않습니다');
      }
      if (u.pathname === '/api/claude/assets' && req.method === 'GET') {
        const a = auth(req, res); if (!a) return;
        const L = a.c.lease, job = u.searchParams.get('job');
        if (!L || L.exp <= Date.now() || L.job_id !== job || L.fp !== a.fp || (u.searchParams.get('lease') && u.searchParams.get('lease') !== L.lease_id)) return fail(res, 409, 'lease_lost', '유효한 작업 임대가 없습니다');
        const r = bundleFor(u.searchParams.get('profile'), a.cid);
        if (!r) return fail(res, 403, 'not_entitled', '이 프로필을 쓸 수 없습니다');
        state.assetsCalls++;
        a.c.plan = a.c.plan || {}; a.c.plan[job] = r.assets.map(x => x.id);
        a.c.assetsByJob = a.c.assetsByJob || {}; a.c.assetsByJob[job] = r.assets;
        const base = `http://${req.headers.host}`;
        return send(res, 200, { ok: true, job, profile_version: r.bundle.profile_version, expires: Math.floor(Date.now() / 1000) + state.blobTtl, bundle: r.bundle,
          assets: r.assets.map(({ file, ...x }) => ({ ...x, url: `${base}/api/claude/blob/${sign({ file })}` })) });
      }
      const pk = u.pathname.match(/^\/api\/claude\/pack\/(.+)$/);
      if (pk && req.method === 'GET') {
        const a = auth(req, res); if (!a) return;
        const id = decodeURIComponent(pk[1]), job = u.searchParams.get('job');
        const list = (a.c.assetsByJob || {})[job] || [];
        const as = list.find(x => x.id === id);
        if (!as) return fail(res, 403, 'not_in_plan', '이번 작업 목록 밖 자산입니다');
        const { file, ...x } = as;
        return send(res, 200, { ok: true, asset: { ...x, url: `http://${req.headers.host}/api/claude/blob/${sign({ file })}` } });
      }
      const bl = u.pathname.match(/^\/api\/claude\/blob\/([0-9a-f]{32})$/);
      if (bl && req.method === 'GET') {
        const b = state.blobs.get(bl[1]);
        if (!b || b.exp < Date.now()) return fail(res, 403, 'expired', '받기 주소가 만료되었습니다');
        const buf = fs.readFileSync(b.file);
        res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Length': buf.length }); return res.end(buf);
      }
      // 편마다 프리셋(관제 234) — 잠그기는 서버와 같은 파이썬 AESGCM(nonce 12 + 암호문 + 태그, 덧붙임 글 cid|job)로 한다(언어 사이 호환 확인)
      if (u.pathname === '/api/claude/rent' && req.method === 'POST') {
        const a = auth(req, res); if (!a) return;
        const b = await body(req);
        const L = a.c.lease;
        if (!L || L.exp <= Date.now() || L.job_id !== b.job || L.fp !== a.fp || (b.lease && b.lease !== L.lease_id)) return fail(res, 409, 'lease_lost', '작업 권한이 없습니다');
        if (!rent) return fail(res, 503, 'not_ready', '이 프리셋을 지금 준비할 수 없습니다');
        if (rent.deny) return fail(res, 403, 'not_entitled', '이 프리셋은 지금 쓸 수 없습니다');
        const aad = `${a.cid}|${b.job}`;
        const py = `import sys,os,json,base64,hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
d=sys.stdin.buffer.read();aad=sys.argv[1].encode()
k=AESGCM.generate_key(bit_length=256);n=os.urandom(12)
print(json.dumps({"pack":base64.b64encode(n+AESGCM(k).encrypt(n,d,aad)).decode(),"key":base64.b64encode(k).decode(),"sha256":hashlib.sha256(d).hexdigest()}))`;
        const out = JSON.parse(execFileSync(process.platform === 'win32' ? 'py' : 'python3', ['-c', py, aad], { input: rent.zip }).toString());
        state.rents = (state.rents || 0) + 1;
        return send(res, 200, { ok: true, preset_path: rent.preset_path, aad, ...(rent.tamper ? { ...out, key: Buffer.alloc(32).toString('base64') } : out) });
      }
      if (u.pathname === '/api/claude/feedback' && req.method === 'POST') {
        const a = auth(req, res); if (!a) return;
        const b = await body(req);
        if (!b || !['request', 'bug'].includes(b.kind) || typeof b.text !== 'string' || b.text.length > 2000) return fail(res, 400, 'bad_request', '요청 모양이 다릅니다');
        state.feedback.push(b); return send(res, 200, { ok: true, id: state.feedback.length });
      }
      // 시험 손잡이
      // 켤 때 자동 업데이트(관제 234) — 서버 claude_portal.update_info 와 같은 꼴
      if (u.pathname === '/api/claude/update' && req.method === 'GET') {
        const a = auth(req, res); if (!a) return;
        const have = u.searchParams.get('have') || '';
        if (!update || have === update.version) return send(res, 200, { ok: true, update: false });
        return send(res, 200, { ok: true, update: true, version: update.version, sha256: crypto.createHash('sha256').update(update.zip).digest('hex'), size: update.zip.length, url: '/__blob/update' });
      }
      // exe 없이 까는 길(사장님 10-20) — 서버 claude_portal.install_info 와 같은 꼴(키만, 기기 지문 없음). FAKE_INSTALL_ZIP = 실물 설치 묶음
      if (u.pathname === '/api/claude/install' && req.method === 'GET') {
        const k = parseKey(req.headers.authorization);
        if (!k || k.bad || k.exp < Date.now() / 1000) return fail(res, 401, 'no_key', '라이선스 키가 없습니다');
        if (!install) return send(res, 200, { ok: true, ready: false });
        return send(res, 200, { ok: true, ready: true, version: install.version, sha256: install.sha256, size: install.size, url: '/__blob/install' });
      }
      if (u.pathname === '/__blob/install' && install) {
        res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Length': install.size });
        return fs.createReadStream(install.file).pipe(res);
      }
      if (u.pathname === '/__blob/update' && update) { res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Length': update.zip.length }); return res.end(update.zip); }
      if (u.pathname === '/__test/force_release') { for (const c of state.customers.values()) c.lease = null; return send(res, 200, { ok: true }); }
      if (u.pathname === '/__test/revoke') { const cid = +u.searchParams.get('cid'); cust(cid).revoked = true; return send(res, 200, { ok: true }); }
      return fail(res, 404, 'bad_request', '없는 경로');
    } catch (e) { return fail(res, 500, 'bad_request', String(e.message || e)); }
  });
  await new Promise(r => server.listen(port, '127.0.0.1', r));
  const url = `http://127.0.0.1:${server.address().port}`;
  return { url, state, server, makeKey, close: () => new Promise(r => { server.closeAllConnections?.(); server.close(r); }) };
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  const port = Number(process.argv[2] || 18849);
  // 하이쿠 1편 시험(관제 234): FAKE_RENT_ZIP(실물 프리셋 꾸러미)·FAKE_RENT_PRESET(엔진 프리셋 경로)·FAKE_RENT_PID(고객용 id)
  const rent = process.env.FAKE_RENT_ZIP ? { zip: fs.readFileSync(process.env.FAKE_RENT_ZIP), preset_path: process.env.FAKE_RENT_PRESET, pid: process.env.FAKE_RENT_PID } : undefined;
  // exe 없이 까는 시험: FAKE_INSTALL_ZIP(build_win 이 만든 설치 묶음) · FAKE_INSTALL_SHA(없으면 여기서 잰다)
  let install;
  if (process.env.FAKE_INSTALL_ZIP) {
    const f = process.env.FAKE_INSTALL_ZIP;
    const sha256 = process.env.FAKE_INSTALL_SHA || crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
    install = { file: f, size: fs.statSync(f).size, sha256, version: process.env.FAKE_INSTALL_VERSION || '1.0.0' };
  }
  startFakeServer({ port, rent, install }).then(s => {
    console.log(JSON.stringify({ url: s.url, key: makeKey(12, Math.floor(Date.now() / 1000) + 86400 * 30, 1) }));
  });
}
