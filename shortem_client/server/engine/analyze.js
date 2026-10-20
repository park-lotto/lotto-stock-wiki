// 소재 분석 — ffprobe(길이·크기·소리) + 장면 바뀜 시각(ffmpeg scene) → 장면 구간 목록.
import { runOk, run } from '../tools_paths.js';

export async function probe(file) {
  const r = await runOk('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:stream=codec_type,width,height,r_frame_rate', '-of', 'json', file], { timeoutMs: 60000 });
  const j = JSON.parse(r.stdout.toString('utf8') || '{}');
  const v = (j.streams || []).find(s => s.codec_type === 'video') || {};
  const a = (j.streams || []).find(s => s.codec_type === 'audio');
  const [n, d] = String(v.r_frame_rate || '30/1').split('/').map(Number);
  return { duration: Number(j.format && j.format.duration) || 0, width: v.width || 0, height: v.height || 0, fps: d ? n / d : 30, audio: !!a, video: !!v.width };
}

// 장면 바뀜(작게 줄여서 빠르게). 반환 [[시작, 끝], …] — 짧은 조각은 앞 장면에 붙인다
export async function sceneCuts(file, duration, { thresh = 0.32, minLen = 0.8 } = {}) {
  if (!duration) return [];
  const r = await run('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-an', '-vf', `scale=320:-2,select='gt(scene,${thresh})',showinfo`, '-f', 'null', '-'], { timeoutMs: 10 * 60000 });
  const times = [...r.stderr.matchAll(/pts_time:([0-9.]+)/g)].map(m => Number(m[1])).filter(t => t > 0.2 && t < duration - 0.2);
  const pts = [0, ...times, duration];
  const segs = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1];
    if (segs.length && b - a < minLen) segs[segs.length - 1][1] = b;
    else segs.push([a, b]);
  }
  return segs.map(([a, b]) => [Math.round(a * 1000) / 1000, Math.round(b * 1000) / 1000]);
}

export async function analyze(video) {
  if (!video) return { probe: null, scenes: [] };
  const p = await probe(video);
  if (!p.video) { const e = new Error('영상 줄기가 없는 파일입니다'); e.code = 'no_video'; throw e; }
  const scenes = await sceneCuts(video, p.duration);
  return { probe: p, scenes };
}
