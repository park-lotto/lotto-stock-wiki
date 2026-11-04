// 4회차 장면 s03 — 손으로 따라 만들라 → 막힘 (19.5초) · 문장 시각 = py ink/times.py s03
// 0.36 문제는 여기서부터 / 1.96 손으로 따라 만들라 / 5.19 그러셨죠? / 6.17 강의 끝 → 첫 장면부터 막힘 / 9.78 채널 2·3개? / 12.61 손편집 x2 x3 / 14.93 편집 화면 앞에서 멈춤
const Y = "#F4E28A";
// ===== 컷1 (−1 ~ 5.19) =====
const c1 = cutL(S, -1, 5.19, { push: [1.0, 1.04], ox: 960, oy: 540 });
const p1 = c1.text("문제는 여기서부터", { x: 960, y: 230, size: 150, s: 0.4, gap: 0.07, anchor: "c" });
c1.underline(p1.box(0, 1), 1.5, 0.35);
const hd = art(c1, "hand.drag", { x: 640, y: 900, sc: 1.9, s: 2.0 });
const mon = rr(950, 430, 760, 430, 18); c1.fill(mon, "#FFFFFF", 2.1, 0.9, 0.2); c1.line(mon, 2.1, 0.5, { w: 8 });
[[0, 260, SKY], [1, 480, PINK], [2, 200, Y], [3, 560, SKY]].forEach(([k, w, col]) => {
  const bar = rr(1000 + (k % 2) * 40, 500 + k * 80, w, 42, 8); c1.fill(bar, col, 2.6 + k * 0.15, 0.7, 0.2); c1.line(bar, 2.6 + k * 0.15, 0.2, { w: 5, pen: false });
});
c1.text("손으로 따라 만들기", { x: 1330, y: 960, size: 96, s: 3.2, gap: 0.05, anchor: "c", c: "#D9622B" });
// ===== 컷2 여러분도 그러셨죠 → 첫 장면부터 막힘 (5.19 ~ 9.78) =====
const c2 = cutL(S, 5.19, 9.78, { push: [1.04, 1.0], ox: 500, oy: 540 });
const st2 = stageN(c2);
st2.fill(rr(0, 960, 1920, 120, 0), BEIGE, -99, 0.5); st2.line(ln(0, 960, 1920, 960), -99, 0.1, { w: 5, pen: false });
INKHERO.put(c2, "g_o_laptop_tired", { x: 480, y: 430, sc: 1.85, s: 5.2, dur: 1.1 });
c2.text("여러분도 그러셨죠?", { x: 1000, y: 230, size: 120, s: 5.3, gap: 0.06 });
const l1 = c2.text("강의는 끝까지 ✓", { x: 1000, y: 470, size: 100, font: "gae", s: 6.3, gap: 0.05 });
const l2 = c2.text("혼자 하려니…", { x: 1000, y: 640, size: 110, s: 7.4, gap: 0.06 });
const l3 = c2.text("첫 장면부터 막힘", { x: 1000, y: 820, size: 120, s: 8.3, gap: 0.06, c: "#D9622B" });
c2.underline(l3.box(0, 4), 9.2, 0.3);
// ===== 컷3 채널 2·3개 → 손편집 x2 x3 (9.78 ~ 14.93) =====
const c3 = cutL(S, 9.78, 14.93, { pan: [20, -20] });
c3.text("한 채널도 버거운데", { x: 960, y: 170, size: 100, font: "gae", s: 9.8, gap: 0.05, anchor: "c" });
[[260, SKY, 10.3, "채널 1"], [800, PINK, 11.1, "채널 2"], [1340, Y, 11.7, "채널 3"]].forEach(([x, col, t, lab]) => {
  const b = rr(x, 280, 320, 400, 24); c3.fill(b, col, t, 0.5, 0.25); c3.line(b, t, 0.4, { w: 8 });
  c3.text(lab, { x: x + 160, y: 400, size: 80, font: "gae", s: t + 0.2, anchor: "c" });
  art(c3, "hand.drag", { x: x + 160, y: 660, sc: 0.85, s: t + 0.35 });
});
const x2 = c3.text("손편집 × 2 × 3", { x: 960, y: 880, size: 160, s: 12.65, gap: 0.07, anchor: "c" });
c3.circleMark(x2.box(4, 8), 13.9, 0.4, 40, 20);
// ===== 컷4 결국 편집 화면 앞에서 멈춤 (14.93 ~) =====
const c4 = cutL(S, 14.93, 1e9, { push: [1.0, 1.05], ox: 1400, oy: 480 });
const st4 = stageN(c4);
st4.fill(ell(1400, 620, 520, 500, { n: 30 }), "#D9D4CC", -99, 0.35);
INKHERO.put(c4, "g_o_frustr_head", { x: 1400, y: 400, sc: 1.85, s: 14.95, dur: 1.0 });
c4.text("강의를 몇 개 들어도", { x: 120, y: 250, size: 100, font: "gae", s: 15.0, gap: 0.05 });
const e1 = c4.text("결국 편집 화면", { x: 120, y: 470, size: 140, s: 16.3, gap: 0.06 });
c4.text("앞에서", { x: 120, y: 640, size: 140, s: 17.2, gap: 0.06 });
const st = c4.text("멈춘다", { x: 120, y: 840, size: 190, s: 17.9, gap: 0.08, c: "#D9622B" });
c4.line(rr(560, 690, 60, 170, 6), 18.5, 0.2, { w: 10 }); c4.line(rr(650, 690, 60, 170, 6), 18.6, 0.2, { w: 10 });
c4.fill(rr(560, 690, 60, 170, 6), INK, 18.7, 0.85, 0.2); c4.fill(rr(650, 690, 60, 170, 6), INK, 18.75, 0.85, 0.2);
