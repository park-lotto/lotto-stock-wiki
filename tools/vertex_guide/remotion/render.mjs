// 사용: node tools/vertex_guide/remotion/render.mjs <prep 출력폴더(public)> <out.mp4> [still프레임들,쉼표]
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'fs'; import path from 'path'; import {fileURLToPath} from 'url';
const here = path.dirname(fileURLToPath(import.meta.url));
const [, , pub, out, stills] = process.argv;
const scenes = JSON.parse(fs.readFileSync(path.join(pub, 'scenes.json'), 'utf-8'));
const serveUrl = await bundle({entryPoint: path.join(here, 'src', 'index.ts'), publicDir: path.resolve(pub)});
const inputProps = {scenes};
const composition = await selectComposition({serveUrl, id: 'VertexGuide', inputProps});
if (stills) {
  for (const fr of stills.split(',').map(Number)) {
    await renderStill({composition, serveUrl, inputProps, frame: fr, output: out.replace(/\.mp4$/, `_f${fr}.png`)});
  }
  console.log('stills done');
} else {
  await renderMedia({composition, serveUrl, inputProps, codec: 'h264', crf: 30, muted: true, outputLocation: out});
  console.log('video done', composition.durationInFrames, 'frames');
}
