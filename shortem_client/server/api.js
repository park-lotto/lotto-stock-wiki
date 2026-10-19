// 우리 서버 REST(계약 §1~§5) — 고객 PC 가 부르는 곳은 license·lease·assets·pack·rent·feedback·blob 뿐(제작 호출 0).
//   네트워크 허용 목록: SHORTEM_BASE 의 origin + SHORTEM_ASSET_HOSTS(자산 저장소) 만. 밖이면 요청하지 않는다.
import { readLicense, deviceFingerprint, deviceName, ENGINE_VERSION } from './license.js';

export const baseUrl = () => String(process.env.SHORTEM_BASE || 'https://shoppingshorts.duckdns.org').replace(/\/+$/, '');

export function allowedOrigins() {
  const out = new Set([new URL(baseUrl()).origin]);
  for (const h of String(process.env.SHORTEM_ASSET_HOSTS || '').split(',').map(s => s.trim()).filter(Boolean)) {
    try { out.add(new URL(h.includes('://') ? h : 'https://' + h).origin); } catch { /* 무시 */ }
  }
  return out;
}

export function urlAllowed(u) {
  try {
    const x = new URL(u);
    if (!['https:', 'http:'].includes(x.protocol)) return false;
    if (x.protocol === 'http:' && !['127.0.0.1', 'localhost'].includes(x.hostname)) return false;   // 평문은 개발 서버만
    return allowedOrigins().has(x.origin);
  } catch { return false; }
}

export class ApiError extends Error {
  constructor(status, body) {
    super((body && body.msg) || '서버 응답 오류');
    this.status = status;
    this.code = (body && body.code) || (status ? 'http_' + status : 'network');
    this.msg = (body && body.msg) || '';
    this.retry_after = body && body.retry_after;
  }
}

function headers(extra = {}) {
  const key = readLicense();
  const h = { 'X-Shortem-Device': deviceFingerprint(), 'X-Shortem-Engine': ENGINE_VERSION, 'X-Shortem-Device-Name': encodeURIComponent(deviceName()), Accept: 'application/json', ...extra };
  if (key) h.Authorization = 'Bearer ' + key;
  return h;
}

export async function call(method, route, { body, query, timeoutMs = 20000 } = {}) {
  const u = new URL(baseUrl() + route);
  for (const [k, v] of Object.entries(query || {})) if (v != null && v !== '') u.searchParams.set(k, String(v));
  if (!urlAllowed(u.href)) throw new ApiError(0, { code: 'blocked_host', msg: '허용 목록 밖 주소' });
  if (!readLicense()) throw new ApiError(401, { code: 'no_key', msg: '라이선스 키가 없습니다' });
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(u, { method, headers: headers(body ? { 'Content-Type': 'application/json' } : {}), body: body ? JSON.stringify(body) : undefined, signal: ctl.signal, redirect: 'error' });
  } catch {
    throw new ApiError(0, { code: 'network', msg: '서버에 연결하지 못했습니다' });
  } finally { clearTimeout(t); }
  let j = null;
  try { j = await res.json(); } catch { j = null; }
  if (!res.ok || !j || j.ok === false) throw new ApiError(res.status, j);
  return j;
}

// 서명 URL 다운로드(자산). 허용 목록 밖이면 거부. 내용은 Buffer.
export async function download(url, { timeoutMs = 120000, maxBytes = 512 << 20 } = {}) {
  try { url = new URL(String(url), baseUrl() + '/').href; } catch { /* 아래에서 거절 */ }   // 서버가 상대 경로(/api/claude/blob/…)로 줄 수 있다
  if (!urlAllowed(url)) throw new ApiError(0, { code: 'blocked_host', msg: '허용 목록 밖 자산 주소' });
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { headers: { 'X-Shortem-Device': deviceFingerprint(), 'X-Shortem-Engine': ENGINE_VERSION }, signal: ctl.signal, redirect: 'error' });
    if (!res.ok) { let j = null; try { j = await res.json(); } catch { /* 본문 없음 */ } throw new ApiError(res.status, j); }
    const ab = await res.arrayBuffer();
    if (ab.byteLength > maxBytes) throw new ApiError(0, { code: 'too_big', msg: '자산이 너무 큽니다' });
    return Buffer.from(ab);
  } catch (e) {
    if (e instanceof ApiError) throw e;
    throw new ApiError(0, { code: 'network', msg: '자산을 받지 못했습니다' });
  } finally { clearTimeout(t); }
}

export const api = {
  license: () => call('GET', '/api/claude/license'),
  lease: body => call('POST', '/api/claude/lease', { body }),
  assets: (profile, job, lease, extra) => call('GET', '/api/claude/assets', { query: { profile, job, lease, extra } }),
  pack: (assetId, job) => call('GET', '/api/claude/pack/' + encodeURIComponent(assetId), { query: { job } }),
  rent: (profile, job, lease, preset) => call('POST', '/api/claude/rent', { body: { ...(profile ? { profile } : {}), ...(preset ? { preset } : {}), job, lease }, timeoutMs: 60000 }),   // 편마다 프리셋(관제 234)
  update: have => call('GET', '/api/claude/update', { query: { have } }),   // 켤 때 자동 업데이트(관제 234)
  feedback: body => call('POST', '/api/claude/feedback', { body }),
};
