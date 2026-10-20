// 고객처럼 한 편(관제 234) — 깔린 설치 폴더 + 라이브 서버 + 진짜 키로, Claude(opus, 머리 없는 claude -p)가 숏템 도구만 써서 만든다.
//   고객 몫 답(후보 1번 · "좋아요, 진행해")은 프롬프트로 준다. 결과물로 판정: 완성본 mp4(ffprobe 1080x1920·길이·소리) + 드라이브 복사.
//   실행: node test/live_episode.js --install <설치 폴더> --key-file <키 파일> --dir <없는 폴더> [--video <주소>] [--drive] [--typecast-file <목소리 키 파일>]
//   키·목소리 키는 파일·환경변수로만 넘기고 출력하지 않는다. 결과 JSON 한 줄, 어긋나면 rc=1.
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { TRACK } from './fake_server.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (n, d) => { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : d; };
const inst = path.resolve(arg('--install'));
const dir = path.resolve(arg('--dir'));
const video = arg('--video', 'https://www.tiktok.com/@11street_official/video/7512363471871216903');
if (!fs.existsSync(path.join(inst, 'tools', 'tools.manifest.json'))) { console.error('--install 이 설치 폴더가 아닙니다'); process.exit(2); }
if (fs.existsSync(dir)) { console.error('없는 폴더를 주세요: ' + dir); process.exit(2); }
const HOME = path.join(dir, 'home'), WORK = path.join(dir, 'work'), CWD = path.join(dir, 'cwd');
for (const d of [HOME, WORK, CWD]) fs.mkdirSync(d, { recursive: true });

// 목소리 키(고객 본인 키 자리) — 트랙 .env 의 TYPECAST 류 값을 keys/typecast 로(값 출력 안 함, e2e_make.js 와 같은 방식)
try {
  const env = fs.readFileSync(path.join(TRACK, '.env'), 'utf8');
  const m = env.match(/^\s*([A-Z0-9_]*TYPECAST[A-Z0-9_]*)\s*=\s*(.+)\s*$/mi);
  if (m && m[2].trim()) { fs.mkdirSync(path.join(HOME, 'keys'), { recursive: true }); fs.writeFileSync(path.join(HOME, 'keys', 'typecast'), m[2].trim().replace(/^["']|["']$/g, ''), { mode: 0o600 }); }
} catch { /* 없으면 목소리 단계가 알려 준다 */ }
if (arg('--typecast-file')) {   // 고객 본인 키 자리 — 파일로만 옮기고 출력하지 않는다
  fs.mkdirSync(path.join(HOME, 'keys'), { recursive: true });
  fs.copyFileSync(arg('--typecast-file'), path.join(HOME, 'keys', 'typecast'));
}
if (process.argv.includes('--drive')) fs.writeFileSync(path.join(HOME, 'deliver.json'), JSON.stringify({ drive: { on: true } }), { mode: 0o600 });

const cfg = path.join(dir, 'mcp.json');
fs.writeFileSync(cfg, JSON.stringify({ mcpServers: { shortem: {
  command: path.join(inst, 'tools', 'node', 'node.exe'),
  args: [path.join(inst, 'claude-plugin', 'shortem', 'launcher.js')],
  env: { SHORTEM_INSTALL: inst, SHORTEM_HOME: HOME, SHORTEM_WORK: WORK, SHORTEM_CLIENT: 'claude-code',
    SHORTEM_LICENSE: fs.readFileSync(arg('--key-file'), 'utf8').trim(), SHORTEM_NO_BROWSER: '1' } } } }), { mode: 0o600 });

const prompt = `숏템으로 숏폼 한 편 만들어줘. 나는 고객이고 이렇게 정했어:
- 먼저 shortem_setup 으로 준비를 확인해(자가점검은 하지 마).
- 소재는 이 영상 하나로 해: ${video} (shortem_make step="start" 에 video 로)
- 소재 후보가 나오면 표로 보여 주고, 내 선택은 "1번"이야.
- 대본·계획 사인이 필요하면 내 답은 "좋아요, 진행해"야.
- AI 요청(need=ai)이 오면 지시대로 바로 답해. 기다리라고 하면 shortem_make(step="wait") 로 이어 가.
끝나면 완성본 파일 경로만 알려줘. 숏템 도구 말고 다른 도구는 쓰지 마.`;

const t0 = Date.now();
const log = path.join(dir, 'claude.jsonl');
// ★셸을 거치면(shell:true) 여러 줄 프롬프트·옵션이 잘려 숏템 설정이 안 붙는다(10-20 첫 시도: 다른 MCP 를 부름) → 실행 파일을 직접
const claude = process.env.CLAUDE_BIN || (process.platform === 'win32' ? path.join(process.env.USERPROFILE || '', '.local', 'bin', 'claude.exe') : 'claude');
const p = spawn(claude, ['-p', prompt, '--mcp-config', cfg, '--strict-mcp-config', '--model', 'opus', '--output-format', 'stream-json', '--verbose',
  '--allowedTools', 'mcp__shortem__shortem_setup,mcp__shortem__shortem_presets,mcp__shortem__shortem_make,mcp__shortem__shortem_ai,mcp__shortem__shortem_job,mcp__shortem__shortem_settings',
  '--max-turns', '400'], { cwd: CWD, stdio: ['ignore', fs.openSync(log, 'w'), 'pipe'], windowsHide: true });
let err = ''; p.stderr.on('data', d => { err += d; });
const code = await new Promise(r => p.on('close', r));

const out = { rc: code, minutes: Math.round((Date.now() - t0) / 6000) / 10 };
const lines = fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
const uses = lines.flatMap(m => (m.message && m.message.content || []).filter(c => c.type === 'tool_use').map(c => c.name.replace('mcp__shortem__', '') + (c.input && c.input.step ? ':' + c.input.step : '')));
out.tool_calls = uses.length;
out.tools = [...new Set(uses)];
out.other_tools = uses.filter(u => !u.startsWith('shortem_') && u !== 'ToolSearch');   // ToolSearch = 도구 불러오기(하네스)
const res = lines.find(m => m.type === 'result');
out.final_text = res ? String(res.result || '').slice(0, 400) : null;
const vdir = path.join(WORK, '완성본');
const vids = fs.existsSync(vdir) ? fs.readdirSync(vdir).filter(n => n.endsWith('.mp4')) : [];
out.videos = vids;
if (vids[0]) {
  const f = path.join(vdir, vids[0]);
  const pr = JSON.parse(execFileSync(path.join(inst, 'tools', 'ffmpeg', 'ffprobe.exe'), ['-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration', '-of', 'json', f]).toString());
  const v = pr.streams.find(s => s.codec_type === 'video') || {};
  out.final = { mb: Math.round(fs.statSync(f).size / 1e5) / 10, w: v.width, h: v.height, sec: Math.round(+pr.format.duration * 10) / 10, audio: pr.streams.some(s => s.codec_type === 'audio') };
  try { out.sent = JSON.parse(fs.readFileSync(f + '.sent.json', 'utf8')); } catch { out.sent = null; }
}
if (code !== 0) out.stderr = err.slice(-500);
out.mcp = (lines.find(m => m.type === 'system' && m.subtype === 'init') || {}).mcp_servers || null;   // 숏템이 붙었나
out.ok = code === 0 && !!out.final && out.final.w === 1080 && out.final.h === 1920 && out.final.audio && out.other_tools.length === 0;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
