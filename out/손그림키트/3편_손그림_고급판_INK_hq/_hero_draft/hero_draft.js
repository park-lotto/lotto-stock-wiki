/* 숏클 새 주인공 시안 (2026-10-29) — 사장님 고르기용. _assets 는 건드리지 않고 INKASSETS 의 손맛 함수(H·O·RR)만 빌려 쓴다.
 * 좌표 문법은 기존과 같다: (0,0)=두 눈 사이, 머리 폭≈140, 상반신 밑 y=330, box 동일 → 고르면 그대로 face/bust API 에 꽂힌다.
 * 시안: A = 단정·현실적(30대 직장인·주부)  /  B = 귀엽고 둥근(머리 크고 눈 큼)
 */
(function (root) {
  const K = root.INKASSETS, { H, O, RR, W1, W2, W3 } = K, C = K.COLORS;
  const INK = C.INK, SKIN = C.SKIN, BLUSH = C.BLUSH, WHITE = "#FFFFFF", SKY = C.SKY;
  const f = (n) => (Math.round(n * 10) / 10).toString();
  const M = (pts) => pts.map((p) => [-p[0], p[1]]);
  const L = (d, w = W1, c = INK, z = 0) => ({ k: "line", d, w, c, z });
  const F = (d, c, op = 0.55, z = 0) => ({ k: "fill", d, c, op, z });
  const LH = (pts, w, o, c, z) => L(H(pts, false, o), w, c, z);
  const LC = (pts, w, o, c, z) => L(H(pts, true, o), w, c, z);
  const FC = (pts, c, op, z) => F(H(pts, true, { jit: 0.3 }), c, op, z);
  const dot = (x, y, r, c = INK, z = 0) => F(H(O(x, y, r, r, 0), true, { jit: 0 }), c, 1, z);

  // ---------- 캐릭터 정의 ----------
  const CH = {
    // A안 남: 30대 직장인. 짙은 갈색 짧은 머리(옆가르마), 안경 없음, 턱이 살아 있는 계란형, 네이비 니트
    mA: {
      hair: "#4A3B33", shirt: "#4F6B8F", sex: "m", round: 0,
      head: [[0, -78], [36, -74], [60, -54], [68, -24], [68, 8], [62, 38], [50, 60], [30, 76], [4, 82], [-24, 78], [-46, 62], [-60, 38], [-67, 8], [-68, -24], [-60, -54], [-36, -74]],
      hairFront: [[-70, -22], [-66, -52], [-50, -76], [-24, -90], [6, -94], [36, -90], [58, -76], [70, -50], [72, -22], [62, -30], [54, -46], [40, -58], [20, -62], [-2, -52], [-18, -44], [-34, -40], [-48, -36], [-60, -30]],
      hairTex: [[[8, -62], [22, -74]], [[-12, -50], [-2, -62]]],
      ears: true, eyeR: 1, nose: "line", lash: false,
    },
    // A안 여: 30대 주부·직장인. 어깨 단발(갈색), 앞머리 옆으로, 작은 귀걸이, 살구 블라우스
    fA: {
      hair: "#5A3F38", shirt: "#F0B59A", sex: "f", round: 0,
      head: [[0, -78], [34, -74], [58, -54], [66, -24], [66, 8], [60, 36], [46, 58], [26, 76], [2, 82], [-22, 78], [-44, 60], [-58, 36], [-65, 8], [-66, -24], [-58, -54], [-34, -74]],
      hairBack: [[-74, -30], [-82, 20], [-88, 70], [-86, 108], [-72, 118], [-40, 112], [0, 110], [40, 112], [72, 118], [86, 108], [88, 70], [82, 20], [74, -30], [40, -80], [0, -92], [-40, -80]],
      hairFront: [[-72, -20], [-68, -54], [-50, -78], [-22, -92], [8, -96], [38, -92], [60, -78], [72, -50], [74, -18], [66, -24], [60, -48], [46, -62], [30, -70], [14, -60], [0, -46], [-14, -36], [-30, -30], [-48, -30], [-62, -22]],
      hairTex: [[[22, -78], [34, -84]], [[-40, -40], [-30, -50]]],
      ears: false, earring: true, eyeR: 1, nose: "dot", lash: true,
    },
    // B안 남: 머리 크고 둥글, 뽀글 앞머리, 눈 크고 반짝, 하늘색 후드
    mB: {
      hair: "#3F3634", shirt: "#8EC3E6", sex: "m", round: 1,
      head: [[0, -84], [40, -80], [66, -58], [76, -26], [76, 10], [70, 42], [56, 66], [32, 82], [2, 88], [-28, 84], [-54, 66], [-70, 42], [-76, 10], [-76, -26], [-66, -58], [-40, -80]],
      hairFront: [[-80, -20], [-76, -54], [-58, -84], [-28, -100], [4, -104], [36, -100], [62, -84], [78, -54], [80, -20], [70, -34], [62, -46], [48, -40], [38, -56], [22, -46], [10, -62], [-6, -48], [-18, -62], [-32, -46], [-44, -58], [-56, -42], [-70, -40]],
      hairTex: [[[-10, -82], [0, -90], [10, -82]]],
      ears: true, eyeR: 1.35, nose: "dot", lash: false, hood: true,
    },
    // B안 여: 둥근 얼굴, 높이 묶은 머리(밝은 갈색) + 머리끈, 큰 눈, 노란 카디건
    fB: {
      hair: "#7A5542", shirt: "#F2D27A", sex: "f", round: 1,
      head: [[0, -84], [38, -80], [64, -58], [74, -26], [74, 10], [68, 42], [54, 66], [30, 82], [2, 88], [-26, 84], [-52, 66], [-68, 42], [-74, 10], [-74, -26], [-64, -58], [-38, -80]],
      hairBack: [[30, -100], [46, -124], [72, -134], [98, -124], [108, -98], [100, -72], [80, -60], [60, -66], [48, -84]],
      hairFront: [[-78, -14], [-76, -54], [-58, -84], [-28, -100], [4, -104], [36, -100], [62, -84], [76, -54], [78, -14], [70, -28], [64, -50], [50, -64], [36, -72], [22, -62], [8, -50], [-10, -52], [-26, -62], [-42, -50], [-56, -40], [-68, -26]],
      hairTex: [[[64, -72], [76, -86]], [[-14, -78], [-2, -86]]],
      ears: false, earring: false, eyeR: 1.35, nose: "dot", lash: true, tie: [52, -80],
    },
  };
  const EXPR = {
    hope:  { brow: [[-16, -32], [0, -37], [16, -33]], eye: "open", mouth: "smileOpen", blush: true },
    tired: { brow: [[-16, -24], [0, -23], [16, -20]], eye: "half", mouth: "down", bags: true },
  };

  function face(who, expr, opt = {}) {
    const P = CH[who], E = EXPR[expr] || EXPR.hope, look = opt.look || [0, 0], it = [];
    const rnd = P.round;
    // 0 뒷머리(머리 뒤)
    if (P.hairBack) { it.push(F(H(P.hairBack, true, { jit: 0.4 }), P.hair, 0.75, -1)); it.push(LC(P.hairBack, W1, { jit: 0.8 }, INK, -1)); }
    if (P.tie) { const [tx, ty] = P.tie; it.push(LC(O(tx, ty, 9, 7), W2, {}, INK, -1)); it.push(F(H(O(tx, ty, 9, 7), true, { jit: 0 }), C.ORG, 0.9, -1)); }
    // 1 머리 윤곽 + 피부 + 귀
    if (P.hairBack) it.push(F(H(P.head, true, { jit: 0.3 }), WHITE, 1));
    it.push(LC(P.head, W1, { jit: 0.9 })); it.push(FC(P.head, SKIN, 0.55));
    if (P.ears) { const e = [[64, 0], [74, 2], [76, 14], [70, 26], [62, 24]]; [e, M(e)].forEach((q) => { it.push(FC(q, SKIN, 0.55)); it.push(LH(q, W2)); }); it.push(LH([[70, 8], [68, 16]], W3)); it.push(LH([[-70, 8], [-68, 16]], W3)); }
    if (P.earring) { [[-64, 44], [64, 44]].forEach((q) => it.push(dot(q[0], q[1], 3.5, C.ORG))); }
    // 2 앞머리
    it.push(F(H(P.hairFront, true, { jit: 0.3 }), P.hair, 0.8)); it.push(LC(P.hairFront, W1, { jit: 0.7 }));
    P.hairTex.forEach((t) => it.push(LH(t, W3)));
    // 3 코 (A: 짧은 선 / B: 점)
    if (P.nose === "line") it.push(LH([[0, 10], [-5, 24], [3, 28]], W2)); else it.push(LH([[-4, 22], [3, 25]], W2, { over: 0 }));
    // 4 눈썹
    const ex = rnd ? 30 : 27, ey = rnd ? 4 : 2, er = 7 * P.eyeR;
    [[-ex, -1], [ex, 1]].forEach(([cx, sd]) => {
      const b = (sd < 0 ? E.brow : M(E.brow)).map((p) => [cx + p[0], ey + p[1] - (rnd ? 2 : 0)]);
      it.push(LH(b, P.sex === "f" ? 4 : 5.5, { jit: 0.5 }));
    });
    // 5 눈 (흰자 타원 + 눈동자 + 하이라이트) — 안경 없음
    [[-ex, -1], [ex, 1]].forEach(([cx, sd]) => {
      const cy = ey, px = cx + look[0] * 4, py = cy + 1 + look[1] * 4;
      if (E.eye === "open") {
        const w = O(cx, cy, er * 1.25, er * 1.15); it.push(F(H(w, true, { jit: 0 }), WHITE, 0.9)); it.push(LC(w, W2, { jit: 0.4 }));
        it.push(dot(px, py, er * 0.8)); it.push(dot(px - er * 0.3, py - er * 0.35, er * 0.28, WHITE));
        if (P.lash) { it.push(LH([[cx + sd * er * 1.1, cy - er * 0.9], [cx + sd * er * 1.7, cy - er * 1.4]], W3, { over: 0 })); it.push(LH([[cx + sd * er * 0.4, cy - er * 1.2], [cx + sd * er * 0.7, cy - er * 1.8]], W3, { over: 0 })); }
      } else { // half: 윗눈꺼풀이 반 덮음
        const w = O(cx, cy + 2, er * 1.25, er * 0.9); it.push(F(H(w, true, { jit: 0 }), WHITE, 0.9));
        it.push(dot(px, py + 2, er * 0.75)); it.push(F(H([[cx - er * 1.4, cy - er * 1.2], [cx + er * 1.4, cy - er * 1.2], [cx + er * 1.4, cy + 1], [cx - er * 1.4, cy + 1]], true, { jit: 0 }), SKIN, 1));
        it.push(LH([[cx - er * 1.3, cy], [cx, cy + 1], [cx + er * 1.3, cy]], W2)); // 눈꺼풀 선
        if (E.bags) it.push(LH([[cx - er * 0.9, cy + er * 1.4], [cx, cy + er * 1.7], [cx + er * 0.9, cy + er * 1.4]], W3, { jit: 0.3 }));
      }
    });
    // 6 입
    const my = rnd ? 54 : 52, MP = (pts) => pts.map((p) => [p[0], my + p[1]]);
    if (E.mouth === "smileOpen") { const sm = [[-16, -4], [-6, 3], [6, 3], [16, -4], [10, 8], [0, 11], [-10, 8]]; it.push(FC(MP(sm), INK, 0.85)); it.push(LC(MP(sm), 4.5)); it.push(F(H(MP([[-8, 7], [0, 9], [8, 7], [5, 10], [0, 11], [-5, 10]]), true, { jit: 0.2 }), BLUSH, 0.9)); }
    else { it.push(LH(MP([[-12, 1], [-4, -1], [4, -1], [12, 2]]), 5)); }
    // 7 홍조(hope) / 그늘 없음
    if (E.blush) [[-ex - 6, 32], [ex + 6, 32]].forEach(([bx, by]) => it.push(F(H(O(bx, by, 11, 6), true, { jit: 0 }), BLUSH, 0.4)));
    return { name: `face.${who}.${expr}.front`, box: [-110, -130, 110, 115], anchor: [0, 0], items: it };
  }

  // ---------- 상반신(폰 포즈) — 몸 폭을 머리 폭의 1.6배로(기존 2.3배 천막 체형 → 어깨가 사람 비율) ----------
  function arm(pts, w, col, z = 1) {
    const Lp = [], Rp = [];
    for (let i = 0; i < pts.length; i++) { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(pts.length - 1, i + 1)], dx = b[0] - a[0], dy = b[1] - a[1], n = Math.hypot(dx, dy) || 1, ww = w * (i === pts.length - 1 ? 0.85 : 1); Lp.push([pts[i][0] - dy / n * ww / 2, pts[i][1] + dx / n * ww / 2]); Rp.push([pts[i][0] + dy / n * ww / 2, pts[i][1] - dx / n * ww / 2]); }
    const poly = Lp.concat(Rp.reverse()); return [FC(poly, col, 0.6, z), LC(poly, W1, { jit: 0.6 }, INK, z)];
  }
  function hand(cx, cy, r, z = 1, rot = 0) {
    const c = Math.cos(rot), s = Math.sin(rot), T = (p) => [cx + p[0] * c - p[1] * s, cy + p[0] * s + p[1] * c];
    const palm = [[-r, -r * 0.6], [-r * 0.4, -r * 1.05], [r * 0.5, -r * 1.0], [r * 1.05, -r * 0.3], [r * 0.95, r * 0.6], [r * 0.3, r * 1.05], [-r * 0.6, r * 0.9], [-r * 1.05, r * 0.2]].map(T);
    return [FC(palm, SKIN, 0.6, z), LC(palm, W2, { jit: 0.5 }, INK, z), LH([T([r * 0.1, -r * 0.3]), T([r * 0.55, -r * 0.1])], W3, {}, INK, z)];
  }
  const rot = (items, deg, dx = 0, dy = 0) => { const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a); const tr = (d) => d.replace(/(-?\d+(?:\.\d+)?)\s(-?\d+(?:\.\d+)?)/g, (m, x, y) => { x = +x; y = +y; return f(x * c - y * s + dx) + " " + f(x * s + y * c + dy); }); return items.map((i) => ({ ...i, d: tr(i.d) })); };

  function bustPhone(who, expr) {
    const P = CH[who], col = P.shirt, back = [], front = [];
    const sw = P.sex === "f" ? 104 : 118; // 어깨 반폭
    const body = [[-22, 100], [-60, 112], [-sw, 136], [-sw - 12, 190], [-sw - 14, 260], [-sw - 14, 330], [sw + 14, 330], [sw + 14, 260], [sw + 12, 190], [sw, 136], [60, 112], [22, 100]];
    back.push(FC(body, col, 0.6, -2)); back.push(LC(body, W1, { jit: 0.8 }, INK, -2));
    // 목
    back.push(F(H([[-20, 80], [20, 80], [22, 112], [-22, 112]], true, { jit: 0 }), SKIN, 0.55, -2)); back.push(LH([[-20, 84], [-21, 106]], W2, { over: 0 }, INK, -2)); back.push(LH([[20, 84], [21, 106]], W2, { over: 0 }, INK, -2));
    if (P.hood) { back.push(LH([[-48, 112], [-30, 134], [0, 142], [30, 134], [48, 112]], W2, {}, INK, -2)); back.push(LH([[-8, 142], [-10, 190]], W3, {}, INK, -2)); back.push(LH([[8, 142], [10, 190]], W3, {}, INK, -2)); }
    else if (P.sex === "f") { back.push(LH([[-22, 100], [-10, 126], [0, 120], [10, 126], [22, 100]], W2, {}, INK, -2)); }
    else { back.push(LH([[-22, 100], [-12, 118], [0, 112], [12, 118], [22, 100]], W2, {}, INK, -2)); }
    // 팔: 어깨에서 나와 가슴 앞에서 폰
    front.push(...arm([[-sw + 10, 150], [-sw - 20, 230], [-74, 266]], 42, col)); front.push(...arm([[sw - 10, 150], [sw + 20, 230], [78, 262]], 42, col));
    front.push(...hand(-50, 262, 20, 1, 0.3)); front.push(...hand(52, 256, 20, 1, -0.3));
    const ph = RR(-38, 186, 80, 134, 12); front.push(FC(ph, WHITE, 0.9, 2)); front.push(LC(ph, W1, { jit: 0.5 }, INK, 2)); front.push(F(H(RR(-32, 194, 68, 100, 6), true, { jit: 0 }), SKY, 0.35, 2)); front.push(LH([[-22, 212], [22, 212]], W3, {}, INK, 2)); front.push(LH([[-20, 236], [14, 236]], W3, {}, INK, 2));
    const head = rot(face(who, expr, { look: [0, 1] }).items, 6, 0, 8);
    return { name: `bust.${who}.phone`, box: [-230, -140, 370, 400], anchor: [0, 0], items: back.concat(head, front) };
  }
  root.HERODRAFT = { CH, face, bustPhone, who: ["mA", "fA", "mB", "fB"] };
})(typeof window !== "undefined" ? window : globalThis);
