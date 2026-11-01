// 이번 편 자산 받기(계약 §3·§4, 설계 §2-3·§7-4).
//   내용주소 캐시 ~/.shortem/cache/<sha256> (파일명에 프리셋·글꼴 이름 없음) · 영수증 receipts/<sha>.json
//   받은 뒤 sha256 대조(틀리면 버림) · 30일 미사용 삭제 · 총량 2GB 넘으면 오래 안 쓴 것부터 삭제 · revoked 면 캐시 비움.
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { api, download, ApiError } from './api.js';
import { homeDir, jail, writeFileIn, ensureDir } from './paths.js';
import { audit } from './audit.js';

const DAY = 86400000;
export const CACHE_DAYS = 30;
export const CACHE_MAX_BYTES = Number(process.env.SHORTEM_CACHE_MAX || 2 * 1024 ** 3);
const SHA_RE = /^[0-9a-f]{64}$/;
const KINDS = new Set(['font', 'sfx', 'bgm', 'template', 'meme']);

const sha256 = b => crypto.createHash('sha256').update(b).digest('hex');
const cacheRel = sha => 'cache/' + sha;
const receiptRel = sha => 'receipts/' + sha + '.json';

export function cachePath(sha) {
  if (!SHA_RE.test(sha)) throw new Error('잘못된 자산 지문');
  return jail(homeDir(), cacheRel(sha));
}

function readReceipt(sha) {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), receiptRel(sha)), 'utf8')); } catch { return null; }
}

function touch(sha, meta) {
  const r = readReceipt(sha) || {};
  const rec = { sha256: sha, size: meta.size ?? r.size, kind: meta.kind ?? r.kind, ext: meta.ext ?? r.ext, first: r.first || Date.now(), last_used: Date.now() };
  writeFileIn(homeDir(), receiptRel(sha), JSON.stringify(rec));
}

// 캐시에 있고 sha 가 맞으면 true. (크기 다르면 바로 버림, 크기가 같으면 영수증 + 한 번 해시 확인)
function cachedOk(a) {
  let p;
  try { p = cachePath(a.sha256); } catch { return false; }
  let st;
  try { st = fs.statSync(p); } catch { return false; }
  if (a.size != null && st.size !== a.size) { fs.rmSync(p, { force: true }); return false; }
  const rec = readReceipt(a.sha256);
  if (rec && rec.verified_mtime === st.mtimeMs) return true;
  const ok = sha256(fs.readFileSync(p)) === a.sha256;
  if (!ok) { fs.rmSync(p, { force: true }); return false; }
  const r = rec || {};
  writeFileIn(homeDir(), receiptRel(a.sha256), JSON.stringify({ ...r, sha256: a.sha256, size: st.size, verified_mtime: st.mtimeMs, last_used: Date.now(), first: r.first || Date.now() }));
  return true;
}

function extOf(name) {
  const m = String(name || '').match(/\.([A-Za-z0-9]{2,5})$/);
  return m ? m[1].toLowerCase() : '';
}

// 자산 하나를 캐시에 둔다. url 이 만료·거절이면 pack/<id> 로 한 번 재발급.
async function fetchOne(a, jobId) {
  if (cachedOk(a)) { touch(a.sha256, { kind: a.kind, size: a.size, ext: extOf(a.name) }); return { hit: true }; }
  let buf;
  try { buf = await download(a.url); }
  catch (e) {
    if (!(e instanceof ApiError) || ![401, 403, 404, 410].includes(e.status)) throw e;
    const r = await api.pack(a.id, jobId);
    buf = await download(r.asset.url);
  }
  if (a.size != null && buf.length !== a.size) throw Object.assign(new Error('자산 크기가 목록과 다릅니다'), { code: 'asset_mismatch' });
  if (sha256(buf) !== a.sha256) throw Object.assign(new Error('자산 지문이 목록과 다릅니다'), { code: 'asset_mismatch' });
  ensureDir(homeDir(), 'cache');
  writeFileIn(homeDir(), cacheRel(a.sha256), buf);
  const st = fs.statSync(cachePath(a.sha256));
  writeFileIn(homeDir(), receiptRel(a.sha256), JSON.stringify({ sha256: a.sha256, size: buf.length, kind: a.kind, ext: extOf(a.name), first: Date.now(), last_used: Date.now(), verified_mtime: st.mtimeMs }));
  return { hit: false, bytes: buf.length };
}

// assets 응답 → 지역 자산표. 반환 {bundle, table:{id:{kind,file,ext,name}}, stats}
//   table 은 job state 에만 저장되고 모델 응답으로는 나가지 않는다(firewall 이 sha256·url 키를 막는다).
export async function fetchJobAssets({ profileId, jobId, leaseId, extra }) {
  const r = await api.assets(profileId, jobId, leaseId, extra);
  if (!r.bundle || !Array.isArray(r.assets)) throw Object.assign(new Error('자산 목록 모양이 다릅니다'), { code: 'bad_bundle' });
  const table = {};
  let hits = 0, bytes = 0;
  for (const a of r.assets) {
    if (!a || !KINDS.has(a.kind) || !SHA_RE.test(String(a.sha256 || '')) || typeof a.id !== 'string') throw Object.assign(new Error('자산 항목 모양이 다릅니다'), { code: 'bad_bundle' });
    const got = await fetchOne(a, jobId);
    if (got.hit) hits++; else bytes += got.bytes;
    table[a.id] = { kind: a.kind, sha256: a.sha256, ext: extOf(a.name), name: String(a.name || '').slice(0, 120) };
  }
  const missing = Array.isArray(r.missing) ? r.missing.filter(x => typeof x === 'string').slice(0, 50) : [];   // 서버에 없는 자산(글꼴 등) — 렌더는 대체 글꼴로
  audit('assets', { job: jobId, profile: profileId, assets: Object.keys(table), n: r.assets.length, result: `hit ${hits} missing ${missing.length}` });
  gcCache();
  return { bundle: r.bundle, table, expires: r.expires, stats: { count: r.assets.length, hits, bytes, missing } };
}

export function assetFile(table, id) {
  const a = table && table[id];
  if (!a) return null;
  const p = cachePath(a.sha256);
  return fs.existsSync(p) ? p : null;
}

// 30일 미사용 삭제 + 총량 LRU. 반환 {removed, bytes}
export function gcCache(now = Date.now(), maxBytes = CACHE_MAX_BYTES) {
  let dir;
  try { dir = jail(homeDir(), 'cache'); } catch { return { removed: 0, bytes: 0 }; }
  let names = [];
  try { names = fs.readdirSync(dir).filter(n => SHA_RE.test(n)); } catch { return { removed: 0, bytes: 0 }; }
  const items = names.map(sha => {
    const rec = readReceipt(sha) || {};
    let size = 0, mtime = 0;
    try { const st = fs.statSync(path.join(dir, sha)); size = st.size; mtime = st.mtimeMs; } catch { /* 사라짐 */ }
    return { sha, size, last: rec.last_used || mtime };
  });
  let removed = 0;
  const kill = it => { fs.rmSync(path.join(dir, it.sha), { force: true }); try { fs.rmSync(jail(homeDir(), receiptRel(it.sha)), { force: true }); } catch { /* 없음 */ } removed++; };
  const alive = [];
  for (const it of items) { if (now - it.last > CACHE_DAYS * DAY) kill(it); else alive.push(it); }
  alive.sort((a, b) => a.last - b.last);
  let total = alive.reduce((s, x) => s + x.size, 0);
  while (total > maxBytes && alive.length) { const it = alive.shift(); total -= it.size; kill(it); }
  return { removed, bytes: total };
}

// 라이선스 회수·만료 → 캐시·영수증 전부 삭제
export function clearCache(why = 'revoked') {
  for (const rel of ['cache', 'receipts']) {
    try { fs.rmSync(jail(homeDir(), rel), { recursive: true, force: true }); } catch { /* 없음 */ }
  }
  audit('cache_clear', { code: why });
}
