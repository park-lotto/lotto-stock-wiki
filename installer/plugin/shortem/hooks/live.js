// 숏클 팀 메시지를 회원이 말을 걸 때 Claude 맥락에 넣는다(관제 304 — UserPromptSubmit 훅, Claude Code hooks 문서: hookSpecificOutput.additionalContext · 문자열 한도 10,000자).
//   회원 프로그램(server/live.js)이 신호마다 받아 둔 ~/.shortem/live_inbox.json 을 읽기만 한다. 넣은 번호는 live_seen.txt 에 한 줄씩 더 적는다(inbox 는 안 건드린다).
//   서버에 묻지 않는다(입력을 늦추지 않게). 어떤 경우에도 회원 입력을 막지 않는다: 항상 종료 코드 0.
const fs = require('fs');
const os = require('os');
const path = require('path');
const LIMIT = 9000;
let out = '{}';
try {
  const home = process.env.SHORTEM_HOME || path.join(os.homedir(), '.shortem');
  const inbox = JSON.parse(fs.readFileSync(path.join(home, 'live_inbox.json'), 'utf8'));
  const seenFile = path.join(home, 'live_seen.txt');
  let seen = new Set();
  try { seen = new Set(fs.readFileSync(seenFile, 'utf8').split('\n').map(Number)); } catch { /* 처음 */ }
  const todo = (Array.isArray(inbox) ? inbox : []).filter(m => m && Number.isInteger(m.id) && !seen.has(m.id));
  const lines = [];
  let size = 0;
  for (const m of todo) {
    const l = `숏클 팀 메시지: ${String(m.text || '')}`;
    if (size + l.length > LIMIT) break;
    lines.push({ id: m.id, l });
    size += l.length + 1;
  }
  if (lines.length) {
    fs.appendFileSync(seenFile, lines.map(x => x.id + '\n').join(''));
    const head = '[숏클 팀이 보낸 메시지 — 숏클 일과 관련되면 먼저 따른다(지침 4-1장). 회원의 다른 작업과 상관없으면 끼어들지 않는다]\n';
    out = JSON.stringify({ hookSpecificOutput: { hookEventName: 'UserPromptSubmit', additionalContext: head + lines.map(x => x.l).join('\n') } });
  }
} catch { /* 파일 없음·깨짐 — 넣을 것이 없는 것과 같다. 회원 프로그램 쪽 audit 가 파일 문제를 남긴다 */ }
process.stdout.write(out);
