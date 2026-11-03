// P1 「밤에 폰 → 강의 결제」 12초, 3컷 — 새 주인공(여, INKHERO) + _assets 소품 (옛 판: scene_v1/v2/v3.js)
// SHOTLIST: A #5 g_f_night_phone / B #3 g_f_hope → 설렘 / C #6 g_f_laptop_hope → 지침. 컷·문구·시간은 옛 판 그대로.
const { H, RR, O, stg, asset, hput, C: KC } = K;
const NIGHT = "#3E4F73", SUN = "#F2D27A";

// ===== 컷 A 0~3.8: 밤, 침대에서 폰 보며 가슴이 뛴다 (카메라 밀기) =====
const cA = K.cut(-1, 3.8, { s0: 1.0, s1: 1.07, ox: 960, oy: 420 });
const A0 = cA.sub();
stg(A0, RR(120, 170, 310, 380, 14), -0.3, { fill: NIGHT, op: 0.45 });                 // 창
stg(A0, [[275, 170], [275, 550]], -0.2, { closed: false, w: 4 }); stg(A0, [[120, 360], [430, 360]], -0.2, { closed: false, w: 4 });
stg(A0, [[330, 225], [282, 240], [268, 300], [300, 345], [240, 340], [215, 285], [240, 245], [290, 222]], -0.1, { fill: SUN, op: 0.8, w: 4 }); // 달
stg(A0, RR(470, 130, 980, 330, 40), -0.3, { fill: KC.BEIGE, op: 0.5 });                 // 침대 머리판
stg(A0, RR(1500, 640, 290, 400, 10), -0.25, { fill: KC.BEIGE, op: 0.5 });              // 협탁
stg(A0, [[1500, 800], [1790, 800]], -0.15, { closed: false, w: 4 });
stg(A0, K.Q([[1560, 440], [1730, 440], [1690, 560], [1600, 560]]), -0.2, { fill: SUN, op: 0.55 }); // 스탠드
stg(A0, [[1645, 560], [1645, 640]], -0.1, { closed: false, w: 5 });
stg(A0, RR(560, 300, 800, 300, 90), -0.2, { fill: KC.SKY, op: 0.3 });                  // 베개
const glow = cA.sub();                                                                   // 폰 빛(얼굴 아래)
glow.fill(H(O(960, 600, 300, 150), true, { jit: 0 }), KC.SKY, 1.9, 0.3, 0.4);
hput(cA, "g_f_night_phone", { x: 960, bottom: 905, u: 320, s: 0.3, dur: 1.15 });
const bl = cA.sub();                                                                     // 이불: 그림 밑변을 덮는다
stg(bl, [[300, 1090], [300, 900], [520, 860], [760, 880], [960, 866], [1180, 880], [1420, 858], [1620, 900], [1620, 1090]], -0.2, { fill: KC.SKY, op: 0.62, solid: true, w: 0 });
stg(bl, [[300, 900], [520, 860], [760, 880], [960, 866], [1180, 880], [1420, 858], [1620, 900]], -0.2, { closed: false });
stg(bl, [[560, 920], [600, 1000], [560, 1080]], -0.05, { closed: false, w: 4 }); stg(bl, [[1360, 920], [1320, 1000], [1360, 1080]], -0.05, { closed: false, w: 4 });

// ===== 컷 B 3.8~7.0: 폰을 들고 보며 기대 → 5.2 설렘 (카메라 당기기) =====
const cB = K.cut(3.8, 7.0, { s0: 1.06, s1: 1.0, ox: 1250, oy: 500 });
const B0 = cB.sub();
stg(B0, RR(860, 150, 800, 520, 40), 3.45, { fill: KC.BEIGE, op: 0.5 });                 // 같은 침실: 머리판·베개·창(밤)
stg(B0, RR(930, 520, 640, 260, 90), 3.45, { fill: KC.SKY, op: 0.3 });
stg(B0, RR(1690, 120, 200, 330, 12), 3.45, { fill: NIGHT, op: 0.45 }); stg(B0, [[1790, 120], [1790, 450]], 3.45, { closed: false, w: 4 });
stg(B0, [[60, 996], [960, 996]], 3.45, { closed: false });
hput(cB, "g_f_hope", { x: 1250, bottom: 1090, u: 330, s: 3.8, dur: 0.75, win: [3.8, 5.2] });
hput(cB, "g_f_excited", { x: 1250, bottom: 1090, u: 330, stat: true, win: [5.2, 7.0] });
const B1 = cB.sub();
const tb1 = B1.text("쇼츠로", { x: 560, y: 380, size: 112, font: "num", weight: 800, anchor: "c", s: 4.65, gap: 0.09 });
const tb2 = B1.text("돈 번다", { x: 560, y: 520, size: 112, font: "num", weight: 800, anchor: "c", s: tb1.end + 0.1, gap: 0.09 });
const heart = H([[560, 702], [530, 660], [480, 672], [476, 730], [560, 800], [644, 730], [640, 672], [590, 660]], true, { jit: 0.6 });
B1.line(heart, tb2.end + 0.1, 0.4, { w: 7 }); B1.fill(heart, "#F2A3A0", tb2.end + 0.45, 0.7, 0.3);
[[820, 520, 910, 470], [820, 600, 920, 600], [820, 680, 910, 730]].forEach(([x1, y1, x2, y2], k) => B1.line(H([[x1, y1], [x2, y2]], false), 6.0 + k * 0.05, 0.2, { w: 6, c: "#F6A93B", pen: false }));   // 두근 선

// ===== 컷 C 7.0~12.0: 노트북 강의 결제 → 9.45 지침 + 손글씨 (카메라 패닝) =====
const cC = K.cut(7.0, 1e9, { s0: 1.0, s1: 1.0, dx: -40, ox: 960, oy: 540 });
hput(cC, "g_f_laptop_hope", { x: 1560, bottom: 975, u: 340, s: 7.0, dur: 0.9, win: [7.0, 9.45] });
hput(cC, "g_f_tired", { x: 1560, bottom: 975, u: 340, stat: true, win: [9.45, 1e9] });
const desk2 = cC.sub();                                                                  // 주인공 앞 책상(그림 밑변을 덮는다)
stg(desk2, K.Q([[1190, 945], [1920, 945], [1920, 1090], [1190, 1090]], 6), 6.7, { solid: true, fill: KC.BEIGE, op: 0.55 });
const PAY = cC.sub().xf(() => ({ y: 80 }));                                              // 결제 노트북 묶음(위에 손글씨 자리)
const desk = PAY.sub();                                                                   // 책상(결제 노트북 밑)
stg(desk, K.Q([[80, 836], [1100, 836], [1100, 905], [80, 905]], 4), 6.7, { solid: true, w: 5 });
stg(desk, K.Q([[40, 772], [1140, 772], [1100, 836], [80, 836]], 6), 6.7, { solid: true, fill: KC.BEIGE, op: 0.6 });
const LP = PAY.sub();
asset(LP, "prop.laptop", { x: 575, y: 790, sc: 2.6, s: 6.7, stage: true, keep: (i, k) => k <= 3 || k >= 8 });
const UI = PAY.sub();
UI.line(H([[284, 268], [882, 268]], false), 6.75, 0.25, { w: 4, pen: false });
[0, 1, 2].forEach((k) => UI.line(H(O(305 + k * 30, 244, 8, 8), true), 6.75, 0.12, { w: 4, pen: false }));
UI.text("강의 결제", { x: 410, y: 245, size: 50, font: "gae", s: 6.75, gap: 0.0001 });
const th = H(RR(300, 300, 250, 160, 10), true); UI.line(th, 7.95, 0.3, { w: 6 }); UI.fill(th, KC.SKY, 8.2, 0.45, 0.3);
UI.line(H(K.Q([[400, 340], [400, 420], [470, 380]], 6), true), 8.2, 0.2, { w: 5, pen: false });
[330, 375, 420].forEach((y, i) => UI.line(H([[585, y], [860 - i * 70, y]], false), 8.2 + i * 0.05, 0.2, { w: 5, pen: false }));
const btn = H(RR(560, 505, 290, 86, 40), true); UI.line(btn, 8.27, 0.22, { w: 6 }); UI.fill(btn, "#F2A3A0", 8.45, 0.55, 0.3);
UI.text("결제하기", { x: 680, y: 553, size: 54, font: "gae", anchor: "c", s: 8.5, gap: 0.05 });
const HP = PAY.sub().xf((t) => { const p = seg(t, 9.12, 9.3), q = seg(t, 9.3, 9.5); return { y: 14 * (p - q) }; });
asset(HP, "hand.press", { x: 830, y: 672, sc: 1.6, s: 8.86, per: 0.035 });
const TX = cC.sub();
const T = TX.text("다 해 보셨을 텐데, 결과는요?", { x: 110, y: 150, size: 125, s: 9.25, gap: 0.045 });
TX.circleMark(T.box(12, 16), 10.1, 0.5, 30, 10);
