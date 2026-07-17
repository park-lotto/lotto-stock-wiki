// 컴포지션 하나를 inputProps(단어 등)와 함께 투명 qtrle .mov로 렌더.
// 텍스트 효과는 비트마다 단어가 달라 미리 못 굽는다 → 이 스크립트로 그때그때 렌더.
// 사용: node src/render-one.mjs <compId> <word> <outFile.mov>
import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {spawnSync} from 'child_process';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const [, , id, word, outFile, position] = process.argv;
if (!id || !outFile) {
  console.error('usage: node src/render-one.mjs <compId> <word> <outFile.mov> [position]');
  process.exit(1);
}
const tmpDir = path.join(here, '..', '.render_tmp');
fs.mkdirSync(tmpDir, {recursive: true});

// word 인자가 JSON({...})이면 통째로 inputProps로. 아니면 word(+position) 단순형.
let inputProps = {};
if (word && word.trim().startsWith('{')) {
  inputProps = JSON.parse(word);
} else {
  if (word) inputProps.word = word;
  if (position) inputProps.position = position;
}
const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts')});
const composition = await selectComposition({serveUrl, id, inputProps});
const proresPath = path.join(tmpDir, id + '_prores.mov');
await renderMedia({
  composition, serveUrl, inputProps,
  codec: 'prores', proResProfile: '4444', pixelFormat: 'yuva444p10le', imageFormat: 'png',
  outputLocation: proresPath,
});
// ProRes4444(알파) → qtrle(argb) 무손실. 제품 오버레이 체인에서 검증된 포맷.
const r = spawnSync('ffmpeg', ['-y', '-i', proresPath, '-an', '-c:v', 'qtrle', path.resolve(outFile)],
  {stdio: 'inherit'});
if (r.status !== 0) throw new Error('ffmpeg qtrle 변환 실패 (status ' + r.status + ')');
fs.rmSync(proresPath, {force: true});
console.log('rendered', outFile);
