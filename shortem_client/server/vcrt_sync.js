// 깨끗한 윈도엔 VC++ 런타임이 없다(11-02 Windows Sandbox: ctranslate2.dll 을 못 읽어 받아쓰기 점검 실패) — 회원에게 재배포 패키지를 깔게 하지 않는다.
//   실행 도구(tools/)는 자동 업데이트로 안 바뀌므로, 묶음의 server/vcrt 를 켤 때 tools/python 에 채운다(python.exe 옆 = 확장 모듈 DLL 검색 자리).
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { toolsDir } from './tools_paths.js';
import { audit } from './audit.js';

const here = path.dirname(fileURLToPath(import.meta.url));

export function syncVcrt({ src = path.join(here, 'vcrt'), dst = path.join(toolsDir(), 'python') } = {}) {
  if (process.platform !== 'win32' && !process.env.SHORTEM_VCRT_FORCE) return { copied: 0 };
  if (!fs.existsSync(src) || !fs.existsSync(dst)) return { copied: 0 };
  let copied = 0;
  for (const f of fs.readdirSync(src)) {
    if (!f.toLowerCase().endsWith('.dll') || fs.existsSync(path.join(dst, f))) continue;
    try { fs.copyFileSync(path.join(src, f), path.join(dst, f)); copied++; }
    catch (e) { audit('vcrt_sync', { result: `${f} ${String((e && e.code) || e).slice(0, 40)}` }); }
  }
  if (copied) audit('vcrt_sync', { result: `copied ${copied}` });
  return { copied };
}
