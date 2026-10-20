// 내 채널 설정 = PC 로컬 파일 하나(~/.shortem/settings.json, 관제 234 5판 사장님 "저장도 로컬").
//   설정 화면(local_ui)·고객 Claude(shortem_settings)·엔진 제작(make_flow)이 모두 이 파일만 읽고 쓴다 — 판단 주인 한 곳.
//   값 검사는 엔진(preview_request.py check)이 한다. 여기는 깊게 합치고 저장만 한다.
import fs from 'node:fs';
import path from 'node:path';
import { homeDir, writeFileIn, jail } from './paths.js';
import { engineTool } from './engine_bridge.js';

const FILE = 'settings.json';
export const PID_RE = /^p_[0-9a-f]{10}$/;

export function readSettings() {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), FILE), 'utf8')); } catch { return { current: null, channels: {} }; }
}
const writeSettings = s => writeFileIn(homeDir(), FILE, JSON.stringify(s, null, 1));   // 임시 파일→이름 바꾸기(화면·Claude 가 동시에 써도 반쯤 쓴 파일을 안 읽는다)

let catCache = null;
export async function catalog() {
  if (catCache) return catCache;
  const r = await engineTool('catalog');
  if (r.error) throw new Error(r.error);
  catCache = r.catalog;
  return catCache;
}

export function useCatalog(c) { catCache = c; }   // 시험용 — 엔진을 띄우지 않고 표를 넣는다

function merge(base, over) {
  if (Array.isArray(over) || over === null || typeof over !== 'object') return over;
  const out = { ...(base && typeof base === 'object' && !Array.isArray(base) ? base : {}) };
  for (const [k, v] of Object.entries(over)) out[k] = merge(out[k], v);
  return out;
}

// ★기본값은 그 프리셋의 원본 영상에 맞춘다 — 모든 프리셋(사장님 10-20). 엔진 기본 팩 ← 프리셋 기본값(엔진 preview_request.preset_defaults 가
//   빌드 때 만든 표) ← 회원이 바꾼 칸. 회원이 안 바꾼 칸은 프리셋 값을 따른다(프리셋 기본값이 바뀌면 같이 바뀐다)
export async function packFor(pid) {
  const s = readSettings();
  const own = (s.channels[pid] || {}).pack;
  const cat = await catalog();
  return merge(merge(cat.default_pack, (cat.preset_defaults || {})[pid] || {}), own || {});
}

// patch 를 합쳐 검사 → 통과하면 저장. 반환 {ok, pack} 또는 {ok:false, errors}
export async function savePack(pid, patch, { select = true } = {}) {
  if (!PID_RE.test(String(pid || ''))) return { ok: false, errors: ['프리셋 id 모양이 아닙니다'] };
  const pack = merge(await packFor(pid), patch || {});
  const r = await engineTool('check', { pack });
  if (r.error) return { ok: false, errors: [r.error] };
  if (r.errors.length) return { ok: false, errors: r.errors };
  const s = readSettings();
  const prev = (s.channels[pid] || {}).pack || {};
  s.channels[pid] = { pack: merge(prev, patch || {}), updated: Date.now() };   // 고객이 바꾼 칸만 남긴다(기본값이 바뀌면 따라간다)
  if (select) s.current = pid;
  writeSettings(s);
  return { ok: true, pack };
}

export function select(pid) {
  if (!PID_RE.test(String(pid || ''))) return false;
  const s = readSettings();
  s.current = pid;
  writeSettings(s);
  return true;
}

export function resetPack(pid) {
  const s = readSettings();
  delete s.channels[pid];
  writeSettings(s);
}

// 엔진 팩 파일(~/.shortem/packs/<pid>.json = {"1": 합친 팩}) — 만들 때마다 지금 설정으로 새로 쓴다
export async function packFile(pid) {
  const rel = path.join('packs', `${pid}.json`);
  writeFileIn(homeDir(), rel, JSON.stringify({ 1: await packFor(pid) }));
  return path.join(homeDir(), rel);
}
