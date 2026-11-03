// Q2 반자동 (12초) — 프롬프트 복사 → AI 창에 붙여넣기 → 대본을 캡컷으로 (화살표 3개), 그래도 영상 파일 더미
// v3(2026-10-29 ART_GATE_1): 타원 책상 삭제 → prop.laptop 을 인물 앞에 / 흐름 상자 높이 240·글 84/110/84 / 캡컷 = prop.app_edit
//   6.9초 종이 넘김(겹침 0) → 컷2 = 큰 시계 + 지친 인물 + 클립 더미(폭 ≥360) + "반은 노가다"
function win(L, x, y, w, h, col) {
  L.shape(rr(x, y, w, h, 14), 0, 0.1, col, { op: 0.45, w: 7 });
  L.line(ln(x + 12, y + 50, x + w - 12, y + 50), 0, 0.1, { w: 4 });
  [0, 1, 2].forEach((i) => L.line(ell(x + 30 + i * 26, y + 25, 7, 7, { n: 8 }), 0, 0.1, { w: 4 }));
}
function paper(L, x, y, w, h) { L.shape(rr(x, y, w, h, 12), 0, 0.1, "#FFFFFF", { op: 0.9, w: 7 }); }
function arrow(L, x0, x1, y, s) { L.line(pl([[x0, y], [(x0 + x1) / 2, y - 6], [x1, y]]), s, 0.25, { w: 8, pen: false }); L.line(pl([[x1 - 28, y - 26], [x1, y], [x1 - 28, y + 26]]), s + 0.2, 0.15, { w: 8, pen: false }); }
function lines(L, x, y, w, n, s, step = 40) { for (let i = 0; i < n; i++) L.line(ln(x, y + i * step, x + w - (i % 3) * 28, y + i * step), s + i * 0.1, 0.25, { w: 4, pen: false }); }
// 책상 (두 컷 공용 무대)
function desk(L) {
  const D = QK.stage(L, -0.3);
  D.fill(rr(0, 985, 1920, 95, 0), "#EFE4CB", 0, 0.85); D.line(ln(0, 985, 1920, 985), 0, 0.1, { w: 7 });
}
const CUT = 6.9;
// ===== 컷1 (0~6.9): 흐름 =====
const c1 = S.layer(); c1.xf((t) => ({ o: t < CUT ? 1 : 0, s: 1 + 0.04 * eo(seg(t, 0, CUT)), ox: 960, oy: 540 }));
desk(c1);
const st = QK.stage(c1, -0.3);
QK.put(st, "prop.clock", { x: 210, y: 820, sc: 1.1, s: 0 });
// 새 주인공(남): 노트북 앞 기대 (그림 속 노트북·책상 그대로 — 따로 노트북 부품을 얹지 않는다)
QK.person(c1, "g_m_laptop_hope", { x: 960, y: 447, H: 670, s: 0.0, dur: 1.0 });
const Y = 30, Hh = 240;
// ① 프롬프트 종이
const w1 = QK.pop(c1, 0.6, 1e9, 250, Y + 120); paper(w1, 40, Y, 420, Hh);
c1.text("프롬프트", { x: 250, y: Y + 70, size: 84, font: "gae", s: 1.1, anchor: "c", gap: 0.09 });
lines(c1, 80, Y + 150, 340, 2, 1.7, 44);
// ② AI 창
const w2 = QK.pop(c1, 1.4, 1e9, 730, Y + 120); win(w2, 540, Y, 380, Hh, SKY);
c1.text("AI", { x: 730, y: Y + 125, size: 110, font: "num", weight: 800, s: 2.2, anchor: "c", gap: 0.12 });
arrow(c1, 466, 534, Y + 120, 3.0);
const trav = (a, x0, x1, y) => { const L = c1.sub({ stat: true }); L.vis(a, a + 1.5, "fade"); const d = rr(0, 0, 117, 81, 8); L.line(d, 0, 0.1, { w: 5 }); L.fill(d, "#FFFFFF", 0, 0.95); [0, 1, 2].forEach((i) => L.line(ln(16, 21 + i * 21, 101 - i * 18, 21 + i * 21), 0, 0.1, { w: 4 })); L.xf((t) => { const p = eo(seg(t, a + 0.2, a + 1.1)); return { x: x0 + (x1 - x0) * p, y: y - 70 * Math.sin(Math.PI * p), ox: 0, oy: 0 }; }); };
trav(3.0, 380, 600, Y + 110);
lines(c1, 570, Y + 195, 320, 1, 3.8, 40);
// ③ 대본 종이
arrow(c1, 926, 994, Y + 120, 4.5);
trav(4.5, 860, 1060, Y + 110);
const w3 = QK.pop(c1, 4.2, 1e9, 1150, Y + 120); paper(w3, 1000, Y, 300, Hh);
c1.text("대본", { x: 1150, y: Y + 70, size: 84, font: "gae", s: 4.7, anchor: "c", gap: 0.12 });
lines(c1, 1035, Y + 150, 230, 2, 5.1, 44);
// ④ 캡컷 (편집 앱 아이콘 부품)
arrow(c1, 1306, 1374, Y + 120, 5.5);
trav(5.5, 1240, 1450, Y + 110);
const w4 = QK.pop(c1, 5.4, 1e9, 1500, Y + 120); QK.put(w4, "prop.app_edit", { x: 1500, y: Y + 214, sc: 0.9, s: 0 });
c1.text("캡컷", { x: 1500, y: Y + 262, size: 60, font: "gae", s: 5.95, anchor: "c", gap: 0.1 });
// ===== 컷2 (6.9~12): 그래도 손으로 — 큰 시계 + 지친 인물 + 클립 더미 =====
const c2 = S.layer(); c2.xf((t) => ({ o: t < CUT ? 0 : Math.min(1, 0.7 + (t - CUT) / 0.12 * 0.3), s: 1.06 - 0.06 * eo(seg(t, CUT, 10.6)), ox: 960, oy: 560 }));
desk(c2);
const st2 = QK.stage(c2, -0.3);
QK.put(st2, "prop.clock", { x: 330, y: 812, sc: 1.6, s: 0 });
QK.person(c2, "g_m_laptop_tired", { x: 960, y: 463, H: 670, stat: true });
// 시계 바늘이 빙글 (6.9~10.6, 마지막 1초 전 정지)
const CX = 330, CY = 812 - 120 * 1.6;
const hm = mk("path", { d: "", stroke: INK, "stroke-width": 9, "stroke-linecap": "round", fill: "none" }, st2.lg);
const hh = mk("path", { d: "", stroke: INK, "stroke-width": 12, "stroke-linecap": "round", fill: "none" }, st2.lg);
S.on((t) => { const tt = Math.min(Math.max(t, CUT), 10.6), a = (tt - CUT) * Math.PI * 2 * 0.9 + 5.4, b = a / 12 + 2.4;
  const L = (r, g) => `M${CX} ${CY.toFixed(1)} L${(CX + r * Math.sin(g)).toFixed(1)} ${(CY - r * Math.cos(g)).toFixed(1)}`;
  hm.setAttribute("d", L(130, a)); hh.setAttribute("d", L(84, b)); });
// 영상 파일 더미 — 오른쪽 책상 위에 하나씩 쌓인다 (폭 380)
const PX = 1420;
c2.fill(ell(PX + 190, 988, 220, 12, { n: 14 }), INK, 7.4, 0.1);
[[0, -3], [1, 2], [2, -2], [3, 3], [4, -1]].forEach(([i, rot]) => {
  const y = 820 - i * 74, x = PX + [0, 16, -10, 18, 4][i], W = 380, Hf = 150;
  const L = QK.pop(c2, 7.4 + i * 0.3, 1e9, x + W / 2, y + Hf / 2); const R = L.sub(); R.xf(() => ({ r: rot, ox: x + W / 2, oy: y + Hf / 2 }));
  R.shape(rr(x, y, W, Hf, 12), 0, 0.1, [SKY, PINK, BEIGE, "#F2D27A", SKY][i], { op: 0.8, w: 7 });
  R.shape(poly([[x + 42, y + 42], [x + 42, y + 108], [x + 98, y + 75]], 5, true, 0.3), 0, 0.1, "#FFFFFF", { op: 0.9, w: 5 });
  R.line(ln(x + 140, y + 56, x + 330, y + 56), 0, 0.1, { w: 5 }); R.line(ln(x + 140, y + 96, x + 270, y + 96), 0, 0.1, { w: 5 });
});
const tt = c2.text("반은 노가다", { x: 960, y: 150, size: 150, s: 9.2, anchor: "c", gap: 0.12 });
c2.underline(tt.box(3, 5), 10.1, 0.5);
