// 렌더 — 영상 창 컷 + 틀 그림(PNG) 겹치기 → 1080×1920, 소리 = 나레 + BGM(나레에 덕킹) + 효과음 → 2패스 loudnorm.
//   ffmpeg 필터 그래프는 jobs/<id>/render/ 의 파일로만 넘기고 감사 로그·응답에는 안 적는다(좌표가 들어 있다).
import fs from 'node:fs';
import path from 'node:path';
import { runOk } from '../tools_paths.js';
import { framesAt, videoRect } from './frame.js';
import { renderOverlays, writeConcat } from './overlay.js';

const FPS = 30;
export const TARGET_LUFS = -14;
const hex = c => c.map(v => v.toString(16).padStart(2, '0')).join('');
const f3 = n => (Math.round(n * 1000) / 1000).toFixed(3);

// 장면 목록(렌더용) = 자막 장면 + 꼬리(틀 끔)
export function renderScenes(tl) {
  const sc = tl.scenes.map(s => ({ t0: s.t0, t1: s.t1, caption: s.caption, text: s.text, words: s.words, frame: s.frame, line: s.line }));
  if (tl.tail > 0) sc.push({ t0: tl.narr_end, t1: tl.total, caption: '', text: '', words: [], frame: sc.length ? sc[sc.length - 1].frame : 'main', off: true });
  return sc;
}

function videoGraph({ spec, tl, src }) {
  const { W, H } = spec;
  const inputs = [], fil = [];
  tl.cuts.forEach((c, k) => {
    const fr = framesAt(spec, c.t0 + 1e-3);
    const v = c.full ? { x: 0, y: 0, w: W, h: H } : (videoRect(fr.layers) || { x: 0, y: 0, w: W, h: H });
    const w = Math.round(v.w / 2) * 2, h = Math.round(v.h / 2) * 2;
    if (src) inputs.push('-ss', f3(c.start), '-t', f3(c.dur + 0.2), '-i', src);
    else inputs.push('-f', 'lavfi', '-t', f3(c.dur + 0.2), '-i', `gradients=s=${w}x${h}:c0=0x2a2f45:c1=0x10131c:speed=0.02:r=${FPS}`);
    fil.push(`[${k}:v]scale=${w}:${h}:force_original_aspect_ratio=increase,crop=${w}:${h},setsar=1,fps=${FPS},format=yuv420p,tpad=stop_mode=clone:stop_duration=${f3(c.dur)},trim=duration=${f3(c.dur)},setpts=PTS-STARTPTS[w${k}]`);
    fil.push(`color=c=black:s=${W}x${H}:r=${FPS}:d=${f3(c.dur)},format=yuv420p[c${k}]`);
    fil.push(`[c${k}][w${k}]overlay=${Math.round(v.x)}:${Math.round(v.y)}:shortest=1[v${k}]`);
  });
  fil.push(tl.cuts.map((_, k) => `[v${k}]`).join('') + `concat=n=${tl.cuts.length}:v=1:a=0,fps=${FPS}[base]`);
  return { inputs, fil, next: tl.cuts.length };
}

async function loudnorm(inWav, outWav) {
  const r = await runOk('ffmpeg', ['-hide_banner', '-nostats', '-i', inWav, '-af', `loudnorm=I=${TARGET_LUFS}:TP=-1.5:LRA=11:print_format=json`, '-f', 'null', '-'], { timeoutMs: 600000 });
  const m = r.stderr.match(/\{[\s\S]*"input_i"[\s\S]*?\}/);
  let af = `loudnorm=I=${TARGET_LUFS}:TP=-1.5:LRA=11`;
  if (m) {
    const j = JSON.parse(m[0]);
    if (Number.isFinite(Number(j.input_i)) && Number(j.input_i) > -70) af += `:measured_I=${j.input_i}:measured_TP=${j.input_tp}:measured_LRA=${j.input_lra}:measured_thresh=${j.input_thresh}:offset=${j.target_offset}:linear=true`;
  }
  await runOk('ffmpeg', ['-v', 'error', '-y', '-i', inWav, '-af', af + ',aresample=48000', '-ar', '48000', '-ac', '2', outWav], { timeoutMs: 600000 });
}

// 소리 섞기 → mix.wav → loudnorm → final.wav
async function audioMix({ tl, voice, bgm, sfx, dir }) {
  const total = tl.total;
  const inputs = [], fil = [], mix = [];
  let n = 0;
  const narr = (voice || []).filter(v => v && v.file);
  narr.forEach((v, k) => {
    inputs.push('-i', v.file);
    const ms = Math.round(tl.lines[k].t0 * 1000);
    fil.push(`[${n}:a]aresample=48000,aformat=channel_layouts=stereo,adelay=${ms}|${ms}[n${k}]`);
    n++;
  });
  if (narr.length) {
    fil.push(narr.map((_, k) => `[n${k}]`).join('') + `amix=inputs=${narr.length}:normalize=0:duration=longest,apad=whole_dur=${f3(total)}[nar]`);
    fil.push('[nar]asplit=2[nar1][narsc]');
    mix.push('[nar1]');
  }
  if (bgm && bgm.file) {
    inputs.push('-stream_loop', '-1', '-i', bgm.file);
    const g = Math.pow(10, (bgm.gain_db ?? -20) / 20);
    fil.push(`[${n}:a]aresample=48000,aformat=channel_layouts=stereo,volume=${g.toFixed(4)},atrim=0:${f3(total)},afade=t=out:st=${f3(Math.max(0, total - 1.2))}:d=1.2[bgm0]`);
    if (narr.length) { fil.push('[bgm0][narsc]sidechaincompress=threshold=0.04:ratio=6:attack=25:release=350:makeup=1[bgm]'); mix.push('[bgm]'); }
    else mix.push('[bgm0]');
    n++;
  } else if (narr.length) fil.push('[narsc]anullsink');
  (sfx || []).forEach((s, k) => {
    inputs.push('-i', s.file);
    const ms = Math.round(s.t * 1000);
    fil.push(`[${n}:a]aresample=48000,aformat=channel_layouts=stereo,volume=${(s.gain ?? 0.35).toFixed(3)},adelay=${ms}|${ms}[x${k}]`);
    mix.push(`[x${k}]`);
    n++;
  });
  const mixWav = path.join(dir, 'mix.wav'), finalWav = path.join(dir, 'final.wav');
  if (!mix.length) {
    await runOk('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=stereo', '-t', f3(total), finalWav]);
    return { file: finalWav, silent: true, novoice: true };
  }
  fil.push(mix.join('') + `amix=inputs=${mix.length}:normalize=0:duration=longest,atrim=0:${f3(total)}[aout]`);
  const g = path.join(dir, 'audio.graph');
  fs.writeFileSync(g, fil.join(';\n'));
  await runOk('ffmpeg', ['-v', 'error', '-y', ...inputs, '-/filter_complex', g, '-map', '[aout]', '-t', f3(total), '-ar', '48000', mixWav], { timeoutMs: 600000 });
  await loudnorm(mixWav, finalWav);
  return { file: finalWav, silent: false, novoice: !narr.length };
}

// 한 편 렌더. 반환 {file, overlay:{metrics,fonts}, audio:{silent}}
export async function renderVideo({ spec, tl, src, title, fonts, voice, bgm, sfx, dir, comment, onProgress }) {
  fs.mkdirSync(dir, { recursive: true });
  const scenes = renderScenes(tl);
  const ov = await renderOverlays({ spec, scenes, title, fonts, outDir: path.join(dir, 'ov'), onProgress: (a, b) => onProgress && onProgress('overlay', a, b) });
  const list = writeConcat(ov.shots, path.join(dir, 'overlay.ffconcat'));
  const audio = await audioMix({ tl, voice, bgm, sfx, dir });
  const vg = videoGraph({ spec, tl, src });
  const inputs = [...vg.inputs, '-f', 'concat', '-safe', '0', '-i', list, '-i', audio.file];
  const ovIdx = vg.next, aIdx = vg.next + 1;
  const fil = [...vg.fil, `[${ovIdx}:v]format=rgba,setsar=1[ov]`, `[base][ov]overlay=0:0:eof_action=repeat:format=auto,format=yuv420p[vout]`];
  const g = path.join(dir, 'video.graph');
  fs.writeFileSync(g, fil.join(';\n'));
  const out = path.join(dir, 'draft.mp4');
  await runOk('ffmpeg', ['-v', 'error', '-y', ...inputs, '-/filter_complex', g, '-map', '[vout]', '-map', `${aIdx}:a`, '-t', f3(tl.total), '-r', String(FPS),
    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart',
    ...(comment ? ['-metadata', `comment=${comment}`] : []), out], { timeoutMs: 30 * 60000 });
  return { file: out, overlay: { metrics: ov.metrics, fonts: ov.fonts, shots: ov.shots.length }, audio };
}

export const bgHex = hex;
