// 랜딩 히어로 벽(LandingHeroWall) 렌더.
//   node src/render-hero.mjs stills 15 100 190 280   → .render_tmp/hero_f<N>.png (글자 검수용)
//   node src/render-hero.mjs mp4                       → ../static/landing/hero_wall.mp4 + hero_wall.jpg
// 썸네일은 public/hero/*.jpg, 폰트는 public/fonts/NotoSansKR-VF.otf (둘 다 gitignore, 재렌더 시 다시 받기).
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
const id = 'LandingHeroWall';

const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts'), publicDir: path.join(here, '..', 'public')});
const composition = await selectComposition({serveUrl, id});

if (mode === 'stills') {
  for (const f of rest.map(Number)) {
    const out = path.join(tmpDir, `hero_f${String(f).padStart(3, '0')}.png`);
    await renderStill({composition, serveUrl, frame: f, output: out, imageFormat: 'png'});
    console.log('still', out);
  }
} else if (mode === 'mp4') {
  const outDir = path.join(here, '..', '..', 'static', 'landing');
  fs.mkdirSync(outDir, {recursive: true});
  const raw = path.join(tmpDir, 'hero_wall_raw.mp4');
  await renderMedia({
    composition, serveUrl, codec: 'h264', imageFormat: 'jpeg', jpegQuality: 92, crf: 16,
    outputLocation: raw, muted: true,
    onProgress: ({progress}) => process.stdout.write(`\r${Math.round(progress * 100)}%`),
  });
  console.log('');
  const mp4 = path.join(outDir, 'hero_wall.mp4');
  // 웹용 재인코딩: yuv420p·faststart·용량 6MB 이하 목표
  const r = spawnSync('ffmpeg', ['-y', '-i', raw, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', String(rest[0] || 24),
    '-vf', 'scale=in_range=full:out_range=tv,format=yuv420p', '-color_range', 'tv', '-movflags', '+faststart', '-r', '30', mp4], {stdio: 'inherit'});
  if (r.status !== 0) throw new Error('ffmpeg 실패 ' + r.status);
  const poster = path.join(outDir, 'hero_wall.jpg');
  await renderStill({composition, serveUrl, frame: Number(rest[1] || 40), output: poster, imageFormat: 'jpeg', jpegQuality: 88});
  console.log('mp4', mp4, fs.statSync(mp4).size, 'bytes / poster', poster);
} else {
  console.error('usage: node src/render-hero.mjs stills <frames...> | mp4 [crf] [posterFrame]');
  process.exit(1);
}
