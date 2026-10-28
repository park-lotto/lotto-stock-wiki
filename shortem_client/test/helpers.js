// 시험 공용 — 실제 홈(~/.shortem)·바탕화면을 더럽히지 않게 SHORTEM_HOME·SHORTEM_WORK 를 임시 폴더로 돌린다.
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { startFakeServer, makeKey } from './fake_server.js';

const SCRATCH = 'C:/Users/TheRose/AppData/Local/Temp/claude/C--Users-TheRose-Desktop-------/8d1c735d-5957-415a-accb-7fcf73ca223d/scratchpad/client';
export const TMP_ROOT = process.env.SHORTEM_TEST_TMP || (fs.existsSync(SCRATCH) ? path.join(SCRATCH, 'tests') : path.join(os.tmpdir(), 'shortem_tests'));

export function freshDirs(name) {
  const root = path.join(TMP_ROOT, name + '_' + process.pid);
  fs.rmSync(root, { recursive: true, force: true });
  fs.mkdirSync(path.join(root, 'home'), { recursive: true });
  fs.mkdirSync(path.join(root, 'work'), { recursive: true });
  process.env.SHORTEM_HOME = path.join(root, 'home');
  process.env.SHORTEM_WORK = path.join(root, 'work');
  process.env.SHORTEM_DEV_TOOLS = '1';
  return root;
}

export async function withFake(opts = {}) {
  const fake = await startFakeServer(opts);
  process.env.SHORTEM_BASE = fake.url;
  process.env.SHORTEM_LICENSE = makeKey(12, Math.floor(Date.now() / 1000) + 86400, 1);
  return fake;
}

// 장면 바뀜이 있는 시험 영상(36초) — 없으면 만든다
export function synthVideo() {
  const p = path.join(TMP_ROOT, 'synth36.mp4');
  if (fs.existsSync(p)) return p;
  fs.mkdirSync(TMP_ROOT, { recursive: true });
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-f', 'lavfi', '-i', 'testsrc2=s=1280x720:r=30:d=12', '-f', 'lavfi', '-i', 'mandelbrot=s=1280x720:r=30', '-f', 'lavfi', '-i', 'sine=f=440:d=36',
    '-filter_complex', '[0:v]trim=0:12,setpts=PTS-STARTPTS[a];[1:v]trim=0:12,setpts=PTS-STARTPTS,format=yuv420p[b];[0:v]trim=0:12,setpts=PTS-STARTPTS,hue=h=120,format=yuv420p[c];[a][b][c]concat=n=3:v=1:a=0,format=yuv420p[v]',
    '-map', '[v]', '-map', '2:a', '-t', '36', '-c:v', 'libx264', '-preset', 'veryfast', '-c:a', 'aac', p]);
  return p;
}

export const SCRIPT_OK = { title: '집에서 만든\n미친 화면 실험', lines: ['이거 처음 보면 눈을 의심하게 돼', '색깔 막대가 갑자기 움직이기 시작했어', '그런데 화면이 통째로 소용돌이로 바뀌었지', '끝없이 빨려 들어가는 무늬가 계속 나와', '보는 사람마다 입을 다물지 못했대'] };

// 응답 JSON 안의 모든 키(깊이 무관)
export function allKeys(v, out = new Set()) {
  if (Array.isArray(v)) v.forEach(x => allKeys(x, out));
  else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) { out.add(k); allKeys(x, out); }
  return out;
}

// 응답 안 숫자(값) 경로 모음 — 허용 경로 밖 숫자 찾기용
export function numberPaths(v, p = '', out = []) {
  if (typeof v === 'number') out.push(p);
  else if (Array.isArray(v)) v.forEach((x, i) => numberPaths(x, p + '[]', out));
  else if (v && typeof v === 'object') for (const [k, x] of Object.entries(v)) numberPaths(x, p ? p + '.' + k : k, out);
  return out;
}
