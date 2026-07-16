// 씬별 리모션(B): 배경 영상을 포함한 전체화면 씬을 h264 mp4로 렌더(투명 아님).
// 오디오는 무음 렌더 후 원본 클립 오디오를 ffmpeg로 다시 muxing(싱크 보장).
// 사용: node src/render-scene.mjs <compId> <propsJSON> <outFile.mp4>
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const [, , id, propsJson, outFile] = process.argv;
if (!id || !outFile) {
  console.error('usage: node src/render-scene.mjs <compId> <propsJSON> <outFile.mp4>');
  process.exit(1);
}
const inputProps = propsJson ? JSON.parse(propsJson) : {};
const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts')});
const composition = await selectComposition({serveUrl, id, inputProps});
await renderMedia({
  composition, serveUrl, inputProps,
  codec: 'h264', pixelFormat: 'yuv420p', imageFormat: 'jpeg',
  outputLocation: path.resolve(outFile),
});
console.log('rendered', outFile);
