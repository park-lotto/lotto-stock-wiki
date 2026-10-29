const I = INK.ID, R = (x, y, w, h, r) => rect(I, x, y, w, h, r), Pp = (a) => P(I, a), E = (cx, cy, rx, ry, o) => ell(I, cx, cy, rx, ry, o);
// ===== 컷 A: 벽걸이 달력이 한 장씩 넘어간다 (0~3.0) =====
const A = ink.cut(0, 3.0);
const CX = 250, CY = 110, CW = 700, CH = 740;
let grid = ""; for (let k = 1; k < 7; k++) grid += `M${CX + k * 100} ${CY + 120} L${CX + k * 100} ${CY + CH} `; for (let k = 0; k < 5; k++) grid += `M${CX} ${CY + 120 + k * 124} L${CX + CW} ${CY + 120 + k * 124} `;
A.path(R(CX, CY, CW, CH, 14), { s: 0, dur: 0.6, tint: "beige", tintOp: 0.2 });
A.path(R(CX, CY, CW, 120, 14), { s: 0.3, dur: 0.4, tint: "pink", tintOp: 0.4 });
A.path(grid, { s: 0.5, dur: 0.8, w: 4, pen: false });
[CX + 200, CX + 500].forEach((x, i) => A.path(E(x, CY + 4, 12, 12, { n: 16 }), { s: 0.9 + i * 0.1, dur: 0.15, w: 5 }));
const heads = ["pink", "sky", "beige", "grey"];
const pages = heads.map((hc, k) => {
  const g = A.group(); g.style.display = "none";
  INK.el("rect", { x: CX, y: CY, width: CW, height: CH, rx: 14, fill: INK.PAPER, stroke: INK.INKC, "stroke-width": 6 }, g);
  INK.el("rect", { x: CX, y: CY, width: CW, height: 120, rx: 14, fill: INK.TINT[hc], "fill-opacity": 0.42, stroke: INK.INKC, "stroke-width": 6 }, g);
  INK.el("path", { d: grid, fill: "none", stroke: INK.INKC, "stroke-width": 4, "stroke-linecap": "round" }, g);
  for (let m = 0; m <= k; m++) INK.el("path", { d: `M${CX + 70 + m * 200} ${CY + 160} l60 60 M${CX + 130 + m * 200} ${CY + 160} l-60 60`, stroke: INK.INKC, "stroke-width": 6, "stroke-linecap": "round", fill: "none" }, g);
  [CX + 200, CX + 500].forEach((x) => INK.el("circle", { cx: x, cy: CY + 4, r: 12, fill: INK.PAPER, stroke: INK.INKC, "stroke-width": 5 }, g));
  return g;
});
pages.slice().reverse().forEach((g) => A.svg.appendChild(g)); // 첫 장이 맨 위
const sh = 1.45, fl = 0.45;
A.anim((t) => {
  const t0 = A.base + sh;
  pages.forEach((g, k) => {
    const ft = t0 + 0.5 + k * 0.55;
    g.style.display = (t >= t0 && !(k < 3 && t >= ft + fl)) ? "block" : "none";
    const p = k < 3 ? INK.eo(INK.seg(t, ft, ft + fl)) : 0;
    g.setAttribute("transform", `translate(0 ${CY}) scale(1 ${Math.max(0.02, 1 - p).toFixed(3)}) translate(0 ${-CY})`);
  });
});
HERO.torso(A, 1470, 430, 115, { h: 6.0, s: 0.3, sp: 0.8 });
HERO.face(A, 1470, 430, 115, { expr: "tired", look: -1, s: 0.4, sp: 0.8 });
// ===== 컷 B: 통장 0원 + 어깨가 처진다 (3.0~6.0) =====
const B = ink.cut(3.0, 6.0);
B.path(R(200, 190, 860, 590, 30), { s: 0, dur: 0.8, tint: "sky", tintOp: 0.32 });
B.path(R(200, 250, 860, 90, 4), { s: 0.5, dur: 0.5, tint: "beige", tintOp: 0.5 });
B.text("통장", { x: 250, y: 255, font: "GG", size: 76, s: 0.9, gap: 0.1 });
B.path(Pp([["M", 250, 430], ["L", 1010, 430]]), { s: 1.0, dur: 0.4, w: 4 });
B.text("0원", { x: 360, y: 450, font: "PB", weight: 800, size: 220, s: 1.2, gap: 0.2 });
B.path(Pp([["M", 250, 720], ["L", 600, 720]]), { s: 1.6, dur: 0.3, w: 4 });
const gB = B.group(), gH = B.group();
const body = HERO.torso(B, 1480, 470, 150, { h: 4.0, s: 0.3, sp: 0.7, parent: gB });
HERO.face(B, 1480, 470, 150, { expr: "tired", look: -1, s: 0.4, sp: 0.7, parent: gH });
B.anim((t) => { const k = INK.eo(INK.seg(t, B.base + 1.5, B.base + 2.3)); const d = body.morph(k);
  body.el.setAttribute("d", d); if (body.tintEl) body.tintEl.setAttribute("d", d);
  gB.setAttribute("transform", `translate(0 ${(k * 16).toFixed(1)})`); gH.setAttribute("transform", `translate(0 ${(k * 34).toFixed(1)}) rotate(${(k * 5).toFixed(1)} 1480 470)`); });
// ===== 컷 C: 어깨 처진 큰 얼굴 + 손글씨 (6.0~9.0) =====
const C = ink.cut(6.0, 9.0);
const gB2 = C.group(), gH2 = C.group();
HERO.torso(C, 560, 480, 210, { h: 3.0, slump: 1, s: 0.2, sp: 0.7, parent: gB2 });
gB2.setAttribute("transform", "translate(0 18)"); gH2.setAttribute("transform", "translate(0 40) rotate(5 560 480)");
HERO.face(C, 560, 480, 210, { expr: "tired", look: 0.3, s: 0.3, sp: 0.75, parent: gH2 });
const T = C.text("언제까지\n수익 없이?", { x: 1090, y: 330, font: "NP", size: 165, s: 1.3, gap: 0.06, rot: -2 });
C.underline(C.box(T, 5, 6), { s: 2.0, dur: 0.5 });
