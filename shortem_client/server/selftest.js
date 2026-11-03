// 자가점검 3종(설계 §3-5·§4-2) — 시험_렌더.mp4(기본 틀 3초) · 시험_목소리.wav(고객 키 1문장, 키 없으면 건너뜀)
//   · 시험_다운로드.mp4(공개 영상 5초) + 자가점검_결과.md. ffmpeg -version 첫 줄 + -filters 의 ' ass ' 확인.
//   실패 모양 {where, why, fix, retry_ok}.
import fs from 'node:fs';
import path from 'node:path';
import { workDir, ensureDir, homeDir } from './paths.js';
import { run, runOk, resolveTools, toolsDir } from './tools_paths.js';
import { browserExe, status as loginStatus, missingLogins, engineCookieEnv } from './logins.js';
import { normalizeFrame, BASIC_FRAME } from './engine/frame.js';
import { plan, timeline } from './engine/plan.js';
import { renderVideo } from './engine/render.js';
import { probeOut } from './engine/check.js';
import { synthLines, readKey } from './engine/voice.js';
import { readSettings, providerOf, engineVoice } from './local_settings.js';
import { engineRoot } from './engine_bridge.js';

export const SELFTEST_URL = () => process.env.SHORTEM_SELFTEST_URL || 'https://www.youtube.com/watch?v=jNQXAC9IVRw';   // 'Me at the zoo'(19초 공개 영상) — 통째로 받고 5초만 잘라 쓴다
const DEFAULT_VOICE = 'tc_68257f68bc6e3c161ab5078d';

export async function ffmpegCheck() {
  const v = await run('ffmpeg', ['-hide_banner', '-version']);
  const first = v.stdout.toString('utf8').split(/\r?\n/)[0] || '';
  const f = await run('ffmpeg', ['-hide_banner', '-filters']);
  const ass = / ass\s/.test(f.stdout.toString('utf8'));
  return { version: first.slice(0, 120), ass };
}

// 영상 인코딩 방식 — 그래픽카드(NVENC)가 실제로 돌면 'gpu', 아니면 'cpu'. 렌더 엔진 encoder.kind() 와 같은 시험(98 #79).
//   어느 쪽이든 통과다(CPU 도 화질 같음, 느릴 뿐). 회원에게 알려 주는 정보.
export async function encoderCheck() {
  try {
    const r = await run('ffmpeg', ['-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=256x256:d=0.2', '-c:v', 'h264_nvenc', '-f', 'null', '-'], { timeoutMs: 30000 });
    return r.code === 0 ? 'gpu' : 'cpu';
  } catch { return 'cpu'; }
}

// 설치 검수(사장님 11-02 "처음 설치는 깐깐하게 천천히") — 인터넷·받아쓰기 모델·브라우저·계정을 실제로 잰다
const NET_SITES = [['유튜브', 'https://www.youtube.com/'], ['틱톡', 'https://www.tiktok.com/'], ['인스타그램', 'https://www.instagram.com/'], ['쿠팡', 'https://www.coupang.com/']];

async function testNet() {
  const bad = [];
  for (const [name, url] of NET_SITES) {
    try { await fetch(url, { method: 'HEAD', redirect: 'manual', signal: AbortSignal.timeout(10000) }); } catch { bad.push(name); }
  }
  if (bad.length) throw new Error('접속 안 됨: ' + bad.join(', '));
  return { sites: NET_SITES.length };
}

async function testWhisper() {
  const dir = path.join(toolsDir(), '..', 'models', 'whisper', 'small');
  if (!fs.existsSync(dir)) return { skipped: true, why: '개발 PC — 설치본 모델 없음' };
  const r = await run('python', ['-I', '-c', 'import sys\nfrom faster_whisper import WhisperModel\nWhisperModel(sys.argv[1], device="cpu", compute_type="int8")\nprint("ok")', dir], { timeoutMs: 180000 });
  if (r.code !== 0 || !r.stdout.toString('utf8').includes('ok')) throw new Error(r.stderr.toString('utf8').slice(-200));
  return {};
}

async function testBrowser() {
  if (!browserExe()) throw new Error('크롬이나 엣지가 없습니다');
  return {};
}

async function testAccounts() {
  const bad = missingLogins(loginStatus().connected).required.map(([, p]) => p.name);
  if (bad.length) throw new Error('로그인 필요: ' + bad.join(', '));
  return {};
}

const stampFile = () => path.join(homeDir(), 'setup_ok.json');
export function setupPassed() {
  try { return !!JSON.parse(fs.readFileSync(stampFile(), 'utf8')).ok; } catch { return false; }
}

async function testRender(dir) {
  const spec = normalizeFrame(BASIC_FRAME, { title: '숏템\n자가점검', fonts: new Set() });
  const script = { title: '숏템\n자가점검', lines: ['숏템 자가점검 시험 렌더입니다'] };
  const p = plan(spec, script);
  const voice = [{ dur: 3.0 }];
  const tl = timeline(p, voice, null, spec);
  const r = await renderVideo({ spec, tl, src: null, title: script.title, fonts: {}, voice: null, bgm: null, sfx: [], dir: path.join(dir, '.render'), comment: 'shortem:selftest' });
  const out = path.join(dir, '시험_렌더.mp4');
  fs.copyFileSync(r.file, out);
  fs.rmSync(path.join(dir, '.render'), { recursive: true, force: true });
  const pr = await probeOut(out);
  return { file: out, duration: Number(pr.duration.toFixed(2)), size: `${pr.width}x${pr.height}` };
}

// 점검이 볼 목소리 = 엔진이 실제로 쓸 목소리 하나(local_settings.engineVoice → memberVoice) — 점검과 제작이 따로 정하던 두 벌을 합쳤다(11-03)

// 일레븐 목소리 id(프리셋 이름 또는 20자 id) → 일레븐 목소리 id. 프리셋 표 = 엔진 voice_presets.json(엔진 narr_align.eleven_direct 와 같은 표)
export function elevenBaseId(voiceId, presets) {
  const p = (presets || []).find(x => x.preset_id === voiceId);
  if (p) return p.base_voice_id || '';
  return /^[A-Za-z0-9]{20}$/.test(String(voiceId || '')) ? voiceId : '';
}

// (판단 주인 — 이 일레븐 키로 고른 목소리를 쓸 수 있나) 무료 요금제는 공유 목록(라이브러리) 목소리를 API 로 못 쓴다 — 키만 보고 통과시키면
//   제작 중 장면 맞추기에서야 payment_required 로 멈췄다(11-03 윤상길). 돈 안 드는 조회 2번(요금제·목소리 종류)만 한다
const ELEVEN_FREE_OK = new Set(['premade', 'cloned', 'generated']);
export async function elevenUsable(key, voiceId, { get = elevenGet, presets = null } = {}) {
  const rows = presets || (() => {
    try {
      const d = JSON.parse(fs.readFileSync(path.join(engineRoot(), 'shopping_shorts', 'assets', 'voice_presets.json'), 'utf8'));
      return Array.isArray(d) ? d : Object.values(d)[0];
    } catch { return []; }
  })();
  const base = elevenBaseId(voiceId, rows);
  if (!base) return;
  const sub = await get('/v1/user/subscription', key);
  if (String(sub.tier || '').toLowerCase() !== 'free') return;
  const v = await get(`/v1/voices/${base}`, key);
  if (ELEVEN_FREE_OK.has(String(v.category || ''))) return;
  throw Object.assign(new Error('eleven_free_library'), {
    why: `일레븐랩스 무료 요금제는 고른 목소리(${voiceId})처럼 공유 목록 목소리를 쓸 수 없습니다`,
    fix: "설정 화면 소리 단계에서 '내가 만든 목소리'(내 계정 목소리)를 고르거나, 일레븐랩스 유료 요금제로 바꾸거나, 타입캐스트·피쉬오디오 키를 넣으세요",
  });
}
async function elevenGet(p, key) {
  const r = await fetch('https://api.elevenlabs.io' + p, { headers: { 'xi-api-key': key }, signal: AbortSignal.timeout(15000) });
  if (r.status === 401) throw Object.assign(new Error('eleven_key'), { why: '일레븐랩스 키가 맞지 않습니다', fix: '설정 화면 키 칸에 일레븐랩스 API 키(sk_…)를 다시 넣으세요' });
  if (!r.ok) return {};          // 조회 실패는 막지 않는다(제작 때 엔진이 실제로 부른다)
  return r.json();
}

async function testVoice(dir) {
  const v = await engineVoice(s => !!readKey(s));
  const provider = (v && providerOf(v)) || 'typecast';
  if (provider !== 'typecast') {   // 시험 합성은 타입캐스트 길뿐이다 — 다른 회사는 키만 보고, 실제 합성은 제작 때 엔진(voice_synth)이 한다
    if (!readKey(provider)) return { skipped: true, why: `고른 목소리(${provider}) 키 없음` };
    if (provider === 'elevenlabs') await elevenUsable(readKey('elevenlabs'), v.voice_id);
    return { provider, key_only: true };
  }
  if (!readKey('typecast')) return { skipped: true, why: '타입캐스트 키 없음(~/.shortem/keys/typecast)' };
  const r = await synthLines(['숏템 자가점검 목소리입니다.'], { voice_id: process.env.SHORTEM_SELFTEST_VOICE || DEFAULT_VOICE, tempo: 1.1 }, path.join(dir, '.voice'));
  const out = path.join(dir, '시험_목소리.wav');
  fs.copyFileSync(r[0].file, out);
  fs.rmSync(path.join(dir, '.voice'), { recursive: true, force: true });
  return { file: out, duration: Number(r[0].dur.toFixed(2)) };
}

async function testDownload(dir) {
  const tmp = path.join(dir, '.dl');
  fs.mkdirSync(tmp, { recursive: true });
  const { toolPath } = await import('./tools_paths.js');
  // 구간 받기는 유튜브에서 느리다 — 짧은 공개 영상을 낮은 화질로 통째로 받고 5초만 잘라 쓴다
  const r = await run('ytdlp', ['--no-playlist', '--no-warnings', '--ffmpeg-location', path.dirname(toolPath('ffmpeg')), '-f', 'bv*[height<=480][ext=mp4]+ba[ext=m4a]/b[height<=480][ext=mp4]/bv*+ba/b', '--merge-output-format', 'mp4', '--max-filesize', '60M',
    '-o', path.join(tmp, 'dl.%(ext)s'), SELFTEST_URL()], { timeoutMs: 5 * 60000, env: { ...process.env, ...engineCookieEnv() } });   // 제작 받기와 같은 쿠키(11-03 회원 윤주홍: 점검만 무쿠키라 봇 확인에 막힘)
  const got = fs.readdirSync(tmp).find(n => n.endsWith('.mp4'));
  if (!got) { fs.rmSync(tmp, { recursive: true, force: true }); throw Object.assign(new Error('download'), { detail: r.stderr.slice(-400) }); }
  const out = path.join(dir, '시험_다운로드.mp4');
  await runOk('ffmpeg', ['-v', 'error', '-y', '-i', path.join(tmp, got), '-t', '5', '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', out], { timeoutMs: 120000 });
  fs.rmSync(tmp, { recursive: true, force: true });
  const pr = await probeOut(out);
  return { file: out, duration: Number(pr.duration.toFixed(2)) };
}

// 반환 {items:[{name, ok, ...}], fails:[{where,why,fix,retry_ok}], report}
export async function selftest() {
  const dir = ensureDir(workDir(), '_자가점검');
  const items = [], fails = [];
  const tools = resolveTools({ force: true });
  let ff = null;
  try {
    ff = await ffmpegCheck();
    items.push({ name: 'ffmpeg', ok: ff.ass, version: ff.version, ass_filter: ff.ass });
    if (!ff.ass) fails.push({ where: 'ffmpeg', why: '자막 굽기 필터(libass)가 없는 ffmpeg 입니다', fix: '설치팩 다시', retry_ok: false });
  } catch { fails.push({ where: 'ffmpeg', why: 'ffmpeg 를 실행하지 못했습니다', fix: '설치팩 다시', retry_ok: false }); }
  const enc = await encoderCheck();
  items.push({ name: '영상 인코딩', ok: true, encoder: enc, how: enc === 'gpu' ? '그래픽카드(NVENC) 우선' : 'CPU(그래픽카드 인코딩 없음 — 화질 같음, 렌더가 더 걸림)' });
  for (const [name, fn, where] of [['인터넷', testNet, '인터넷'], ['받아쓰기 모델', testWhisper, '받아쓰기'], ['브라우저', testBrowser, '브라우저'], ['계정 로그인', testAccounts, '계정'], ['시험 렌더', testRender, '렌더'], ['시험 목소리', testVoice, '음성'], ['시험 다운로드', testDownload, '다운로드']]) {
    try {
      const r = await fn(dir);
      items.push({ name, ok: !r.skipped, ...r });
    } catch (e) {
      items.push({ name, ok: false });
      if (e.why) { fails.push({ where, why: e.why, fix: e.fix || '', retry_ok: true }); continue; }
      fails.push({ where, why: ['인터넷', '받아쓰기', '브라우저', '계정'].includes(where) ? String(e.message || name).slice(0, 160) : `${name}을(를) 만들지 못했습니다`, fix: where === '다운로드' ? '인터넷 연결을 확인하고 다시 시도하세요' : where === '음성' ? '타입캐스트 키·크레딧을 확인하세요' : '설치팩 다시', retry_ok: true });
      if (process.env.SHORTEM_DEBUG) process.stderr.write(`[selftest] ${name}: ${e.stack || e}\n${e.detail || ''}\n`);
    }
  }
  const md = ['# 숏템 자가점검 결과', '', `- 시각: ${new Date().toLocaleString('ko-KR')}`, `- 실행 도구: ${tools.mode === 'dev' ? '개발 모드' : '설치본'} · 문제 ${tools.problems.length}건`, ff ? `- ffmpeg: ${ff.version} · ass 필터 ${ff.ass ? '있음' : '없음'}` : '- ffmpeg: 실행 실패',
    `- 영상 인코딩: ${enc === 'gpu' ? '그래픽카드(NVENC) 우선 — 실패하면 CPU 로 다시' : 'CPU(그래픽카드 인코딩 없음)'}`, '',
    '| 점검 | 결과 | 파일 |', '|---|---|---|',
    ...items.filter(i => i.name !== 'ffmpeg').map(i => `| ${i.name} | ${i.ok ? '통과' : i.skipped ? '건너뜀 — ' + i.why : '실패'} | ${i.file ? path.basename(i.file) : '-'} |`), '',
    ...(fails.length ? ['## 고칠 것', ...fails.map(f => `- [${f.where}] ${f.why} → ${f.fix}`)] : ['모든 점검을 통과했습니다.'])].join('\n');
  const report = path.join(dir, '자가점검_결과.md');
  fs.writeFileSync(report, md + '\n');
  fs.writeFileSync(stampFile(), JSON.stringify({ ok: !fails.length && !items.some(i => i.name === '시험 목소리' && i.skipped), at: Date.now(), fails: fails.map(f => f.where) }));   // 전부 통과해야 제작이 열린다(flow_driver.startFlow)
  return { items, fails, report, dir };
}
