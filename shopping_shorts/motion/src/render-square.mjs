// 랜딩 4단계 정사각 칸 영상 렌더.
//   node src/render-square.mjs stills sq_1 15 75 165      → .render_tmp/sq_1_f<N>.png
//   node src/render-square.mjs mp4 sq_1 [sq_2b ...]       → ../static/landing/<id>.mp4
// 캡처 원본은 public/sq/{A,B,C}.png (gitignore).
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import {spawnSync} from 'child_process';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const tmpDir = path.join(here, '..', '.render_tmp');
fs.mkdirSync(tmpDir, {recursive: true});
const [, , mode, ...rest] = process.argv;
const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts'), publicDir: path.join(here, '..', 'public')});

if (mode === 'stills') {
  const [id, ...frames] = rest;
  const composition = await selectComposition({serveUrl, id: `LandingSquare-${id.replace(/_/g, "-")}`});
  for (const f of frames.map(Number)) {
    const out = path.join(tmpDir, `${id}_f${String(f).padStart(3, '0')}.png`);
    await renderStill({composition, serveUrl, frame: f, output: out, imageFormat: 'png'});
    console.log('still', out);
  }
} else if (mode === 'mp4') {
  const outDir = path.join(here, '..', '..', 'static', 'landing');
  for (const id of rest) {
    const composition = await selectComposition({serveUrl, id: `LandingSquare-${id.replace(/_/g, "-")}`});
    const raw = path.join(tmpDir, `${id}_raw.mp4`);
    await renderMedia({composition, serveUrl, codec: 'h264', imageFormat: 'png', crf: 14, outputLocation: raw, muted: true});
    const mp4 = path.join(outDir, `${id}.mp4`);
    const r = spawnSync('ffmpeg', ['-y', '-v', 'error', '-i', raw, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', '23',
      '-vf', 'scale=in_range=full:out_range=tv,format=yuv420p', '-color_range', 'tv', '-movflags', '+faststart', '-r', '30', mp4], {stdio: 'inherit'});
    if (r.status !== 0) throw new Error('ffmpeg 실패 ' + r.status);
    console.log('mp4', mp4, fs.statSync(mp4).size, 'bytes');
  }
} else {
  console.error('usage: node src/render-square.mjs stills <id> <frames...> | mp4 <id...>');
  process.exit(1);
}
