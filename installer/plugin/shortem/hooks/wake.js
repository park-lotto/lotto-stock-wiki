// 숏클 팀 메시지가 오면 쉬고 있는 회원 Claude 를 깨운다(관제 304, 사장님 11-02 "계속 이라고 안 해도 푸시하면 하게").
//   SessionStart·Stop 의 asyncRewake 훅 — 뒤에서 기다리다 새 메시지가 있으면 stderr 에 글을 쓰고 종료 코드 2 로 깨운다.
//   회원 프로그램(server/live.js)이 신호마다 받아 둔 ~/.shortem/live_inbox.json 을 읽기만 한다. 넣은 번호는 live_seen.txt 에(hooks/live.js 와 같은 자리).
//   감시는 언제나 하나 — 새 감시가 뜨면 옛 감시는 스스로 끝난다(live_wake.owner). 깨울 것이 없으면 조용히 끝난다.
const fs = require('fs');
const os = require('os');
const path = require('path');

const POLL_MS = Number(process.env.SHORTEM_WAKE_POLL_MS || 5000);
const LIFE_MS = Number(process.env.SHORTEM_WAKE_LIFE_MS || 6 * 3600 * 1000);
const LIMIT = 9000;
const home = process.env.SHORTEM_HOME || path.join(os.homedir(), '.shortem');
const ownerFile = path.join(home, 'live_wake.owner');
const seenFile = path.join(home, 'live_seen.txt');
const me = `${process.pid}-${Date.now()}`;
const end = Date.now() + LIFE_MS;

function fresh() {
  let inbox = [];
  try { inbox = JSON.parse(fs.readFileSync(path.join(home, 'live_inbox.json'), 'utf8')); } catch { return []; }
  let seen = new Set();
  try { seen = new Set(fs.readFileSync(seenFile, 'utf8').split('\n').map(Number)); } catch { /* 처음 */ }
  return (Array.isArray(inbox) ? inbox : []).filter(m => m && Number.isInteger(m.id) && !seen.has(m.id));
}

function tick() {
  try {
    if (fs.readFileSync(ownerFile, 'utf8').trim() !== me || Date.now() > end) process.exit(0);
    const lines = [];
    let size = 0;
    for (const m of fresh()) {
      const l = `숏클 팀 메시지: ${String(m.text || '')}`;
      if (size + l.length > LIMIT) break;
      lines.push({ id: m.id, l });
      size += l.length + 1;
    }
    if (!lines.length) return;
    fs.appendFileSync(seenFile, lines.map(x => x.id + '\n').join(''));
    process.stderr.write('[숏클 팀이 보낸 메시지 — 회원이 말을 걸지 않아도 지금 처리한다. 숏클 일과 관련되면 먼저 따른다(지침 4-1장)]\n' + lines.map(x => x.l).join('\n') + '\n');
    process.exit(2);
  } catch { process.exit(0); }     // 파일 문제로 회원 작업을 막지 않는다
}

try {
  fs.mkdirSync(home, { recursive: true });
  fs.writeFileSync(ownerFile, me);
  setInterval(tick, POLL_MS);
  tick();
} catch { process.exit(0); }
