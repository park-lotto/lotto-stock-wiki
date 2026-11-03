// 한 PC 에 숏클 서버가 여럿 — Claude 창마다 서버가 하나씩 뜬다(정민혜 창 7개). 작업 폴더·제작 잠금(rent.lock)을 같이 써서
//   한 창이 만드는 동안 다른 창은 빌리기에서 기다리거나 같은 폴더를 건드린다. 막지 않고, 두 번째 창부터 점검(setup)에서 알린다.
//   장부 = ~/.shortem/servers/<pid>.json — 켤 때 적고 끌 때 지운다. 주인이 죽은 장부는 읽을 때 치운다.
import fs from 'node:fs';
import path from 'node:path';
import { homeDir } from './paths.js';

const dir = () => path.join(homeDir(), 'servers');
const alive = pid => { try { process.kill(pid, 0); return true; } catch { return false; } };

export function registerServer(pid = process.pid) {
  try {
    fs.mkdirSync(dir(), { recursive: true });
    fs.writeFileSync(path.join(dir(), `${pid}.json`), JSON.stringify({ pid, at: Date.now() }));
  } catch { /* 장부 없이도 서버는 돈다 */ }
  if (pid === process.pid) process.on('exit', () => { try { fs.rmSync(path.join(dir(), `${pid}.json`), { force: true }); } catch { /* 다음에 치운다 */ } });
}

// 이 서버 말고 살아 있는 숏클 서버 pid 목록
export function otherServers(self = process.pid) {
  let names = [];
  try { names = fs.readdirSync(dir()); } catch { return []; }
  const out = [];
  for (const n of names) {
    const pid = Number(path.basename(n, '.json'));
    if (!pid || pid === self) continue;
    if (alive(pid)) out.push(pid);
    else { try { fs.rmSync(path.join(dir(), n), { force: true }); } catch { /* 다음에 */ } }
  }
  return out;
}

export const OTHERS_NOTICE = n => `이 PC 에서 숏클이 다른 Claude 창 ${n}곳에서도 켜져 있습니다. 작업 폴더를 같이 써서 한 번에 한 편씩만 만들어집니다 — 회원에게 그대로 알리고, 안 쓰는 Claude 창은 닫아 달라고 부탁`;
