// 회원처럼 한 편 — 볼케이노형(관제 234, 10-21): 개발 MCP(이 폴더 server/index.js) + 서버(로컬 시험 서버 또는 라이브) + 머리 없는 claude -p(opus)가
//   숏템 도구만 써서 "<벤치 URL> 이걸로 연예인상품+후기형으로 만들어줘" 한 줄을 끝까지 만든다. 설치본 판은 live_episode.js.
//   실행: node test/flow_episode.js --engine <엔진 트랙> --base http://127.0.0.1:18849 --key-file <키 파일> --dir <없는 폴더> --say "<한 줄>" [--cache <소스 캐시>]
//   키는 파일로만 넘기고 출력하지 않는다. 결과 JSON 한 줄(진행 한 줄 목록·도구 호출·완성본 ffprobe).
import { spawn, execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const arg = (n, d) => { const i = process.argv.indexOf(n); return i >= 0 ? process.argv[i + 1] : d; };
const dir = path.resolve(arg('--dir'));
const RESUME = arg('--resume');   // 이어 가기 시험: 같은 폴더(같은 회원 PC)에서 그 편 sid 를 이어서 끝까지
if (fs.existsSync(dir) && !RESUME) { console.error('없는 폴더를 주세요: ' + dir); process.exit(2); }
const HOME = path.join(dir, 'home'), WORK = path.join(dir, 'work'), CWD = path.join(dir, 'cwd');
for (const d of [HOME, WORK, CWD]) fs.mkdirSync(d, { recursive: true });
const env = { SHORTEM_HOME: HOME, SHORTEM_WORK: WORK, SHORTEM_CLIENT: 'claude-code', SHORTEM_NO_BROWSER: '1', SHORTEM_DEV_TOOLS: '1', SHORTEM_DEV: '1',
  SHORTEM_ENGINE: path.resolve(arg('--engine')), SHORTEM_BASE: arg('--base'), SHORTEM_LICENSE: fs.readFileSync(arg('--key-file'), 'utf8').trim(),
  CALCOPY_DEV_MINA_SERVER: '1', CALCOPY_DEV_COUPANG_SERVER: '1', SHORTEM_WAIT_SEC: '50', SHORTEM_YT_PROFILES: process.env.SHORTEM_YT_PROFILES || 'mcp' };   // 이 시험은 전용 파이어폭스 프로필 mcp* 로그인만(원본찾기 세션 yt* 와 계정 한도 나눔)
if (arg('--cache')) env.SHORTEM_SOURCE_CACHE = path.resolve(arg('--cache'));
for (const k of ['ORIGIN_YT_ONLY', 'SHORTEM_YT_GAP']) if (process.env[k]) env[k] = process.env[k];   // 쓸 계정·요청 간격 — MCP 서버는 부모 환경을 다 물려받지 않는다(넘길 것만 적는다)
const cfg = path.join(dir, 'mcp.json');
fs.writeFileSync(cfg, JSON.stringify({ mcpServers: { shortem: { command: process.execPath, args: [path.join(HERE, '..', 'server', 'index.js')], env } } }), { mode: 0o600 });

const prompt = RESUME ? `숏템에서 만들던 편(sid ${RESUME})을 이어서 끝까지 만들어줘. shortem_make(step="status", sid="${RESUME}") 부터.
나는 고객이고 대본은 이미 봤어 — 사인할게: "좋아요, 진행해"(사인을 다시 물으면 같은 답으로 바로 사인해). 진행 상황은 숏템이 주는 한 줄만, 끝나면 완성본 경로를 알려줘.` :`${arg('--say')}
(내 답을 미리 적어 둘게: 대본 사인은 "좋아요, 진행해". 진행 상황은 숏템이 주는 한 줄만 알려 주고, 끝나면 완성본 경로를 알려줘.)`;
const t0 = Date.now();
const log = path.join(dir, RESUME ? `claude_resume_${Date.now()}.jsonl` : 'claude.jsonl');
const claude = process.env.CLAUDE_BIN || (process.platform === 'win32' ? path.join(process.env.USERPROFILE || '', '.local', 'bin', 'claude.exe') : 'claude');
const p = spawn(claude, ['-p', prompt, '--mcp-config', cfg, '--strict-mcp-config', '--model', 'opus', '--output-format', 'stream-json', '--verbose',
  '--allowedTools', 'mcp__shortem__shortem_setup,mcp__shortem__shortem_presets,mcp__shortem__shortem_make,mcp__shortem__shortem_ai,mcp__shortem__shortem_job,mcp__shortem__shortem_settings,WebSearch,WebFetch',
  '--max-turns', '600'], { cwd: CWD, stdio: ['ignore', fs.openSync(log, 'w'), 'pipe'], windowsHide: true });
let err = ''; p.stderr.on('data', d => { err += d; });
const code = await new Promise(r => p.on('close', r));

const out = { rc: code, minutes: Math.round((Date.now() - t0) / 6000) / 10 };
const lines = fs.readFileSync(log, 'utf8').split('\n').filter(Boolean).map(l => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
const uses = lines.flatMap(m => (m.message && m.message.content || []).filter(c => c.type === 'tool_use').map(c => c.name.replace('mcp__shortem__', '') + (c.input && c.input.step ? ':' + c.input.step : '')));
out.tool_calls = uses.length;
out.tools = [...new Set(uses)];
out.other_tools = uses.filter(u => !u.startsWith('shortem_') && !['ToolSearch', 'WebSearch', 'WebFetch'].includes(u));
// 회원이 본 진행 한 줄(볼케이노처럼) — 도구 결과의 message 를 순서대로
out.messages = [...new Set(lines.flatMap(m => (m.message && m.message.content || []).filter(c => c.type === 'tool_result').map(c => {
  const t = Array.isArray(c.content) ? c.content.map(x => x.text || '').join('') : String(c.content || '');
  const mm = t.match(/"message":"([^"]{1,80})"/);
  return mm ? mm[1] : null;
}).filter(Boolean)))];
const res = lines.find(m => m.type === 'result');
out.final_text = res ? String(res.result || '').slice(0, 400) : null;
const vdir = path.join(WORK, '완성본');
const vids = fs.existsSync(vdir) ? fs.readdirSync(vdir).filter(n => n.endsWith('.mp4')) : [];
out.videos = vids.map(v => path.join(vdir, v));
if (vids[0]) {
  const f = path.join(vdir, vids[0]);
  const pr = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type,width,height:format=duration', '-of', 'json', f]).toString());
  const v = pr.streams.find(s => s.codec_type === 'video') || {};
  out.final = { mb: Math.round(fs.statSync(f).size / 1e5) / 10, w: v.width, h: v.height, sec: Math.round(+pr.format.duration * 10) / 10, audio: pr.streams.some(s => s.codec_type === 'audio') };
}
if (code !== 0) out.stderr = err.slice(-500);
out.ok = code === 0 && !!out.final && out.final.w === 1080 && out.final.h === 1920 && out.final.audio && out.other_tools.length === 0;
console.log(JSON.stringify(out));
process.exit(out.ok ? 0 : 1);
