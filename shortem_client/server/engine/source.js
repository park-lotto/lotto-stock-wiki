// 소재 가져오기 — 유튜브(설치팩 동봉 yt-dlp 절대 경로) / 로컬 파일(읽기만) / 텍스트.
//   받은 영상은 jobs/<id>/source/ 에만 둔다. 외부 글(제목·설명·자막)은 data 로만 모델에 간다(지시로 읽지 않게 머리글은 firewall).
import fs from 'node:fs';
import path from 'node:path';
import { run, runOk, toolPath } from '../tools_paths.js';
import { inside } from '../paths.js';

const YT_RE = /^https:\/\/(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?v=|shorts\/)|youtu\.be\/)[A-Za-z0-9_-]{6,15}(?:[?&#][^\s]*)?$/;
const VIDEO_EXT = new Set(['.mp4', '.mov', '.mkv', '.webm', '.m4v', '.avi']);
export const MAX_SOURCE_SEC = 180;
const LONG_SEC = 1800;

export class SourceError extends Error {
  constructor(why, fix) { super(why); this.why = why; this.fix = fix; this.code = 'source'; }
}

export function checkSource(src) {
  if (!src || typeof src !== 'object') throw new SourceError('소재가 비어 있습니다', '유튜브 주소·내 PC 영상 경로·글 중 하나를 주세요');
  const kind = src.kind;
  if (kind === 'youtube') {
    if (!YT_RE.test(String(src.url || ''))) throw new SourceError('유튜브 영상 주소가 아닙니다', 'https://www.youtube.com/watch?v=… 또는 /shorts/… 주소를 주세요');
    return { kind, url: String(src.url) };
  }
  if (kind === 'local_video') {
    const p = String(src.path || '');
    if (!path.isAbsolute(p)) throw new SourceError('영상 경로는 전체 경로여야 합니다', '예: C:\\Users\\나\\Videos\\영상.mp4');
    if (!VIDEO_EXT.has(path.extname(p).toLowerCase())) throw new SourceError('영상 파일이 아닙니다', 'mp4·mov·mkv·webm 파일을 주세요');
    let st;
    try { st = fs.statSync(p); } catch { throw new SourceError('그 경로에 파일이 없습니다', '경로를 다시 확인해 주세요'); }
    if (!st.isFile()) throw new SourceError('파일이 아닙니다', '영상 파일 경로를 주세요');
    return { kind, path: p };
  }
  if (kind === 'text') {
    const t = String(src.text || '').trim();
    if (t.length < 10) throw new SourceError('글이 너무 짧습니다', '대본 재료가 될 글을 몇 문장 주세요');
    const out = { kind, text: t.slice(0, 8000) };
    if (src.video_path) out.video = checkSource({ kind: 'local_video', path: src.video_path }).path;
    return out;
  }
  throw new SourceError('지원하지 않는 소재입니다', 'youtube·local_video·text 중 하나로 주세요');
}

function vttToText(vtt) {
  const seen = new Set(), out = [];
  for (const line of vtt.split(/\r?\n/)) {
    if (!line.trim() || /-->/.test(line) || /^(WEBVTT|Kind:|Language:|NOTE)/.test(line) || /^\d+$/.test(line.trim())) continue;
    const t = line.replace(/<[^>]+>/g, '').trim();
    if (t && !seen.has(t)) { seen.add(t); out.push(t); }
  }
  return out.join(' ');
}

// 반환 {video: 절대경로|null, info:{title, text, transcript, kind}}
export async function fetchSource(src, jobDir) {
  const dir = path.join(jobDir, 'source');
  fs.mkdirSync(dir, { recursive: true });
  if (src.kind === 'local_video') return { video: src.path, info: { kind: 'local_video', title: path.basename(src.path, path.extname(src.path)), text: '', transcript: '' } };
  if (src.kind === 'text') return { video: src.video || null, info: { kind: 'text', title: '', text: src.text, transcript: '' } };
  // youtube — 먼저 정보만(-J), 그다음 앞부분만 받는다(긴 영상은 앞 MAX_SOURCE_SEC 초)
  const ff = path.dirname(toolPath('ffmpeg'));
  const j = await runOk('ytdlp', ['-J', '--no-playlist', '--no-warnings', src.url], { timeoutMs: 120000 }).catch(() => { throw new SourceError('유튜브 영상 정보를 못 받았습니다', '주소가 공개 영상인지 확인하고 다시 시도하세요'); });
  let meta = {};
  try { meta = JSON.parse(j.stdout.toString('utf8')); } catch { /* 빈 정보 */ }
  const dur = Number(meta.duration) || 0;
  // 구간 받기(--download-sections)는 유튜브에서 매우 느리다(실측 40초 구간 ≈10분) — 30분 이하 영상은 통째로 받고 앞부분만 잘라 쓴다
  const whole = !dur || dur <= LONG_SEC;
  const args = ['--no-playlist', '--no-warnings', '--ffmpeg-location', ff, '-f', 'bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4][height<=1080]/bv*[height<=1080]+ba/b', '--merge-output-format', 'mp4',
    '--write-auto-subs', '--write-subs', '--sub-langs', 'ko.*,ko', '--sub-format', 'vtt', '-o', path.join(dir, whole ? 'full.%(ext)s' : 'src.%(ext)s')];
  if (!whole) args.push('--download-sections', `*0-${MAX_SOURCE_SEC}`);
  args.push(src.url);
  const r = await run('ytdlp', args, { timeoutMs: 30 * 60000 });
  const mp4 = path.join(dir, 'src.mp4');
  const full = path.join(dir, 'full.mp4');
  if (whole && fs.existsSync(full)) {
    if (dur > MAX_SOURCE_SEC) { await runOk('ffmpeg', ['-v', 'error', '-y', '-i', full, '-t', String(MAX_SOURCE_SEC), '-c', 'copy', mp4], { timeoutMs: 600000 }); fs.rmSync(full, { force: true }); }
    else fs.renameSync(full, mp4);
  }
  if (!fs.existsSync(mp4)) throw new SourceError('유튜브 영상을 받지 못했습니다', '잠시 뒤 다시 시도하거나 내 PC 영상 파일로 주세요');
  if (r.code !== 0 && !fs.statSync(mp4).size) throw new SourceError('유튜브 영상을 받지 못했습니다', '잠시 뒤 다시 시도하세요');
  let transcript = '';
  for (const n of fs.readdirSync(dir)) if (n.endsWith('.vtt')) { transcript = vttToText(fs.readFileSync(path.join(dir, n), 'utf8')); break; }
  return { video: mp4, info: { kind: 'youtube', title: String(meta.title || '').slice(0, 200), text: String(meta.description || '').slice(0, 3000), transcript: transcript.slice(0, 6000) } };
}

export const isInJob = (jobDir, p) => inside(jobDir, p);
