// 회원 지침을 작업 폴더 CLAUDE.md 로 — Claude Code 가 이 폴더에서 시작할 때 자동으로 먼저 읽는다(사장님 11-02 "폴더를 시작할때 반드시 먼저 읽게").
//   원본 = 설치 폴더 server/guide/MEMBER_GUIDE.md(자동 업데이트가 바꾼다). 내용이 다를 때만 쓴다. 회원이 지워도 다음 점검에서 복원된다.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { workDir } from './paths.js';

const HEAD = '<!-- 숏클 회원 지침 — 숏클이 자동으로 관리합니다. 고치면 다음 업데이트에 덮입니다. -->\n';
const here = path.dirname(fileURLToPath(import.meta.url));

export function syncGuide() {
  try {
    const src = fs.readFileSync(path.join(here, 'guide', 'MEMBER_GUIDE.md'), 'utf8');
    const dst = path.join(workDir(), 'CLAUDE.md');
    const want = HEAD + src;
    let now = '';
    try { now = fs.readFileSync(dst, 'utf8'); } catch { /* 처음 */ }
    if (now !== want) fs.writeFileSync(dst, want, 'utf8');
    return true;
  } catch (e) {
    console.error('[guide_sync] 지침을 작업 폴더에 쓰지 못했다:', e && e.message);
    return false;
  }
}
