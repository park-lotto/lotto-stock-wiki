// P4 「수료증·노트 더미 → 캡컷 하나 → 남은 건 캡컷 실력뿐」 9초, 3컷 — _lib_p 엔진 + _assets (옛 판 = scene_v1.js)
const { H, RR, O, stg, asset, hput, C: KC } = K;
const TN = { beige: KC.BEIGE, sky: KC.SKY, pink: "#F2B8B0" };
function cert(L, x, y, w, h, s, tint, fast) {               // 수료증
  const d = H(RR(x, y, w, h, 6), true, { jit: 0.7 });
  L.fill(d, "#FBF8F1", s, 0.85, 0.15); L.fill(d, "#FBF8F1", s, 0.85, 0.15); L.fill(d, TN[tint], s + 0.1, 0.32, 0.3);
  L.line(d, s, fast ? 0.3 : 0.4, { w: 7, pen: !fast });
  L.line(H(RR(x + 16, y + 16, w - 32, h - 32, 4), true, { jit: 0.4 }), s + 0.2, 0.3, { w: 3, pen: false });
  [0.28, 0.4, 0.52].forEach((k, i) => L.line(H([[x + w * 0.2, y + h * k], [x + w * (0.8 - i * 0.1), y + h * k]], false), s + 0.3 + i * 0.04, 0.15, { w: 4, pen: false }));
  const sl = H(O(x + w / 2, y + h * 0.76, w * 0.1, w * 0.1), true); L.line(sl, s + 0.4, 0.2, { w: 5, pen: false }); L.fill(sl, "#F2A3A0", s + 0.5, 0.6, 0.2);
}
function note(L, x, y, w, h, s, tint, fast) {                 // 공책
  const d = H(RR(x, y, w, h, 8), true, { jit: 0.7 });
  L.fill(d, "#FBF8F1", s, 0.85, 0.15); L.fill(d, "#FBF8F1", s, 0.85, 0.15); L.fill(d, TN[tint], s + 0.1, 0.38, 0.3);
  L.line(d, s, fast ? 0.3 : 0.32, { w: 7, pen: !fast });
  L.line(H([[x + 40, y + 4], [x + 40, y + h - 4]], false, { over: 0 }), s + 0.2, 0.12, { w: 4, pen: false });
  L.line(H([[x + 80, y + h / 2], [x + w - 40, y + h / 2]], false), s + 0.25, 0.15, { w: 4, pen: false });
}
function sparkle(P, cx, cy, k, s, col, stop) {               // 아이콘 둘레 반짝(끝 −1초 전에 멈춤)
  const R = P.sub().xf((t) => ({ o: t > s + 0.6 && t < stop ? 0.55 + 0.45 * Math.sin((t - s) * 7) : 1 }));
  [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([sx, sy], i) => {
    const px = cx + sx * k, py = cy + sy * k * 0.85, l = 26;
    R.line(`M${px - l} ${py} L${px + l} ${py} M${px} ${py - l} L${px} ${py + l}`, s + i * 0.08, 0.25, { w: 7, c: col, pen: false });
  });
}
// ===== 컷 A 0~3.0: 책상 위에 강의(공책)·수료증이 쌓인다 =====
const cA = K.cut(-1, 3.0, { s0: 1.0, s1: 1.05, ox: 1100, oy: 520 });                   // 밀기
hput(cA, "g_m_laptop_tired", { x: 1520, bottom: 900, u: 250, s: 0.0, dur: 0.9, win: [-1, 2.0] });   // #10 강의는 쌓이는데 — 지침
hput(cA, "g_m_tired", { x: 1520, bottom: 900, u: 250, stat: true, win: [2.0, 3.0] });                 // 2.0 이마 짚음(정지 교체)
const DK = cA.sub();                                          // 책상: 주인공 몸 아래를 가린다
stg(DK, K.Q([[80, 910], [1840, 910], [1840, 1090], [80, 1090]], 4), -0.3, { solid: true, fill: KC.BEIGE, op: 0.3 });
stg(DK, K.Q([[40, 860], [1880, 860], [1840, 910], [80, 910]], 6), -0.3, { solid: true, fill: KC.BEIGE, op: 0.65 });
stg(DK, [[700, 975], [1220, 975]], -0.2, { closed: false, w: 4 }); stg(DK, [[930, 1000], [990, 1000]], -0.2, { closed: false, w: 6 });
const A1 = cA.sub();
[["beige", 0], ["sky", 1], ["pink", 2], ["beige", 3], ["sky", 4]].forEach(([c, i]) => note(A1, 160 + (i % 2) * 24, 776 - i * 84, 520 - (i % 2) * 20, 84, 0.95 + i * 0.24, c));
cert(A1, 730, 360, 290, 500, 2.15, "beige"); cert(A1, 900, 460, 250, 400, 2.5, "sky");
// ===== 컷 B 3.0~6.0: 그 위에 편집 앱(캡컷) 하나만 반짝 =====
const cB = K.cut(3.0, 6.0, { s0: 1.0, s1: 1.06, ox: 960, oy: 553 });                   // 아이콘으로 밀기
const B0 = cB.sub();
stg(B0, [[60, 1000], [1860, 1000]], 2.7, { closed: false });
cert(B0, 200, 190, 340, 560, 2.7, "beige", 1); cert(B0, 1380, 170, 340, 580, 2.7, "sky", 1);
note(B0, 440, 925, 1040, 70, 2.7, "beige", 1);
const B1 = cB.sub();
asset(B1, "prop.app_edit", { x: 960, y: 740, sc: 1.6, s: 3.2, per: 0.08 });
B1.text("캡컷", { x: 960, y: 860, size: 96, font: "gae", anchor: "c", s: 4.2, gap: 0.08 });
sparkle(cB, 960, 553, 260, 4.5, "#F6A93B", 5.9);
const HB = cB.sub().xf((t) => ({ x: t > 5.0 ? -12 * Math.max(0, Math.sin((t - 5.0) * 6)) : 0 }));
asset(HB, "hand.point", { x: 560, y: 610, sc: 1.6, s: 4.6, per: 0.05 });
// ===== 컷 C 6.0~9.0: 머리 감싼 주인공 + 손글씨 =====
const cC = K.cut(6.0, 1e9, { s0: 1.05, s1: 1.0, ox: 520, oy: 450 });                   // 당기기
const C0 = cC.sub();
stg(C0, [[60, 985], [1860, 985]], 5.7, { closed: false, w: 4 });
asset(C0, "prop.app_edit", { x: 1450, y: 720, sc: 1.1, s: 5.7, stage: true });
C0.text("캡컷", { x: 1450, y: 800, size: 72, font: "gae", anchor: "c", s: 5.7, gap: 0.0001 });
hput(cC, "g_m_frustr_head", { x: 520, bottom: 985, u: 240, stat: true });            // #11 남은 건 캡컷 실력뿐 (글이 6.4 부터라 펜 없이)
const TX = cC.sub();
const T = TX.text("남은 건 캡컷 실력뿐", { x: 990, y: 210, size: 140, s: 6.4, gap: 0.05 });
TX.underline(T.box(5, 6), 7.3, 0.3);
