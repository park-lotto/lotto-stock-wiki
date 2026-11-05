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
import { homeDir } from './paths.js';
import { mineById, myRoot } from './my_presets.js';

const MARK = '.rented';
let current = null;                                       // 지금 빌린 것(PC 1대 · 작업 하나)

export function channelDir(engineRoot) { return path.join(engineRoot, 'channel'); }
// 기술 꾸러미(사장님 10-21 '프리셋처럼 편마다 빌려주기') — 집 PC 제작 라인 코드가 풀리는 자리. 설치본에는 없다(engine_bundle FORBIDDEN).
//   풀 때 자리마다 표식(.rented) — 표식 없는 자리(개발 PC 의 진짜 코드)는 지우지 않는다
// 빌리는 기술 자리 = 판 설정 폴더만 — 실행기·렌더 코드(hybrid/*.py·yanshot)는 설치본 엔진 묶음에 있어 같은 자리를 덮으면 '진짜 코드' 막음에 걸린다(10-29)
export const TECH_DIRS = ['tools/calcopy/hybrid/styles'];
const ALLOWED = ['channel/', ...TECH_DIRS.map(d => d + '/')];
const techDir = (engineRoot, d) => path.join(engineRoot, ...d.split('/'));
// 만드는 중엔 판 교체를 미룬다 — 연결기가 pending.json 을 보면 engine 폴더를 통째로 바꿔 빌린 판이 사라진다(11-02 742 '판이 없다').
//   연결기는 푸시로 못 고치므로 표시를 잠시 숨겼다가 반납 때 돌려놓는다. 프로그램이 죽어 숨김이 남으면 켤 때 sweep 이 돌려놓는다.
// 프로그램이 둘 뜰 수 있다(Claude 재연결·창 하나 더) — 다른 프로그램의 제작을 지우거나 판을 바꾸지 않게 PC 전체 잠금을 둔다(11-02 742).
const lockFile = () => path.join(homeDir(), 'rent.lock');
function lockOwner() {
  try {
    const t = fs.readFileSync(lockFile(), 'utf8');
    const j = t.trim().startsWith('{') ? JSON.parse(t) : { pid: Number(t) };   // 옛 잠금 = pid 숫자만
    return j && j.pid ? j : null;
  } catch { return null; }
}
function otherRenting() {
  const o = lockOwner();
  if (!o || o.pid === process.pid) return false;
  try { process.kill(o.pid, 0); return true; } catch { return false; }      // 주인 죽음 = 비어 있다
}
// 죽은 프로그램이 남긴 임대 반납은 lease.js freeDeadLeases 한 곳(Lease.acquire 가 부른다).
const pendFile = hold => path.join(process.env.SHORTEM_INSTALL || '', '_update', hold ? 'pending.hold.json' : 'pending.json');
export function holdPending(on) {
  if (!process.env.SHORTEM_INSTALL) return;
  try { if (fs.existsSync(pendFile(!on))) fs.renameSync(pendFile(!on), pendFile(on)); } catch { /* 없으면 숨길 것도 없다 */ }
}
function wipe(engineRoot) {
  for (const d of [channelDir(engineRoot), ...TECH_DIRS.map(x => techDir(engineRoot, x))]) {
    if (fs.existsSync(path.join(d, MARK))) { try { fs.rmSync(d, { recursive: true, force: true }); } catch { /* 다음 sweep 이 지운다 */ } }
  }
}

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
  const engine = path.dirname(path.resolve(root));
  for (const f of readZip(zip)) {
    const top = ALLOWED.find(a => f.name.startsWith(a));
    if (!top || f.name.includes('..') || f.name.includes('\\')) throw new Error('꾸러미에 바깥 경로가 있습니다');
    const dir = path.resolve(engine, top);
    const dst = path.resolve(engine, f.name);
    if (!dst.startsWith(dir + path.sep)) throw new Error('꾸러미에 바깥 경로가 있습니다');
    if (top !== 'channel/') {             // 기술 꾸러미 자리 — 표식 없는 진짜 코드(개발 PC)는 덮지 않는다
      if (fs.existsSync(dir) && !fs.existsSync(path.join(dir, MARK))) throw new Error('이 PC 에 같은 자리의 진짜 코드가 있습니다');
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(path.join(dir, MARK), '');
    }
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.writeFileSync(dst, f.data);
  }
}

// 지난번에 못 지운 것(프로그램이 죽었을 때) — 표식이 있는 자리(channel·기술 꾸러미)만 지운다(개발 PC 의 진짜 파일은 표식이 없다).
export function sweep(engineRoot) {
  if (current || otherRenting()) return false;
  holdPending(false);
  const had = [channelDir(engineRoot), ...TECH_DIRS.map(x => techDir(engineRoot, x))].some(d => fs.existsSync(path.join(d, MARK)));
  wipe(engineRoot);
  return had;
}

// 빌리기 → { presetPath, release() }. 개발 PC(표식 없는 진짜 channel 이 이미 있음)는 빌리지 않고 그 파일을 쓴다.
//   kind: 'make'(제작 한 단계 — 엔진이 끝나면 반납) · 'ui'(설정 화면 미리보기 — 10분 안 쓰면 반납, 제작이 오면 넘겨준다)
const UI_IDLE_MS = 10 * 60 * 1000;
export async function rentPreset({ engineRoot, presetId, profileId, stepName, kind = 'make' }) {
  const root = channelDir(engineRoot);
  if (fs.existsSync(root) && !fs.existsSync(path.join(root, MARK))) return { presetPath: null, dev: true, release: async () => {} };
  const want = presetId || profileId;
  if (current) {
    if (current.want === want && (kind === 'ui' || current.kind === 'ui')) {   // 같은 프리셋이 이미 풀려 있다 — 다시 받지 않는다
      if (current.kind === 'ui' && kind === 'make') { current.kind = 'make'; clearTimeout(current.idle); holdPending(true); }
      else if (current.kind === 'ui') touch(current, engineRoot);
      const me = current;
      return { presetPath: me.presetPath, release: kind === 'make' ? () => release(me, engineRoot) : async () => {} };
    }
    if (current.kind === 'ui') await release(current, engineRoot);   // 미리보기는 제작·다른 프리셋 미리보기에 자리를 내준다(10-30 실측: 다른 프리셋을 누르면 409 로 첫 프리셋만 남았다)
    else throw new ApiError(409, { code: 'busy', msg: kind === 'ui' ? '제작 중에는 다른 프리셋 미리보기를 잠시 못 합니다' : '앞 작업이 끝난 뒤 다시 부르세요' });
  }
  if (otherRenting()) throw new ApiError(409, { code: 'busy', msg: '앞 작업이 끝난 뒤 다시 부르세요' });
  sweep(engineRoot);
  const jobId = (kind === 'ui' ? 'u' : 'm') + Date.now().toString(36) + crypto.randomBytes(3).toString('hex');
  const mine = presetId ? mineById(presetId) : null;     // 내 벤치마킹 프리셋(관제 304) — 이 PC 에 있으니 서버를 안 부른다. 쓰고 지우는 꼴은 같다
  const lease = mine ? null : new Lease(jobId, { stepName: stepName || (() => '소재') });
  if (lease) await lease.acquire();
  const me = { jobId, lease, kind, want };
  current = me;
  try { fs.writeFileSync(lockFile(), JSON.stringify({ pid: process.pid, job: jobId })); } catch { /* 잠금 없이도 이 프로그램 안의 보호는 돈다 */ }
  if (kind === 'make') holdPending(true);
  try {
    const r = mine ? null : await api.rent(presetId ? null : profileId, jobId, lease.id, presetId || null);
    fs.mkdirSync(root, { recursive: true });
    fs.writeFileSync(path.join(root, MARK), jobId);
    if (mine) fs.cpSync(path.join(myRoot(), mine.slug), path.join(root, mine.slug), { recursive: true });
    else unpack(openPack(r), root);
    audit('preset_rent', { job: jobId, result: 'ok' });
    me.presetPath = mine ? `channel/${mine.slug}/preset/${mine.style}` : r.preset_path;
  } catch (e) {
    await release(me, engineRoot);
    throw e;
  }
  if (kind === 'ui') touch(me, engineRoot);
  return { presetPath: me.presetPath, release: kind === 'make' ? () => release(me, engineRoot) : async () => {} };
}

function touch(me, engineRoot) {
  clearTimeout(me.idle);
  me.idle = setTimeout(() => { if (current === me && me.kind === 'ui') release(me, engineRoot).catch(() => {}); }, UI_IDLE_MS);
  if (me.idle.unref) me.idle.unref();
}

async function release(me, engineRoot) {
  if (current !== me) return;
  current = null;
  clearTimeout(me.idle);
  try { fs.rmSync(lockFile(), { force: true }); } catch { /* 주인이 없으면 비어 있는 것으로 본다 */ }
  holdPending(false);
  wipe(engineRoot);                                       // 프리셋(channel) + 기술 꾸러미(hybrid·yanshot) — 표식 있는 자리만
  if (me.lease) await me.lease.release();
  audit('preset_return', { job: me.jobId, result: 'ok' });
}

export async function releaseAll(engineRoot) { if (current) await release(current, engineRoot); }

export const renting = () => !!current || otherRenting();
