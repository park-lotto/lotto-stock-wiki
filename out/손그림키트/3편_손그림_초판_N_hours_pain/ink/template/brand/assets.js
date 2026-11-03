/* 숏클 손그림 자산 라이브러리 — 아트 디렉터 원화 (2026-10-29)
 * 판정서 ART_REVIEW.md ⑥ 권고: 자산은 여기서 한 번 그리고, 장면(P1~P10)은 조립만 한다.
 * 형식: 자산 하나 = { box, anchor, ground, items:[ {k:"line", d, w, c, z} | {k:"fill", d, c, op, z} ] }
 *   - items 는 "펜이 그리는 순서"대로 정렬돼 있다(큰 윤곽 → 안쪽 디테일 → 표정). 채색(fill)은 그 선 바로 뒤에 온다.
 *   - 선 2단(R8①): 외곽 W1=7 / 디테일 W2=4. 접지(R8②): ground=true 면 밑에 그림자 타원.
 *   - 좌표는 자산 로컬. 주인공 얼굴은 "두 눈 사이" 가 (0,0), 머리 폭 ≈ 130. 소품·직급은 바닥 중심이 (0,0).
 * 사용: README.md
 */
(function (root) {
  const INK = "#1F1D1A", ORG = "#F6A93B", SKIN = "#F2B8B0", HAIR = "#8E877C", SHIRT = "#8EC3E6",
    BLUSH = "#F0948C", WHITE = "#FFFFFF", BEIGE = "#E3D3B0", SKY = "#A8D2EA", LIL = "#BFA8E0", GRAY = "#CFD6DA", YEL = "#F2D27A", GREEN = "#9FD0A8";
  const W1 = 7, W2 = 4, W3 = 3;

  // ---------- 손맛: 결정적 흔들림 + 카트멀-롬 ----------
  let _s = 1;
  const seed = (n) => { _s = (n * 9301 + 49297) % 233280 || 7; };
  const rnd = () => { _s = (_s * 9301 + 49297) % 233280; return _s / 233280; };
  const J = (a) => (rnd() * 2 - 1) * a;
  const f = (n) => (Math.round(n * 10) / 10).toString();
  const hash = (pts) => pts.reduce((h, p) => (h * 31 + Math.round(p[0] * 7 + p[1] * 13)) % 100000, 17);
  // 손으로 그은 곡선: 점을 지나되, 끝은 살짝 넘치고(overshoot) 점마다 0.6px 흔들린다
  function H(pts, closed, o = {}) {
    seed(hash(pts)); const jit = o.jit === undefined ? 0.7 : o.jit, ten = o.ten === undefined ? 1 : o.ten;
    let P = pts.map((p) => [p[0] + J(jit), p[1] + J(jit)]);
    const n = P.length; if (n < 2) return "";
    if (!closed && o.over !== false && n >= 2) { // 끝 넘침
      const a = P[n - 2], b = P[n - 1], L = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1, k = (o.over || 2.5) / L;
      P[n - 1] = [b[0] + (b[0] - a[0]) * k, b[1] + (b[1] - a[1]) * k];
    }
    const G = (i) => closed ? P[(i + n) % n] : P[Math.max(0, Math.min(n - 1, i))];
    let d = "M" + f(P[0][0]) + " " + f(P[0][1]);
    const cnt = closed ? n : n - 1;
    for (let i = 0; i < cnt; i++) {
      const p0 = G(i - 1), p1 = G(i), p2 = G(i + 1), p3 = G(i + 2), t = ten / 6;
      d += " C" + f(p1[0] + (p2[0] - p0[0]) * t) + " " + f(p1[1] + (p2[1] - p0[1]) * t) + " " + f(p2[0] - (p3[0] - p1[0]) * t) + " " + f(p2[1] - (p3[1] - p1[1]) * t) + " " + f(p2[0]) + " " + f(p2[1]);
    }
    return closed ? d + " Z" : d;
  }
  const M = (pts) => pts.map((p) => [-p[0], p[1]]); // 좌우 반전
  const S = (pts, dx, dy, k = 1, ky) => pts.map((p) => [dx + p[0] * k, dy + p[1] * (ky === undefined ? k : ky)]);
  // 둥근 사각(손맛) : 모서리에 점을 두 개씩
  function RR(x, y, w, h, r) {
    return [[x + r, y], [x + w - r, y], [x + w, y + r], [x + w, y + h - r], [x + w - r, y + h], [x + r, y + h], [x, y + h - r], [x, y + r]];
  }
  // 손으로 그린 동그라미: 12점, 살짝 찌그러짐
  function O(cx, cy, rx, ry, k = 1) {
    ry = ry === undefined ? rx : ry; const pts = []; seed(Math.round(cx * 3 + cy * 5 + rx * 7));
    for (let i = 0; i < 12; i++) { const a = -Math.PI / 2 + i / 12 * Math.PI * 2, q = 1 + J(0.035) * k; pts.push([cx + rx * q * Math.cos(a), cy + ry * q * Math.sin(a)]); }
    return pts;
  }
  const L = (d, w = W1, c = INK, z = 0) => ({ k: "line", d, w, c, z });
  const F = (d, c, op = 0.55, z = 0) => ({ k: "fill", d, c, op, z });
  const LH = (pts, w, o, c, z) => L(H(pts, false, o), w, c, z);
  const LC = (pts, w, o, c, z) => L(H(pts, true, o), w, c, z);
  const FC = (pts, c, op, z) => F(H(pts, true, { jit: 0.3 }), c, op, z);
  const dot = (x, y, r, c = INK, z = 0) => F(H(O(x, y, r, r, 0), true, { jit: 0 }), c, 1, z);

  // =====================================================================
  // 주인공 얼굴 — 각도 3(front · tq(¾, 화면 왼쪽을 봄) · side(옆, 왼쪽을 봄)) × 표정 6
  // =====================================================================
  const VIEW = {
    front: {
      head: [[0, -80], [34, -76], [58, -58], [68, -28], [70, 6], [67, 34], [56, 58], [34, 76], [4, 82], [-28, 77], [-54, 60], [-66, 34], [-71, 6], [-68, -28], [-58, -58], [-34, -76]],
      chin2: [[-14, 70], [0, 74], [14, 70]],
      hairOut: [[-62, -30], [-58, -52], [-44, -68], [-22, -78], [0, -82], [24, -78], [46, -68], [59, -50], [62, -30]],
      hairIn: [[60, -36], [52, -28], [44, -38], [32, -52], [14, -58], [-4, -59], [-22, -56], [-38, -46], [-48, -32], [-54, -26], [-60, -36]],
      hairTex: [[[-10, -72], [-2, -66], [8, -70]], [[20, -66], [30, -56]], [[-36, -60], [-26, -54]]],
      ears: [[[-64, -6], [-74, -2], [-77, 10], [-70, 22], [-62, 20]], [[64, -6], [74, -2], [77, 10], [70, 22], [62, 20]]],
      earIn: [[[-71, 4], [-68, 12]], [[71, 4], [68, 12]]],
      eyes: [{ c: [-27, 3], rx: 22, ry: 21, side: -1 }, { c: [27, 3], rx: 22, ry: 21, side: 1 }],
      bridge: [[-6, 0], [0, -5], [6, 0]],
      temples: [[[-48, 2], [-63, 0]], [[48, 2], [63, 0]]],
      nose: [[2, 12], [-4, 24], [-7, 32], [2, 35]],
      naso: [[[-30, 30], [-28, 40], [-22, 48]], [[30, 30], [28, 40], [22, 48]]],
      mouthC: [0, 54], mw: 1,
      neck: [[[-20, 86], [-22, 108]], [[20, 86], [22, 108]]],
    },
    tq: {
      head: [[-8, -80], [28, -78], [56, -62], [68, -34], [70, 4], [66, 34], [54, 60], [30, 78], [0, 84], [-28, 80], [-48, 64], [-58, 42], [-62, 18], [-60, -6], [-60, -30], [-52, -58], [-30, -76]],
      chin2: [[-20, 70], [-6, 74], [8, 71]],
      hairOut: [[-56, -34], [-54, -56], [-40, -72], [-16, -82], [10, -82], [36, -74], [56, -56], [64, -34], [66, -14]],
      hairIn: [[64, -22], [56, -14], [50, -26], [40, -44], [26, -58], [6, -62], [-14, -58], [-30, -50], [-42, -40], [-50, -34], [-56, -40]],
      hairTex: [[[-4, -74], [4, -68], [14, -72]], [[26, -70], [36, -60]], [[-30, -64], [-22, -58]]],
      ears: [[[66, -4], [76, 0], [78, 12], [72, 24], [64, 22]]],
      earIn: [[[73, 6], [70, 14]]],
      eyes: [{ c: [-34, 4], rx: 17, ry: 21, side: -1, near: true }, { c: [14, 3], rx: 22, ry: 21, side: 1 }],
      bridge: [[-17, 1], [-12, -4], [-8, 1]],
      temples: [[[36, 2], [64, 0]]],
      nose: [[-44, 10], [-56, 24], [-62, 32], [-50, 36]],
      naso: [[[12, 32], [14, 42], [10, 50]]],
      mouthC: [-18, 54], mw: 0.85,
      neck: [[[-24, 86], [-26, 108]], [[16, 88], [18, 108]]],
    },
    side: {
      head: [[-26, -72], [-44, -54], [-54, -30], [-56, -8], [-52, 4], [-58, 12], [-70, 24], [-64, 32], [-52, 34], [-50, 44], [-54, 52], [-48, 56], [-52, 66], [-40, 76], [-22, 84], [2, 86], [28, 78], [50, 60], [64, 32], [68, 0], [62, -30], [48, -56], [26, -74], [0, -80]],
      chin2: [[-30, 70], [-16, 74], [-4, 72]],
      hairOut: [[-44, -46], [-42, -62], [-26, -74], [0, -82], [26, -78], [48, -62], [60, -36], [64, -8], [60, 10]],
      hairIn: [[56, 4], [50, -8], [46, -26], [36, -46], [18, -60], [-4, -64], [-24, -60], [-36, -50], [-42, -42], [-46, -50]],
      hairTex: [[[8, -72], [16, -66], [26, -70]], [[-18, -70], [-10, -62]], [[40, -52], [48, -40]]],
      ears: [[[36, -8], [50, -10], [56, 4], [50, 20], [38, 22], [34, 10]]],
      earIn: [[[44, 0], [48, 8], [42, 16]]],
      eyes: [{ c: [-36, 2], rx: 11, ry: 20, side: -1, near: true, prof: true }],
      bridge: null,
      temples: [[[-26, 0], [36, -2]]],
      nose: null,
      naso: [[[-40, 36], [-38, 46]]],
      mouthC: [-46, 48], mw: 0.5, prof: true,
      neck: [[[-30, 86], [-30, 108]], [[20, 86], [22, 108]]],
    },
  };

  // 표정 사전 — 눈썹(눈 로컬) · 눈 · 입 · 덤
  const EXPR = {
    hope:     { brow: [[-18, -30], [-2, -36], [16, -30]], eye: "open", mouth: "smileOpen", blush: true, label: "기대" },
    tired:    { brow: [[-18, -24], [0, -24], [16, -21]], eye: "half", mouth: "down", bags: true, label: "지침" },
    frustr:   { brow: [[-18, -31], [0, -26], [16, -19]], eye: "shut", mouth: "wavy", sweat: 2, gloom: true, label: "좌절" },
    surprise: { brow: [[-18, -38], [0, -44], [16, -38]], eye: "wide", mouth: "o", rays: true, label: "놀람" },
    relief:   { brow: [[-18, -30], [0, -33], [16, -29]], eye: "happy", mouth: "smile", sweat: 1, puff: true, label: "안도" },
    excited:  { brow: [[-18, -34], [0, -40], [16, -34]], eye: "star", mouth: "grin", blush: true, sparkle: true, label: "설렘" },
  };

  function face(expr, view, opt = {}) {
    const V = VIEW[view] || VIEW.front, E = EXPR[expr] || EXPR.hope, look = opt.look || [0, 0];
    const it = [];
    // 1 머리 윤곽 + 피부
    it.push(LC(V.head, W1, { jit: 0.9 })); it.push(FC(V.head, SKIN, 0.55));
    it.push(LH(V.chin2, W3, { jit: 0.4 }));
    // 2 귀
    V.ears.forEach((e) => it.push(LH(e, W2))); V.earIn.forEach((e) => it.push(LH(e, W3)));
    // 3 머리카락
    it.push(LH(V.hairOut, W1)); it.push(LH(V.hairIn, W2, { jit: 0.5 }));
    it.push(F(H(V.hairOut.concat(V.hairIn), true, { jit: 0.3 }), HAIR, 0.6));
    V.hairTex.forEach((t) => it.push(LH(t, W3)));
    // 4 코 · 팔자
    if (V.nose) it.push(LH(V.nose, W2));
    V.naso.forEach((n) => it.push(LH(n, W3, { jit: 0.3 })));
    // 5 안경 + 눈 (렌즈 안을 흰색으로 살짝 띄워 피부와 구분)
    V.eyes.forEach((e) => {
      const rim = O(e.c[0], e.c[1], e.rx, e.ry);
      it.push(F(H(rim, true, { jit: 0 }), WHITE, 0.45));
      it.push(LC(rim, 5, { jit: 0.6 }));
    });
    if (V.bridge) it.push(LH(V.bridge, 5, { over: 0 }));
    V.temples.forEach((t) => it.push(LH(t, W2, { over: 0 })));
    // 6 눈썹 (눈 로컬 → 각도별 위치; near 눈은 좁게)
    V.eyes.forEach((e) => {
      const k = e.prof ? 0.55 : (e.near ? 0.8 : 1), b = (e.side < 0 ? E.brow : M(E.brow)).map((p) => [e.c[0] + p[0] * k, e.c[1] + p[1] - (e.ry - 21)]);
      it.push(LH(b, 5, { jit: 0.5 }));
    });
    // 7 눈알
    V.eyes.forEach((e) => {
      const cx = e.c[0] + look[0] * 6 * (e.prof ? 0.4 : 1), cy = e.c[1] + 2 + look[1] * 5, r = e.prof ? 3.8 : 5;
      const kind = E.eye;
      if (kind === "open") it.push(dot(cx, cy, r));
      else if (kind === "wide") { it.push(LC(O(cx, cy, r * 1.9, r * 1.9), W3)); it.push(dot(cx, cy, r * 1.1)); it.push(dot(cx - r * 0.5, cy - r * 0.55, 1.7, WHITE)); }
      else if (kind === "half") { it.push(dot(cx, cy + 1, r)); it.push(LH([[cx - 11, cy - 5], [cx, cy - 2], [cx + 11, cy - 5]], W2)); if (E.bags) it.push(LH([[cx - 8, cy + 9], [cx, cy + 12], [cx + 8, cy + 9]], W3)); }
      else if (kind === "shut") it.push(LH([[cx - 10, cy - 4], [cx, cy + 3], [cx + 10, cy - 4]], W2));
      else if (kind === "happy") it.push(LH([[cx - 10, cy + 3], [cx, cy - 5], [cx + 10, cy + 3]], W2));
      else if (kind === "star") { it.push(LH([[cx, cy - 8], [cx + 2, cy - 2], [cx + 8, cy], [cx + 2, cy + 2], [cx, cy + 8], [cx - 2, cy + 2], [cx - 8, cy], [cx - 2, cy - 2], [cx, cy - 8]], W3, { jit: 0.2, over: 0 })); it.push(dot(cx, cy, 2.2)); }
    });
    // 8 입 (각도별 중심·폭)
    const [mx, my] = V.mouthC, mw = V.mw, m = E.mouth;
    const MP = (pts) => pts.map((p) => [mx + p[0] * mw, my + p[1]]);
    if (V.prof) { // 옆얼굴: 입은 짧은 선 하나
      const P = { smileOpen: [[-6, 0], [4, -2], [12, -8]], down: [[-8, -4], [2, -2], [10, 2]], wavy: [[-8, -2], [-2, 2], [4, -2], [10, 2]], o: null, smile: [[-6, 0], [4, -3], [12, -9]], grin: [[-8, 0], [4, -2], [14, -10]] }[m];
      if (m === "o") { it.push(LC(O(mx - 2, my, 5, 7), W2)); it.push(FC(O(mx - 2, my, 5, 7), INK, 0.8)); }
      else { it.push(LH(MP(P), 5)); if (m === "grin") { it.push(LH(MP([[-8, 0], [2, 8], [14, -10]]), W2)); } }
    } else if (m === "smileOpen") { const sm = [[-20, -6], [-8, 2], [8, 2], [20, -6], [12, 8], [0, 11], [-12, 8]]; it.push(FC(MP(sm), INK, 0.8)); it.push(LC(MP(sm), 5)); it.push(LH(MP([[-22, -9], [-18, -4]]), W3, { over: 0 })); it.push(LH(MP([[22, -9], [18, -4]]), W3, { over: 0 })); }
    else if (m === "smile") { it.push(LH(MP([[-20, -5], [0, 5], [20, -5]]), 5.5)); it.push(LH(MP([[-22, -8], [-18, -3]]), W3, { over: 0 })); it.push(LH(MP([[22, -8], [18, -3]]), W3, { over: 0 })); }
    else if (m === "down") { it.push(LH(MP([[-16, 2], [-6, -1], [6, -1], [16, 3]]), 5.5)); }
    else if (m === "wavy") { it.push(LH(MP([[-18, 2], [-10, -4], [-2, 2], [6, -4], [14, 2], [18, -2]]), 5.5)); }
    else if (m === "o") { const oo = O(mx, my + 2, 9 * mw, 12); it.push(LC(oo, 5)); it.push(FC(oo, INK, 0.75)); }
    else if (m === "grin") { const g = [[-24, -8], [0, -4], [24, -8], [18, 10], [0, 16], [-18, 10]]; it.push(FC(MP(g), WHITE, 0.9)); it.push(LC(MP(g), 5)); it.push(LH(MP([[-22, -6], [0, -2], [22, -6]]), W3, { over: 0 })); it.push(F(H(MP([[-18, 6], [0, 9], [18, 6], [14, 11], [0, 15], [-14, 11]]), true, { jit: 0.2 }), BLUSH, 0.8)); }
    // 9 덤: 홍조·땀·울적선·놀람선·숨·반짝
    if (E.blush) V.eyes.forEach((e) => { const bx = e.c[0] + (e.side < 0 ? -8 : 8) * (e.near ? 0.6 : 1), by = e.c[1] + 32; it.push(F(H(O(bx, by, e.prof ? 7 : 11, 6), true, { jit: 0 }), BLUSH, 0.45)); it.push(LH([[bx - 7, by + 3], [bx - 2, by + 6]], W3, { over: 0 })); it.push(LH([[bx + 1, by + 2], [bx + 6, by + 5]], W3, { over: 0 })); });
    const sweatAt = (x, y, k = 1) => { const d = [[x, y - 14 * k], [x + 7 * k, y - 2 * k], [x + 5 * k, y + 7 * k], [x, y + 9 * k], [x - 5 * k, y + 7 * k], [x - 7 * k, y - 2 * k]]; it.push(FC(d, SKY, 0.7)); it.push(LC(d, W3)); };
    if (E.sweat) { sweatAt(view === "side" ? 56 : 72, -36, 1.1); if (E.sweat > 1) sweatAt(view === "side" ? 66 : 80, -4, 0.8); }
    if (E.gloom) [[-8, -98], [10, -102], [28, -96]].forEach((p) => it.push(LH([[p[0], p[1]], [p[0] - 2, p[1] + 14]], W3)));
    if (E.rays) [[-70, -72], [-40, -96], [10, -106], [58, -92], [84, -62]].forEach((p) => it.push(LH([[p[0], p[1]], [p[0] * 1.18, p[1] * 1.2]], W2, { over: 0 })));
    if (E.puff) [[76, 44], [84, 56]].forEach((p, i) => it.push(LH([[p[0], p[1] - 6], [p[0] + 10 + i * 4, p[1]], [p[0] + 4, p[1] + 8]], W3, { jit: 0.4 })));
    if (E.sparkle) [[-92, -40, 1], [86, -58, 1.3], [-80, 20, 0.7]].forEach((p) => { const [x, y, k] = p; it.push(LH([[x, y - 12 * k], [x + 3 * k, y - 3 * k], [x + 12 * k, y], [x + 3 * k, y + 3 * k], [x, y + 12 * k], [x - 3 * k, y + 3 * k], [x - 12 * k, y], [x - 3 * k, y - 3 * k], [x, y - 12 * k]], W3, { jit: 0.2, over: 0 }, ORG)); });
    return { name: `face.${expr}.${view}`, box: [-110, -120, 110, 115], anchor: [0, 0], items: it, tilt: opt.tilt || 0 };
  }

  // =====================================================================
  // 상반신 포즈 4 — 얼굴 원점과 같은 좌표계(머리 (0,0)). back = 머리 뒤에, front = 머리 앞에
  // =====================================================================
  const torso = () => [[-24, 104], [-70, 118], [-120, 140], [-150, 190], [-160, 250], [-164, 330], [164, 330], [160, 250], [150, 190], [120, 140], [70, 118], [24, 104]];
  const collar = () => [LH([[-24, 100], [-6, 136], [-40, 128]], W2), LH([[24, 100], [6, 136], [40, 128]], W2), LH([[0, 136], [0, 328]], W3, { over: 0 }), dot(0, 180, 4), dot(0, 240, 4), dot(0, 300, 4)];
  const sleeveLines = () => [LH([[-120, 140], [-108, 220]], W3, { jit: 0.3 }), LH([[120, 140], [108, 220]], W3, { jit: 0.3 })];
  const neckItems = () => [LH([[-20, 86], [-22, 108]], W2, { over: 0 }), LH([[20, 86], [22, 108]], W2, { over: 0 }), F(H([[-22, 84], [22, 84], [24, 110], [-24, 110]], true, { jit: 0 }), SKIN, 0.55)];
  // 팔(소매) = 굵은 튜브 외곽을 점으로 직접 그린 것
  function arm(pts, w, z = 1) { // 중심선 점 → 양쪽 외곽선 닫힌 도형
    const Lp = [], Rp = [];
    for (let i = 0; i < pts.length; i++) {
      const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], n = Math.hypot(dx, dy) || 1, ww = w * (i === pts.length - 1 ? 0.85 : 1);
      Lp.push([pts[i][0] - dy / n * ww / 2, pts[i][1] + dx / n * ww / 2]); Rp.push([pts[i][0] + dy / n * ww / 2, pts[i][1] - dx / n * ww / 2]);
    }
    const poly = Lp.concat(Rp.reverse());
    return [FC(poly, SHIRT, 0.55, z), LC(poly, W1, { jit: 0.6 }, INK, z)];
  }
  function hand(cx, cy, r, z = 1, rot = 0) { // 주먹 비슷한 손: 손바닥 + 손가락 마디 2개
    const c = Math.cos(rot), s = Math.sin(rot), T = (p) => [cx + p[0] * c - p[1] * s, cy + p[0] * s + p[1] * c];
    const palm = [[-r, -r * 0.6], [-r * 0.4, -r * 1.05], [r * 0.5, -r * 1.0], [r * 1.05, -r * 0.3], [r * 0.95, r * 0.6], [r * 0.3, r * 1.05], [-r * 0.6, r * 0.9], [-r * 1.05, r * 0.2]].map(T);
    return [FC(palm, SKIN, 0.6, z), LC(palm, W2, { jit: 0.5 }, INK, z), LH([T([r * 0.1, -r * 0.3]), T([r * 0.55, -r * 0.1])], W3, {}, INK, z), LH([T([r * 0.1, r * 0.3]), T([r * 0.55, r * 0.45])], W3, {}, INK, z)];
  }
  function bust(pose) {
    const back = [], front = [];
    const body = torso();
    back.push(FC(body, SHIRT, 0.55, -1)); back.push(LH(body.slice(0, 7), W1, { jit: 0.8 }, INK, -1)); back.push(LH(body.slice(5, 12).reverse(), W1, { jit: 0.8 }, INK, -1));
    back.push(...collar().map((i) => ({ ...i, z: -1 }))); back.push(...sleeveLines().map((i) => ({ ...i, z: -1 })));
    back.push(...neckItems().map((i) => ({ ...i, z: -1 })));
    let head = { tilt: 0, dx: 0, dy: 0, look: [0, 0] };
    if (pose === "phone") { // 두 팔을 올려 가슴 앞에서 폰을 잡는다, 고개 숙임
      front.push(...arm([[-128, 150], [-150, 230], [-90, 262]], 46)); front.push(...arm([[128, 150], [150, 230], [96, 258]], 46));
      front.push(...hand(-62, 258, 22, 1, 0.3)); front.push(...hand(66, 252, 22, 1, -0.3));
      const ph = RR(-44, 178, 92, 150, 12); front.push(FC(ph, WHITE, 0.9, 2)); front.push(LC(ph, W1, { jit: 0.5 }, INK, 2)); front.push(LH([[-30, 196], [30, 196]], W3, {}, INK, 2)); front.push(LH([[-26, 220], [20, 220]], W3, {}, INK, 2)); front.push(LH([[-26, 240], [26, 240]], W3, {}, INK, 2));
      front.push(F(H(RR(-38, 186, 80, 110, 6), true, { jit: 0 }), SKY, 0.35, 2));
      head = { tilt: 6, dx: 0, dy: 8, look: [0, 1] };
    } else if (pose === "laptop") { // 팔을 아래로 내려 자판에, 노트북 뚜껑이 앞을 가린다
      front.push(...arm([[-126, 150], [-140, 215], [-110, 262]], 46)); front.push(...arm([[126, 150], [140, 215], [110, 262]], 46));
      const lid = RR(-190, 232, 380, 150, 10); front.push(FC(lid, GRAY, 0.5, 2)); front.push(LC(lid, W1, { jit: 0.6 }, INK, 2)); front.push(LH([[-174, 246], [174, 246], [176, 366], [-176, 366], [-174, 246]], W2, { jit: 0.4, over: 0 }, INK, 2));
      front.push(dot(0, 306, 7, INK, 2)); front.push(LH([[-210, 384], [210, 384]], W1, { jit: 0.5 }, INK, 2));
      head = { tilt: 0, dx: 0, dy: 4, look: [0, 0.6] };
    } else if (pose === "point") { // 오른팔(화면 오른쪽)을 뻗어 가리킨다
      front.push(...arm([[126, 148], [200, 150], [270, 140]], 46));
      front.push(...hand(296, 134, 22, 1, -0.2)); // 손바닥
      const fin = [[300, 116], [340, 110], [356, 112], [358, 120], [344, 124], [304, 128]]; front.push(FC(fin, SKIN, 0.6, 2)); front.push(LC(fin, W2, { jit: 0.4 }, INK, 2));
      head = { tilt: -4, dx: 0, dy: 0, look: [1, 0] };
    } else if (pose === "head") { // 두 손으로 머리를 감싼다(팔꿈치 밖으로)
      front.push(...arm([[-132, 150], [-190, 60], [-110, -20]], 46)); front.push(...arm([[132, 150], [190, 60], [110, -20]], 46));
      front.push(...hand(-84, -34, 24, 2, 1.1)); front.push(...hand(84, -34, 24, 2, -1.1));
      head = { tilt: 5, dx: 0, dy: 14, look: [0, 1] };
    }
    return { name: `bust.${pose}`, box: [-230, -60, 370, 400], anchor: [0, 0], back, front, head };
  }

  // 조립: 포즈 + 표정 + 각도 → 아이템 한 벌(순서: 몸 → 머리 → 앞팔)
  const rot = (items, deg, dx = 0, dy = 0) => {
    if (!deg && !dx && !dy) return items;
    const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    const tr = (d) => d.replace(/(-?\d+(?:\.\d+)?)\s(-?\d+(?:\.\d+)?)/g, (m, x, y) => { x = +x; y = +y; return f(x * c - y * s + dx) + " " + f(x * s + y * c + dy); });
    return items.map((i) => ({ ...i, d: tr(i.d) }));
  };
  function hero(o = {}) {
    const B = bust(o.pose || "phone"), Fc = face(o.expr || "hope", o.view || "front", { look: o.look || B.head.look });
    const headItems = rot(Fc.items, (o.tilt === undefined ? B.head.tilt : o.tilt), B.head.dx, B.head.dy);
    return { name: `hero.${o.pose || "phone"}.${o.expr || "hope"}.${o.view || "front"}`, box: B.box, anchor: [0, 0], ground: false, items: B.back.concat(headItems, B.front) };
  }

  // =====================================================================
  // 손 4 — 원점 = 손목 중심, 손가락은 위(point 는 오른쪽)
  // =====================================================================
  function handAsset(kind) {
    const it = [];
    const cuff = [[-34, 30], [34, 30], [36, 52], [-36, 52]]; it.push(FC(cuff, SHIRT, 0.55)); it.push(LC(cuff, W1, { jit: 0.5 }));
    if (kind === "press" || kind === "drag") { // 검지 펴고 나머지 접음, 엄지는 앞에 걸침
      const palm = [[-28, 30], [-33, 2], [-30, -14], [-24, -22], [-22, -56], [-16, -68], [-6, -66], [-2, -56], [-3, -20], [8, -26], [16, -16], [24, -22], [30, -12], [36, -6], [36, 10], [31, 30]];
      it.push(FC(palm, SKIN, 0.6)); it.push(LC(palm, W1, { jit: 0.7 }));
      it.push(LH([[-3, -18], [6, -8], [0, 4]], W2)); it.push(LH([[14, -14], [22, -2], [14, 8]], W2)); it.push(LH([[28, -10], [34, 2], [28, 12]], W3)); // 접힌 손가락 셋
      it.push(LH([[-28, -8], [-12, -2], [-14, 12], [-26, 14]], W2, { jit: 0.4 })); // 엄지
      it.push(LH([[-16, -58], [-12, -40]], W3, { over: 0 })); // 검지 마디
      if (kind === "press") { it.push(LH([[-34, -86], [-28, -78]], W2, { over: 0 })); it.push(LH([[-11, -94], [-11, -84]], W2, { over: 0 })); it.push(LH([[12, -86], [7, -78]], W2, { over: 0 })); }
      else { [[26, -72], [34, -66]].forEach((p, i) => it.push(LH([[p[0], p[1] - 20], [p[0] + 18 + i * 10, p[1] - 6], [p[0] + 18 + i * 10, p[1] + 10]], W2, { jit: 0.3, over: 0 }))); it.push(LH([[46, -40], [72, -40]], W2, {}, ORG)); it.push(LH([[64, -48], [74, -40], [64, -32]], W2, { over: 0 }, ORG)); }
    } else if (kind === "thumb") { // 엄지 척: 주먹 위로 엄지, 손가락 넷이 층층이
      const palm = [[-28, 30], [-34, 6], [-32, -14], [-26, -24], [-22, -48], [-16, -64], [-6, -68], [2, -60], [0, -28], [12, -28], [26, -24], [34, -14], [36, 2], [34, 16], [30, 30]];
      it.push(FC(palm, SKIN, 0.6)); it.push(LC(palm, W1, { jit: 0.7 }));
      [[-14, -14], [-12, -1], [-10, 12]].forEach((p, i) => it.push(LH([[p[0], p[1]], [p[0] + 14, p[1] - 4], [p[0] + 30, p[1] - 2], [p[0] + 44, p[1] + 2]], W2, { jit: 0.4 })));
      it.push(LH([[-22, -26], [-8, -30]], W3, { over: 0 })); it.push(LH([[-14, -56], [-10, -42]], W3, { over: 0 }));
      it.push(LH([[-20, -30], [-32, -42]], W2, { over: 0 }, ORG)); it.push(LH([[-6, -78], [-6, -92]], W2, { over: 0 }, ORG)); it.push(LH([[12, -64], [22, -76]], W2, { over: 0 }, ORG));
    } else if (kind === "point") { // 오른쪽을 가리킴: 검지 길게, 나머지 셋 말림
      const palm = [[-28, 30], [-32, -4], [-26, -28], [-8, -36], [14, -34], [56, -31], [66, -24], [62, -16], [22, -14], [28, -6], [30, 4], [26, 12], [28, 20], [22, 28], [2, 32], [-12, 30]];
      it.push(FC(palm, SKIN, 0.6)); it.push(LC(palm, W1, { jit: 0.7 }));
      it.push(LH([[22, -14], [14, -4], [22, 4]], W2)); it.push(LH([[26, 4], [18, 12], [26, 20]], W3)); it.push(LH([[8, -4], [10, 10]], W3, { over: 0 }));
      it.push(LH([[-20, -24], [-6, -20], [-10, -6], [-22, -8]], W2, { jit: 0.4 })); it.push(LH([[30, -30], [34, -16]], W3, { over: 0 }));
      it.push(LH([[82, -26], [106, -26]], W2, {}, ORG)); it.push(LH([[98, -34], [108, -26], [98, -18]], W2, { over: 0 }, ORG));
    }
    return { name: `hand.${kind}`, box: [-50, -100, 120, 60], anchor: [0, 0], items: it };
  }

  // =====================================================================
  // 소품 6 — 원점 = 바닥 중심, 접지 그림자 있음
  // =====================================================================
  function prop(kind) {
    const it = []; let box = [-120, -240, 120, 10], ground = true;
    if (kind === "phone") {
      const b = [[-54, -4], [-58, -200], [-50, -214], [50, -214], [58, -200], [54, -4], [44, 2], [-44, 2]];
      it.push(FC(b, INK, 0.9)); it.push(LC(b, W1, { jit: 0.6 }));
      const scr = RR(-46, -196, 92, 182, 6); it.push(FC(scr, WHITE, 0.95)); it.push(LC(scr, W2, { jit: 0.3 }));
      it.push(LH([[-14, -204], [14, -204]], W3, { over: 0 })); it.push(LH([[-30, -178], [30, -178]], W3)); it.push(LH([[-30, -150], [26, -150]], W3)); it.push(LH([[-30, -122], [30, -122]], W3)); it.push(LH([[-12, -10], [12, -10]], W3, { over: 0 }));
      it.push(F(H(RR(-36, -100, 72, 56, 5), true, { jit: 0 }), ORG, 0.55));
      box = [-70, -230, 70, 12];
    } else if (kind === "laptop") {
      const base = [[-170, 0], [-130, -40], [130, -40], [170, 0]]; const lid = [[-128, -42], [-112, -236], [128, -236], [140, -42]];
      it.push(FC(lid, GRAY, 0.55)); it.push(LC(lid, W1, { jit: 0.7 }));
      const scr = [[-114, -54], [-100, -222], [116, -222], [126, -54]]; it.push(FC(scr, WHITE, 0.9)); it.push(LC(scr, W2, { jit: 0.4 }));
      it.push(LH([[-76, -190], [60, -190]], W3)); it.push(LH([[-74, -160], [80, -160]], W3)); it.push(LH([[-72, -130], [50, -130]], W3)); it.push(F(H(RR(-50, -112, 110, 40, 4), true, { jit: 0 }), ORG, 0.55));
      it.push(FC(base, BEIGE, 0.55)); it.push(LC(base, W1, { jit: 0.7 }));
      for (let r = 0; r < 2; r++) for (let c = 0; c < 7; c++) it.push(LH([[-96 + c * 32 - r * 6, -30 + r * 12], [-80 + c * 32 - r * 6, -30 + r * 12]], W3, { over: 0 }));
      it.push(LH([[-30, -8], [30, -8]], W3, { over: 0 }));
      box = [-190, -250, 190, 12];
    } else if (kind === "clock") {
      it.push(LH([[0, -232], [0, -246]], W2, { over: 0 })); it.push(LC(O(0, -254, 7, 7), W3));
      const o = O(0, -120, 110, 108); it.push(FC(o, WHITE, 0.9)); it.push(LC(o, W1, { jit: 0.8 })); it.push(LC(O(0, -120, 96, 94), W3, { jit: 0.5 }));
      [[0, -210, 0, -194], [88, -120, 72, -120], [0, -30, 0, -46], [-88, -120, -72, -120]].forEach((t) => it.push(LH([[t[0], t[1]], [t[2], t[3]]], W2, { over: 0 })));
      for (let i = 0; i < 12; i++) if (i % 3) { const a = i / 12 * Math.PI * 2; it.push(LH([[Math.sin(a) * 90, -120 - Math.cos(a) * 88], [Math.sin(a) * 80, -120 - Math.cos(a) * 78]], W3, { over: 0 })); }
      it.push(LH([[0, -120], [-46, -162]], W1, { over: 0 })); it.push(LH([[0, -120], [60, -104]], W2, { over: 0 })); it.push(LH([[0, -120], [26, -190]], W3, { over: 0 }, ORG)); it.push(dot(0, -120, 6));
      it.push(LH([[-120, -10], [120, -10]], W2, { jit: 0.3 })); ground = false; box = [-130, -270, 130, 0];
    } else if (kind === "calendar") {
      const body = RR(-120, -200, 240, 200, 8); it.push(FC(body, WHITE, 0.9)); it.push(LC(body, W1, { jit: 0.8 }));
      const head = [[-120, -200], [120, -200], [120, -156], [-120, -156]]; it.push(FC(head, ORG, 0.65)); it.push(LH([[-120, -156], [120, -156]], W2));
      [-70, 70].forEach((x) => { it.push(LC(O(x, -200, 9, 9), W2)); it.push(LH([[x, -200], [x, -226]], W2, { over: 0 })); });
      for (let r = 0; r < 3; r++) for (let c = 0; c < 5; c++) it.push(LH([[-96 + c * 44, -130 + r * 44], [-76 + c * 44, -130 + r * 44]], W3, { over: 0 }));
      it.push(LC(O(-8, -86, 20, 18), 5, { jit: 1 }, ORG)); it.push(LH([[-120, -200], [-120, -224], [-96, -224]], W3, { over: 0 }));
      box = [-130, -236, 130, 10];
    } else if (kind === "bankbook") { // 펼친 통장: 가운데 접힘, 왼쪽 표지 초록, 오른쪽 거래 줄 + 도장
      const Lp = [[-200, -6], [-196, -150], [-8, -140], [-4, 0]], Rp = [[4, 0], [8, -140], [196, -150], [200, -6]];
      it.push(FC(Lp, GREEN, 0.5)); it.push(LC(Lp, W1, { jit: 0.7 })); it.push(FC(Rp, WHITE, 0.9)); it.push(LC(Rp, W1, { jit: 0.7 }));
      it.push(LH([[-150, -112], [-54, -108]], W2)); it.push(LH([[-150, -84], [-80, -82]], W3)); it.push(LH([[-150, -56], [-100, -54]], W3));
      for (let r = 0; r < 4; r++) it.push(LH([[26, -116 + r * 28], [176, -118 + r * 28]], W3, { over: 0 }));
      [[40, -124], [40, -96], [40, -68], [40, -40]].forEach((p, i) => it.push(LH([[p[0] + 96 - i * 10, p[1] + 10], [p[0] + 134, p[1] + 10]], W2, { over: 0 }, i === 3 ? ORG : INK)));
      it.push(LC(O(146, -40, 22, 22), W2, { jit: 0.9 }, "#D9534F")); it.push(LH([[136, -46], [156, -34]], W3, {}, "#D9534F"));
      box = [-210, -160, 210, 10];
    } else if (kind === "coin") {
      const o = O(0, -100, 98, 98); it.push(FC(o, YEL, 0.7)); it.push(LC(o, W1, { jit: 1 })); it.push(LC(O(0, -100, 78, 78), W3, { jit: 0.6 }));
      // ₩
      it.push(LH([[-44, -140], [-24, -62], [-2, -124], [22, -62], [44, -140]], W1, { jit: 0.4, over: 0 })); it.push(LH([[-50, -116], [50, -116]], W2, { over: 0 })); it.push(LH([[-50, -100], [50, -100]], W2, { over: 0 }));
      it.push(LH([[-60, -164], [-50, -150]], W3, { over: 0 }));
      box = [-110, -210, 110, 10];
    }
    return { name: `prop.${kind}`, box, anchor: [0, 0], ground, items: it };
  }

  // =====================================================================
  // 소품 추가 8 (ART_GATE_1, 아트 디렉터) — 장면이 직접 그리던 차·TV·폴더폰·편집앱·모니터·지구본을 자산으로.
  // 원점 = 바닥 중심, 접지 그림자 있음. 기존 소품 6개는 손대지 않았다.
  // =====================================================================
  const RED = "#D9534F", SILVER = "#D8DCE0", DARK = "#55514B";
  function propX(kind) {
    const it = []; let box = [-120, -240, 120, 10], ground = true;
    const wheel = (cx, cy, r) => { it.push(F(H(O(cx, cy, r, r), true, { jit: 0.4 }), DARK, 0.9)); it.push(LC(O(cx, cy, r, r), W1, { jit: 0.8 })); it.push(FC(O(cx, cy, r * 0.42, r * 0.42), SILVER, 0.95)); it.push(LC(O(cx, cy, r * 0.42, r * 0.42), W3, { jit: 0.5 })); };
    if (kind === "car_sedan") { // 아반떼 — 평범한 준중형 세단, 은회색. 폭 430
      const body = [[-206, -30], [-212, -62], [-196, -84], [-130, -92], [-96, -148], [-44, -160], [66, -160], [120, -110], [186, -96], [210, -78], [212, -48], [200, -30], [150, -30], [138, -14], [102, -14], [90, -30], [-92, -30], [-104, -14], [-140, -14], [-152, -30]];
      it.push(FC(body, SILVER, 0.75)); it.push(LC(body, W1, { jit: 0.8 }));
      const w1 = [[-86, -96], [-60, -144], [-6, -148], [-6, -96]], w2 = [[8, -148], [60, -148], [104, -104], [8, -96]];
      it.push(FC(w1, SKY, 0.6)); it.push(LC(w1, W2, { jit: 0.4 })); it.push(FC(w2, SKY, 0.6)); it.push(LC(w2, W2, { jit: 0.4 }));
      it.push(LH([[-6, -92], [-6, -36]], W2, { over: 0 })); it.push(LH([[-70, -70], [-30, -70]], W3, { over: 0 })); it.push(LH([[6, -70], [46, -70]], W3, { over: 0 })); // 문·손잡이
      it.push(LH([[-104, -120], [-116, -108], [-104, -102]], W2, { jit: 0.3 })); // 사이드미러
      it.push(F(H(O(-196, -70, 10, 8), true, { jit: 0 }), ORG, 0.85)); it.push(LC(O(-196, -70, 10, 8), W3)); it.push(F(H(O(200, -66, 9, 7), true, { jit: 0 }), RED, 0.8)); // 헤드·테일
      it.push(LH([[-214, -40], [-178, -40]], W2, { over: 0 })); // 범퍼
      wheel(-120, -26, 40); wheel(124, -26, 40);
      box = [-225, -175, 225, 16];
    } else if (kind === "car_sport") { // 포르쉐 — 낮고 넓은 쿠페, 빨강, 뒤 스포일러, 속도선. 폭 520
      const body = [[-256, -26], [-266, -50], [-250, -72], [-150, -84], [-80, -132], [-10, -148], [90, -146], [160, -112], [230, -92], [262, -74], [264, -48], [250, -26], [196, -26], [182, -10], [134, -10], [120, -26], [-108, -26], [-122, -10], [-170, -10], [-184, -26]];
      it.push(FC(body, RED, 0.6)); it.push(LC(body, W1, { jit: 0.8 }));
      const win = [[-70, -90], [-30, -126], [70, -126], [130, -96]]; it.push(FC(win, SKY, 0.6)); it.push(LC(win, W2, { jit: 0.4 }));
      it.push(LH([[-26, -124], [-26, -90]], W3, { over: 0 }));
      it.push(LH([[210, -96], [236, -118], [268, -118]], W2, { jit: 0.3 })); it.push(LH([[236, -118], [236, -92]], W3, { over: 0 })); // 스포일러
      it.push(LH([[-96, -108], [-112, -100], [-98, -92]], W2, { jit: 0.3 })); // 미러
      it.push(F(H(O(-246, -62, 12, 9), true, { jit: 0 }), ORG, 0.9)); it.push(LC(O(-246, -62, 12, 9), W3)); it.push(F(H(O(250, -60, 10, 7), true, { jit: 0 }), RED, 1));
      it.push(LH([[-150, -60], [-40, -60]], W3, { over: 0 })); it.push(LH([[-10, -62], [36, -62]], W3, { over: 0 }));
      wheel(-150, -24, 42); wheel(166, -24, 46);
      [[-330, -110], [-350, -80], [-330, -50]].forEach((p, i) => it.push(LH([[p[0], p[1]], [p[0] - 60 + i * 10, p[1]]], W2, { over: 0 }))); // 속도선
      box = [-420, -160, 280, 16];
    } else if (kind === "tv_crt" || kind === "tv_color") { // 브라운관 TV — 토끼귀 안테나, 다이얼 2, 다리 2. tv_color 는 화면에 컬러 띠
      const color = kind === "tv_color";
      it.push(LH([[-20, -280], [-96, -400]], W2, { jit: 0.3 })); it.push(LH([[-20, -280], [70, -404]], W2, { jit: 0.3 })); it.push(LC(O(-20, -282, 12, 12), W2)); // 안테나
      [[-110, -16], [110, -16]].forEach((p) => it.push(LH([[p[0], p[1] - 10], [p[0] + (p[0] < 0 ? -10 : 10), 0]], W1, { over: 0 }))); // 다리
      const body = RR(-190, -276, 380, 258, 22); it.push(FC(body, color ? BEIGE : GRAY, 0.75)); it.push(LC(body, W1, { jit: 0.8 }));
      const scr = [[-168, -250], [-176, -148], [-168, -46], [86, -40], [98, -148], [86, -254]]; // 볼록한 화면
      it.push(FC(scr, color ? WHITE : DARK, color ? 0.9 : 0.55)); it.push(LC(scr, W2, { jit: 0.6 }));
      if (color) { const cols = [RED, ORG, YEL, GREEN, SKY, LIL]; cols.forEach((c, i) => { const x0 = -160 + i * 41; it.push(F(H([[x0, -236], [x0 + 38, -236], [x0 + 38, -56], [x0, -56]], true, { jit: 0.4 }), c, 0.7)); }); }
      else { it.push(LH([[-150, -200], [-20, -110], [40, -190], [70, -140]], W2, { jit: 0.5 }, WHITE)); it.push(LH([[-150, -120], [70, -120]], W3, { jit: 0.2 }, WHITE)); } // 흑백 파형
      [[-152, -230], [-146, -214]].forEach((p) => it.push(LH([[p[0], p[1]], [p[0] + 16, p[1] - 10]], W3, { over: 0 }, WHITE))); // 반사광
      [[150, -210], [150, -140]].forEach((p) => { it.push(FC(O(p[0], p[1], 22, 22), WHITE, 0.9)); it.push(LC(O(p[0], p[1], 22, 22), W2, { jit: 0.6 })); it.push(LH([[p[0], p[1]], [p[0] + 12, p[1] - 12]], W3, { over: 0 })); }); // 다이얼
      for (let r = 0; r < 4; r++) it.push(LH([[126, -92 + r * 12], [174, -92 + r * 12]], W3, { over: 0 })); // 스피커 줄
      box = [-200, -410, 200, 16];
    } else if (kind === "flipphone") { // 2G 폴더폰 — 열어 세운 상태, 윗몸 작은 화면, 경첩, 아랫몸 3×4 키패드, 짧은 안테나. 높이 400
      it.push(LH([[52, -344], [52, -392]], W1, { over: 0 })); it.push(FC(O(52, -396, 8, 8), DARK, 0.9)); // 안테나
      const top = RR(-66, -350, 132, 176, 18); it.push(FC(top, SILVER, 0.85)); it.push(LC(top, W1, { jit: 0.7 }));
      const scr = RR(-46, -326, 92, 112, 6); it.push(FC(scr, "#CFE2B8", 0.9)); it.push(LC(scr, W2, { jit: 0.3 })); // 녹색빛 작은 화면
      it.push(LH([[-30, -300], [24, -300]], W3, { over: 0 })); it.push(LH([[-30, -278], [14, -278]], W3, { over: 0 })); it.push(LH([[-30, -256], [20, -256]], W3, { over: 0 }));
      it.push(LC(O(0, -196, 8, 8), W3)); // 스피커
      const hinge = RR(-72, -176, 144, 22, 10); it.push(FC(hinge, DARK, 0.6)); it.push(LC(hinge, W2, { jit: 0.4 }));
      const bot = RR(-66, -156, 132, 154, 14); it.push(FC(bot, SILVER, 0.85)); it.push(LC(bot, W1, { jit: 0.7 }));
      it.push(LC(RR(-22, -146, 44, 26, 6), W2, { jit: 0.3 })); // 방향키
      for (let r = 0; r < 4; r++) for (let c = 0; c < 3; c++) { const x = -34 + c * 34, y = -104 + r * 22; it.push(FC(RR(x - 13, y - 7, 26, 14, 5), WHITE, 0.9)); it.push(LC(RR(x - 13, y - 7, 26, 14, 5), W3, { jit: 0.3 })); }
      box = [-80, -410, 80, 12];
    } else if (kind === "app_edit") { // 편집 앱 아이콘(캡컷 자리) — 검정 둥근 사각 + 흰 가위 + 필름 조각. 이름표는 장면에서 text("캡컷")
      const sq = RR(-104, -222, 208, 208, 36).flatMap((q, i, P) => { const n = P[(i + 1) % P.length]; return Math.hypot(n[0] - q[0], n[1] - q[1]) > 80 ? [q, [(q[0] + n[0]) / 2, (q[1] + n[1]) / 2]] : [q]; }); it.push(FC(sq, INK, 0.92)); it.push(LC(sq, W1, { jit: 0.6 }));
      const strip = [[-40, -62], [78, -178], [100, -156], [-18, -40]]; it.push(FC(strip, WHITE, 0.25)); it.push(LC(strip, W3, { jit: 0.3 }, WHITE));
      [[-32, -70], [-10, -92], [12, -114], [34, -136], [56, -158]].forEach((p) => it.push(F(H(O(p[0] + 4, p[1] - 4, 5, 5, 0), true, { jit: 0 }), WHITE, 0.9)));
      // 가위: 축 (-4,-120) 에서 날 두 개가 오른쪽 위·오른쪽 아래로, 손잡이 고리는 왼쪽
      it.push(LH([[-6, -120], [74, -196]], 9, { over: 0 }, WHITE)); it.push(LH([[-6, -120], [74, -44]], 9, { over: 0 }, WHITE));
      it.push(LC(O(-44, -88, 24, 18), 7, { jit: 0.6 }, WHITE)); it.push(LC(O(-44, -152, 24, 18), 7, { jit: 0.6 }, WHITE));
      it.push(FC(O(-4, -120, 8, 8), WHITE, 1));
      box = [-116, -234, 116, 12];
    } else if (kind === "monitor") { // 데스크톱 모니터 — 화면 440×280, 창 위 점 3개, 받침. 화면 내용은 장면이 올린다
      it.push(F(H([[-100, -2], [100, -2], [60, -16], [-60, -16]], true, { jit: 0.3 }), GRAY, 0.6)); it.push(LC([[-100, -2], [100, -2], [60, -16], [-60, -16]], W1, { jit: 0.4 }));
      it.push(FC(RR(-26, -74, 52, 60, 6), GRAY, 0.6)); it.push(LC(RR(-26, -74, 52, 60, 6), W2, { jit: 0.4 })); // 목
      const mid = (P) => P.flatMap((q, i) => { const n = P[(i + 1) % P.length]; return Math.hypot(n[0] - q[0], n[1] - q[1]) > 80 ? [q, [(q[0] + n[0]) / 2, (q[1] + n[1]) / 2]] : [q]; }); const bez = mid(RR(-230, -362, 460, 292, 30)); it.push(FC(bez, GRAY, 0.55)); it.push(LC(bez, W1, { jit: 0.8 }));
      const scr = mid(RR(-212, -344, 424, 254, 18)); it.push(FC(scr, WHITE, 0.92)); it.push(LC(scr, W2, { jit: 0.3 }));
      it.push(LH([[-212, -306], [212, -306]], W3, { over: 0 })); [-196, -178, -160].forEach((x) => it.push(dot(x, -325, 5)));
      it.push(LH([[-192, -270], [-70, -270]], W3)); it.push(LH([[-192, -236], [-110, -236]], W3)); it.push(F(H(RR(-192, -210, 150, 96, 6), true, { jit: 0 }), SKY, 0.5)); it.push(LH([[-150, -186], [-150, -138], [-110, -162]], W2, { over: 0 }, ORG));
      box = [-240, -372, 240, 12];
    } else if (kind === "globe") { // 지구본 — 구 r128, 경위선, 초록 대륙 3, 반원 지지대 + 받침
      it.push(FC([[-70, -4], [70, -4], [48, -20], [-48, -20]], DARK, 0.7)); it.push(LC([[-70, -4], [70, -4], [48, -20], [-48, -20]], W1, { jit: 0.5 }));
      it.push(LH([[0, -20], [0, -40]], W1, { over: 0 }));
      const arc = []; for (let i = 0; i <= 12; i++) { const a = Math.PI * 0.5 + i / 12 * Math.PI * 1.15; arc.push([Math.cos(a) * 146, -176 + Math.sin(a) * 146]); }
      it.push(LH(arc, W1, { jit: 0.5 })); // 지지대: 아래에서 왼쪽을 돌아 위 오른쪽까지 감싸는 반원
      const sph = O(0, -176, 128, 128); it.push(FC(sph, SKY, 0.6)); it.push(LC(sph, W1, { jit: 0.9 }));
      [-80, 0, 80].forEach((x) => it.push(LH([[x * 0.55, -300], [x * 1.1, -176], [x * 0.55, -52]], W3, { jit: 0.3 })));
      it.push(LH([[-124, -214], [124, -214]], W3, { jit: 0.4 })); it.push(LH([[-128, -176], [128, -176]], W3, { jit: 0.4 })); it.push(LH([[-124, -138], [124, -138]], W3, { jit: 0.4 }));
      const land = [[[-88, -232], [-48, -256], [-20, -230], [-40, -200], [-70, -196]], [[10, -246], [60, -250], [86, -220], [54, -190], [20, -206]], [[-30, -140], [20, -150], [40, -110], [0, -80], [-36, -104]]];
      land.forEach((p) => { it.push(FC(p, GREEN, 0.8)); it.push(LC(p, W3, { jit: 1 })); });
      it.push(LH([[-90, -270], [-110, -240]], W3, { over: 0 }, WHITE));
      box = [-160, -320, 160, 12];
    }
    return { name: `prop.${kind}`, box, anchor: [0, 0], ground, items: it };
  }
  const PROPS2 = ["car_sedan", "car_sport", "tv_crt", "tv_color", "flipphone", "app_edit", "monitor", "globe"];

  // =====================================================================
  // 직급 3 — 로봇(AI 워커). 라이브 56:30 비유: 하이쿠=사원·대리 / 소넷=과장 / 오푸스·페이블=부장·사장
  // 한눈에 서열: 키 220 → 290 → 370, 머리 모양(돔→상자→넓은 상자), 눈(점→둥근→안경), 장식(명찰→넥타이→넥타이+수염+배지+안테나 2)
  // =====================================================================
  function rank(kind) {
    const it = []; let box;
    const eyesOk = (y, dx, r) => { it.push(LC(O(-dx, y, r, r), W2)); it.push(dot(-dx + r * 0.25, y, r * 0.42)); it.push(LC(O(dx, y, r, r), W2)); it.push(dot(dx + r * 0.25, y, r * 0.42)); };
    if (kind === "staff") { // 사원 — 작고 둥근 돔 머리, 점 눈, 명찰
      const body = RR(-52, -120, 104, 118, 16); it.push(FC(body, GRAY, 0.5)); it.push(LC(body, W1, { jit: 0.7 }));
      const head = [[-46, -124], [-44, -170], [-24, -196], [0, -202], [24, -196], [44, -170], [46, -124]]; it.push(FC(head, GRAY, 0.5)); it.push(LC(head, W1, { jit: 0.8 }));
      it.push(LH([[0, -204], [0, -222]], W2, { over: 0 })); it.push(dot(0, -228, 6));
      it.push(dot(-16, -158, 5)); it.push(dot(16, -158, 5)); it.push(LH([[-10, -142], [0, -136], [10, -142]], W2));
      const tag = RR(-30, -100, 40, 26, 3); it.push(FC(tag, WHITE, 0.9)); it.push(LC(tag, W3)); it.push(LH([[-22, -88], [2, -88]], W3, { over: 0 }));
      [[-52, -100, -72, -40], [52, -100, 72, -40]].forEach((a) => { it.push(...arm([[a[0], a[1]], [a[2], a[3]]], 22)); it.push(LC(O(a[2], a[3] + 10, 11, 11), W2)); });
      [[-30, 0], [30, 0]].forEach((p) => it.push(LC(RR(p[0] - 20, -8, 40, 14, 5), W2)));
      box = [-80, -240, 80, 10];
    } else if (kind === "manager") { // 과장 — 상자 머리, 둥근 눈, 넥타이, 서류
      const body = RR(-66, -160, 132, 158, 18); it.push(FC(body, SKY, 0.5)); it.push(LC(body, W1, { jit: 0.7 }));
      const head = RR(-58, -278, 116, 108, 22); it.push(FC(head, SKY, 0.5)); it.push(LC(head, W1, { jit: 0.8 }));
      it.push(LH([[0, -280], [0, -300]], W2, { over: 0 })); it.push(dot(0, -306, 7));
      it.push(LH([[-66, -246], [-70, -210]], W2, { over: 0 })); it.push(LH([[66, -246], [70, -210]], W2, { over: 0 }));
      eyesOk(-228, 22, 11); it.push(LH([[-14, -196], [0, -190], [14, -196]], 5));
      const tie = [[-10, -156], [10, -156], [16, -140], [4, -72], [-4, -72], [-16, -140]]; it.push(FC(tie, "#D9534F", 0.6)); it.push(LC(tie, W2, { jit: 0.4 }));
      it.push(LH([[-20, -160], [-10, -156]], W2, { over: 0 })); it.push(LH([[20, -160], [10, -156]], W2, { over: 0 }));
      it.push(...arm([[-66, -130], [-94, -70], [-70, -40]], 26)); it.push(...arm([[66, -130], [96, -72], [74, -40]], 26));
      const doc = RR(50, -62, 60, 44, 4); it.push(FC(doc, WHITE, 0.95, 2)); it.push(LC(doc, W2, {}, INK, 2)); it.push(LH([[60, -48], [98, -48]], W3, {}, INK, 2)); it.push(LH([[60, -34], [90, -34]], W3, {}, INK, 2));
      it.push(LC(O(-70, -30, 12, 12), W2));
      [[-36, 0], [36, 0]].forEach((p) => it.push(LC(RR(p[0] - 24, -10, 48, 16, 6), W2)));
      box = [-110, -320, 120, 10];
    } else { // 부장 — 크고 넓은 머리, 안경, 수염, 안테나 2, 넥타이+배지
      const body = RR(-84, -200, 168, 198, 20); it.push(FC(body, LIL, 0.5)); it.push(LC(body, W1, { jit: 0.7 }));
      const head = RR(-74, -352, 148, 142, 24); it.push(FC(head, LIL, 0.5)); it.push(LC(head, W1, { jit: 0.8 }));
      [[-40, -354, -46, -382], [40, -354, 46, -382]].forEach((a) => { it.push(LH([[a[0], a[1]], [a[2], a[3]]], W2, { over: 0 })); it.push(dot(a[2], a[3] - 7, 8)); });
      it.push(LH([[-84, -320], [-88, -268]], W2, { over: 0 })); it.push(LH([[84, -320], [88, -268]], W2, { over: 0 }));
      // 안경(사각 뿔테) + 눈
      [-30, 30].forEach((dx) => { const g = RR(dx - 26, -310, 52, 42, 8); it.push(FC(g, WHITE, 0.5)); it.push(LC(g, 5, { jit: 0.5 })); it.push(dot(dx + 4, -288, 6)); });
      it.push(LH([[-4, -292], [4, -292]], 5, { over: 0 })); it.push(LH([[-56, -292], [-74, -296]], W2, { over: 0 })); it.push(LH([[56, -292], [74, -296]], W2, { over: 0 }));
      it.push(LH([[-54, -328], [-30, -334], [-8, -328]], 5)); it.push(LH([[8, -328], [30, -334], [54, -328]], 5)); // 굵은 눈썹
      it.push(LH([[-28, -246], [-14, -254], [0, -250], [14, -254], [28, -246]], 5)); // 콧수염
      it.push(LH([[-16, -228], [0, -222], [16, -228]], 5));
      const tie = [[-12, -196], [12, -196], [20, -176], [6, -96], [-6, -96], [-20, -176]]; it.push(FC(tie, ORG, 0.7)); it.push(LC(tie, W2, { jit: 0.4 }));
      it.push(LH([[-26, -200], [-12, -196]], W2, { over: 0 })); it.push(LH([[26, -200], [12, -196]], W2, { over: 0 }));
      const badge = O(-56, -166, 14, 14); it.push(FC(badge, ORG, 0.8)); it.push(LC(badge, W3)); it.push(LH([[-56, -176], [-53, -168], [-45, -167], [-51, -162], [-49, -154], [-56, -158], [-63, -154], [-61, -162], [-67, -167], [-59, -168], [-56, -176]], W3, { jit: 0.2, over: 0 }));
      it.push(...arm([[-84, -160], [-124, -110], [-70, -100]], 30)); it.push(...arm([[84, -160], [124, -110], [70, -100]], 30)); // 팔짱
      it.push(LC(O(-64, -104, 14, 14), W2)); it.push(LC(O(64, -104, 14, 14), W2));
      [[-44, 0], [44, 0]].forEach((p) => it.push(LC(RR(p[0] - 30, -12, 60, 18, 7), W2)));
      box = [-140, -400, 140, 10];
    }
    return { name: `rank.${kind}`, box, anchor: [0, 0], ground: true, items: it };
  }

  // =====================================================================
  // 목록 · 내보내기
  // =====================================================================
  const EXPRS = Object.keys(EXPR), VIEWS = ["front", "tq", "side"], POSES = ["phone", "laptop", "point", "head"], HANDS = ["press", "drag", "thumb", "point"], PROPS = ["phone", "laptop", "clock", "calendar", "bankbook", "coin"], RANKS = ["staff", "manager", "director"];
  const RANK_LABEL = { staff: "사원(대리) · 하이쿠", manager: "과장 · 소넷", director: "부장(사장) · 오푸스·페이블" };
  function get(name, o) {
    const p = name.split(".");
    if (p[0] === "face") return face(p[1], p[2], o);
    if (p[0] === "bust") return hero({ pose: p[1], expr: p[2] || "hope", view: p[3] || "front", ...o });
    if (p[0] === "hero") return hero(o);
    if (p[0] === "hand") return handAsset(p[1]);
    if (p[0] === "prop") return PROPS2.includes(p[1]) ? propX(p[1]) : prop(p[1]);
    if (p[0] === "rank") return rank(p[1]);
    throw new Error("unknown asset " + name);
  }
  function list() {
    const n = [];
    EXPRS.forEach((e) => VIEWS.forEach((v) => n.push(`face.${e}.${v}`)));
    POSES.forEach((p) => n.push(`bust.${p}`)); HANDS.forEach((h) => n.push(`hand.${h}`)); PROPS.forEach((p) => n.push(`prop.${p}`)); PROPS2.forEach((p) => n.push(`prop.${p}`)); RANKS.forEach((r) => n.push(`rank.${r}`));
    return n;
  }
  // 정적 SVG 문자열 (검수·썸네일·CapCut 용) — paper:true 면 종이결 필터, shadow 는 ground 자산에 자동
  function toSVG(asset, o = {}) {
    const A = typeof asset === "string" ? get(asset, o) : asset, sc = o.sc || 1, pad = o.pad === undefined ? 16 : o.pad;
    const [x0, y0, x1, y1] = A.box, w = (x1 - x0 + pad * 2) * sc, h = (y1 - y0 + pad * 2) * sc;
    let s = `<svg xmlns="http://www.w3.org/2000/svg" width="${f(w)}" height="${f(h)}" viewBox="${f(x0 - pad)} ${f(y0 - pad)} ${f(x1 - x0 + pad * 2)} ${f(y1 - y0 + pad * 2)}">`;
    if (o.bg !== false) s += `<rect x="${f(x0 - pad)}" y="${f(y0 - pad)}" width="${f(x1 - x0 + pad * 2)}" height="${f(y1 - y0 + pad * 2)}" fill="#FBF8F1"/>`;
    if (A.ground) { const gw = (x1 - x0) * 0.9; s += `<ellipse cx="${f((x0 + x1) / 2)}" cy="4" rx="${f(gw / 2)}" ry="12" fill="${INK}" opacity="0.1"/>`; }
    A.items.slice().sort((a, b) => (a.z || 0) - (b.z || 0)).forEach((i) => {
      if (i.k === "fill") s += `<path d="${i.d}" fill="${i.c}" opacity="${i.op}" stroke="none"/>`;
      else s += `<path d="${i.d}" fill="none" stroke="${i.c}" stroke-width="${i.w}" stroke-linecap="round" stroke-linejoin="round"/>`;
    });
    if (o.paper) s += `<filter id="pg"><feTurbulence baseFrequency="0.9" numOctaves="2" seed="3"/><feColorMatrix values="0 0 0 0 0.45 0 0 0 0 0.4 0 0 0 0 0.3 0 0 0 0.16 0"/></filter><rect x="${f(x0 - pad)}" y="${f(y0 - pad)}" width="${f(x1 - x0 + pad * 2)}" height="${f(y1 - y0 + pad * 2)}" filter="url(#pg)" style="mix-blend-mode:multiply"/>`;
    return s + "</svg>";
  }
  // hq.js 레이어에 펜 순서대로 얹기. L = Layer(line/fill 있음). 반환: 마지막 선 끝 시각
  function draw(L, asset, o = {}) {
    const A = typeof asset === "string" ? get(asset, o) : asset, x = o.x || 0, y = o.y || 0, sc = o.sc || 1, s = o.s || 0, per = o.per || 0.12, pen = o.pen !== false;
    const tr = (d) => d.replace(/(-?\d+(?:\.\d+)?)\s(-?\d+(?:\.\d+)?)/g, (m, px, py) => f(x + (+px) * sc) + " " + f(y + (+py) * sc));
    const items = A.items.slice().sort((a, b) => (a.z || 0) - (b.z || 0));
    if (A.ground && L.fill) { const [x0, , x1] = A.box, gw = (x1 - x0) * 0.9 * sc, cx = x + (x0 + x1) / 2 * sc; const pts = []; for (let i = 0; i < 12; i++) { const a = i / 12 * Math.PI * 2; pts.push([cx + gw / 2 * Math.cos(a), y + 4 * sc + 12 * Math.sin(a)]); } L.fill(H(pts, true, { jit: 0 }), INK, s, 0.1, 0.3); }
    let t = s, n = 0;
    items.forEach((i) => {
      if (i.k === "fill") L.fill(tr(i.d), i.c, t + 0.25, i.op, 0.35);
      else { const big = i.w >= W1 - 0.5, dur = big ? per * 2.2 : per; L.line(tr(i.d), t, dur, { w: i.w * sc, c: i.c === INK ? undefined : i.c, pen: pen && big }); t += dur * (big ? 1 : 0.5); n++; }
    });
    return { end: t, n };
  }

  root.INKASSETS = { get, list, toSVG, draw, hero, face, bust, hand: handAsset, prop, propX, rank, EXPRS, VIEWS, POSES, HANDS, PROPS, PROPS2, RANKS, RANK_LABEL, COLORS: { INK, ORG, SKIN, HAIR, SHIRT, BLUSH, SKY, LIL, GRAY, YEL, GREEN, BEIGE }, W1, W2, W3, H, O, RR };
})(typeof window !== "undefined" ? window : globalThis);
