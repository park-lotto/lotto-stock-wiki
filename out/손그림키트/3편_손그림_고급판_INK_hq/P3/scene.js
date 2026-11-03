// P3 「달력 넘김 → 통장 0원 → 언제까지 수익 없이?」 9초, 3컷 — _lib_p 엔진 + _assets (옛 판 = scene_v1.js)
const { H, RR, O, stg, asset, hput, C: KC } = K;
// ===== 컷 A 0~3.0: 벽걸이 달력이 한 장씩 넘어간다 =====
const cA = K.cut(-1, 3.0, { s0: 1.0, s1: 1.05, ox: 1000, oy: 500 });                   // 밀기
const A0 = cA.sub();
stg(A0, [[60, 905], [1100, 905]], -0.3, { closed: false, w: 4 });
const CS = 3.1, CX = 600, CY = 900;                                   // 달력 자산: 바닥 중심 (600,900), 몸통 -200..0
asset(A0, "prop.calendar", { x: CX, y: CY, sc: CS, s: -0.3, stage: true, ground: false });
// 넘어가는 장(종이) 4장 — 위 끝을 축으로 접힌다
const PG = cA.sub(), bx = CX - 120 * CS, by = CY - 156 * CS, bw = 240 * CS, bh = 156 * CS;
const pages = [0, 1, 2, 3].map((k) => {
  const g = mk("g", { opacity: 0 }, PG.lg);
  mk("path", { d: H(RR(bx, by, bw, bh, 6), true, { jit: 0.4 }), fill: "#FFFFFF", stroke: "#1F1D1A", "stroke-width": 7, "stroke-linejoin": "round" }, g);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) mk("path", { d: H([[CX + (-96 + c * 44) * CS, CY + (-130 + r * 44) * CS], [CX + (-76 + c * 44) * CS, CY + (-130 + r * 44) * CS]], false, { over: 0 }), stroke: "#1F1D1A", "stroke-width": 4, fill: "none", "stroke-linecap": "round" }, g);
  for (let m = 0; m <= k; m++) { const x = CX + (-86 + m * 44) * CS, y = CY - 130 * CS; mk("path", { d: `M${x - 26} ${y - 26} l52 52 M${x + 26} ${y - 26} l-52 52`, stroke: "#D9534F", "stroke-width": 9, "stroke-linecap": "round", fill: "none" }, g); }
  return g;
});
pages.slice().reverse().forEach((g) => PG.lg.appendChild(g));       // 첫 장이 맨 위
S.on((t) => pages.forEach((g, k) => {
  const t0 = 1.0, ft = 1.35 + k * 0.42, fl = 0.36, p = k < 3 ? eo(seg(t, ft, ft + fl)) : 0;
  g.setAttribute("opacity", t >= t0 && !(k < 3 && t >= ft + fl) ? Math.min(1, (t - t0) / 0.2).toFixed(2) : 0);
  g.setAttribute("transform", `translate(0 ${by}) scale(1 ${Math.max(0.02, 1 - p).toFixed(3)}) translate(0 ${-by})`);
}));
asset(A0, "prop.clock", { x: 1750, y: 370, sc: 1.3, s: -0.3, stage: true });     // 벽시계(시간이 흐른다)
const HN = cA.sub().xf((t) => ({ r: Math.max(0, t - 1.0) * 260, ox: 1750, oy: 370 - 120 * 1.3 }));
HN.line(`M1750 ${370 - 120 * 1.3} L1750 ${370 - 205 * 1.3}`, 0.9, 0.2, { w: 6, c: "#F6A93B", pen: false });
hput(cA, "g_f_tired", { x: 1480, bottom: 1090, u: 300, s: 0.0, dur: 1.0 });           // #4 달력이 넘어가도 그대로 — 지침
// ===== 컷 B 3.0~6.0: 통장 0원 + 어깨가 처진다 =====
// ===== 컷 B 3.0~6.0: 통장 0원 + 어깨가 처진다 =====
const cB = K.cut(3.0, 6.0, { s0: 1.06, s1: 1.0, ox: 1100, oy: 600 });                  // 당기기
const B0 = cB.sub();
stg(B0, [[60, 930], [1860, 930]], 2.7, { closed: false, w: 4 });
hput(cB, "g_f_tired", { x: 1600, bottom: 930, u: 290, mir: true, stat: true });        // #4 반전, 재등장 = stat(같은 그림 펜 2회 금지)
const B1 = cB.sub();
asset(B1, "prop.bankbook", { x: 560, y: 930, sc: 2.2, s: 2.7, stage: true, solid: true });
const tb = B1.text("통장", { x: 560, y: 500, size: 80, font: "gae", anchor: "c", s: 3.2, gap: 0.1 });
B1.text("0원", { x: 560, y: 700, size: 220, font: "num", weight: 800, anchor: "c", s: tb.end + 0.15, gap: 0.2 });
// ===== 컷 C 6.0~9.0: 머리 감싼 주인공 + 손글씨 =====
const cC = K.cut(6.0, 1e9, { s0: 1.0, s1: 1.05, ox: 560, oy: 450 });                   // 밀기
const C0 = cC.sub();
hput(cC, "g_f_frustr_head", { x: 560, bottom: 1090, u: 290, stat: true });            // #9 언제까지… 그만두고 싶은데 (글이 6.1 부터라 펜 없이)
const C1 = cC.sub();
asset(C1, "prop.bankbook", { x: 560, y: 1060, sc: 1.6, s: 5.7, stage: true, solid: true });
const TX = cC.sub();
const t1 = TX.text("언제까지", { x: 1180, y: 300, size: 165, s: 6.1, gap: 0.055 });
const t2 = TX.text("수익 없이?", { x: 1180, y: 510, size: 165, s: t1.end + 0.1, gap: 0.055 });
TX.underline(t2.box(), 7.45, 0.3);
