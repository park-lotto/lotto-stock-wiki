// P6 진짜 바라는 것 (12초) — 디자인 기준: ink_explainer 레퍼런스(정본) + INK_스타일규칙
const base = S.layer();
person(base, { cx: 500, cy: 480, sc: 2.15, s: 0.1,
  faces: [ { e: "smile", a: -1, b: 5.2, look: [1, -1] }, { e: "grin", a: 5.2, b: 9.4, look: [1, -1] }, { e: "grin", a: 9.4, b: 1e9, look: [1, 0], brow: "up" } ],
  arms: [ { pts: [[128, 128], [190, 196], [250, 200], [304, 168]], hand: [310, 152], s: 9.5, win: [9.3, 1e9] } ] });
const trail = base.sub();
[[712, 436, 11], [756, 402, 18], [804, 362, 26]].forEach(([x, y, r], i) => { const d = ell(x, y, r, r, { n: 12 }); trail.line(d, 3.3 + i * 0.15, 0.22, { w: 5 }); trail.fill(d, "#FFFFFF", 3.7 + i * 0.15, 0.5); });
const CX = 1340, CY = 300, CRX = 500, CRY = 240;
const cl = cloud(CX, CY, CRX, CRY, 11, 0.06);

// ---- 풍선 ① 좋아하는 채널 ----
const b1 = S.layer().vis(3.2, 5.7, "pop");
b1.line(cl, 3.5, 0.7); b1.fill(cl, "#FFFFFF", 4.5, 0.6);
b1.shape(rr(930, 175, 340, 215, 16), 4.1, 0.55, SKY);
b1.line(poly([[1020, 250], [1020, 335], [1092, 292]], 5, true, 0.5), 4.7, 0.3, { w: 5 });
b1.line(ell(1180, 222, 17, 17, { n: 10 }), 4.85, 0.2, { w: 4.5 });
b1.line(ln(1150, 345, 1245, 345), 4.95, 0.2, { w: 4.5, pen: false }); b1.line(ln(1150, 368, 1215, 368), 5.0, 0.2, { w: 4.5, pen: false });
b1.line(ln(1100, 392, 1100, 420), 4.8, 0.15, { pen: false }); b1.line(ln(1060, 422, 1140, 422), 4.85, 0.2, { pen: false });
const t1a = b1.text("저 채널 스타일,", { x: 1315, y: 255, size: 70, font: "gae", s: 4.9, gap: 0.05 });
const t1b = b1.text("나도 그대로", { x: 1315, y: 345, size: 70, font: "gae", s: 5.1, gap: 0.05 });

// ---- 풍선 ② 돋보기로 원본 ----
const b2 = S.layer().vis(5.4, 9.9, "pop");
b2.line(cl, 5.5, 0.7); b2.fill(cl, "#FFFFFF", 6.5, 0.6);
b2.shape(rr(920, 190, 320, 195, 14), 6.1, 0.55, BEIGE);
b2.line(poly([[1020, 250], [1020, 325], [1085, 288]], 5, true, 0.5), 6.6, 0.3, { w: 5 });
const lens = ell(1190, 362, 80, 80, { n: 24 });
b2.line(lens, 6.9, 0.6, { w: 7 }); b2.fill(lens, "#FFFFFF", 7.4, 0.6); b2.line(ln(1247, 420, 1298, 474), 7.4, 0.3, { w: 12 });
b2.text("원본", { x: 1190, y: 364, size: 56, font: "gae", s: 7.6, anchor: "c" });
const burst = []; for (let i = 0; i < 16; i++) { const a = i / 16 * Math.PI * 2, r = i % 2 ? 26 : 48; burst.push([1262 + r * Math.cos(a), 205 + r * Math.sin(a)]); }
b2.line(poly(burst, 0, true, 0.6), 7.9, 0.45, { w: 5 }); b2.fill(poly(burst, 0, true, 0), "#F6A93B", 8.3, 0.4);
b2.text("원본만 찾으면,", { x: 1335, y: 255, size: 70, font: "gae", s: 6.3, gap: 0.05 });
b2.text("나도 터지는 영상", { x: 1335, y: 345, size: 70, font: "gae", s: 6.9, gap: 0.05 });

// ---- 마무리 손글씨 ----
const end = S.layer().vis(9.4, 1e9, "fade");
end.line(ell(1230, 160, 42, 42, { n: 16 }), 9.8, 0.35, { w: 5 }); end.text("1", { x: 1230, y: 162, size: 56, font: "gae", s: 10.1, anchor: "c" });
end.line(rr(1300, 132, 130, 62, 8), 10.0, 0.3, { w: 5 }); end.line(poly([[1347, 144], [1347, 182], [1381, 163]], 4, true, 0.3), 10.2, 0.2, { w: 4.5 });
end.line(ell(1560, 160, 42, 42, { n: 16 }), 10.2, 0.35, { w: 5 }); end.text("2", { x: 1560, y: 162, size: 56, font: "gae", s: 10.5, anchor: "c" });
end.line(ell(1470, 160, 22, 22, { n: 12 }), 10.4, 0.3, { w: 5 }); end.line(ln(1486, 176, 1508, 198), 10.6, 0.15, { w: 6 });
const e1 = end.text("이 두 가지", { x: 1130, y: 420, size: 200, s: 9.9, gap: 0.09 });
const e2 = end.text("아닙니까", { x: 1130, y: 640, size: 200, s: 10.8, gap: 0.09 });
end.underline(e1.box(2, 5), 11.4, 0.5);
