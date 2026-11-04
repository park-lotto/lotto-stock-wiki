// 4회차 장면 s11 — 그 회원의 지금 (8.6초) · 문장 시각 = py ink/times.py s11 (★확인 안 된 대사: 회원 본인 확인·동의 전)
// 0.31 편집 앱 대신 클로드 창 / 4.71 이메일만 보내던 분도 / 6.55 대딸깍 시대
const Y = "#F4E28A", CL = "#D97757";
const c1 = cutL(S, -1, 4.71, { push: [1.0, 1.04], ox: 960, oy: 540 });
const st1 = stageN(c1);
st1.fill(ell(480, 620, 500, 480, { n: 30 }), Y, -99, 0.38);
INKHERO.put(c1, "g_o_phone_wow", { x: 480, y: 410, sc: 1.85, s: 0.05, dur: 1.0 });
const ap = c1.text("편집 앱", { x: 1150, y: 300, size: 120, s: 0.35, gap: 0.06, c: "#8C8A86" });
c1.line(ln(ap.x - 20, ap.y + 80, ap.x + ap.w + 20, ap.y + 80), 1.4, 0.25, { c: ORG, w: 14 });
const cw = rr(1000, 430, 800, 470, 24); c1.fill(cw, "#FFFFFF", 1.8, 0.95, 0.2); c1.line(cw, 1.8, 0.5, { w: 9 });
c1.line(ln(1000, 510, 1800, 510), 2.2, 0.2, { w: 6 }); c1.fill(ell(1050, 470, 16, 16, { n: 12 }), CL, 2.3, 0.95, 0.15);
c1.text("Claude", { x: 1085, y: 486, size: 54, font: "num", s: 2.3 });
const op = c1.text("클로드 창부터 연다", { x: 1400, y: 720, size: 100, s: 2.6, gap: 0.05, anchor: "c" });
c1.underline(op.box(0, 2), 3.8, 0.3);
const c2 = cutL(S, 4.71, 1e9, { push: [1.05, 1.0], ox: 960, oy: 540 });
const st2 = stageN(c2);
st2.fill(ell(1450, 620, 460, 460, { n: 30 }), SKY, -99, 0.35);
INKHERO.put(c2, "g_o_hope", { x: 1450, y: 400, sc: 1.8, s: 4.75, dur: 0.9 });
c2.text("이메일만 보내던 분도", { x: 120, y: 300, size: 100, font: "gae", s: 4.75, gap: 0.04 });
const ok = c2.text("됩니다", { x: 120, y: 500, size: 170, s: 5.6, gap: 0.08, c: CL });
c2.underline(ok.box(), 6.2, 0.3);
c2.text("대딸깍 시대", { x: 120, y: 820, size: 180, s: 6.6, gap: 0.07 });
