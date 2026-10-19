// 편마다 프리셋 빌리기(관제 234 5판, 사장님 "등급별 프리셋 / 노하우가 자산").
//   판단 주인은 서버 claude_portal.preset_rent(작업 권한·등급). 여기는 받아서 풀고, 엔진이 도는 동안만 두고, 끝나면 지운다.
//   열쇠는 메모리에만 — 잠긴 꾸러미도 디스크에 쓰지 않는다. 풀린 파일은 engineRoot()/channel 에만, 표식(.rented)과 함께.
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import zlib from 'node:zlib';
import { api, ApiError } from './api.js';
import { Lease } from './lease.js';
import { audit } from './audit.js';

const MARK = '.rented';
let current = null;                                       // 지금 빌린 것(PC 1대 · 작업 하나)

export function channelDir(engineRoot) { return path.join(engineRoot, 'channel'); }

// 잠긴 꾸러미(b64: nonce 12 + 암호문 + 태그 16) → zip Buffer. 덧붙임 글(cid|job)이 다르면 풀리지 않는다.
export function openPack(r) {
  const buf = Buffer.from(String(r.pack || ''), 'base64');
  if (buf.length < 29) throw new Error('꾸러미가 비었습니다');
  const d = crypto.createDecipheriv('aes-256-gcm', Buffer.from(String(r.key || ''), 'base64'), buf.subarray(0, 12));
  d.setAAD(Buffer.from(String(r.aad || ''), 'utf8'));
  d.setAuthTag(buf.subarray(buf.length - 16));
  const zip = Buffer.concat([d.update(buf.subarray(12, buf.length - 16)), d.final()]);
  if (crypto.createHash('sha256').update(zip).digest('hex') !== r.sha256) throw new Error('꾸러미 확인값이 다릅니다');
  return zip;
}

// 작은 zip 읽기(저장·deflate 만) — 이름은 channel/ 밑 상대 경로만 받는다.
export function readZip(zip) {
  let e = zip.length - 22;
  while (e >= 0 && zip.readUInt32LE(e) !== 0x06054b50) e--;
  if (e < 0) throw new Error('zip 끝 표식이 없습니다');
  const n = zip.readUInt16LE(e + 10);
  let p = zip.readUInt32LE(e + 16);
  const out = [];
  for (let i = 0; i < n; i++) {
    if (zip.readUInt32LE(p) !== 0x02014b50) throw new Error('zip 목록이 깨졌습니다');
    const method = zip.readUInt16LE(p + 10), csize = zip.readUInt32LE(p + 20);
    const nlen = zip.readUInt16LE(p + 28), xlen = zip.readUInt16LE(p + 30), clen = zip.readUInt16LE(p + 32);
    const name = zip.subarray(p + 46, p + 46 + nlen).toString('utf8');
    const lh = zip.readUInt32LE(p + 42);
    const start = lh + 30 + zip.readUInt16LE(lh + 26) + zip.readUInt16LE(lh + 28);
    const raw = zip.subarray(start, start + csize);
    p += 46 + nlen + xlen + clen;
    if (name.endsWith('/')) continue;
    if (method !== 0 && method !== 8) throw new Error('모르는 압축 방식');
    out.push({ name, data: method === 8 ? zlib.inflateRawSync(raw) : Buffer.from(raw) });
  }
  return out;
}

function unpack(zip, root) {
  const base = path.resolve(root);
  for (const f of readZip(zip)) {
    if (!f.name.startsWith('channel/') || f.name.includes('..') || f.name.includes('\\')) throw new Error('꾸러미에 바깥 경로가 있습니다');
    const dst = path.resolve(path.dirname(base), f.name);
    if (!dst.startsWith(base + path.sep)) throw new Error('꾸러미에 바깥 경로가 있습니다');
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.writeFileSync(dst, f.data);
  }
}

// 지난번에 못 지운 것(프로그램이 죽었을 때) — 표식이 있는 channel 만 지운다(개발 PC 의 진짜 channel 은 표식이 없다).
export function sweep(engineRoot) {
  const root = channelDir(engineRoot);
  if (current || !fs.existsSync(path.join(root, MARK))) return false;
  fs.rmSync(root, { recursive: true, force: true });
  return true;
}

// 빌리기 → { presetPath, release() }. 개발 PC(표식 없는 channel 이 이미 있음)는 빌리지 않고 그 파일을 쓴다.
export async function rentPreset({ engineRoot, profileId, stepName }) {
  const root = channelDir(engineRoot);
  if (fs.existsSync(root) && !fs.existsSync(path.join(root, MARK))) return { presetPath: null, dev: true, release: async () => {} };
  if (current) throw new ApiError(409, { code: 'busy', msg: '앞 작업이 끝난 뒤 다시 부르세요' });
  sweep(engineRoot);
  const jobId = 'm' + Date.now().toString(36) + crypto.randomBytes(3).toString('hex');
  const lease = new Lease(jobId, { stepName: stepName || (() => '소재') });
  await lease.acquire();
  const me = { jobId, lease };
  current = me;
  try {
    const r = await api.rent(profileId, jobId, lease.id);
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(path.join(root, MARK), jobId);
    unpack(openPack(r), root);
    audit('preset_rent', { job: jobId, result: 'ok' });
    me.presetPath = r.preset_path;
  } catch (e) {
    await release(me, engineRoot);
    throw e;
  }
  return { presetPath: me.presetPath, release: () => release(me, engineRoot) };
}

async function release(me, engineRoot) {
  if (current !== me) return;
  current = null;
  try { fs.rmSync(channelDir(engineRoot), { recursive: true, force: true }); } catch { /* 다음 sweep 이 지운다 */ }
  await me.lease.release();
  audit('preset_return', { job: me.jobId, result: 'ok' });
}

export const renting = () => !!current;
