// 켤 때 자동 업데이트 라이브 시험(관제 234) — 깔린 설치 폴더를 라이브 서버 키로 두 번 켠다:
//   1번째 = 새 판을 받아 _update/pending.json 까지(받기 쪽 server/updater.js) · 2번째 = 연결기가 바꾼다(launcher.js applyPending).
//   실행: node test/live_update_check.js --install <설치 폴더> --key-file <키 파일> --work <없어도 되는 시험 폴더>
//   출력: JSON 한 줄 {before, after, pending_after_1st, ok}. 키는 환경변수로만, 출력 안 함.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const arg = (n, d) => { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : d; };
const I = path.resolve(arg('--install')), W = path.resolve(arg('--work'));
const H = path.join(W, 'home_upd');
fs.mkdirSync(H, { recursive: true });
const env = { ...process.env, SHORTEM_INSTALL: I, SHORTEM_HOME: H, SHORTEM_WORK: path.join(W, 'work_upd'),
  SHORTEM_LICENSE: fs.readFileSync(arg('--key-file'), 'utf8').trim(), SHORTEM_NO_BROWSER: '1' };
delete env.SHORTEM_BASE;
const ver = () => JSON.parse(fs.readFileSync(path.join(I, 'app_version.json'), 'utf8')).version;
const pend = () => fs.existsSync(path.join(I, '_update', 'pending.json'));

async function once(waitMs, stopWhenPending) {
  const p = spawn(path.join(I, 'tools', 'node', 'node.exe'), [path.join(I, 'claude-plugin', 'shortem', 'launcher.js')], { env, stdio: ['pipe', 'pipe', 'pipe'] });
  p.stdin.write(JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'initialize', params: { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'u', version: '1' } } }) + '\n');
  const t0 = Date.now();
  while (Date.now() - t0 < waitMs) {
    await new Promise(r => setTimeout(r, 3000));
    if (stopWhenPending && pend()) break;
  }
  p.kill();
  await new Promise(r => setTimeout(r, 1500));
}

const out = { before: ver() };
await once(15 * 60 * 1000, true);
out.pending_after_1st = pend();
await once(20000, false);
out.after = ver();
out.pending_left = pend();
out.ok = out.pending_after_1st && !out.pending_left && out.after !== out.before;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
