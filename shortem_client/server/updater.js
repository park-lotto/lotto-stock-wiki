// 켤 때 자동 업데이트 — 받기 쪽(관제 234 5판, 사장님 10-19 "업데이트는 자동으로 켤 때 받을 수 있게").
//   판단(새 판인가)은 서버 claude_portal.update_info. 여기는: 받기 → sha 대조 → <설치>/_update/<판>/ 에 풀기 → pending.json.
//   바꾸기는 다음에 켤 때 연결기(installer/mcpb/launcher.js applyPending)가 서버를 띄우기 전에 한다(돌고 있는 파일을 안 건드린다).
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { api, download } from './api.js';
import { ENGINE_VERSION } from './license.js';
import { toolsDir, devMode } from './tools_paths.js';
import { readZip } from './preset_rent.js';
import { audit } from './audit.js';

const OK_PATH = /^(server|engine)\/[^\0]+$|^app_version\.json$/;
export const installDir = () => path.resolve(toolsDir(), '..');

export async function checkUpdate({ force = false } = {}) {
  if (devMode() && !force) return { skipped: 'dev' };
  const home = installDir();
  if (!fs.existsSync(path.join(home, 'tools', 'tools.manifest.json')) && !force) return { skipped: 'not_installed' };
  const r = await api.update(ENGINE_VERSION);
  if (!r.update) return { update: false, latest: r.latest };
  const dir = path.join(home, '_update', r.version);
  const pend = path.join(home, '_update', 'pending.json');
  try { if (JSON.parse(fs.readFileSync(pend, 'utf8')).version === r.version) return { update: true, ready: true, version: r.version }; } catch { /* 처음 */ }
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
  for (const need of ['server/index.js', 'engine/tools/calcopy/make.py', 'app_version.json']) {
    if (!fs.existsSync(path.join(dir, need))) throw new Error(`업데이트 묶음이 덜 찼습니다: ${need}`);
  }
  fs.writeFileSync(pend + '.tmp', JSON.stringify({ version: r.version, dir: r.version, at: Date.now() }));
  fs.renameSync(pend + '.tmp', pend);
  audit('update_ready', { result: r.version });
  return { update: true, ready: true, version: r.version };
}
