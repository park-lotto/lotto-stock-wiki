const I = INK.ID, R = (x, y, w, h, r) => rect(I, x, y, w, h, r), Pp = (a) => P(I, a), E = (cx, cy, rx, ry, o) => ell(I, cx, cy, rx, ry, o);
function wall(c, x0, y0, x1, y1, s) {
  c.path(R(x0, y0, x1 - x0, y1 - y0, 6), { s, dur: 0.7, tint: "pink", tintOp: 0.3 });
  let h = "", v = ""; const bh = 72; let row = 0;
  for (let y = y0 + bh; y < y1; y += bh, row++) { h += `M${x0} ${y} L${x1} ${y + (row % 2 ? 1.5 : -1.5)} `; }
  row = 0; for (let y = y0; y < y1; y += bh, row++) { for (let x = x0 + (row % 2 ? 110 : 0) + 110; x < x1; x += 220) v += `M${x} ${y} L${x + 1} ${Math.min(y + bh, y1)} `; }
  c.path(h, { s: s + 0.5, dur: 0.9, w: 4, pen: false }); c.path(v, { s: s + 0.9, dur: 0.9, w: 4, pen: false });
}
function refresh(c, cx, cy, r, s) {
  const g = c.group(); const a0 = -50, sw = 290;
  c.path(E(cx, cy, r, r, { a0, sweep: sw, n: 40 }), { s, dur: 0.6, w: 8, parent: g, pen: false });
  const a = (a0 + sw) * Math.PI / 180, ex = cx + r * Math.cos(a), ey = cy + r * Math.sin(a), tx = -Math.sin(a), ty = Math.cos(a);
  const rot = (x, y, d) => { const q = d * Math.PI / 180; return [x * Math.cos(q) - y * Math.sin(q), x * Math.sin(q) + y * Math.cos(q)]; };
  const [b1x, b1y] = rot(-tx, -ty, 35), [b2x, b2y] = rot(-tx, -ty, -35), L = r * 0.55;
  c.path(`M${ex + b1x * L} ${ey + b1y * L} L${ex} ${ey} L${ex + b2x * L} ${ey + b2y * L}`, { s: s + 0.55, dur: 0.2, w: 8, parent: g, pen: false });
  c.anim((t) => { const k = Math.max(0, t - (c.base + s + 0.8)); g.setAttribute("transform", `rotate(${(k * 200).toFixed(1)} ${cx} ${cy})`); });
}
const ENG = "text-shadow:4px 4px 0 rgba(255,255,255,.75),-3px -3px 0 rgba(0,0,0,.28);";
// ===== 컷 A: 벽 앞에 선 주인공, 벽에 999 (0~4.0) =====
const A = ink.cut(0, 4.0);
wall(A, 140, 120, 1780, 850, 0);
A.path(Pp([["M", 60, 850], ["L", 1860, 850]]), { s: 0.4, dur: 0.6 });
A.text("999", { x: 1010, y: 300, font: "PB", weight: 800, size: 340, s: 1.9, gap: 0.2, color: "#8F877A", css: ENG });
HERO.torso(A, 560, 440, 105, { h: 3.9, s: 0.6, sp: 0.8 });
HERO.face(A, 560, 440, 105, { expr: "worry", look: 0.6, s: 0.8, sp: 0.8 });
refresh(A, 800, 270, 62, 2.5);
// ===== 컷 B: 가까이서 — 999와 손글씨 (4.0~10.0) =====
const B = ink.cut(4.0, 10.0);
wall(B, 930, 100, 1830, 770, 0);
B.path(Pp([["M", 60, 770], ["L", 1860, 770]]), { s: 0.3, dur: 0.6 });
B.text("999", { x: 1010, y: 230, font: "PB", weight: 800, size: 330, s: 1.5, gap: 0.2, color: "#8F877A", css: ENG });
HERO.torso(B, 480, 410, 170, { h: 2.1, s: 0.3, sp: 0.9 });
HERO.face(B, 480, 410, 170, { expr: "worry", look: 0.7, s: 0.4, sp: 0.9 });
refresh(B, 800, 215, 58, 2.2);
const T = B.text("열심히 올렸는데, 천 회를 못 벗어납니다", { x: 150, y: 815, font: "NP", size: 118, s: 3.0, gap: 0.05, rot: -1 });
B.circle(B.box(T, 10, 10), { s: 4.1, dur: 0.6, px: 38, py: 14 });
