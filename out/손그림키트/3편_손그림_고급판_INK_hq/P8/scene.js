// P8 왜 원본인가 (14초) — v3(Opus, ART_GATE_1: 전환 겹침 0·4.8~5.0 백지 제거·지구본 부품) / v2(Opus): 폰·시계 = _assets(prop.phone·prop.clock), R1(채색 먼저→펜 윤곽)·R4·R5·R8
// 컷1 -~5.2 해외에서 터짐 / 컷2 4.9~9.7 1년 뒤 한국에서 또 / 컷3 9.4~ 재편집 X → 원본을 찾아야. 문구·순서 v1(scene_v1.js) 그대로.
function starPts(cx, cy, R, r, n = 5, rot = -Math.PI / 2) { const p = []; for (let i = 0; i < n * 2; i++) { const a = rot + i * Math.PI / n, k = i % 2 ? r : R; p.push([cx + k * Math.cos(a), cy + k * Math.sin(a)]); } return p; }
function burst(L, cx, cy, R, s, n = 12) {
  const d = poly(starPts(cx, cy, R, R * 0.45, 5, -Math.PI / 2 + 0.2), 0, true, 0.8);
  L.fill(d, "#F2D27A", s, 0.85, 0.2); L.line(d, s, 0.3, { w: 7, pen: false });
  for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2 + 0.1, r0 = R * 1.25, r1 = R * (1.5 + (i % 2) * 0.2); L.line(ln(cx + r0 * Math.cos(a), cy + r0 * Math.sin(a), cx + r1 * Math.cos(a), cy + r1 * Math.sin(a)), s + 0.2 + i * 0.02, 0.12, { w: 6, c: ORG, pen: false }); }
}
function arrowHead(L, x, y, ang, s, size = 36) { const a1 = ang + 2.6, a2 = ang - 2.6; L.line(pl([[x + size * Math.cos(a1), y + size * Math.sin(a1)], [x, y], [x + size * Math.cos(a2), y + size * Math.sin(a2)]]), s, 0.12, { w: 9, pen: false }); }
// 폰(자산) + 화면 재생 단추
function phoneA(L, x, y, sc, s, o = {}) {
  const r = art(o.stat ? L.sub({ stat: true }) : L, "prop.phone", { x, y, sc, s, per: 0.04 });
  const tri = poly([[x - 16 * sc, y - 140 * sc], [x - 16 * sc, y - 96 * sc], [x + 22 * sc, y - 118 * sc]], 4 * sc, true, 0.4);
  const P = o.stat ? L.sub({ stat: true }) : L;
  P.fill(tri, "#FFFFFF", r.end, 0.95, 0.15); P.line(tri, r.end, 0.15, { w: 6, pen: false });
  return r.end + 0.15;
}

// ===== 컷1: 지구본에서 해외 영상이 터짐 =====
const c1 = cutL(S, -1, 5.0, { push: [1.0, 1.04], ox: 900, oy: 600 });
const sg1 = stageN(c1); sg1.fill(rr(0, 945, 1920, 135, 0), BEIGE, -99, 0.45); sg1.line(ln(0, 945, 1920, 945), -99, 0.1, { w: 5 });
const GX = 520;
const gb = art(c1.sub(), "prop.globe", { x: GX, y: 900, sc: 2.0, s: 0.0, per: 0.035, opaque: true });   // 지구본 = _assets prop.globe
c1.text("해외", { x: GX, y: 190, size: 100, s: Math.max(1.5, gb.end), anchor: "c", gap: 0.1 });
c1.line(`M880 420 Q1030 290 1230 370`, Math.max(1.95, gb.end + 0.38), 0.5, { w: 9 }); arrowHead(c1, 1230, 370, 0.25, Math.max(2.45, gb.end + 0.88));
const pe1 = phoneA(c1, 1420, 940, 2.45, Math.max(2.5, gb.end + 0.92));
burst(c1, 1640, 420, 80, Math.max(3.6, pe1 + 0.05));

// ===== 컷2: 1년 뒤, 한국 폰에서 또 터짐 =====
const c2 = cutL(S, 5.0, 9.5, { pan: [24, -24] });
const sg2 = stageN(c2); sg2.fill(rr(0, 945, 1920, 135, 0), BEIGE, -99, 0.45); sg2.line(ln(0, 945, 1920, 945), -99, 0.1, { w: 5 });
phoneA(c2, 330, 900, 2.0, 5.0, { stat: true });
const sm = poly(starPts(470, 470, 56, 25, 5, -Math.PI / 2 + 0.2), 0, true, 0.6); const smL = c2.sub({ stat: true }); smL.fill(sm, "#F2D27A", -99, 0.85); smL.line(sm, -99, 0.1, { w: 6 });
c2.text("해외", { x: 300, y: 400, size: 90, s: 5.15, anchor: "c", gap: 0.1 });
c2.line(`M420 400 Q600 120 900 200 Q1150 260 1240 400`, 5.5, 0.5, { w: 10 }); arrowHead(c2, 1240, 400, 1.1, 6.0, 40);
const ck = art(c2.sub(), "prop.clock", { x: 760, y: 470, sc: 1.45, s: 6.0, per: 0.022 });
c2.text("1년 뒤", { x: 760, y: 610, size: 170, s: Math.max(6.7, ck.end), anchor: "c", gap: 0.12 });
const pe2 = phoneA(c2, 1490, 940, 2.4, 7.25);
c2.text("한국", { x: 1450, y: 340, size: 90, s: Math.max(8.35, pe2), anchor: "c", gap: 0.1 });
burst(c2, 1700, 430, 82, 8.75);

// ===== 컷3: 재편집 영상 + 남의 자막 → X =====
const c3 = cutL(S, 9.5, 1e9, { push: [1.04, 1.0] });
const s3 = stageN(c3);
const FX = 90, FY = 150, FW = 920, FH = 540;
s3.fill(rr(FX, FY, FW, FH, 18), SKY, -99, 0.5); s3.line(rr(FX, FY, FW, FH, 18), -99, 0.1, { w: 8 });
shadow(s3, FX + FW / 2, FY + FH + 26, FW);
const hill = [[FX + 40, FY + FH - 30], [FX + 250, FY + 190], [FX + 400, FY + FH - 160], [FX + 560, FY + 220], [FX + FW - 40, FY + FH - 30]];
s3.fill(smooth(hill.concat([[FX + FW - 40, FY + FH - 20], [FX + 40, FY + FH - 20]]), true), "#9FD0A8", -99, 0.55);
s3.line(pl(hill), -99, 0.1, { w: 5 });
const sun = ell(FX + 720, FY + 110, 54, 54, { n: 16 }); s3.fill(sun, "#F2D27A", -99, 0.85); s3.line(sun, -99, 0.1, { w: 5 });
[0, 1].forEach((i) => {
  const y = FY + 310 + i * 82, b = rr(FX + 50, y, FW - 100, 64, 8);
  s3.fill(b, "#B7A98C", -99, 0.85); s3.line(b, -99, 0.1, { w: 5 });
  s3.line(pl([[FX + 90, y + 32], [FX + 190, y + 18], [FX + 300, y + 44], [FX + 410, y + 20], [FX + 520, y + 44], [FX + 630, y + 20], [FX + 760, y + 40]]), -99, 0.1, { w: 5, c: "#FFFFFF" });
});
c3.line(ln(FX + 10, FY + 10, FX + FW - 10, FY + FH - 10), 9.7, 0.3, { w: 18 });
c3.line(ln(FX + FW - 10, FY + 10, FX + 10, FY + FH - 10), 10.05, 0.3, { w: 18 });
c3.text("재편집", { x: FX + FW / 2, y: 820, size: 110, s: 10.4, anchor: "c", gap: 0.06 });
c3.text("처음 찍은", { x: 1090, y: 330, size: 170, s: 10.8, gap: 0.05 });
const l2 = c3.text("원본을 찾아야", { x: 1090, y: 540, size: 170, s: 11.15, gap: 0.05 });
c3.text("합니다", { x: 1090, y: 750, size: 170, s: 11.6, gap: 0.05 });
c3.underline(l2.box(0, 1), 11.95, 0.3);
