import {bundle} from '@remotion/bundler';
import {renderMedia, selectComposition} from '@remotion/renderer';
import {spawnSync} from 'child_process';
import fs from 'fs';
import path from 'path';
import {fileURLToPath} from 'url';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(here, '..', '..', 'assets', 'motion');
const tmpDir = path.join(here, '..', '.render_tmp');
fs.mkdirSync(tmpDir, {recursive: true});

// 자산 포맷 결정(2026-07-15 실측): VP9 알파 webm은 ffmpeg 기본 vp9 디코더가 알파를 무시해
// (alphaextract YAVG=255=완전불투명) 제품 오버레이 체인에서 불투명 박스로 나온다.
// libvpx-vp9 디코더를 명시해야만 알파가 살지만 제품 빌더(_motion_layer_filters)는 디코더를
// 지정하지 않는다. 따라서 파이프라인에서 검증된 qtrle(argb) .mov로 확정한다.
// 방법: Remotion에서 ProRes4444(알파) 렌더 → ffmpeg로 qtrle .mov 변환(무손실 알파 보존).
const LIB = [
  {id: 'SwipeLeft', file: 'swipe_left.mov'},
  {id: 'Sparkle', file: 'sparkle.mov'},
];

const serveUrl = await bundle({entryPoint: path.join(here, 'index.ts')});
for (const {id, file} of LIB) {
  const composition = await selectComposition({serveUrl, id});
  const proresPath = path.join(tmpDir, id + '_prores.mov');
  await renderMedia({
    composition, serveUrl,
    codec: 'prores', proResProfile: '4444', pixelFormat: 'yuva444p10le', imageFormat: 'png',
    outputLocation: proresPath,
  });
  const finalPath = path.join(outDir, file);
  const r = spawnSync('ffmpeg', ['-y', '-i', proresPath, '-an', '-c:v', 'qtrle', finalPath],
    {stdio: 'inherit'});
  if (r.status !== 0) {
    throw new Error('ffmpeg qtrle 변환 실패: ' + file + ' (status ' + r.status + ')');
  }
  fs.rmSync(proresPath, {force: true});
  console.log('rendered', file);
}
fs.rmSync(tmpDir, {recursive: true, force: true});
