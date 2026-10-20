// 자가점검 3종(설계 §3-5·§4-2) — 시험_렌더.mp4(기본 틀 3초) · 시험_목소리.wav(고객 키 1문장, 키 없으면 건너뜀)
//   · 시험_다운로드.mp4(공개 영상 5초) + 자가점검_결과.md. ffmpeg -version 첫 줄 + -filters 의 ' ass ' 확인.
//   실패 모양 {where, why, fix, retry_ok}.
import fs from 'node:fs';
import path from 'node:path';
import { workDir, ensureDir } from './paths.js';
import { run, runOk, resolveTools } from './tools_paths.js';
import { normalizeFrame, BASIC_FRAME } from './engine/frame.js';
import { plan, timeline } from './engine/plan.js';
import { renderVideo } from './engine/render.js';
import { probeOut } from './engine/check.js';
import { synthLines, readKey } from './engine/voice.js';

export const SELFTEST_URL = () => process.env.SHORTEM_SELFTEST_URL || 'https://www.youtube.com/watch?v=jNQXAC9IVRw';   // 'Me at the zoo'(19초 공개 영상) — 통째로 받고 5초만 잘라 쓴다
const DEFAULT_VOICE = 'tc_68257f68bc6e3c161ab5078d';

export async function ffmpegCheck() {
  const v = await run('ffmpeg', ['-hide_banner', '-version']);
  const first = v.stdout.toString('utf8').split(/\r?\n/)[0] || '';
  const f = await run('ffmpeg', ['-hide_banner', '-filters']);
  const ass = / ass\s/.test(f.stdout.toString('utf8'));
  return { version: first.slice(0, 120), ass };
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

async function testVoice(dir) {
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
    '-o', path.join(tmp, 'dl.%(ext)s'), SELFTEST_URL()], { timeoutMs: 5 * 60000 });
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
  for (const [name, fn, where] of [['시험 렌더', testRender, '렌더'], ['시험 목소리', testVoice, '음성'], ['시험 다운로드', testDownload, '다운로드']]) {
    try {
      const r = await fn(dir);
      items.push({ name, ok: !r.skipped, ...r });
    } catch (e) {
      items.push({ name, ok: false });
      fails.push({ where, why: `${name}을(를) 만들지 못했습니다`, fix: where === '다운로드' ? '인터넷 연결을 확인하고 다시 시도하세요' : where === '음성' ? '타입캐스트 키·크레딧을 확인하세요' : '설치팩 다시', retry_ok: true });
      if (process.env.SHORTEM_DEBUG) process.stderr.write(`[selftest] ${name}: ${e.stack || e}\n${e.detail || ''}\n`);
    }
  }
  const md = ['# 숏템 자가점검 결과', '', `- 시각: ${new Date().toLocaleString('ko-KR')}`, `- 실행 도구: ${tools.mode === 'dev' ? '개발 모드' : '설치본'} · 문제 ${tools.problems.length}건`, ff ? `- ffmpeg: ${ff.version} · ass 필터 ${ff.ass ? '있음' : '없음'}` : '- ffmpeg: 실행 실패', '',
    '| 점검 | 결과 | 파일 |', '|---|---|---|',
    ...items.filter(i => i.name !== 'ffmpeg').map(i => `| ${i.name} | ${i.ok ? '통과' : i.skipped ? '건너뜀 — ' + i.why : '실패'} | ${i.file ? path.basename(i.file) : '-'} |`), '',
    ...(fails.length ? ['## 고칠 것', ...fails.map(f => `- [${f.where}] ${f.why} → ${f.fix}`)] : ['모든 점검을 통과했습니다.'])].join('\n');
  const report = path.join(dir, '자가점검_결과.md');
  fs.writeFileSync(report, md + '\n');
  return { items, fails, report, dir };
}
