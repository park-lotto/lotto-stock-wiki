// P7 대리에서 부장으로 (18초) — v3(Opus, ART_GATE_1 반영: 전환 겹침 0·차 부품·이름표 64~72px·결론 16.4/밑줄 16.75) / v2(Opus): 직급 = _assets rank.staff/manager/director(라이브 56:30 3단계), 판정서 P7 지시(컷3 → 2컷), R1~R8
// 컷1 -~6.6 대리(사원) / 컷2 6.2~11.9 부장 — 계단 3단(사원·과장·부장)으로 서열을 보여 주고 부장이 일함 / 컷3a 11.7~14.6 차 / 컷3b 14.6~18 성적표+결론
// 문구는 v1(scene_v1.js) 그대로, 로봇 이름표만 INKASSETS.RANK_LABEL(README 지시)로 바꿨다.
const RL = A.RANK_LABEL;
function arrowR(L, x0, x1, y, s, o = {}) { L.line(pl([[x0, y], [(x0 + x1) / 2, y - 6], [x1, y]]), s, o.d || 0.3, { w: 8, pen: o.pen }); L.line(pl([[x1 - 32, y - 26], [x1, y], [x1 - 32, y + 26]]), s + (o.d || 0.3), 0.12, { w: 8, pen: false }); }

// ================= 컷1: 대리(사원) — 일이 쌓여 막힘 =================
const c1 = cutL(S, -1, 6.4, { push: [1.0, 1.04], ox: 620, oy: 600 });
const st1 = stageN(c1);
// 책상(무대) — 로봇 뒤
st1.fill(rr(100, 640, 1460, 40, 8), BEIGE, -99, 0.7); st1.line(rr(100, 640, 1460, 40, 8), -99, 0.1, { w: 7 });
st1.fill(rr(160, 680, 1340, 240, 6), BEIGE, -99, 0.45); st1.line(rr(160, 680, 1340, 240, 6), -99, 0.1, { w: 7 });
st1.line(ln(220, 920, 220, 1010), -99, 0.1, { w: 7 }); st1.line(ln(1440, 920, 1440, 1010), -99, 0.1, { w: 7 });
shadow(st1, 830, 1012, 1500);
const plate = poly([[1110, 730], [1390, 730], [1410, 850], [1090, 850]], 8, true, 0.8);
st1.fill(plate, "#F2D27A", -99, 0.6); st1.line(plate, -99, 0.1, { w: 6 });
art(st1, "prop.clock", { x: 1760, y: 310, sc: 0.95 });   // 벽시계(무대)
// 왼쪽 서류 더미(무대)
for (let i = 0; i < 5; i++) { const d = rr(140, 590 - i * 13, 170, 46, 5); st1.fill(d, "#FFFFFF", -99, 0.95); st1.line(d, -99, 0.1, { w: 4 }); }
// 사원 로봇 — 펜(채색 먼저)
const rb1 = art(c1.sub(), "rank.staff", { x: 620, y: 1010, sc: 2.75, s: 0.1, per: 0.045, opaque: true });
c1.text("대리", { x: 1250, y: 795, size: 110, s: Math.max(1.7, rb1.end + 0.05), anchor: "c", gap: 0.12 });
c1.text(RL.staff, { x: 620, y: 300, size: 58, font: "gae", s: 2.15, anchor: "c", gap: 0.04 });
// 하나씩 처리: 왼 더미 → 로봇 앞 → 오른쪽 더미
for (let i = 0; i < 4; i++) {
  const L = c1.sub(), t0 = 2.6 + i * 0.75, ex = 900 + (i % 2) * 12, ey = 590 - i * 13;
  const d = rr(0, 0, 170, 46, 5); L.line(d, -99, 0.1, { w: 4, pen: false }); L.fill(d, "#FFFFFF", -99, 0.95);
  L.vis(t0 - 0.05, 1e9, "none");
  L.xf((t) => { const p1 = eo(seg(t, t0, t0 + 0.45)), p2 = eo(seg(t, t0 + 0.5, t0 + 0.95));
    const x = 140 + (ex - 140) * (0.5 * p1 + 0.5 * p2), y = 525 + (ey - 525) * p2 - 140 * Math.sin(Math.PI * (0.5 * p1 + 0.5 * p2));
    return { x, y, ox: 0, oy: 0 }; });
}
// 이것도 만들어 줘 — 메모가 쌓임(포스트잇 4장, 글자는 맨 위 1장)
[[0, 0], [1, -4], [2, 3], [3, -2]].forEach(([i, rot]) => {
  const L = c1.sub(), x = 1100 + (i % 2) * 22, y = 500 - i * 96, ts = 3.6 + i * 0.25;
  L.vis(ts - 0.1, 1e9, "pop");
  const d = rr(x, y, 440, 124, 8); L.fill(d, "#F4E28A", ts, 0.75, 0.2); L.line(d, ts, 0.22, { w: 6 });
  L.xf(() => ({ r: rot, ox: x + 220, oy: y + 62 }));
  if (i === 3) L.text("이것도 만들어 줘", { x: x + 220, y: y + 70, size: 64, font: "gae", s: 4.62, anchor: "c", gap: 0.045 });
});
// 5.0 막힘: 땀 + …
const stuck = win(c1.sub(), 5.0);
sweat(stuck, 760, 420, 20, 5.0);
stuck.text("…", { x: 800, y: 470, size: 150, s: 5.15, gap: 0.08 });

// ================= 컷2: 부장 — 계단 3단 서열 + 일하는 부장 =================
const c2 = cutL(S, 6.4, 11.7, { pan: [24, -24] });
const st2 = stageN(c2);
const steps = [[20, 350, 880], [350, 650, 790], [650, 1090, 690]];
steps.forEach(([x0, x1, y]) => { const d = rr(x0, y, x1 - x0, 1100 - y, 4); st2.fill(d, BEIGE, -99, 0.55); st2.line(d, -99, 0.1, { w: 7 }); });
art(st2, "rank.staff", { x: 185, y: 880, sc: 1.25 });
art(st2, "rank.manager", { x: 500, y: 790, sc: 1.25 });
st2.text("사원(대리)", { x: 185, y: 945, size: 64, font: "gae", anchor: "c" }); st2.text("하이쿠", { x: 185, y: 1025, size: 64, font: "gae", anchor: "c" });
st2.text("과장", { x: 500, y: 860, size: 64, font: "gae", anchor: "c" }); st2.text("소넷", { x: 500, y: 940, size: 64, font: "gae", anchor: "c" });
// 부장 로봇 — 펜
const rb2 = art(c2.sub(), "rank.director", { x: 870, y: 690, sc: 1.45, s: 6.45, per: 0.035 });
// 오른쪽 1칸: 원본 영상 → 돋보기 → 확인한 서류
const wk = c2.sub();
const fr2 = rr(1250, 160, 560, 330, 16); wk.fill(fr2, BEIGE, 7.95, 0.6, 0.25); wk.line(fr2, 8.0, 0.35, { w: 7 });
const pl2 = poly([[1475, 260], [1475, 390], [1585, 325]], 8, true, 0.5); wk.line(pl2, 8.38, 0.2, { w: 7 }); wk.fill(pl2, "#FFFFFF", 8.45, 0.9, 0.2);
const dc2 = rr(1270, 570, 520, 360, 10); wk.fill(dc2, "#FFFFFF", 8.62, 0.95, 0.2); wk.line(dc2, 8.65, 0.35, { w: 7 });
[0, 1, 2, 3].forEach((i) => wk.line(ln(1310, 640 + i * 60, 1700 - i * 70, 640 + i * 60), 9.0 + i * 0.05, 0.15, { w: 5, pen: false }));
const ln2 = ell(1745, 470, 96, 96, { n: 22 }); wk.fill(ln2, "#FFFFFF", 9.05, 0.6, 0.2); wk.line(ln2, 9.1, 0.35, { w: 8 }); wk.line(ln(1812, 538, 1870, 600), 9.45, 0.12, { w: 15, pen: false });
wk.line(pl([[1600, 830], [1640, 875], [1730, 770]]), 9.55, 0.3, { w: 11, c: ORG });
c2.text("부장(사장)", { x: 870, y: 790, size: 72, font: "gae", s: 9.95, anchor: "c", gap: 0.04 });
c2.text("오푸스·페이블", { x: 870, y: 885, size: 60, font: "gae", s: 10.35, anchor: "c", gap: 0.035 });
// 10.4 아이디어 — 전구
const bulb = win(c2.sub(), 10.4);
const bb = ell(1135, 190, 70, 70, { n: 20 });
bulb.fill(bb, "#F2D27A", 10.4, 0.85, 0.2); bulb.line(bb, 10.42, 0.3, { w: 7, pen: false });
bulb.line(rr(1112, 262, 46, 36, 5), 10.5, 0.15, { w: 5, pen: false });
for (let i = 0; i < 7; i++) { const a = -Math.PI + i * Math.PI / 6; bulb.line(ln(1135 + 88 * Math.cos(a), 190 + 88 * Math.sin(a), 1135 + 116 * Math.cos(a), 190 + 116 * Math.sin(a)), 10.55 + i * 0.03, 0.1, { w: 6, c: ORG, pen: false }); }

// ================= 컷3a: 차 (11.7 ~ 14.6) — 차 = _assets prop.car_sedan / prop.car_sport =================
const c3 = cutL(S, 11.7, 14.6, { pan: [-30, 30] });
const st3 = stageN(c3);
// 길가 건물·도로(무대) — 컷이 열리는 순간 깔림
[[20, 210, 330], [250, 160, 230], [430, 240, 400], [700, 190, 280], [910, 230, 360], [1170, 170, 250], [1360, 250, 420], [1640, 260, 300]].forEach(([x, w, h], i) => {
  const d = rr(x, 660 - h, w, h, 6); st3.fill(d, i % 2 ? SKY : BEIGE, -99, 0.4); st3.line(d, -99, 0.1, { w: 4, c: "#8C8A86" });
  for (let r = 0; r < Math.min(2, Math.floor((h - 60) / 70)); r++) for (let c = 0; c < Math.floor((w - 30) / 60); c++) st3.line(rr(x + 22 + c * 60, 660 - h + 30 + r * 70, 30, 36, 4), -99, 0.1, { w: 3, c: "#8C8A86" });
});
st3.fill(rr(0, 660, 1920, 115, 0), "#CFD6DA", -99, 0.8);
st3.line(ln(0, 660, 1920, 660), -99, 0.1, { w: 6 }); st3.line(ln(0, 775, 1920, 775), -99, 0.1, { w: 6 });
for (let x = 40; x < 1920; x += 180) st3.line(ln(x, 750, x + 90, 750), -99, 0.1, { w: 5, c: "#FFFFFF" });
const car1 = art(c3.sub(), "prop.car_sedan", { x: 520, y: 720, sc: 1.5, s: 11.75, per: 0.035, opaque: true });
c3.text("아반떼", { x: 520, y: 840, size: 96, font: "gae", s: car1.end + 0.02, anchor: "c", gap: 0.08 });
arrowR(c3, 820, 1120, 560, car1.end + 0.4, { d: 0.12, pen: false });
const car2 = art(c3.sub(), "prop.car_sport", { x: 1500, y: 720, sc: 1.4, s: 13.0, per: 0.035, opaque: true });
c3.text("포르쉐", { x: 1500, y: 840, size: 96, font: "gae", s: car2.end + 0.02, anchor: "c", gap: 0.08 });

// ================= 컷3b: 성적표 + 결론 (14.6 ~ 18) =================
const c4 = cutL(S, 14.6, 1e9, { push: [1.04, 1.0] });
const st4 = stageN(c4);
function card(L, cx, cy, good) {
  const d = rr(cx - 240, cy - 160, 480, 320, 12); L.fill(d, good ? "#F4E28A" : "#FFFFFF", -99, good ? 0.75 : 0.95); L.line(d, -99, 0.1, { w: 7 });
  L.line(ln(cx - 190, cy - 100, cx + 40, cy - 100), -99, 0.1, { w: 5 }); L.line(ln(cx - 190, cy - 58, cx - 40, cy - 58), -99, 0.1, { w: 5 });
  shadow(L, cx, cy + 172, 480);
}
card(st4, 480, 400, false); card(st4, 1440, 400, true);
c4.text("전교 30등", { x: 480, y: 470, size: 110, font: "gae", s: 14.7, anchor: "c", gap: 0.05 });
arrowR(c4, 800, 1120, 400, 15.15, { d: 0.12, pen: false });
c4.text("전교 1등", { x: 1440, y: 470, size: 110, font: "gae", s: 15.25, anchor: "c", gap: 0.05 });
const crown = pl([[1560, 270], [1582, 232], [1612, 270], [1644, 228], [1668, 270], [1550, 274]]);
c4.fill(crown, ORG, 15.62, 0.7, 0.12); c4.line(crown, 15.62, 0.1, { w: 6, pen: false });
const brain = c4.text("두뇌가 다릅니다", { x: 960, y: 690, size: 200, s: 15.75, anchor: "c", gap: 0.073 });
c4.underline(brain.box(0, 1), 16.45, 0.3);
