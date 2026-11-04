// 4회차 장면 s09 — 채널 여러 개 (27.0초) · 문장 시각 = py ink/times.py s09 · 칸 영상 = tiles.json · 숫자 형식 6·스타일 24 실측
// 0.44 이런 채널 해 보고 싶다 / 6.24 부러우셨죠 / 9.05 하나만 할 이유 없다 / 10.86 열 개·스무 개·수십 개 / 17.81 형식 6·스타일 24 / 21.99 하고 싶은 채널? / 23.52 나만의 채널로
const Y = "#F4E28A", CL = "#D97757";
function phone(L, x, y, w, h, t) { const fr = rr(x - 12, y - 12, w + 24, h + 24, 24); L.fill(fr, "#1F1D1A", t, 0.9, 0.2); L.line(fr, t, 0.3, { w: 7 }); }
// ===== 컷1 해 보고 싶다·부럽다 (−1 ~ 9.05) =====
const c1 = cutL(S, -1, 9.05, { push: [1.0, 1.04], ox: 500, oy: 500 });
const st1 = stageN(c1);
st1.fill(ell(480, 620, 500, 480, { n: 30 }), Y, -99, 0.38);
INKHERO.put(c1, "g_o_phone_wow", { x: 480, y: 410, sc: 1.85, s: 0.05, dur: 1.1 });
const bub = smooth([[980, 180], [1820, 180], [1840, 560], [1180, 580], [1060, 680], [1090, 580], [990, 560], [980, 180]], true);
c1.fill(bub, "#FFFFFF", 0.6, 0.95, 0.2); c1.line(bub, 0.5, 0.5, { w: 8 });
c1.text("나도 이런 채널", { x: 1400, y: 320, size: 100, s: 1.2, gap: 0.05, anchor: "c" });
c1.text("한번 해 보고 싶다", { x: 1400, y: 450, size: 100, s: 2.4, gap: 0.05, anchor: "c" });
c1.text("저건 어떻게 만들었지?", { x: 1400, y: 800, size: 90, font: "gae", s: 6.3, gap: 0.04, anchor: "c" });
const en = c1.text("부럽다…", { x: 1400, y: 960, size: 120, s: 7.6, gap: 0.07, anchor: "c", c: "#D9622B" });
// ===== 컷2 채널 하나만 할 이유 없다 → 수십 개 (9.05 ~ 17.81) =====
const c2 = cutL(S, 9.05, 17.81);
c2.text("채널을 하나만 할 이유가 없다", { x: 960, y: 120, size: 96, s: 9.1, gap: 0.04, anchor: "c" });
const T = [10.9, 11.7, 12.5, 13.3, 14.0, 14.6, 15.2, 15.7];
T.forEach((t, k) => phone(c2, 300 + (k % 4) * 350, 210 + Math.floor(k / 4) * 380, 190, 338, t));
const many = c2.text("열 개, 스무 개, 수십 개도", { x: 960, y: 1010, size: 100, s: 13.4, gap: 0.05, anchor: "c", c: CL });
// ===== 컷3 형식 6 · 스타일 24 (17.81 ~ 21.99) =====
const c3 = cutL(S, 17.81, 21.99, { push: [1.0, 1.04], ox: 960, oy: 540 });
c3.text("지금 숏클 안에", { x: 960, y: 200, size: 100, font: "gae", s: 17.85, gap: 0.05, anchor: "c" });
const n1 = c3.text("6", { x: 560, y: 560, size: 300, font: "num", s: 18.6, anchor: "c" });
c3.text("형식", { x: 560, y: 820, size: 110, s: 18.8, anchor: "c" });
const n2 = c3.text("24", { x: 1360, y: 560, size: 300, font: "num", s: 19.9, anchor: "c", c: CL });
c3.text("채널 스타일", { x: 1360, y: 820, size: 110, s: 20.1, gap: 0.05, anchor: "c" });
c3.circleMark(n2.box(), 20.6, 0.4, 50, 20);
// ===== 컷4 하고 싶은 채널 → 나만의 채널로 (21.99 ~) =====
const c4 = cutL(S, 21.99, 1e9, { push: [1.05, 1.0], ox: 960, oy: 540 });
const st4 = stageN(c4);
st4.fill(ell(1450, 620, 460, 460, { n: 30 }), SKY, -99, 0.35);
INKHERO.put(c4, "g_o_hope", { x: 1450, y: 400, sc: 1.8, s: 22.0, dur: 1.0 });
c4.text("하고 싶은 채널,", { x: 120, y: 250, size: 110, s: 22.05, gap: 0.05 });
c4.text("있으신가요?", { x: 120, y: 420, size: 110, s: 22.6, gap: 0.05 });
const mc = c4.text("그 채널도", { x: 120, y: 680, size: 120, s: 23.6, gap: 0.06 });
const mc2 = c4.text("나만의 채널로", { x: 120, y: 870, size: 150, s: 24.7, gap: 0.06, c: CL });
c4.underline(mc2.box(0, 2), 25.9, 0.3);
