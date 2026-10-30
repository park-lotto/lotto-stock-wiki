// 숏클 안쪽 잠금(사장님 10-30 "보고 고치는 능력은 똑같이, 대신 엔진은 고치지 못하게 가둔다") — 회원 Claude 의 파일 쓰기가 설치 폴더·플러그인에 닿으면 거절한다.
//   판 설정·대본·재료는 숏클 도구로 바꾸므로 이 잠금과 무관하다. 결함은 shortem_feedback → 중앙 수리 → 자동 업데이트.
const os = require('os');
const path = require('path');
const norm = s => String(s || '').replace(/\\/g, '/').replace(/\/+/g, '/').toLowerCase();
const local = process.env.LOCALAPPDATA || path.join(os.homedir(), 'AppData', 'Local');
const ROOTS = [process.env.SHORTEM_INSTALL, path.join(local, 'Shortem'), process.env.CLAUDE_PLUGIN_ROOT,
  path.join(os.homedir(), 'Library', 'Application Support', 'Shortem'), path.join(os.homedir(), '.local', 'share', 'Shortem')].filter(Boolean).map(norm);
const WRITES = /(^|[\s;&|(])(rm|rmdir|del|erase|mv|move|cp|copy|xcopy|robocopy|ren|rename|tee|touch|truncate|chmod|icacls|attrib|set-content|add-content|out-file|remove-item|move-item|copy-item|rename-item|new-item|clear-content)(\.exe)?\s|sed\s+-i|>|writefile|write_text|open\([^)]*['"][wa]/i;
const inside = p => { const n = norm(p); return ROOTS.some(r => n === r || n.startsWith(r + '/')); };

function blocked(tool, input) {
  if (['Edit', 'Write', 'MultiEdit', 'NotebookEdit'].includes(tool)) return inside(input.file_path || input.notebook_path);
  if (tool === 'Bash' || tool === 'PowerShell') {
    const c = norm(input.command);
    return ROOTS.some(r => c.includes(r)) && WRITES.test(c);
  }
  return false;
}

let raw = '';
process.stdin.on('data', d => { raw += d; });
process.stdin.on('end', () => {
  let j = {};
  try { j = JSON.parse(raw); } catch { process.exit(0); }
  if (blocked(j.tool_name, j.tool_input || {})) {
    process.stdout.write(JSON.stringify({ hookSpecificOutput: { hookEventName: 'PreToolUse', permissionDecision: 'deny',
      permissionDecisionReason: '숏클 안쪽은 고칠 수 없습니다. 판 설정·대본·재료로 풀고, 안 되면 가장 가까운 것으로 끝낸 뒤 shortem_feedback 으로 알리세요.' } }));
  }
  process.exit(0);
});
