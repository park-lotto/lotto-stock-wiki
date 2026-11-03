// P5 「탭이 늘고 해가 진다 → 땀 → 원본 하나 찾다가 하루가 다 갑니다」 10초, 3컷 — _lib_p 엔진 + _assets (옛 판 = scene_v1.js)
const { H, RR, O, stg, asset, hput, C: KC } = K;
const lerp = (a, b, k) => a + (b - a) * k, hex = (s) => [1, 3, 5].map((i) => parseInt(s.substr(i, 2), 16));
const mix = (a, b, k) => "rgb(" + hex(a).map((v, i) => Math.round(lerp(v, hex(b)[i], k))).join(",") + ")";
let _cp = 0;
function windowSky(L, x, y, w, h) {                         // 창 안 하늘(색이 바뀐다) + 잘림 영역
  const id = "p5cp" + (_cp++), cp = mk("clipPath", { id }, S.svg); mk("rect", { x, y, width: w, height: h }, cp);
  const g = mk("g", { "clip-path": `url(#${id})` }, L.fg), sky = mk("rect", { x, y, width: w, height: h, fill: "#F6E3A1", opacity: 0 }, g), sunG = mk("g", {}, g);
  return { g, sky, sunG };
}
function tabs(L, x0, y, n, w, s, e) {
  for (let i = 0; i < n; i++) {
    const x = x0 + i * w, t = s + e * Math.pow(i / n, 1.4);
    const d = H([[x, y + 50], [x, y + 8], [x + 8, y], [x + w - 10, y], [x + w - 2, y + 8], [x + w - 2, y + 50]], false, { over: 0, jit: 0.5 });
    L.line(d, t, 0.16, { w: 4, pen: i % 2 === 0 }); L.fill(d + " Z", [KC.SKY, KC.BEIGE, "#F2B8B0"][i % 3], t + 0.1, 0.45, 0.2);
  }
}
const LAPK = (i, k) => k <= 3 || k >= 8;                     // 노트북 자산에서 화면 속 줄·주황 칸만 뺀다
// ===== 컷 A 0~4.0: 노트북에 탭이 계속 늘고, 창밖 해가 진다 =====
const cA = K.cut(-1, 3.5, { s0: 1.0, s1: 1.05, ox: 900, oy: 420 });                    // 밀기
const A0 = cA.sub();
stg(A0, [[0, 905], [1920, 905]], -0.3, { closed: false, w: 4 });
const W = windowSky(A0, 1540, 110, 330, 560);
stg(A0, RR(1540, 110, 330, 560, 10), -0.3, {});
stg(A0, [[1705, 110], [1705, 670]], -0.2, { closed: false, w: 4 });
mk("path", { d: H(O(1640, 280, 62, 62), true), fill: "#F2D27A", stroke: "#1F1D1A", "stroke-width": 5 }, W.sunG);
mk("path", { d: H([[1540, 520], [1650, 485], [1760, 520], [1870, 505], [1870, 670], [1540, 670]], true), fill: "#B9BEC4", opacity: 0.8 }, W.g);
S.on((t) => { const k = seg(t, 1.0, 3.3); W.sky.setAttribute("opacity", (0.7 * clamp((t + 0.3) / 0.3)).toFixed(2)); W.sky.setAttribute("fill", mix("#F6E3A1", "#3E4F73", k)); W.sunG.setAttribute("transform", `translate(0 ${(eo(k) * 260).toFixed(1)})`); });
asset(A0, "prop.laptop", { x: 720, y: 900, sc: 3.4, s: -0.3, stage: true, keep: LAPK });
const A1 = cA.sub();                                         // 화면: x 332~1148, y 145~716
A1.line(H([[352, 248], [1130, 248]], false), 0.35, 0.25, { w: 4, pen: false });
// 탭 4개(높이 70) + 글: 나레이션 "틱톡 갔다가, 인스타 갔다가, 구글 렌즈" 순서
[["틱톡", 0.9], ["인스타", 1.4], ["렌즈", 1.9], ["…", 2.3]].forEach(([w, t], i) => {
  const x = 360 + i * 194, y = 176, tw = 186, d = H([[x, y + 72], [x, y + 10], [x + 10, y], [x + tw - 12, y], [x + tw - 2, y + 10], [x + tw - 2, y + 72]], false, { over: 0, jit: 0.5 });
  A1.line(d, t - 0.25, 0.2, { w: 5, pen: false }); A1.fill(d + " Z", [KC.SKY, KC.BEIGE, "#F2B8B0", KC.SKY][i], t - 0.15, 0.5, 0.2);
  A1.text(w, { x: x + tw / 2, y: y + 40, size: 44, font: "gae", anchor: "c", s: t, gap: 0.07 });
});
for (let r = 0; r < 2; r++) for (let q = 0; q < 3; q++) { const d = H(RR(380 + q * 250, 290 + r * 200, 220, 160, 8), true); A1.line(d, 0.7 + (r * 3 + q) * 0.25, 0.25, { w: 5, pen: false }); A1.fill(d, KC.SKY, 0.85 + (r * 3 + q) * 0.25, 0.3, 0.2); }
// ===== 컷 B 4.0~7.0: 주인공 이마에 땀 =====
const cB = K.cut(3.5, 7.0, { s0: 1.05, s1: 1.0, ox: 900, oy: 500 });                   // 당기기
const B0 = cB.sub();
stg(B0, [[0, 870], [1920, 870]], 3.2, { closed: false, w: 4 });
asset(B0, "prop.laptop", { x: 1370, y: 865, sc: 2.9, s: 3.2, stage: true, keep: LAPK });
const B1 = cB.sub();                                         // 화면: x 1022~1718, y 221~708
tabs(B1, 1040, 240, 14, 48, 4.55, 0.7);
for (let r = 0; r < 2; r++) for (let q = 0; q < 3; q++) { const d = H(RR(1050 + q * 215, 330 + r * 180, 190, 150, 8), true); B1.line(d, 4.6 + (r * 3 + q) * 0.08, 0.22, { w: 5, pen: false }); B1.fill(d, KC.SKY, 4.7 + (r * 3 + q) * 0.08, 0.3, 0.2); }
// 5.3초: 남의 자막이 덮인 영상(나레이션 "남의 자막이 덮여 있잖아요")
const VD = cB.sub().xf((t) => ({ o: clamp((t - 5.3) / 0.15) }));
stg(VD, RR(1180, 330, 480, 270, 12), 5.15, { solid: true, fill: KC.SKY, op: 0.55 });
stg(VD, K.Q([[1380, 365], [1380, 445], [1450, 405]], 6), 5.15, { fill: "#FBF8F1", op: 0.85, w: 5 });
[[1210, 468], [1210, 532]].forEach(([x, y]) => { const d = H(RR(x, y, 420, 50, 6), true, { jit: 0.3 }); VD.fill(d, "#1F1D1A", 5.15, 0.85, 0.15); VD.fill(d, "#1F1D1A", 5.15, 0.85, 0.15);
  [0, 1, 2, 3, 4, 5].forEach((q) => { const w = q % 2 ? 40 : 70, x0 = x + 40 + q * 60; VD.fill(H(RR(x0, y + 20, w, 10, 5), true, { jit: 0 }), "#FBF8F1", 5.15, 0.85, 0.15); }); });   // 자막 글줄(흰 획)
hput(cB, "g_m_tired", { x: 470, bottom: 870, u: 240, s: 3.5, dur: 1.0, win: [3.5, 5.45] });      // #2 틱톡·인스타·렌즈 — 지침
hput(cB, "g_m_frustr_head", { x: 470, bottom: 870, u: 240, stat: true, win: [5.45, 7.0] });    // 5.45 남의 자막 → 좌절(정지 교체)
// ===== 컷 C 7.0~10.0: 해가 졌다 + 손글씨 =====
const cC = K.cut(7.0, 1e9, { s0: 1.0, s1: 1.0, dx: 40, ox: 960, oy: 540 });              // 패닝
const C0 = cC.sub();
const W2 = windowSky(C0, 1040, 100, 760, 470); W2.sky.setAttribute("fill", "#3E4F73");
W2.sky.setAttribute("opacity", 0.78);
stg(C0, RR(1040, 100, 760, 470, 12), 6.7, {});
stg(C0, [[1420, 100], [1420, 570]], 6.75, { closed: false, w: 4 });
stg(C0, [[1660, 250], [1612, 262], [1590, 330], [1635, 400], [1570, 395], [1532, 330], [1555, 285], [1610, 250]], 6.75, { fill: "#F2D27A", op: 0.8, w: 4 });
[[1150, 200], [1300, 300], [1250, 480], [1560, 470], [1720, 520]].forEach(([x, y], i) => C0.line(`M${x - 14} ${y} L${x + 14} ${y} M${x} ${y - 14} L${x} ${y + 14}`, 6.75 + i * 0.04, 0.12, { w: 5, c: "#FBF8F1", pen: false }));
stg(C0, [[60, 800], [1860, 800]], 6.7, { closed: false, w: 4 });
hput(cC, "g_m_laptop_tired", { x: 520, bottom: 800, u: 215, stat: true });            // #10 하루가 다 간다 (글이 7.2 부터라 펜 없이)
const TX = cC.sub();
const T1 = TX.text("원본 하나 찾다가", { x: 960, y: 690, size: 118, s: 7.05, gap: 0.035 });   // 창 아래 오른쪽 두 줄(아래 가운데 = 자막 자리)
const T = TX.text("하루가 다 갑니다", { x: 960, y: 815, size: 118, s: T1.end + 0.1, gap: 0.035 });
TX.circleMark(T.box(0, 1), 8.05, 0.5, 34, 12);
