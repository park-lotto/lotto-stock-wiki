// 플러그인(훅·스킬) 자동 갱신 — 회원이 설치를 다시 하지 않게 한다(사장님 11-02 "서버 업데이트하면 클로드가 받게").
//   묶음 안 server/plugin_update 를 설치 폴더 claude-plugin 에 덮고 Claude Code 에 갱신을 알린다. 판이 바뀌었을 때만 돈다.
//   실패해도 제작은 막지 않는다 — 다음 켤 때 다시 하고 숏클 팀에 알린다. 훅은 Claude 를 다음에 켤 때부터 적용된다.
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { homeDir } from './paths.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const stampFile = () => path.join(homeDir(), 'plugin_version.txt');

function setVersion(file, version) {
  const j = JSON.parse(fs.readFileSync(file, 'utf8'));
  j.version = version;
  fs.writeFileSync(file, JSON.stringify(j, null, 2));
}

const defaultRun = args => {
  const r = spawnSync('claude', args, { stdio: 'ignore', timeout: 60000, windowsHide: true, shell: process.platform === 'win32' });
  return r.status === 0;
};

export function syncPlugin({ version, installRoot, src = path.join(here, 'plugin_update'), run = defaultRun, report = () => {} }) {
  if (!fs.existsSync(src) || !installRoot) return { done: false, why: 'no_source' };
  let now = '';
  try { now = fs.readFileSync(stampFile(), 'utf8').trim(); } catch { /* 처음 */ }
  if (now === version) return { done: false, why: 'same' };
  try {
    const dst = path.join(installRoot, 'claude-plugin');
    fs.cpSync(src, dst, { recursive: true, force: true });
    setVersion(path.join(dst, 'shortem', '.claude-plugin', 'plugin.json'), version);
    const ok = run(['plugin', 'marketplace', 'update', 'shortem']) && run(['plugin', 'update', 'shortem@shortem']);
    if (!ok) throw new Error('claude plugin update 실패');
    fs.writeFileSync(stampFile(), version);
    return { done: true, version };
  } catch (e) {
    report(String((e && e.message) || e).slice(0, 200));
    return { done: false, why: 'fail' };
  }
}
