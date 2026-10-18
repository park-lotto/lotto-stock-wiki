// 감사 로그 ~/.shortem/audit.jsonl (설계 §7-4·§7-7) — 90일 롤링.
//   적는 것: 시각·사건·job·단계 이름·결과·자산 id. 안 적는 것: 키·토큰·서명 URL·좌표·명령줄·대본 원문.
import fs from 'node:fs';
import path from 'node:path';
import { homeDir, jail } from './paths.js';

const KEEP_DAYS = 90;
const ALLOWED = new Set(['ev', 'job', 'step', 'result', 'code', 'assets', 'n', 'tool', 'key_fp', 'device_fp', 'profile', 'status', 'where', 'ms']);

// 값 청소 — 비밀처럼 생긴 것은 지운다
function scrub(v) {
  if (typeof v === 'number' || typeof v === 'boolean' || v == null) return v;
  if (Array.isArray(v)) return v.slice(0, 50).map(scrub);
  if (typeof v === 'object') return '[obj]';
  let s = String(v).slice(0, 200);
  s = s.replace(/SHORTEM-L1\.[^\s"']+/g, '[key]')
       .replace(/https?:\/\/\S+/g, '[url]')
       .replace(/\b[0-9a-f]{32,}\b/gi, '[hex]')
       .replace(/(?:[A-Za-z]:)?[\\/][^\s"']*[\\/][^\s"']*/g, '[path]');
  return s;
}

export function audit(ev, fields = {}) {
  const row = { ts: new Date().toISOString(), ev: scrub(ev) };
  for (const [k, v] of Object.entries(fields)) if (ALLOWED.has(k) && k !== 'ev') row[k] = k === 'key_fp' || k === 'device_fp' ? String(v).slice(0, 12) : scrub(v);
  try {
    const p = jail(homeDir(), 'audit.jsonl');
    fs.mkdirSync(path.dirname(p), { recursive: true });
    fs.appendFileSync(p, JSON.stringify(row) + '\n');
  } catch { /* 로그 실패로 제작을 멈추지 않는다 */ }
}

export function pruneAudit(now = Date.now()) {
  let p;
  try { p = jail(homeDir(), 'audit.jsonl'); } catch { return 0; }
  let lines;
  try { lines = fs.readFileSync(p, 'utf8').split('\n').filter(Boolean); } catch { return 0; }
  const cut = now - KEEP_DAYS * 86400000;
  const keep = lines.filter(l => { try { return Date.parse(JSON.parse(l).ts) >= cut; } catch { return false; } });
  if (keep.length !== lines.length) fs.writeFileSync(p, keep.join('\n') + (keep.length ? '\n' : ''));
  return lines.length - keep.length;
}
