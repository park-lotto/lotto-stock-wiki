// 무중단 업데이트(사장님 11-01 "재실행 안 해도 / 고객 불편하지 않게") — 고객 Claude 와의 연결은 이 부모가 쥐고, 실제 서버는 자식으로 돌린다.
//   자식이 '새 판 받음·돌던 일 없음'을 알리면(swap) 요청이 없을 때만 자식을 내리고 server·engine 을 바꿔 다시 띄운다. Claude 쪽 연결은 끊기지 않는다.
//   이 파일은 node 기본 부품만 쓴다.
import fs from 'node:fs';
import path from 'node:path';
import { spawn, execFile } from 'node:child_process';

export const SWAP_EXIT = 75;
const IDLE_MS = Number(process.env.SHORTEM_SWAP_IDLE_MS || 5 * 60 * 1000);   // 마지막 요청 뒤 이만큼 조용할 때만 바꾼다

export function applyUpdate(home) {            // 실패하면 되돌리고 옛 판으로 계속
  const up = path.join(home, '_update'), pend = path.join(up, 'pending.json');
  let p;
  try { p = JSON.parse(fs.readFileSync(pend, 'utf8')); } catch { return null; }
  if (!/^\d+\.\d+\.\d+$/.test(String(p.version)) || p.dir !== p.version) { try { fs.unlinkSync(pend); } catch { /* 없음 */ } return null; }
  const src = path.join(up, p.dir), old = path.join(up, 'old-' + Date.now()), moved = [];
  try {
    fs.mkdirSync(old, { recursive: true });
    for (const d of ['server', 'engine']) {
      if (!fs.existsSync(path.join(src, d))) throw new Error('덜 찬 업데이트: ' + d);
      if (fs.existsSync(path.join(home, d))) { fs.renameSync(path.join(home, d), path.join(old, d)); moved.push(d); }
      fs.renameSync(path.join(src, d), path.join(home, d));
    }
    fs.copyFileSync(path.join(src, 'app_version.json'), path.join(home, 'app_version.json'));
    fs.unlinkSync(pend);
    try { fs.rmSync(src, { recursive: true, force: true }); fs.rmSync(old, { recursive: true, force: true }); } catch { /* 다음에 */ }
    return p.version;
  } catch (e) {
    for (const d of moved) { try { fs.rmSync(path.join(home, d), { recursive: true, force: true }); fs.renameSync(path.join(old, d), path.join(home, d)); } catch { /* 되돌리기 최선 */ } }
    try { fs.unlinkSync(pend); } catch { /* 없음 */ }
    process.stderr.write('[숏템] 업데이트 적용 실패 — 예전 판으로 계속합니다: ' + e.message + '\n');
    return null;
  }
}

export function notifyMember(text) {           // 고객 PC 알림 — 실패해도 제작에는 영향 없다
  try {
    if (process.platform === 'win32') {
      const ps = "Add-Type -AssemblyName System.Windows.Forms;$n=New-Object System.Windows.Forms.NotifyIcon;$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;$n.ShowBalloonTip(10000,'숏클',$env:SHORTEM_NOTE,'Info');Start-Sleep 11;$n.Dispose()";
      execFile('powershell', ['-NoProfile', '-WindowStyle', 'Hidden', '-Command', ps], { windowsHide: true, env: { ...process.env, SHORTEM_NOTE: text } }, () => {});
    } else if (process.platform === 'darwin') {
      execFile('osascript', ['-e', 'on run a', '-e', 'display notification (item 1 of a) with title "숏클"', '-e', 'end run', text], () => {});
    }
  } catch { /* 알림 없이 간다 */ }
}

export function runSupervisor(home, { entry = path.join(home, 'server', 'index.js') } = {}) {
  let child, buf = '', init = null, inited = null, last = Date.now(), swapping = false;
  const open = new Set();
  const start = (replay) => {
    child = spawn(process.execPath, [entry], { stdio: ['pipe', 'pipe', 'inherit', 'ipc'], env: { ...process.env, SHORTEM_CHILD: '1' }, windowsHide: true, cwd: home });
    let out = '';
    child.stdout.on('data', d => {
      out += d.toString('utf8');
      let i;
      while ((i = out.indexOf('\n')) >= 0) {
        const line = out.slice(0, i); out = out.slice(i + 1);
        let m = null; try { m = JSON.parse(line); } catch { /* 그대로 넘긴다 */ }
        if (m && m.id === '__sv') { if (inited) child.stdin.write(inited + '\n'); continue; }   // 다시 띄운 자식의 인사 답은 삼킨다
        if (m && m.id != null && (m.result !== undefined || m.error !== undefined)) open.delete(m.id);
        process.stdout.write(line + '\n');
      }
    });
    child.on('message', m => {
      if (!m || !m.swap || swapping) return;
      if (open.size === 0 && Date.now() - last >= IDLE_MS) { swapping = true; child.send({ go: 1 }); }
    });
    child.on('exit', (code, sig) => {
      if (code === SWAP_EXIT) {
        const v = applyUpdate(home);
        swapping = false;
        start(true);
        if (v) notifyMember(`숏클이 ${v} 판으로 수리됐어요. 멈춘 편은 Claude 에게 '이어서'라고 해 주세요.`);
        return;
      }
      process.exit(sig ? 1 : (code == null ? 1 : code));
    });
    if (replay && init) {
      const m = JSON.parse(init); m.id = '__sv';
      child.stdin.write(JSON.stringify(m) + '\n');
    }
  };
  process.stdin.on('data', d => {
    buf += d.toString('utf8');
    let i;
    while ((i = buf.indexOf('\n')) >= 0) {
      const line = buf.slice(0, i); buf = buf.slice(i + 1);
      let m = null; try { m = JSON.parse(line); } catch { /* 그대로 넘긴다 */ }
      if (m) {
        if (m.method === 'initialize') init = line;
        if (m.method === 'notifications/initialized') inited = line;
        if (m.method && m.id != null) { open.add(m.id); last = Date.now(); }
      }
      child.stdin.write(line + '\n');
    }
  });
  process.stdin.on('end', () => { try { child.kill(); } catch { /* 이미 끝남 */ } process.exit(0); });
  for (const s of ['SIGINT', 'SIGTERM']) process.on(s, () => { try { child.kill(s); } catch { /* 이미 끝남 */ } });
  start(false);
}
