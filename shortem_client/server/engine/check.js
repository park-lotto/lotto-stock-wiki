// 결과물 검사(설계 §6) — 고객 PC 에서만 돌고 서버로 보내지 않는다. verdict.json 은 job 폴더에만.
//   ffprobe 길이·해상도·코덱 / ebur128 통합 음량(LUFS) / 자막 칸 수(계획 = 그린 수)·자막이 화면 안·글꼴 로드.
import { run, runOk } from '../tools_paths.js';

export const DEFAULT_CHECK = Object.freeze({ lufs: [-16.5, -11.5], dur_tol: 0.35, width: 1080, height: 1920 });

export async function measureLufs(file) {
  const r = await run('ffmpeg', ['-hide_banner', '-nostats', '-i', file, '-vn', '-af', 'ebur128=framelog=quiet', '-f', 'null', '-'], { timeoutMs: 600000 });
  const sum = r.stderr.split('Summary:').pop();
  const m = sum.match(/I:\s*(-?[\d.]+|-inf)\s*LUFS/);
  return m ? (m[1] === '-inf' ? -Infinity : Number(m[1])) : null;
}

export async function probeOut(file) {
  const r = await runOk('ffprobe', ['-v', 'error', '-show_entries', 'format=duration:format_tags=comment:stream=codec_type,codec_name,width,height,r_frame_rate', '-of', 'json', file], { timeoutMs: 60000 });
  const j = JSON.parse(r.stdout.toString('utf8'));
  const v = (j.streams || []).find(s => s.codec_type === 'video') || {};
  const a = (j.streams || []).find(s => s.codec_type === 'audio');
  return { duration: Number(j.format.duration), width: v.width, height: v.height, vcodec: v.codec_name, fps: v.r_frame_rate, audio: !!a, comment: (j.format.tags || {}).comment || '' };
}

// 반환 {pass, items:[{name, ok, got?, want?}], measured}
export async function checkVideo(file, { tl, render, rules, silent, expectCaptions }) {
  const R = { ...DEFAULT_CHECK, ...((rules && rules.check) || {}) };
  const p = await probeOut(file);
  const lufs = await measureLufs(file);
  const items = [];
  const add = (name, ok, got, want) => items.push({ name, ok: !!ok, ...(got !== undefined ? { got } : {}), ...(want !== undefined ? { want } : {}) });
  add('해상도', p.width === R.width && p.height === R.height, `${p.width}x${p.height}`, `${R.width}x${R.height}`);
  add('영상 코덱', p.vcodec === 'h264', p.vcodec, 'h264');
  add('길이', Math.abs(p.duration - tl.total) <= R.dur_tol, Number(p.duration.toFixed(3)), Number(tl.total.toFixed(3)));
  add('소리 줄기', p.audio, p.audio, true);
  if (!silent) add('음량', lufs != null && lufs >= R.lufs[0] && lufs <= R.lufs[1], lufs, R.lufs);
  const m = (render && render.overlay && render.overlay.metrics) || [];
  const drawn = m.filter(x => !x.off && x.caption && x.caption.text);
  const want = expectCaptions != null ? expectCaptions : tl.scenes.length;
  add('자막 칸 수', drawn.length === want, drawn.length, want);
  add('자막이 화면 안', drawn.every(x => x.caption.inside), drawn.filter(x => !x.caption.inside).length, 0);
  const fonts = (render && render.overlay && render.overlay.fonts) || {};
  add('글꼴', Object.values(fonts).every(Boolean), Object.entries(fonts).filter(([, v]) => !v).map(([k]) => k).join(',') || 'ok', 'ok');
  return { pass: items.every(i => i.ok), items, measured: { ...p, lufs } };
}

// 미달 항목 → 고객용 방향 문장(수치 없음)
export function failHints(items) {
  const map = { 해상도: '화면 크기가 규격과 다릅니다', '영상 코덱': '영상 압축 형식이 다릅니다', 길이: '영상 길이가 계획과 다릅니다 — 다시 렌더하세요', '소리 줄기': '소리가 비었습니다',
    음량: '소리 크기가 기준 밖입니다 — 배경음 크기를 바꾸거나 다시 렌더하세요', '자막 칸 수': '자막 일부가 그려지지 않았습니다', '자막이 화면 안': '자막이 화면 밖으로 나갔습니다 — 해당 줄을 더 짧게', 글꼴: '글꼴 일부를 불러오지 못했습니다 — 다시 시도하세요' };
  return items.filter(i => !i.ok).map(i => map[i.name] || i.name);
}
