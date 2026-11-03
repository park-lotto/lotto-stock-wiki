// 켤 때 자동 업데이트 — 받기 쪽(관제 234 5판, 사장님 10-19 "업데이트는 자동으로 켤 때 받을 수 있게").
//   판단(새 판인가)은 서버 claude_portal.update_info. 여기는: 받기 → sha 대조 → <설치>/_update/<판>/ 에 풀기 → pending.json.
//   바꾸기는 다음에 켤 때 연결기(installer/mcpb/launcher.js applyPending)가 서버를 띄우기 전에 한다(돌고 있는 파일을 안 건드린다).
//   판독 모델은 <설치>/models 에 둔다 — 연결기가 engine/ 을 통째로 바꿔도 남는다(adoptModels).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { api, download } from './api.js';
import { ENGINE_VERSION } from './license.js';
import { toolsDir, devMode } from './tools_paths.js';
import { readZip, renting, holdPending } from './preset_rent.js';
import { audit } from './audit.js';
import { activeRuns } from './engine_bridge.js';

const OK_PATH = /^(server|engine)\/[^\0]+$|^app_version\.json$/;
export const installDir = () => path.resolve(toolsDir(), '..');

// 멈춘 편을 다시 시도할 때 — 받아 둔 새 판의 engine/ 만 지금 자리에 덮는다. server/ 는 돌고 있으니 다음 켤 때 연결기가 바꾼다.
//   돌던 편이 없을 때만 부른다(retryFlow 자리). 실패해도 다시 시도는 막지 않는다 — 옛 엔진으로 이어 간다.
export function applyPendingEngine(home = installDir()) {
  const pend = path.join(home, '_update', 'pending.json');
  const mark = path.join(home, '_update', 'engine_now.json');
  let v;
  try { v = JSON.parse(fs.readFileSync(pend, 'utf8')).version; } catch { return { applied: false, why: 'no_pending' }; }
  try { if (JSON.parse(fs.readFileSync(mark, 'utf8')).version === v) return { applied: false, why: 'already', version: v }; } catch { /* 처음 */ }
  const src = path.join(home, '_update', v, 'engine');
  if (!fs.existsSync(path.join(src, 'tools', 'calcopy', 'make.py'))) return { applied: false, why: 'no_engine' };
  fs.cpSync(src, path.join(home, 'engine'), { recursive: true, force: true });
  fs.writeFileSync(mark, JSON.stringify({ version: v, at: Date.now() }));
  audit('engine_now', { result: v });
  return { applied: true, version: v };
}

// 옛 설치본의 engine/models 를 설치 폴더 models/ 로 복사한다. 못 옮긴 이름을 돌려준다(빈 배열 = 안전).
//   engine/models 는 연결기가 다음 판으로 바꿀 때 같이 사라진다. 여기서 지우지 않는다 — 돌고 있는 엔진이 읽고 있을 수 있다.
export function adoptModels(home = installDir()) {
  const src = path.join(home, 'engine', 'models');
  const dst = path.join(home, 'models');
  let names;
  try { names = fs.readdirSync(src).filter(n => n.endsWith('.onnx')); } catch { return []; }
  const left = [];
  for (const n of names) {
    const to = path.join(dst, n);
    try {
      const size = fs.statSync(path.join(src, n)).size;
      if (fs.existsSync(to) && fs.statSync(to).size === size) continue;
      fs.mkdirSync(dst, { recursive: true });
      fs.copyFileSync(path.join(src, n), to + '.tmp');
      fs.renameSync(to + '.tmp', to);
    } catch (e) {
      left.push(n);
      audit('models_adopt_fail', { result: `${n} ${String(e && e.message || e).slice(0, 60)}` });
    }
  }
  return left;
}

const READY_MARK = '.ready';           // 다 풀고 확인까지 끝난 판 표시 — 내용은 묶음 sha
const UPDATE_NEED = ['server/index.js', 'engine/tools/calcopy/make.py', 'app_version.json'];
const readJson = f => { try { return JSON.parse(fs.readFileSync(f, 'utf8')); } catch { return null; } };

// 이 판이 이미 <설치>/_update/<판> 에 온전히 풀려 있나 — 끊겨 반쯤 풀린 폴더는 표시가 없고, 바꾸다 실패한 폴더는 파일이 빠져 있다.
function unpacked(dir, sha256) {
  try { if (fs.readFileSync(path.join(dir, READY_MARK), 'utf8') !== sha256) return false; } catch { return false; }
  return UPDATE_NEED.every(n => fs.existsSync(path.join(dir, n)));
}

function writePending(pend, version) {
  fs.writeFileSync(pend + '.tmp', JSON.stringify({ version, dir: version, at: Date.now() }));
  fs.renameSync(pend + '.tmp', pend);
}

export async function retryUpdate() {
  try { await checkUpdate(); return applyPendingEngine(); }
  catch (e) { audit('engine_now_fail', { result: String(e && e.message || e).slice(0, 80) }); return { applied: false, why: 'fail' }; }
}

export async function checkUpdate({ force = false } = {}) {
  if (devMode() && !force) return { skipped: 'dev' };
  const home = installDir();
  if (!fs.existsSync(path.join(home, 'tools', 'tools.manifest.json')) && !force) return { skipped: 'not_installed' };
  // 숨김은 '도는 제작 중엔 바꾸지 마라' — 아무도 안 만들면 되살린다. 제작 중 창을 닫으면 숨김이 남고, 켤 때는 제작을 빌릴 때만 sweep 이 풀었다가 바로 다시 숨겨 앱 판이 안 바뀌었다(#1507)
  if (!renting()) holdPending(false);
  const left = adoptModels(home);
  // ENGINE_VERSION 은 이 프로그램이 뜰 때의 판 — 켜진 사이 다른 연결기가 판을 바꿨으면(프로그램 둘) 그 값을 보내 같은 판을 또 받았다. 설치 폴더 판이 진짜다
  const r = await api.update(readJson(path.join(home, 'app_version.json'))?.version || ENGINE_VERSION);
  if (!r.update) return { update: false, latest: r.latest };
  if (renting()) return { update: true, held: true, version: r.version };   // 만드는 중엔 받지도 바꾸지도 않는다 — 다음 확인 때
  const dir = path.join(home, '_update', r.version);
  const pend = path.join(home, '_update', 'pending.json');
  const hold = path.join(home, '_update', 'pending.hold.json');   // 만드는 중엔 표시가 이 이름으로 숨어 있다(preset_rent.holdPending)
  if ([pend, hold].some(f => readJson(f)?.version === r.version)) return { update: true, ready: true, version: r.version };
  if (unpacked(dir, r.sha256)) {                                  // 표시만 없어진 경우(바꾸기 실패 등) — 받지 않고 다시 건다
    writePending(pend, r.version);
    audit('update_reuse', { result: r.version });
    return { update: true, ready: true, version: r.version, reused: true };
  }
  const buf = await download(r.url, { timeoutMs: 15 * 60 * 1000, maxBytes: 1 << 30 });
  if (crypto.createHash('sha256').update(buf).digest('hex') !== r.sha256) throw new Error('업데이트 묶음 확인값이 다릅니다');
  fs.rmSync(dir, { recursive: true, force: true });
  for (const f of readZip(buf)) {
    if (!OK_PATH.test(f.name) || f.name.includes('..') || f.name.includes('\\')) throw new Error('업데이트 묶음에 바깥 경로가 있습니다');
    const dst = path.resolve(dir, f.name);
    if (!dst.startsWith(path.resolve(dir) + path.sep)) throw new Error('업데이트 묶음에 바깥 경로가 있습니다');
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.writeFileSync(dst, f.data);
  }
  for (const need of UPDATE_NEED) {
    if (!fs.existsSync(path.join(dir, need))) throw new Error(`업데이트 묶음이 덜 찼습니다: ${need}`);
  }
  if (left.length && !fs.existsSync(path.join(dir, 'engine', 'models'))) {   // 이대로 바꾸면 engine/models 와 함께 모델이 사라진다
    fs.rmSync(dir, { recursive: true, force: true });
    throw new Error(`판독 모델을 옮기지 못해 업데이트를 미룹니다: ${left.join(', ')}`);
  }
  fs.writeFileSync(path.join(dir, READY_MARK), r.sha256);
  writePending(pend, r.version);
  audit('update_ready', { result: r.version });
  applyDownloaded(dir, home, activeRuns().length);
  return { update: true, ready: true, version: r.version };
}

// 받자마자 엔진을 새 판으로(관제 298, 사장님 '두 번 켜기 없애기'). 엔진은 편마다 새로 뜨는 파이썬이라 다시 켜지 않아도 다음 실행부터 새 판이다.
//   복사라 묶음은 남고, 다음에 켤 때 연결기가 server 까지 통째로 바꾼다. 만드는 중이면 건드리지 않는다(다음 켤 때).
export function applyDownloaded(dir, home, running) {   // 관제 304 합치기에서 이름이 겹쳐 프로그램이 안 뜨던 것(같은 이름 export 두 개)을 가른다
  if (running) return false;
  try {
    fs.cpSync(path.join(dir, 'engine'), path.join(home, 'engine'), { recursive: true, force: true });
    audit('update_engine_now', { result: path.basename(dir) });
    return true;
  } catch (e) {
    audit('update_fail', { result: 'engine_now ' + String(e && e.message || e).slice(0, 70) });
    return false;
  }
}
