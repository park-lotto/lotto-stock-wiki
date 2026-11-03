// 회원 PC 내 프리셋(관제 304) — 고급반 벤치마킹으로 만든 프리셋. 서버에 올라가지 않고 이 PC(~/.shortem/my_presets/<채널>/) 에만 있다.
//   목록 판단 주인 = 이 파일 한 곳. 모양은 서버 프리셋과 같게(id·name) 줘서 shortem_presets·프리셋 고르기·설정 화면이 그대로 쓴다.
//   제작 때 엔진 자리(channel/)로 옮기는 일은 preset_rent.rentPreset 이 한다 — 서버 임대와 같은 꼴(쓰는 동안만 두고 지운다).
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { ensureDir, homeDir, jail, writeFileIn } from './paths.js';

const FILE = 'my_presets.json';
export const myRoot = () => ensureDir(homeDir(), 'my_presets');
export const mineId = (slug, style) => 'p_' + crypto.createHash('sha256').update(`local/${slug}/${style}`).digest('hex').slice(0, 10);

export function listMine() {
  try { return JSON.parse(fs.readFileSync(jail(homeDir(), FILE), 'utf8')).presets || []; } catch { return []; }
}
export const mineById = id => listMine().find(p => p.id === id) || null;

// 벤치마킹 결과(<out>/channel/<slug>) → 내 프리셋. 같은 이름으로 다시 만들면 새 것으로 바꾼다.
export function addMine(out, r, channel = '') {
  const dst = path.join(myRoot(), r.slug);
  fs.rmSync(dst, { recursive: true, force: true });
  fs.cpSync(path.join(out, 'channel', r.slug), dst, { recursive: true });
  const fresh = r.presets.map((p, i) => ({ id: mineId(r.slug, p.style), name: i ? `${r.name} ${i + 1}` : r.name, slug: r.slug, style: p.style,
    sources: p.sources.length, channel, made: Date.now() }));
  writeFileIn(homeDir(), FILE, JSON.stringify({ presets: [...listMine().filter(p => p.slug !== r.slug), ...fresh] }));
  return fresh;
}

// 채널 벤치마킹 2판 시험 편 임시본(관제 319) — 임시본은 같은 slug 로 올라가 같은 이름의 원래 내 프리셋을 덮는다.
//   덮기 전에 원래 것을 한 벌 두고(keepMine), 완성 못 한 흐름 끝에서 임시본을 지우고 되살린다(dropMine). 완성이면 addMine 이 갈아 끼우고 둔 벌만 버린다(forgetKept).
const SLUG_RE = /^[\w-]{1,60}$/;
const keepDir = slug => path.join(myRoot(), '_keep', slug);
//   완성 표식 = list.json(마지막에 쓴다). 복사는 _keep/<slug>.tmp 에서 하고 renameSync 로 확정 — 중간에 끊긴 반쪽은 완성본 자리에 남지 않는다.
//   표식 없는 _keep/<slug>(옛 판이 남긴 반쪽)·남은 .tmp 는 '이미 둠'으로 보지 않고 지운 뒤 다시 둔다(최종 검토 — 반쪽을 믿으면 dropMine 이 원본을 잃는다).
const keptOk = slug => fs.existsSync(path.join(keepDir(slug), 'list.json'));
export function keepMine(slug) {
  if (!SLUG_RE.test(String(slug || '')) || keptOk(slug)) return false;
  const tmp = keepDir(slug) + '.tmp';
  fs.rmSync(tmp, { recursive: true, force: true });
  fs.rmSync(keepDir(slug), { recursive: true, force: true });       // 표식 없는 반쪽
  const old = listMine().filter(p => p.slug === slug);
  if (!old.length || !fs.existsSync(path.join(myRoot(), slug))) return false;
  try {
    fs.cpSync(path.join(myRoot(), slug), path.join(tmp, 'files'), { recursive: true });
    fs.writeFileSync(path.join(tmp, 'list.json'), JSON.stringify(old));
    fs.renameSync(tmp, keepDir(slug));
  } catch (e) { fs.rmSync(tmp, { recursive: true, force: true }); throw e; }   // 던진다 — 둘 곳을 못 만들었는데 임시본이 원본을 덮으면 안 된다(부르는 쪽이 멈춘다)
  return true;
}
export function forgetKept(slug) { if (SLUG_RE.test(String(slug || ''))) fs.rmSync(keepDir(slug), { recursive: true, force: true }); }
export function dropMine(slug) {
  if (!SLUG_RE.test(String(slug || ''))) return false;
  const dst = path.join(myRoot(), slug);
  let back = [];
  if (fs.existsSync(path.join(keepDir(slug), 'list.json'))) {   // 되살리기가 지우기보다 먼저 — 둔 벌을 옆에 다 옮겨 놓은 뒤에만 임시본을 지운다
    back = JSON.parse(fs.readFileSync(path.join(keepDir(slug), 'list.json'), 'utf8'));
    const tmp = dst + '.restore';
    fs.rmSync(tmp, { recursive: true, force: true });
    fs.cpSync(path.join(keepDir(slug), 'files'), tmp, { recursive: true });
    fs.rmSync(dst, { recursive: true, force: true });
    fs.renameSync(tmp, dst);
  } else fs.rmSync(dst, { recursive: true, force: true });
  writeFileIn(homeDir(), FILE, JSON.stringify({ presets: [...listMine().filter(p => p.slug !== slug), ...back] }));
  forgetKept(slug);
  return true;
}
// 둔 벌이 남은 slug 들 — 켤 때 주인 흐름이 없으면 되살린다(benchmark.recoverBench)
export function keptSlugs() {
  try { return fs.readdirSync(path.join(myRoot(), '_keep')).filter(n => SLUG_RE.test(n)); } catch { return []; }
}

// 서버 프리셋 목록(profiles.json 꼴) + 내 프리셋 — 프리셋 이름을 다루는 곳은 이 합친 목록만 본다
export function withMine(c) {
  const mine = listMine();
  if (!mine.length) return c;
  const view = p => ({ id: p.id, name: p.name, desc: '내 벤치마킹 프리셋', aliases: [] });
  return { ...c, presets: [...((c && c.presets) || []), ...mine.map(view)], entitled_presets: [...((c && c.entitled_presets) || []), ...mine.map(p => p.id)] };
}
