// 작업 기록지(관제 263/265, 사장님 10-25 "회원은 어디에 저장할지 모르니 기록지를 따로. 날짜·채널 등등").
//   회원이 완성본을 어디로 옮기든 기록은 고정 자리 ~/.shortem/작업기록.jsonl(SHORTEM_HOME) 에 한 편 한 줄.
//   칸·뜻은 엔진 기록지(tools/calcopy/work_log.py FIELDS)와 같다 — 엔진 done_list 가 이 파일도 읽는다(list_(member=True)).
//   부르는 곳 = make_flow.keepFinal 한 곳(완성본을 작업 폴더에 새로 복사한 직후). 모르는 칸은 null — 지어 넣지 않는다.
import fs from 'node:fs';
import crypto from 'node:crypto';
import { homeDir, jail } from './paths.js';
import { readLicense, keyPrint } from './license.js';

export const FIELDS = ['date', 'bench_channel', 'our_channel', 'style', 'person', 'product', 'bench_url', 'origin_url',
  'final_path', 'final_md5', 'drive_path', 'duration', 'made_by', 'status', 'note'];
const STATUS = ['delivered', 'stopped', 'made'];
export const workLogPath = () => jail(homeDir(), '작업기록.jsonl');

// KST ISO(초까지, +09:00) — 엔진 now_kst 와 같은 꼴
export function nowKst(ms = Date.now()) {
  return new Date(ms + 9 * 3600e3).toISOString().slice(0, 19) + '+09:00';
}

export function memberId() {
  const k = readLicense();
  return 'member:' + (k ? keyPrint(k) : 'unknown');   // 라이선스 키는 그대로 적지 않는다(지문 12자)
}

export function readWorkLog() {
  let txt = '';
  try { txt = fs.readFileSync(workLogPath(), 'utf8'); } catch { return []; }
  const rows = [];
  for (const ln of txt.split('\n')) { if (!ln.trim()) continue; try { rows.push(JSON.parse(ln)); } catch { /* 깨진 줄은 건너뛴다 */ } }
  return rows;
}

export function fileMd5(p) {
  const h = crypto.createHash('md5');
  const fd = fs.openSync(p, 'r');
  try {
    const buf = Buffer.alloc(1 << 20);
    let n;
    while ((n = fs.readSync(fd, buf, 0, buf.length, null)) > 0) h.update(buf.subarray(0, n));
  } finally { fs.closeSync(fd); }
  return h.digest('hex');
}

// 한 편 한 줄 — 같은 final_md5+final_path(+status) 줄이 이미 있으면 다시 쓰지 않는다
export function appendWorkLog(rec) {
  const bad = Object.keys(rec).filter(k => !FIELDS.includes(k));
  if (bad.length) throw new Error('모르는 칸: ' + bad.join(','));
  const row = Object.fromEntries(FIELDS.map(k => [k, rec[k] ?? null]));
  row.date = row.date || nowKst();
  row.made_by = row.made_by || memberId();
  row.status = row.status || 'delivered';
  if (!STATUS.includes(row.status)) throw new Error('status 는 ' + STATUS.join('|'));
  if (row.status === 'stopped' && !row.note) throw new Error('멈춘 편은 note 에 이유');
  if (row.final_md5 && readWorkLog().some(r => r.final_md5 === row.final_md5 && r.final_path === row.final_path && r.status === row.status)) return row;
  fs.mkdirSync(homeDir(), { recursive: true });
  fs.appendFileSync(workLogPath(), JSON.stringify(row) + '\n', 'utf8');
  return row;
}

// 완성본 한 편 — 실패해도 완성 응답은 막지 않는다(경보 한 줄은 남긴다)
export function logFinal(video, { title = '', preset = null, product = null, sid = '' } = {}) {
  try {
    return appendWorkLog({ style: preset ? String(preset) : null, product: product ? String(product) : null,
      final_path: video, final_md5: fileMd5(video), status: 'delivered', note: [title && `제목 ${title}`, sid && `sid ${sid}`].filter(Boolean).join(' · ') || null });
  } catch (e) {
    console.error('[작업기록 실패]', String(e && e.message || e).slice(0, 200));
    return null;
  }
}
