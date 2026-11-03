// N_hours_pain 「쉽다더니 몇 시간」 14초 (s02) — INK 손그림판(_lib_p + _assets + 새 주인공 남). 옛 판 = ../template (Sonnet 흰 바탕), ../out_v2.mp4
// 컷 흐름(옛 판 유지): 쉽다고 해서 시작했는데… → 시계·할 일 7개 체크 → 5~6시간 → 쇼츠 한 편에, 결국 몇 시간
// 주인공: P1 이 여자라 남자. 기대(g_m_laptop_hope) → 4.8 지침(g_m_laptop_tired) → 10.0 지침·이마(g_m_tired)
const { H, RR, O, stg, asset, hput, C: KC } = K;
// 카메라: 0~2.1 밀기(주인공) → 2.1~8.8 당기기(목록 전체) → 9.0~13.0 시계·숫자 쪽으로 패닝
const R = S.layer().xf((t) => {
  if (t < 2.1) { const k = eo(seg(t, 0, 2.1)); return { s: 1.0 + 0.06 * k, ox: 1440, oy: 420 }; }
  if (t < 9.0) { const k = eo(seg(t, 2.1, 8.8)); return { s: 1.06 - 0.06 * k, ox: 1440, oy: 420 }; }
  const k = eo(seg(t, 9.0, 13.0)); return { s: 1.0 + 0.04 * k, x: 30 * k, ox: 500, oy: 600 };
});
// 무대: 벽시계(시간이 흐른다) — 0초에 이미 걸려 있다
const ST = R.sub();
asset(ST, "prop.clock", { x: 760, y: 590, sc: 1.4, s: -0.3, stage: true });
const HN = R.sub().xf((t) => ({ r: Math.max(0, t - 1.9) * 150, ox: 760, oy: 590 - 120 * 1.4 }));   // 도는 바늘(주황)
HN.line(`M760 ${590 - 120 * 1.4} L760 ${590 - 215 * 1.4}`, 1.7, 0.2, { w: 7, c: "#F6A93B", pen: false });
// 주인공(오른쪽): 펜 0~1.0 → 4.8 지침 → 10.0 이마 짚음
hput(R, "g_m_laptop_hope", { x: 1440, bottom: 1090, u: 280, s: 0.0, dur: 0.85, win: [-1, 4.8] });
hput(R, "g_m_laptop_tired", { x: 1440, bottom: 1090, u: 280, stat: true, win: [4.8, 10.0] });
hput(R, "g_m_tired", { x: 1440, bottom: 1090, u: 280, stat: true, win: [10.0, 1e9] });
const DK = R.sub();                                                                       // 책상 앞판(그림 밑변을 덮는다) — 0초에 이미 있다
stg(DK, K.Q([[880, 960], [1920, 960], [1920, 1100], [880, 1100]], 6), -0.3, { solid: true, fill: KC.BEIGE, op: 0.55 });
stg(DK, [[880, 960], [1920, 960]], -0.3, { closed: false });

// 제목: 쉽다고 해서 시작했는데… (10.8 에 빠지고 그 자리에 결론)
const TT = R.sub().xf((t) => ({ o: 1 - clamp((t - 10.8) / 0.2) }));
TT.text("쉽다고 해서 시작했는데…", { x: 90, y: 110, size: 110, s: 1.05, gap: 0.05 });
// 할 일 7개: 글 → 네모 → 체크(펜 하나, 겹치지 않게)
const LS = R.sub();
["소재 찾기", "원본 찾기", "자르기", "대본 쓰기", "목소리", "자막", "썸네일"].forEach((w, i) => {
  const y = 250 + i * 72, s = 2.1 + i * 0.95;
  const T = LS.text(w, { x: 150, y: y + 30, size: 58, font: "gae", s, gap: 0.05 });
  const bx = 80, by = y;
  LS.line(H(RR(bx, by, 50, 50, 6), true, { jit: 0.5 }), T.end + 0.02, 0.15, { w: 5, pen: false });
  LS.line(H([[bx + 8, by + 26], [bx + 22, by + 42], [bx + 64, by - 10]], false), T.end + 0.2, 0.2, { w: 7, c: "#F6A93B" });
});
// 5~6시간 + 밑줄
const NB = R.sub();
const N = NB.text("5~6시간", { x: 80, y: 800, size: 150, font: "num", weight: 800, s: 9.0, gap: 0.1 });
NB.underline(N.box(), 9.75, 0.45);
// 결론(위쪽 — 아래 가운데는 나레이션 자막 자리)
const CL = R.sub();
const T2 = CL.text("쇼츠 한 편에, 결국 몇 시간", { x: 90, y: 110, size: 120, s: 11.0, gap: 0.05 });
CL.underline(T2.box(9, 13), 11.9, 0.4);
