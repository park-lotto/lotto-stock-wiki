// 4회차 장면2 — 50대 회원 (27.0초) · 대본 B 문장 시각(필재 1.1배 음성 26.41초를 글자 수로 나눔)
// s1 0~2.91 쉰 살 넘은 회원 / s2 2.91~6.05 컴퓨터=이메일 / s3 6.05~11.17 고액 강의 두 개 / s4 11.17~15.36 결국 손편집 강의
// s5 15.36~18.61 자르고·자막·목소리 / s6 18.61~21.64 몇 달 뒤 0 / s7 21.64 게을러서? / s8 23.15 아닙니다 / s9 23.73 솔직해집시다 / s10 24.55 시대가 아니잖아요
// 주인공 = 50대 새 주인공(o_*) 5장, 컷마다 다른 그림(같은 그림 펜 2번 금지 — 재등장은 stat)

// ================= 컷1: 쉰 살 넘은 회원 → 이메일이 전부 (0 ~ 6.05) =================
const c1 = cutL(S, -1, 6.05, { push: [1.0, 1.05], ox: 620, oy: 480 });
const st1 = stageN(c1);
st1.fill(ell(620, 640, 560, 520, { n: 30 }), SKY, -99, 0.38);
heroSeq(c1, [["g_o_hope", 0], ["g_o_laptop_blank", 2.91]], { x: 620, y: 400, sc: 2.0, s: 0.05, dur: 1.15 });
const t1 = win(c1.sub(), -1, 2.91, 0.12);
t1.text("쉰 살이 넘은", { x: 1110, y: 360, size: 120, s: 0.6, gap: 0.06 });
const r1 = t1.text("회원님", { x: 1110, y: 560, size: 170, s: 1.35, gap: 0.08 });
t1.underline(r1.box(), 2.0, 0.35);
const t2 = win(c1.sub(), 2.91, 6.05, 0.12);
const env = rr(1130, 250, 300, 200, 14);
t2.fill(env, BEIGE, 3.0, 0.6, 0.25); t2.line(env, 3.0, 0.4, { w: 7 });
t2.line(pl([[1130, 255], [1280, 360], [1430, 255]]), 3.35, 0.3, { w: 6 });
t2.text("컴퓨터 =", { x: 1110, y: 590, size: 110, s: 3.7, gap: 0.06 });
const r2 = t2.text("이메일이 전부", { x: 1110, y: 760, size: 130, s: 4.2, gap: 0.07 });
t2.circleMark(r2.box(0, 2), 5.2, 0.5);

// ================= 컷2: 쇼츠 부업 → 수백만 원짜리 강의 두 개 (6.05 ~ 11.17) =================
const c2 = cutL(S, 6.05, 11.17, { pan: [30, -30] });
const st2 = stageN(c2);
st2.fill(ell(1400, 600, 560, 520, { n: 30 }), "#F4E28A", -99, 0.33);
INKHERO.put(c2, "g_o_phone_wow", { x: 1400, y: 390, sc: 1.9, s: 6.1, dur: 1.1 });
const ph = rr(300, 150, 300, 330, 26);
c2.fill(ph, "#FFFFFF", 6.2, 0.9, 0.2); c2.line(ph, 6.2, 0.45, { w: 7 });
c2.text("쇼츠로", { x: 450, y: 270, size: 80, font: "gae", s: 6.7, anchor: "c" });
c2.text("부업!", { x: 450, y: 380, size: 96, font: "gae", s: 7.0, anchor: "c", c: "#D9622B" });
[[150, 600], [520, 600]].forEach(([x, y], i) => {
  const card = rr(x, y, 330, 210, 16), s0 = 8.0 + i * 0.7;
  c2.fill(card, i ? PINK : BEIGE, s0, 0.55, 0.25); c2.line(card, s0, 0.4, { w: 7 });
  c2.text(`강의 ${i + 1}`, { x: x + 30, y: y + 70, size: 66, font: "gae", s: s0 + 0.3 });
  c2.text("₩", { x: x + 30, y: y + 160, size: 70, font: "num", s: s0 + 0.45 });
  c2.fill(rr(x + 100, y + 130, 190, 50, 6), INK, s0 + 0.55, 0.85, 0.2);
});
const won = c2.text("수백만 원 x 2", { x: 430, y: 960, size: 110, s: 9.6, gap: 0.06, anchor: "c" });
c2.underline(won.box(0, 4), 10.5, 0.35);

// ================= 컷3: 결국 손편집 강의 → 자르고·자막·목소리 (11.17 ~ 18.61) =================
const c3 = cutL(S, 11.17, 18.61, { push: [1.04, 1.0], ox: 960, oy: 540 });
const st3 = stageN(c3);
st3.fill(rr(0, 960, 1920, 120, 0), BEIGE, -99, 0.5); st3.line(ln(0, 960, 1920, 960), -99, 0.1, { w: 5, pen: false });
INKHERO.put(c3, "g_o_laptop_tired", { x: 470, y: 430, sc: 1.85, s: 11.2, dur: 1.1 });
const mon = rr(930, 140, 900, 470, 18);
c3.fill(mon, "#FFFFFF", 11.5, 0.9, 0.2); c3.line(mon, 11.5, 0.5, { w: 8 });
c3.line(ln(1380, 610, 1380, 680), 11.9, 0.15, { w: 8 }); c3.line(ln(1250, 690, 1510, 690), 12.0, 0.2, { w: 8 });
[[0, 300, SKY], [1, 520, PINK], [2, 230, "#F4E28A"], [3, 610, SKY]].forEach(([k, w, col]) => {
  const bar = rr(980 + (k % 2) * 40, 230 + k * 85, w, 46, 8); c3.fill(bar, col, 12.1 + k * 0.15, 0.7, 0.2); c3.line(bar, 12.1 + k * 0.15, 0.2, { w: 5, pen: false });
});
const hd = c3.text("결국 손편집 강의", { x: 1380, y: 735, size: 110, s: 12.9, gap: 0.06, anchor: "c" });
c3.underline(hd.box(3, 5), 14.0, 0.35);
const tk = win(c3.sub(), 15.36, 1e9, 0.12);
[["장면 자르고", 15.4], ["자막 하나하나", 16.45], ["목소리 맞추고", 17.5]].forEach(([s, t], i) => {
  const cx = 1060 + i * 330;
  tk.fill(ell(cx, 845, 36, 36, { n: 14 }), ORG, t, 0.55, 0.2); tk.line(ell(cx, 845, 36, 36, { n: 14 }), t, 0.25, { w: 5 });
  tk.text(String(i + 1), { x: cx, y: 852, size: 52, font: "num", s: t + 0.05, anchor: "c" });
  tk.text(s, { x: cx, y: 935, size: 46, font: "gae", s: t + 0.15, gap: 0.04, anchor: "c" });
});

// ================= 컷4: 몇 달이 지나도 → 올린 영상 0 (18.61 ~ 21.64) =================
const c4 = cutL(S, 18.61, 21.64, { push: [1.0, 1.06], ox: 1400, oy: 450 });
const st4 = stageN(c4);
st4.fill(ell(1400, 620, 520, 500, { n: 30 }), "#D9D4CC", -99, 0.35);
INKHERO.put(c4, "g_o_frustr_head", { x: 1400, y: 400, sc: 1.85, s: 18.65, dur: 1.0 });
for (let i = 2; i >= 0; i--) {
  const pg = rr(170 + i * 26, 170 - i * 22, 640, 520, 14);
  c4.fill(pg, "#FFFFFF", 18.7 + (2 - i) * 0.12, 0.92, 0.15); c4.line(pg, 18.7 + (2 - i) * 0.12, 0.3, { w: 6 });
}
c4.line(ln(170, 270, 810, 270), 19.2, 0.25, { w: 6 });
for (let k = 1; k < 7; k++) c4.line(ln(170 + k * 91, 270, 170 + k * 91, 690), 19.3 + k * 0.04, 0.12, { w: 3, pen: false });
for (let k = 1; k < 4; k++) c4.line(ln(170, 270 + k * 105, 810, 270 + k * 105), 19.5 + k * 0.04, 0.12, { w: 3, pen: false });
c4.text("몇 달 뒤...", { x: 490, y: 225, size: 70, font: "gae", s: 19.4, anchor: "c" });
const z = c4.text("올린 영상 = 0", { x: 490, y: 880, size: 130, s: 20.0, gap: 0.07, anchor: "c" });
c4.circleMark(z.box(7, 7), 21.0, 0.45, 40, 20);

// ================= 컷5: 게을러서? → 아닙니다 → 솔직해집시다 → 시대가 아니잖아요 (21.64 ~ 27) =================
const c5 = cutL(S, 21.64, 1e9, { push: [1.04, 1.0], ox: 960, oy: 540 });
const st5 = stageN(c5);
st5.fill(rr(0, 1000, 1920, 80, 0), BEIGE, -99, 0.5); st5.line(ln(0, 1000, 1920, 1000), -99, 0.1, { w: 5, pen: false });
st5.fill(ell(470, 620, 440, 460, { n: 30 }), SKY, -99, 0.35);
heroSeq(c5, [["g_o_laptop_tired", 21.64], ["g_o_hope", 24.55]], { x: 470, y: 400, sc: 1.85, stat: true });
const q = c5.text("게을러서?", { x: 1000, y: 260, size: 150, s: 21.7, gap: 0.08 });
c5.line(ln(980, 170, 1640, 330), 23.18, 0.2, { c: ORG, w: 14 }); c5.line(ln(980, 330, 1640, 170), 23.3, 0.2, { c: ORG, w: 14 });
c5.text("아닙니다", { x: 1000, y: 410, size: 100, font: "gae", s: 23.35, gap: 0.04, c: "#D9622B" });
c5.text("솔직해집시다", { x: 1000, y: 580, size: 120, s: 23.78, gap: 0.05 });
const era1 = c5.text("이제 그런 시대가", { x: 1000, y: 760, size: 120, s: 24.6, gap: 0.05 });
const era2 = c5.text("아니잖아요", { x: 1000, y: 915, size: 150, s: 25.4, gap: 0.06 });
c5.underline(era2.box(), 26.3, 0.35);
