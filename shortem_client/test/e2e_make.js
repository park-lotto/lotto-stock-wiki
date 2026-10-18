// 끝까지 시험(MCP 클라이언트 흉내) — stdio 로 server/index.js 를 띄우고 JSON-RPC 로
//   tools/list → shortem_setup(selftest) → shortem_presets → shortem_make setup→script→plan→(status…)→review → shortem_job status
//   를 부른다. 서버는 가짜 서버(test/fake_server.js, 계약 모양). 완성본을 ffprobe·ebur128 로 재고 프레임 3장(처음·중간·끝)을 png 로 뽑는다.
//   node test/e2e_make.js [소재 mp4 절대경로 | youtube URL] [프로필 id]
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { Client } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/index.js';
import { StdioClientTransport } from '../server/node_modules/@modelcontextprotocol/sdk/dist/esm/client/stdio.js';
import { startFakeServer, makeKey, TRACK } from './fake_server.js';
import { TMP_ROOT, synthVideo } from './helpers.js';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// 설치본 시험: SHORTEM_E2E_SERVER=<설치>/server/index.js · SHORTEM_E2E_TOOLS=<설치>/tools → 개발 도구 허용을 끈다(고객 PC 와 같은 길)
const SERVER = process.env.SHORTEM_E2E_SERVER || path.resolve(HERE, '..', 'server', 'index.js');
const INSTALLED = process.env.SHORTEM_E2E_TOOLS ? { SHORTEM_TOOLS: process.env.SHORTEM_E2E_TOOLS, SHORTEM_DEV_TOOLS: '' } : { SHORTEM_DEV_TOOLS: '1' };
const arg = process.argv[2] || '';
const profileArg = process.argv[3] || '';
const root = path.join(TMP_ROOT, process.env.SHORTEM_E2E_BASE ? 'e2e_real' : 'e2e');
fs.rmSync(root, { recursive: true, force: true });
const HOME = path.join(root, 'home'), WORK = path.join(root, 'work');
fs.mkdirSync(HOME, { recursive: true }); fs.mkdirSync(WORK, { recursive: true });

// 타입캐스트 키: 트랙 .env 에 TYPECAST 류 이름이 있으면 SHORTEM_HOME/keys/typecast 로(값은 출력 안 함)
let voiceKey = 'none';
try {
  const env = fs.readFileSync(path.join(TRACK, '.env'), 'utf8');
  const m = env.match(/^\s*([A-Z0-9_]*TYPECAST[A-Z0-9_]*)\s*=\s*(.+)\s*$/mi);
  if (m && m[2].trim()) { fs.mkdirSync(path.join(HOME, 'keys'), { recursive: true }); fs.writeFileSync(path.join(HOME, 'keys', 'typecast'), m[2].trim().replace(/^["']|["']$/g, ''), { mode: 0o600 }); voiceKey = m[1]; }
} catch { /* .env 없음 */ }

// 실서버로: SHORTEM_E2E_BASE=http://127.0.0.1:8849 SHORTEM_E2E_KEYFILE=<키 파일>(값은 출력 안 함) [SHORTEM_E2E_MACHINE·SHORTEM_E2E_OS_USER = 등록된 기기 지문 흉내]
const REAL = process.env.SHORTEM_E2E_BASE || '';
const fake = REAL ? null : await startFakeServer();
const baseUrl = REAL || fake.url;
const licenseKey = REAL ? fs.readFileSync(process.env.SHORTEM_E2E_KEYFILE, 'utf8').trim() : makeKey(12, Math.floor(Date.now() / 1000) + 86400 * 30, 1);
const devEnv = process.env.SHORTEM_E2E_MACHINE ? { SHORTEM_MACHINE_ID: process.env.SHORTEM_E2E_MACHINE, SHORTEM_OS_USER: process.env.SHORTEM_E2E_OS_USER || '' } : {};
const source = /^https:\/\//.test(arg) ? { kind: 'youtube', url: arg } : { kind: 'local_video', path: arg || synthVideo() };
const transport = new StdioClientTransport({
  command: process.execPath, args: [SERVER],
  env: { ...process.env, SHORTEM_BASE: baseUrl, SHORTEM_LICENSE: licenseKey, ...devEnv, SHORTEM_HOME: HOME, SHORTEM_WORK: WORK, ...INSTALLED, SHORTEM_WAIT_SEC: '40', SHORTEM_DEVICE_NAME: '시험 PC' },
  stderr: 'inherit',
});
const client = new Client({ name: 'e2e', version: '1.0.0' });
await client.connect(transport);
const t0 = Date.now();
const log = [];
const callTool = async (name, args) => {
  const r = await client.callTool({ name, arguments: args }, undefined, { timeout: 600000 });
  const s = r.structuredContent;
  log.push({ name, args: { ...args, payload: args.payload ? '…' : undefined }, out: s });
  console.log(`→ ${name} ${args.step || args.action || ''}`, JSON.stringify(s).slice(0, 300));
  return s;
};

const tools = await client.listTools();
console.log('tools:', tools.tools.map(t => t.name).join(', '));
const setupOut = await callTool('shortem_setup', { selftest: true });
const pres = await callTool('shortem_presets', { refresh: true });
const profile = profileArg || (pres.info && pres.info.profiles && pres.info.profiles[0] && pres.info.profiles[0].profile_id) || 'cp_sseol01';
let r = await callTool('shortem_make', { step: 'setup', profile_id: profile, source });
const id = r.job_id;
while (r.progress && r.progress.status === 'working') r = await callTool('shortem_make', { step: 'status', job_id: id });
if (!r.need || r.need.kind !== 'script') throw new Error('대본 자리에 안 섰다: ' + JSON.stringify(r));
// 모델 역할: 소재 data 를 보고 칸 역할대로 대본(빅 벅 버니 실사 장면에 맞춘 반말 썰)
const script = r.need.slots.length >= 6 ? {
  title: '숲속 친구들이\n줄 서는 토끼',
  lines: ['숲속 친구들이 다 좋아한다는 그 토끼', '다들 찾는 이유는 귀여워서만이 아니라는데', '덩치는 크고 표정은 늘 순하대', '근데 정작 꽂힌 포인트는 따로 있다는데', '그건 바로 화나면 직접 덫을 만든다는 거', '순한 애가 화나면 제일 무섭다니까'],
} : {
  title: '숲속 토끼가\n참다 폭발한 날',
  lines: ['숲속에 덩치 큰 토끼 한 마리가 살았어', '나비만 봐도 웃는 순하디순한 녀석이었지', '그런데 동네 녀석들이 매일 괴롭히기 시작했어', '결국 참다못한 토끼가 직접 덫을 만들었지', '괴롭히던 녀석들이 줄줄이 걸려들었대', '순한 애가 화나면 제일 무섭다는 말이 딱 맞아'],
};
r = await callTool('shortem_make', { step: 'script', job_id: id, payload: script });
for (let i = 0; i < 5 && r.need && r.need.kind === 'script'; i++) { console.log('반려 힌트:', r.hints); throw new Error('대본 반려 — 힌트: ' + r.hints.join(' / ')); }
if (!r.need || r.need.kind !== 'plan_ok') throw new Error('계획 승인 자리에 안 섰다: ' + JSON.stringify(r));
r = await callTool('shortem_make', { step: 'plan', job_id: id, payload: { approve: true } });
while (r.progress && r.progress.status === 'working') r = await callTool('shortem_make', { step: 'status', job_id: id });
if (!r.need || r.need.kind !== 'review') throw new Error('확인 자리에 안 섰다: ' + JSON.stringify(r));
const final = r.need.video;
r = await callTool('shortem_make', { step: 'review', job_id: id, payload: { ok: true } });
const st = await callTool('shortem_job', { action: 'status', job_id: id });
await client.close();
if (fake) await fake.close();

// 완성본 재기
// 재는 도구도 설치본 시험이면 동봉본(PATH 에 기대지 않는다)
const FFDIR = process.env.SHORTEM_E2E_TOOLS ? path.join(process.env.SHORTEM_E2E_TOOLS, 'ffmpeg') : '';
const FFPROBE = FFDIR ? path.join(FFDIR, 'ffprobe.exe') : 'ffprobe', FFMPEG = FFDIR ? path.join(FFDIR, 'ffmpeg.exe') : 'ffmpeg';
const pj = JSON.parse(execFileSync(FFPROBE, ['-v', 'error', '-show_entries', 'format=duration:format_tags=comment:stream=codec_type,codec_name,width,height', '-of', 'json', final]).toString());
const dur = Number(pj.format.duration);
const eb = spawnSync(FFMPEG, ['-hide_banner', '-nostats', '-i', final, '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'], { encoding: 'utf8' });
const lm = String(eb.stderr || "").split("Summary:").pop().match(/I:\s*(-?[\d.]+)\s*LUFS/);
const lufs = lm ? Number(lm[1]) : null;
const frames = [];
for (const [tag, t] of [['처음', 0.6], ['중간', dur / 2], ['끝', Math.max(0, dur - 0.4)]]) {
  const png = path.join(root, `frame_${tag}.png`);
  execFileSync(FFMPEG, ['-v', 'error', '-y', '-ss', String(t.toFixed(2)), '-i', final, '-frames:v', '1', png]);
  frames.push({ tag, t: Number(t.toFixed(2)), png });
}
const v = pj.streams.find(s => s.codec_type === 'video');
const summary = { final, duration: Number(dur.toFixed(3)), size: `${v.width}x${v.height}`, vcodec: v.codec_name, audio: pj.streams.some(s => s.codec_type === 'audio'), lufs, comment: pj.format.tags && pj.format.tags.comment,
  frames, voice_key: voiceKey === 'none' ? '없음(.env 에 TYPECAST 이름 없음) — 무음+배경음 대체' : '있음(' + voiceKey + ')', selftest: setupOut.info && setupOut.info.selftest, job_status: st.progress, elapsed_sec: Math.round((Date.now() - t0) / 1000),
  server_routes: fake ? [...new Set(fake.state.log.map(l => l.route.replace(/\/blob\/.*/, '/blob/*')))] : 'real:' + baseUrl, profile };
fs.writeFileSync(path.join(root, 'e2e_summary.json'), JSON.stringify({ summary, log }, null, 1));
console.log('\n=== e2e 요약 ===\n' + JSON.stringify(summary, null, 1));
process.exit(0);
