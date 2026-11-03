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

// 서버 프리셋 목록(profiles.json 꼴) + 내 프리셋 — 프리셋 이름을 다루는 곳은 이 합친 목록만 본다
export function withMine(c) {
  const mine = listMine();
  if (!mine.length) return c;
  const view = p => ({ id: p.id, name: p.name, desc: '내 벤치마킹 프리셋', aliases: [] });
  return { ...c, presets: [...((c && c.presets) || []), ...mine.map(view)], entitled_presets: [...((c && c.entitled_presets) || []), ...mine.map(p => p.id)] };
}
