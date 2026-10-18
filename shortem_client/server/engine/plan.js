// 장면 계획 — 대본 줄 → 자막 조각(장면) · 줄마다 영상 컷 · 효과음 자리 · 꼬리(틀 끈 구간).
//   plan(): 렌더·TTS 전 계획(선검수용, 시각은 추정). timeline(): 음성 길이가 나온 뒤 실제 시각을 확정.
//   판단 주인: 자막 나누기 = chunkLine · 컷 고르기 = pickCuts · 시각 = timeline. 렌더는 timeline 결과만 읽는다.
import { captionLayer, titleLayer, framesAt } from './frame.js';

export const EST_CPS = 7.6;      // 음성이 없을 때 줄 길이 추정(글자/초, 공백 뺌)
const bare = s => String(s || '').replace(/\s+/g, '');

// 자막 칸 한 줄에 들어갈 글자 수(대략) — 칸 폭 / (글자 크기 + 자간)
export function captionCapacity(cap) {
  if (!cap) return 16;
  const per = Math.max(8, cap.size * 0.92 + (cap.letter_spacing || 0));
  return Math.max(6, Math.floor(cap.w / per));
}

// 줄 하나를 자막 조각들로 — 어절 단위, 쉼표·마침표 뒤를 먼저 끊는다, 조각 길이를 고르게
export function chunkLine(text, cap) {
  const words = String(text || '').trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  const total = words.join(' ').length;
  const k = Math.max(1, Math.ceil(total / cap));
  const target = total / k;
  const out = [];
  let cur = '';
  for (let i = 0; i < words.length; i++) {
    const w = words[i];
    const next = cur ? cur + ' ' + w : w;
    const left = words.length - i;
    if (cur && (next.length > cap || (cur.length >= target * 0.85 && /[,.!?…]$/.test(cur)) || (cur.length >= target && out.length < k - 1 && left > 0))) {
      out.push(cur); cur = w;
    } else cur = next;
  }
  if (cur) out.push(cur);
  return out;
}

// 계획(추정 시각). spec = normalizeFrame 결과, script = {title, lines}, opts = {mode:'single'|'accumulate'}
export function plan(spec, script, opts = {}) {
  const fr0 = spec.frames[0];
  const cap = captionLayer(fr0.layers) || captionLayer(spec.frames[spec.frames.length - 1].layers);
  const capacity = captionCapacity(cap);
  const accumulate = opts.mode === 'accumulate' && cap && cap.lines > 1;
  const lines = script.lines.map((text, i) => {
    const chunks = chunkLine(text, capacity);
    return { i, text, est: Math.max(0.9, bare(text).length / EST_CPS), chunks };
  });
  const scenes = [];
  lines.forEach(l => l.chunks.forEach((c, j) => {
    const shown = accumulate ? l.chunks.slice(Math.max(0, j - cap.lines + 1), j + 1).join('\n') : c;
    scenes.push({ line: l.i, chunk: j, text: c, caption: shown });
  }));
  return { capacity, accumulate, lines, scenes, tail_sec: spec.tail_sec || 0, title: script.title };
}

// 영상 컷 고르기 — 줄마다 소재의 서로 다른 장면 구간에서, 줄 길이만큼(겹치지 않게, 앞에서부터)
export function pickCuts(durs, analysis, tailSec = 0) {
  const D = (analysis && analysis.probe && analysis.probe.duration) || 0;
  const segs = (analysis && analysis.scenes && analysis.scenes.length ? analysis.scenes : (D ? [[0, D]] : [])).map(([a, b]) => ({ a, b, used: a }));
  const need = [...durs, ...(tailSec ? [tailSec] : [])];
  if (!D) return need.map(d => ({ src: null, start: 0, dur: d }));
  const cuts = [];
  let si = 0;
  for (const d of need) {
    let pick = null;
    for (let k = 0; k < segs.length; k++) {   // 앞에서부터 남은 길이가 충분한 장면
      const s = segs[(si + k) % segs.length];
      if (s.b - s.used >= d + 0.05) { pick = s; si = (si + k + 1) % segs.length; break; }
    }
    if (pick) { cuts.push({ start: pick.used + 0.02, dur: d }); pick.used += d + 0.05; continue; }
    // 충분한 장면이 없으면 가장 많이 남은 곳, 그것도 없으면 처음부터 다시(반복 허용)
    const best = segs.reduce((m, s) => (s.b - s.used > m.b - m.used ? s : m), segs[0]);
    if (best.b - best.used > 0.6) { const len = Math.min(d, best.b - best.used); cuts.push({ start: best.used, dur: d, short: len < d }); best.used += len; }
    else { const st = Math.max(0, Math.min(D - d - 0.05, (cuts.length * 1.7) % Math.max(0.1, D - d))); cuts.push({ start: st, dur: d, reuse: true }); }
  }
  return cuts.map(c => ({ ...c, start: Math.max(0, Math.min(c.start, Math.max(0, D - 0.1))) }));
}

// 실제 시각 확정 — voice = [{dur, align?:{chars,starts,ends}}] (없으면 추정 길이)
//   반환 {total, narr_end, lines:[{i,t0,t1}], scenes:[{…,t0,t1,words?}], cuts:[{line|null,t0,dur,start,full}], tail}
export function timeline(p, voice, analysis, spec, { gap = 0.04 } = {}) {
  let t = 0;
  const lines = [], scenes = [];
  p.lines.forEach((l, k) => {
    const v = voice && voice[k];
    const dur = v && v.dur > 0 ? v.dur : l.est;
    const t0 = t, t1 = t + dur;
    lines.push({ i: l.i, t0, t1 });
    // 조각 시각: 정렬(글자 시각)이 있으면 그 글자 시각, 없으면 글자 수 비례
    const lens = l.chunks.map(c => bare(c).length);
    const sum = lens.reduce((a, b) => a + b, 0) || 1;
    let acc = 0;
    l.chunks.forEach((c, j) => {
      let a = t0 + (acc / sum) * dur, b = t0 + ((acc + lens[j]) / sum) * dur;
      if (v && v.align && v.align.ends && v.align.ends.length) {
        const ends = v.align.ends, starts = v.align.starts, n = ends.length;
        const map = x => Math.min(n - 1, Math.max(0, Math.round((x / sum) * n)));
        a = t0 + (j === 0 ? 0 : starts[map(acc)] || 0);
        b = t0 + (j === l.chunks.length - 1 ? dur : ends[Math.max(0, map(acc + lens[j]) - 1)] || 0);
        if (b <= a) b = a + 0.3;
      }
      acc += lens[j];
      scenes.push({ ...p.scenes.find(s => s.line === l.i && s.chunk === j), t0: a, t1: b });
    });
    t = t1 + (k < p.lines.length - 1 ? gap : 0);
  });
  // 조각 사이 빈틈 없애기(앞 조각 끝 = 다음 조각 시작)
  for (let i = 0; i < scenes.length - 1; i++) scenes[i].t1 = scenes[i + 1].t0;
  const narrEnd = t;
  const tail = p.tail_sec || 0;
  const total = narrEnd + tail;
  if (scenes.length) scenes[scenes.length - 1].t1 = narrEnd;
  // 단어 시각(강조 'auto' 용) — 조각 안 글자 수 비례
  for (const s of scenes) {
    const ws = s.text.split(/\s+/).filter(Boolean), ln = ws.map(w => w.length), sm = ln.reduce((a, b) => a + b, 0) || 1;
    let a = 0;
    s.words = ws.map((w, k) => { const r = { w, t0: s.t0 + (a / sm) * (s.t1 - s.t0) }; a += ln[k]; return r; });
  }
  // 컷: 줄마다 하나(줄 사이 틈은 다음 줄 컷에 붙인다) + 꼬리 하나
  const durs = lines.map((l, k) => (k < lines.length - 1 ? lines[k + 1].t0 : narrEnd) - l.t0);
  const picks = pickCuts(durs, analysis, tail);
  const cuts = picks.map((c, k) => ({ line: k < lines.length ? k : null, t0: k < lines.length ? lines[k].t0 : narrEnd, dur: c.dur, start: c.start, full: k >= lines.length }));
  // 장면마다 그 시각의 틀(frames 여러 장일 때)
  for (const s of scenes) s.frame = framesAt(spec, s.t0 + 1e-3).id;
  return { total, narr_end: narrEnd, lines, scenes, cuts, tail };
}

export const titleLinesOf = spec => { const t = titleLayer(spec.frames[0].layers) || titleLayer(spec.frames[spec.frames.length - 1].layers); return t ? t.lines : 0; };
