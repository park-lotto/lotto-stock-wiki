// 숏클 회원 지침(installer/common/CLAUDE_숏클.md)을 매 세션 시작에 Claude 맥락으로 넣는다(관제 290 — 회원 ~/.claude/CLAUDE.md 는 건드리지 않는다).
//   훅 맥락 한 번 한도 10,000자(Claude Code hooks 문서) → 장(## ) 경계로 CHUNK 자 이하 덩어리로 나눠 n 번째만 낸다(hooks.json 이 1·2·3 으로 부른다).
//   지침 파일: 설치 폴더 server/guide(켤 때 자동 업데이트가 바꾼다) → 없으면 플러그인 안 guide.
const fs = require('fs');
const path = require('path');
const CHUNK = 9000;
const n = Math.max(1, Number(process.argv[2] || 1));
const cands = [process.env.SHORTEM_INSTALL && path.join(process.env.SHORTEM_INSTALL, 'server', 'guide', 'CLAUDE_숏클.md'),
  path.join(__dirname, '..', 'guide', 'CLAUDE_숏클.md')].filter(Boolean);
let text = '';
for (const f of cands) { try { text = fs.readFileSync(f, 'utf8'); break; } catch { /* 다음 자리 */ } }
const parts = [];
let cur = '';
for (const sec of text.split(/\n(?=## )/)) {
  const s = (cur ? '\n' : '') + sec;
  if (cur && cur.length + s.length > CHUNK) { parts.push(cur); cur = sec; } else cur += s;
}
if (cur) parts.push(cur);
const piece = parts[n - 1];
if (!piece) { process.stdout.write('{}'); process.exit(0); }
const head = `[숏클 회원 지침 ${n}/${parts.length} — 숏클(숏템) 도구로 영상을 만들 때 따른다. 이 글은 숏클이 넣는다(수정하지 않는다)]\n`;
process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'SessionStart', additionalContext: head + piece } }));
