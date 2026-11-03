// Q3 클로드에게 부탁 (14초) — 만들어줘 → 매끈한 가짜 같은 영상 카드 → 조금만 고쳐줘 마다 동전이 크레딧 계기판에서 빠져나감
// v2(2026-10-29): _assets 주인공(가리키며 기대 → 7.0 머리 감싸고 좌절: 표정+손 한 묶음)·동전 자산 / 창·카드는 펜 없이 톡(R1·R5)
//   R6 생각 구름 외곽은 한 번만, 글만 갈아 씀 / R4 결론 손글씨 12.0 전 완성, 동그라미 12.6, 마지막 1초 정지
function star(L, cx, cy, r, s, col) { const pts = []; for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 - Math.PI / 2, k = i % 2 ? r * 0.28 : r; pts.push([cx + k * Math.cos(a), cy + k * Math.sin(a)]); } const d = poly(pts, 0, true, 0.4); L.line(d, s, 0.2, { w: 4, pen: false }); L.fill(d, col || "#F2D27A", s + 0.2, 0.8); }
const base = S.layer(); base.xf((t) => ({ s: 1.035 - 0.035 * eo(seg(t, 0, 7.0)) + 0.03 * eo(seg(t, 7.0, 12.0)), ox: 960, oy: 540 }));
// 주인공: 0~7.0 채팅창을 가리키며 기대 → 7.0 머리 감싸고 좌절
// 새 주인공(여): 채팅 창을 가리키며 기대(펜 0~1.2) → 7.0 머리 감싸고 좌절(정지 교체)
QK.person(base, "g_f_point_hope", { x: 300, y: 555, H: 760, s: 0.0, dur: 1.0, win: [-1, 7.0] });
QK.person(base, "g_f_frustr_head", { x: 400, y: 575, H: 680, stat: true, win: [7.0, 1e9] });
// 채팅 창 (무대: 처음부터 있다 — R1)
const CW = QK.stage(base, -0.3);
CW.shape(rr(720, 60, 620, 540, 18), 0, 0.1, BEIGE, { op: 0.35, w: 7 });
CW.line(ln(732, 118, 1328, 118), 0, 0.1, { w: 4 });
[0, 1, 2].forEach((i) => CW.line(ell(764 + i * 28, 90, 8, 8, { n: 8 }), 0, 0.1, { w: 4 }));
const BB = QK.pop(base, 2.2, 1e9, 1170, 200); BB.shape(rr(990, 145, 340, 110, 44), 0, 0.1, PINK, { op: 0.6, w: 6 });
base.text("만들어줘", { x: 1160, y: 206, size: 70, font: "gae", s: 2.7, anchor: "c", gap: 0.1 });
// AI가 만든 매끈한 카드 3장 (3.6 / 4.3 / 5.0 톡)
const cardCols = [SKY, PINK, "#F2D27A"];
[0, 1, 2].forEach((i) => {
  const x = 745 + i * 195, y = 290, s = 3.6 + i * 0.7, P = QK.pop(base, s, 1e9, x + 88, y + 125);
  P.shape(rr(x, y, 176, 250, 24), 0, 0.1, cardCols[i], { op: 0.55, w: 7 });
  P.shape(poly([[x + 62, y + 56], [x + 62, y + 112], [x + 110, y + 84]], 6, true, 0.3), 0, 0.1, "#FFFFFF", { op: 0.9, w: 5 });
  base.line(pl([[x + 24, y + 206], [x + 70, y + 156], [x + 110, y + 186], [x + 150, y + 132]]), s + 0.2, 0.25, { w: 5, pen: false });
  star(base, x + 144, y + 40, 22, s + 0.3);
  base.line(pl([[x + 18, y + 40], [x + 30, y + 24], [x + 46, y + 18]]), s + 0.35, 0.15, { w: 4, pen: false });
});
// 크레딧 계기판 (2.4 톡)
const GB = QK.pop(base, 2.4, 1e9, 1630, 330);
GB.shape(rr(1400, 60, 460, 540, 18), 0, 0.1, BEIGE, { op: 0.35, w: 7 });
base.text("크레딧", { x: 1630, y: 150, size: 80, font: "gae", s: 3.8, anchor: "c", gap: 0.1 });
const GX = 1630, GY = 450, GR = 180;
const arc = []; for (let i = 0; i <= 18; i++) { const a = Math.PI + i / 18 * Math.PI; arc.push([GX + GR * Math.cos(a), GY + GR * Math.sin(a)]); }
GB.line(smooth(arc, false), 0, 0.1, { w: 7 }); GB.line(ln(GX - GR - 10, GY, GX + GR + 10, GY), 0, 0.1, { w: 5 });
GB.fill(smooth(arc.concat([[GX, GY]]), true), "#F2D27A", 0, 0.45);
for (let i = 0; i <= 6; i++) { const a = Math.PI + i / 6 * Math.PI; GB.line(ln(GX + (GR - 26) * Math.cos(a), GY + (GR - 26) * Math.sin(a), GX + (GR - 2) * Math.cos(a), GY + (GR - 2) * Math.sin(a)), 0, 0.1, { w: 4 }); }
GB.line(ell(GX, GY, 16, 16, { n: 10 }), 0, 0.1, { w: 5 });
const needle = mk("path", { d: "", stroke: INK, "stroke-width": 9, "stroke-linecap": "round", fill: "none" }, GB.lg);
const V = (t) => 1 - 0.28 * eo(seg(t, 7.4, 8.0)) - 0.27 * eo(seg(t, 9.1, 9.7)) - 0.27 * eo(seg(t, 10.8, 11.4));
S.on((t) => { const th = Math.PI * (1 - V(t)); needle.setAttribute("d", `M${GX} ${GY} L${(GX + 150 * Math.cos(th)).toFixed(1)} ${(GY - 150 * Math.sin(th)).toFixed(1)}`); });
// 조금만 고쳐줘 — 구름 외곽은 6.9에 한 번, 글만 세 번 갈아 쓴다(R6) + 그때마다 동전 두 닢이 빠진다
const CL = QK.pop(base, 6.9, 1e9, 400, 185);
CL.shape(cloud(400, 185, 330, 110, 11, 0.05), 0, 0.1, "#FFFFFF", { op: 0.9, w: 7 });
[[0.6, 76, 25, 23], [0.65, 72, 15, 13]].forEach(([k, r, x, y]) => CL.shape(ell(250 - x * 4, 330 + y * 2, r * k * 0.4, r * k * 0.4, { n: 10 }), 0, 0.1, "#FFFFFF", { op: 0.9, w: 5 }));
const asks = [7.0, 8.7, 10.4];
asks.forEach((a, k) => {
  const nb = k + 1 < asks.length ? asks[k + 1] + 0.35 : 1e9;
  const TL = base.sub(); TL.xf((t) => ({ o: nb < 1e8 ? Math.max(0, Math.min(1, (nb - t) / 0.12)) : 1 }));
  TL.text("조금만 고쳐줘", { x: 400, y: 192, size: 84, font: "gae", s: k === 2 ? a + 0.4 : a + 0.5, anchor: "c", gap: k === 2 ? 0.06 : 0.07 });
  [0, 1].forEach((j) => {
    const t0 = a + 0.5 + j * 0.3, C = base.sub({ stat: true });
    C.xf((t) => { const p = eo(seg(t, t0, t0 + 1.4)), on = t >= t0 && t < t0 + 1.4 ? Math.min(1, (t0 + 1.4 - t) / 0.3) : 0; return { x: (j ? 70 : -70) * p, y: 190 * p + 30 * p * p, o: on, ox: 0, oy: 0 }; });
    QK.put(C, { ...INKASSETS.get("prop.coin"), ground: false }, { x: GX, y: GY + 50, sc: 0.5, s: 0 });
  });
});
// 결론 손글씨 (12.0 전에 완성)
const tx = base.text("다시 만들 때마다 크레딧", { x: 1290, y: 890, size: 128, s: 11.34, anchor: "c", gap: 0.048 });
base.circleMark(tx.box(10, 12), 12.05, 0.55, 30, 14);
