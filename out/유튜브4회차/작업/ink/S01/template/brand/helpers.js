/* P6~P10 장면 보조 (Opus 실행, 2026-10-29) — hq.js Layer + _assets/assets.js 위에서만 쓴다. 공용 파일은 건드리지 않는다.
 * art()   : 자산을 z 층마다 sub 레이어로 나눠 얹는다(앞팔·폰 채색이 몸 선을 덮도록). ff=true 면 채색 먼저(0.25초) → 펜 윤곽(R1).
 * stageL(): 무대 레이어 — 이미 그려진 상태로 0.45초 페이드인(R1, dashoffset 그리기 없음).
 * win()   : 0.15초 전환 창(겹침 없는 교체, R2·R6).
 * heroX() : 주인공 표정 묶음 전환(얼굴 전체 교체, 컷당 1회).
 */
const A = INKASSETS;
const W1 = A.W1;
function stageL(P, a, b = 1e9) { return P.sub({ stat: true }).vis(a, b, "fade"); }
function win(L, a, b = 1e9, k = 0.15) { return L.xf((t) => ({ o: Math.min(clamp((t - a) / k), 1 - clamp((t - b) / k)) })); }
function lw(sc) { return clamp(sc * 0.78, 1, 1.6); }
function art(L, asset, o = {}) {
  const As = typeof asset === "string" ? A.get(asset, o) : asset;
  const x = o.x || 0, y = o.y || 0, sc = o.sc || 1, s = o.s || 0, per = o.per || 0.05, pen = o.pen !== false, ff = o.ff !== false, k = lw(sc) * (o.wk || 1);
  const tr = (d) => d.replace(/(-?\d+(?:\.\d+)?)\s(-?\d+(?:\.\d+)?)/g, (m, px, py) => f(x + (+px) * sc) + " " + f(y + (+py) * sc));
  const items = As.items.map((i, n) => ({ ...i, n })).sort((a, b) => ((a.z || 0) - (b.z || 0)) || (a.n - b.n));
  const zs = [...new Set(items.map((i) => i.z || 0))];
  const subs = {}; zs.forEach((z) => (subs[z] = L.sub()));
  if (As.ground && o.shadow !== false) {
    const [x0, , x1] = As.box, gw = (x1 - x0) * 0.9 * sc, cx = x + (x0 + x1) / 2 * sc;
    subs[zs[0]].fill(ell(cx, y + 4 * sc, gw / 2, 12 * Math.max(1, sc * 0.8), { n: 16, a0: 0, sweep: Math.PI * 2 }), "#1F1D1A", s, 0.1, 0.25);
  }
  let t = s + (ff ? 0.12 : 0);
  items.forEach((i) => {
    const Lz = subs[i.z || 0];
    if (i.k === "fill") { if (o.opaque && i.c !== "#1F1D1A") { Lz.fill(tr(i.d), "#FFFFFF", ff ? s : t + 0.2, 0.85, ff ? 0.25 : 0.3); Lz.fill(tr(i.d), "#FFFFFF", ff ? s : t + 0.2, 0.85, ff ? 0.25 : 0.3); } Lz.fill(tr(i.d), i.c, ff ? s : t + 0.2, i.op, ff ? 0.25 : 0.3); }
    else {
      const big = i.w >= W1 - 0.5, dur = big ? per * 2.2 : per;
      Lz.line(tr(i.d), t, dur, { w: i.w * k, c: i.c === "#1F1D1A" ? undefined : i.c, pen: pen && big });
      t += dur * (big ? 1 : 0.5);
    }
  });
  return { end: t + per };
}
// 주인공 — faces: [{expr, at, look, tilt, view, pose}] (첫 얼굴 at 무시). draw:"pen"(첫 얼굴 펜) | "stat"(이미 그려진 채 등장)
function heroX(L, o) {
  const F = o.faces, out = { end: o.s || 0 };
  F.forEach((fc, i) => {
    const a = i ? fc.at : -1e9, b = i < F.length - 1 ? F[i + 1].at : 1e9;
    const Li = win(L.sub(), a, b, 0.15);
    const asset = A.hero({ pose: fc.pose || o.pose, expr: fc.expr, view: fc.view || o.view || "front", look: fc.look, tilt: fc.tilt });
    const T = (i === 0 && o.draw === "pen") ? Li : Li.sub({ stat: true });
    const r = art(T, asset, { x: o.x, y: o.y, sc: o.sc, s: o.s || 0, per: o.per || 0.04, ff: true, opaque: true });
    if (i === 0) out.end = r.end;
  });
  return out;
}
// 얼굴만(클로즈업)
function faceX(L, o) {
  const F = o.faces, out = { end: o.s || 0 };
  F.forEach((fc, i) => {
    const a = i ? fc.at : -1e9, b = i < F.length - 1 ? F[i + 1].at : 1e9;
    const Li = win(L.sub(), a, b, 0.15);
    const asset = A.face(fc.expr, fc.view || o.view || "front", { look: fc.look || [0, 0] });
    const T = (i === 0 && o.draw === "pen") ? Li : Li.sub({ stat: true });
    const r = art(T, asset, { x: o.x, y: o.y, sc: o.sc, s: o.s || 0, per: o.per || 0.04, ff: true, wk: o.wk, opaque: true });
    if (i === 0) out.end = r.end;
  });
  return out;
}
// 접지 그림자 (R8②)
function shadow(L, cx, y, w, s = -99) { L.fill(ell(cx, y, w * 0.45, 12, { n: 16, a0: 0, sweep: Math.PI * 2 }), "#1F1D1A", s, 0.1, 0.25); }
// 땀방울
function sweat(L, x, y, r, s) { const d = smooth([[x, y - r * 1.6], [x + r * 0.9, y], [x, y + r], [x - r * 0.9, y], [x, y - r * 1.6]], false); L.line(d, s, 0.2, { w: 5, pen: false }); L.fill(d, "#A8D2EA", s + 0.15, 0.7, 0.2); }
// ---- ART_GATE_1 C1: 컷 전환 겹침 0 — 앞 컷 끝 = 뒤 컷 시작, 한 프레임에 바뀐다(유령·백지 없음) ----
// cam: 컷마다 카메라 한 가지 — {push:[s0,s1], ox, oy} (밀기/당기기) 또는 {pan:[dx0,dx1]} (패닝). ease-out, 흔들림 없음
function cutL(S, a, b = 1e9, cam) {
  return S.layer().xf((t) => {
    const o = (t >= a && t < b) ? 1 : 0; if (!cam) return { o };
    const B = b > 1e8 ? S.dur - 1.3 : b, p = eo(clamp((t - Math.max(a, 0)) / Math.max(0.5, B - Math.max(a, 0))));
    if (cam.pan) return { o, x: cam.pan[0] + (cam.pan[1] - cam.pan[0]) * p };
    return { o, s: cam.push[0] + (cam.push[1] - cam.push[0]) * p, ox: cam.ox || 960, oy: cam.oy || 540 };
  });
}
// 새 주인공(INKHERO) 표정·그림 교체: list = [[이름, 시작초, {옵션}], ...] — 첫 그림만 펜, 나머지는 stat(정지 교체)
function heroSeq(L, list, base) {
  const out = [];
  list.forEach(([name, at, o = {}], i) => {
    const a = i ? at : -1e9, b = i < list.length - 1 ? list[i + 1][1] : 1e9;
    out.push(INKHERO.put(L, name, Object.assign({}, base, { win: [a, b], stat: i > 0 || !!(base && base.stat) }, o)));
  });
  return out;
}
// 컷 안 무대: 컷이 열리는 순간 이미 깔려 있다
function stageN(P) { return P.sub({ stat: true }); }
