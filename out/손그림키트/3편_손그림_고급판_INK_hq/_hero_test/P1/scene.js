// 새 주인공 시험(INKHERO.put) — P1 무대 일부 + 여(컷A 펜→컬러) / 남(컷B 펜→컬러, 5.6 정지 교체) / 여(컷C 회색→9.0 컬러 0.25초)
const { H, RR, O, stg, C: KC } = K;
const LEG = location.hash === "#legacy";   // 전후 비교용(옛 꺾은선 방식)
const NIGHT = "#3E4F73", SUN = "#F2D27A";
// ===== 컷 A 0~3.8: 여 g_f_night_phone (펜 0.35~1.7, 컬러 2.0) =====
const cA = K.cut(-1, 3.8);
const A0 = cA.sub();
stg(A0, RR(120, 170, 310, 380, 14), -0.3, { fill: NIGHT, op: 0.45 });
stg(A0, RR(1500, 640, 290, 400, 10), -0.25, { fill: KC.BEIGE, op: 0.5 });
const hA = INKHERO.put(cA, "g_f_night_phone", { x: 960, y: 395, sc: 1.75, s: 0.35, dur: 1.35, legacy: LEG });
// ===== 컷 B 3.8~7.0: 남 g_m_tired (펜 3.85~5.0, 컬러 5.3) → 5.6 g_m_excited 정지 교체 =====
const cB = K.cut(3.8, 7.0);
stg(cB.sub(), [[60, 996], [1860, 996]], 3.45, { closed: false });
INKHERO.put(cB, "g_m_tired", { x: 1180, y: 430, sc: 1.7, s: 3.85, dur: 1.15, win: [3.8, 5.6], legacy: LEG });
INKHERO.put(cB, "g_m_excited", { x: 1180, y: 430, sc: 1.7, stat: true, win: [5.6, 7.0] });
const B1 = cB.sub();
B1.text("쇼츠로", { x: 560, y: 380, size: 112, font: "num", weight: 800, anchor: "c", s: 4.0, gap: 0.09 });
// ===== 컷 C 7.0~12: 여 g_f_laptop_hope (펜 7.05~8.2, 컬러 8.5) 회색 → 9.0 에 0.25초 컬러(P10 방식) =====
const cC = K.cut(7.0, 1e9);
INKHERO.put(cC, "g_f_laptop_hope", { x: 1490, y: 355, sc: 1.6, s: 7.05, dur: 1.15, gray: 9.0, cdur: 0.25 });
cC.sub().text("다 해 보셨을 텐데, 결과는요?", { x: 150, y: 952, size: 110, s: 9.25, gap: 0.045 });
