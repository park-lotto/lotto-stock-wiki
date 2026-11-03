// P2 「벽 앞 999 — 천 회를 못 벗어남」 10초, 2컷 — _lib_p 엔진 + _assets (옛 판 = scene_v1.js)
const { H, RR, O, stg, asset, hput, C: KC } = K;
const GRAY9 = "#8F877A", ENG = "4px 4px 0 rgba(255,255,255,.75),-3px -3px 0 rgba(0,0,0,.28)";
function wall(L, x0, y0, x1, y1, s) {                       // 벽돌 벽(무대, 펜 없음)
  stg(L, RR(x0, y0, x1 - x0, y1 - y0, 18), s, { fill: "#F2B8B0", op: 0.32 });
  let h = "", v = ""; const bh = 72; let row = 0;
  for (let y = y0 + bh; y < y1; y += bh, row++) h += `M${x0} ${y} L${x1} ${y + (row % 2 ? 1.5 : -1.5)} `;
  row = 0; for (let y = y0; y < y1; y += bh, row++) for (let x = x0 + (row % 2 ? 110 : 0) + 110; x < x1; x += 220) v += `M${x} ${y} L${x + 1} ${Math.min(y + bh, y1)} `;
  L.line(h, s + 0.1, 0.35, { w: 4, pen: false }); L.line(v, s + 0.2, 0.35, { w: 4, pen: false });
}
function refresh(P, cx, cy, r, s) {                         // 돌아가는 새로고침
  const g = P.sub().xf((t) => ({ r: Math.max(0, Math.min(t, 8.9) - (s + 0.7)) * 200, ox: cx, oy: cy }));   // R4: 마지막 1초는 멈춤
  const a0 = -50 * Math.PI / 180, sw = 290 * Math.PI / 180;
  g.line(ell(cx, cy, r, r, { a0, sweep: sw, n: 40 }), s, 0.5, { w: 9, pen: false });
  const a = a0 + sw, ex = cx + r * Math.cos(a), ey = cy + r * Math.sin(a), tx = -Math.sin(a), ty = Math.cos(a);
  const rot = (x, y, d) => { const q = d * Math.PI / 180; return [x * Math.cos(q) - y * Math.sin(q), x * Math.sin(q) + y * Math.cos(q)]; };
  const [b1x, b1y] = rot(-tx, -ty, 35), [b2x, b2y] = rot(-tx, -ty, -35), L = r * 0.55;
  g.line(`M${ex + b1x * L} ${ey + b1y * L} L${ex} ${ey} L${ex + b2x * L} ${ey + b2y * L}`, s + 0.45, 0.2, { w: 9, pen: false });
}
// ===== 컷 A 0~4.0: 벽 앞에 선 주인공, 벽에 999 =====
const cA = K.cut(-1, 4.0, { s0: 1.0, s1: 1.05, ox: 760, oy: 420 });                     // 밀기
const A0 = cA.sub();
wall(A0, 140, 120, 1780, 850, -0.3);
stg(A0, [[60, 850], [1860, 850]], -0.3, { closed: false });
const tA = A0.text("999", { x: 1120, y: 300, size: 340, font: "num", weight: 800, c: GRAY9, s: 2.05, gap: 0.2 }); tA.d.style.textShadow = ENG;
hput(cA, "g_m_point_hope", { x: 420, bottom: 850, u: 230, s: 0.3, dur: 1.1 });          // #7 999 벽을 가리킴
refresh(cA, 800, 230, 62, 2.65);
// ===== 컷 B 4.0~10.0: 가까이서 — 999 와 손글씨 =====
const cB = K.cut(4.0, 1e9, { s0: 1.06, s1: 1.0, ox: 470, oy: 420 });                     // 당기기
const B0 = cB.sub();
wall(B0, 930, 340, 1830, 845, 3.55);                      // 무대·999 는 4.0 에 이미 깔려 있다(R1)
stg(B0, [[60, 860], [1860, 860]], 3.55, { closed: false });
const tB = B0.text("999", { x: 1010, y: 560, size: 330, font: "num", weight: 800, c: GRAY9, s: 3.6, gap: 0.0001 }); tB.d.style.textShadow = ENG;
hput(cB, "g_m_tired", { x: 470, bottom: 860, u: 240, s: 4.3, dur: 1.0, win: [4.0, 6.3] });   // #2 새로고침… 긴 밤
hput(cB, "g_m_frustr_head", { x: 470, bottom: 860, u: 240, stat: true, win: [6.3, 1e9] }); // 6.3 좌절(정지 교체)
refresh(cB, 840, 420, 58, 4.05);
const TX = cB.sub();
const T1 = TX.text("열심히 올렸는데,", { x: 860, y: 130, size: 118, s: 6.7, gap: 0.05 });        // 위쪽(아래 가운데 = 자막 자리)
const T = TX.text("천 회를 못 벗어납니다", { x: 860, y: 262, size: 118, s: T1.end + 0.1, gap: 0.05 });
TX.circleMark(T.box(0, 0), 8.05, 0.55, 38, 14);
