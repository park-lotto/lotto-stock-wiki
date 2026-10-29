const I = INK.ID, R = (x, y, w, h, r) => rect(I, x, y, w, h, r), Pp = (a) => P(I, a), E = (cx, cy, rx, ry, o) => ell(I, cx, cy, rx, ry, o);
function cert(c, x, y, w, h, s, tint) {
  c.mask(R(x, y, w, h, 6), s);
  c.path(R(x, y, w, h, 6), { s, dur: 0.45, tint, tintOp: 0.3 });
  c.path(R(x + 16, y + 16, w - 32, h - 32, 4), { s: s + 0.25, dur: 0.35, w: 4, pen: false });
  [0.28, 0.4, 0.52].forEach((k, i) => c.path(Pp([["M", x + w * 0.2, y + h * k], ["L", x + w * (0.8 - i * 0.1), y + h * k]]), { s: s + 0.4 + i * 0.05, dur: 0.15, w: 4, pen: false }));
  c.path(E(x + w / 2, y + h * 0.76, w * 0.1, w * 0.1, { n: 24 }), { s: s + 0.55, dur: 0.2, w: 5, tint: "pink", tintOp: 0.5, pen: false });
}
function note(c, x, y, w, h, s, tint) {
  c.mask(R(x, y, w, h, 8), s); c.path(R(x, y, w, h, 8), { s, dur: 0.4, tint, tintOp: 0.35 });
  c.path(Pp([["M", x + 40, y], ["L", x + 40, y + h]]), { s: s + 0.3, dur: 0.15, w: 4, pen: false });
  c.path(Pp([["M", x + 80, y + h / 2], ["L", x + w - 40, y + h / 2]]), { s: s + 0.35, dur: 0.15, w: 4, pen: false });
}
function capcut(c, cx, cy, sz, s, col) {
  const x = cx - sz / 2, y = cy - sz / 2;
  c.path(R(x, y, sz, sz, sz * 0.22), { s, dur: 0.6, fill: INK.INKC });
  c.path(`M${cx - sz * 0.28} ${cy - sz * 0.28} L${cx + sz * 0.28} ${cy + sz * 0.28}`, { s: s + 0.5, dur: 0.25, w: sz * 0.075, color: INK.PAPER, pen: false });
  c.path(`M${cx - sz * 0.28} ${cy + sz * 0.28} L${cx + sz * 0.28} ${cy - sz * 0.28}`, { s: s + 0.7, dur: 0.25, w: sz * 0.075, color: INK.PAPER, pen: false });
  const rs = []; const k = sz * 0.9;
  [[-1, -1], [1, -1], [1, 1], [-1, 1]].forEach(([sx, sy], i) => { const px = cx + sx * k * 0.72, py = cy + sy * k * 0.72, L = sz * 0.14;
    rs.push(c.path(`M${px - L} ${py} L${px + L} ${py} M${px} ${py - L} L${px} ${py + L}`, { s: s + 1.0 + i * 0.08, dur: 0.25, w: 6, color: col, pen: false })); });
  c.anim((t) => { const q = 0.55 + 0.45 * Math.sin((t - c.base) * 7); if (t > c.base + s + 1.5) rs.forEach((it) => it.el.setAttribute("opacity", q.toFixed(2))); });
}
// ===== 컷 A: 책상 위에 수료증·노트가 쌓인다 (0~3.2) =====
const A = ink.cut(0, 3.2);
A.path(Pp([["M", 60, 840], ["L", 1860, 840]]), { s: 0, dur: 0.6 });
note(A, 250, 760, 520, 80, 0.3, "beige"); note(A, 280, 680, 500, 80, 0.6, "sky"); note(A, 240, 600, 520, 80, 0.9, "pink"); note(A, 270, 520, 500, 80, 1.2, "beige");
cert(A, 830, 450, 270, 380, 0.5, "beige"); cert(A, 1000, 520, 250, 320, 0.9, "sky");
HERO.torso(A, 1560, 400, 115, { h: 3.8, s: 0.5, sp: 0.8 });
HERO.face(A, 1560, 400, 115, { expr: "tired", look: -1, s: 0.6, sp: 0.8 });
// ===== 컷 B: 그 위에 작은 캡컷 아이콘 하나만 반짝 (3.2~6.0) =====
const B = ink.cut(3.2, 6.0);
B.path(Pp([["M", 60, 960], ["L", 1860, 960]]), { s: 0, dur: 0.5 });
cert(B, 220, 380, 330, 470, 0.2, "beige"); cert(B, 1370, 360, 330, 470, 0.5, "sky");
note(B, 440, 870, 1040, 90, 0.4, "beige"); note(B, 480, 770, 960, 100, 0.7, "sky"); note(B, 430, 660, 1060, 110, 0.9, "pink");
capcut(B, 960, 430, 300, 1.2, INK.ORANGE);
// ===== 컷 C: 주인공 얼굴 + 손글씨 (6.0~9.0) =====
const C = ink.cut(6.0, 9.0);
C.path(Pp([["M", 60, 760], ["L", 1860, 760]]), { s: 0, dur: 0.5 });
HERO.torso(C, 470, 400, 170, { h: 2.1, s: 0.2, sp: 0.7 });
HERO.face(C, 470, 400, 170, { expr: "worry", look: 0.8, s: 0.3, sp: 0.7 });
note(C, 1100, 700, 600, 60, 0.3, "beige"); note(C, 1130, 640, 560, 60, 0.5, "sky");
capcut(C, 1400, 400, 250, 0.7, INK.INKC);
const T = C.text("남은 건 캡컷 실력뿐", { x: 150, y: 810, font: "NP", size: 140, s: 1.4, gap: 0.05, rot: -1.5 });
C.underline(C.box(T, 5, 6), { s: 2.3, dur: 0.5 });
