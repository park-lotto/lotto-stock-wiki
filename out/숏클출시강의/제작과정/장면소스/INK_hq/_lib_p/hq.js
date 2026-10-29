/* 숏클 손그림 고퀄 엔진 (P6~P10) — render(t) 순수 함수. INK_스타일규칙.md 준수 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const INK = "#1F1D1A", ORG = "#F6A93B", PAPER = "#FBF8F1", GRAYINK = "#8C8A86";
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const eo = (p) => 1 - Math.pow(1 - p, 3);
  const qo = (p) => p * (2 - p);
  let _s = 4242; const rnd = () => { _s = (_s * 16807) % 2147483647; return (_s - 1) / 2147483646; };
  const J = (a) => (rnd() * 2 - 1) * a;
  const f = (n) => (+n).toFixed(1);
  const mk = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const toGray = (hex) => { const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255; const y = Math.round(0.3 * r + 0.59 * g + 0.11 * b); const h = y.toString(16).padStart(2, "0"); return "#" + h + h + h; };
  const FONTS = { pen: "NP", gae: "GB", num: "PB" };

  // ---------- 손맛 나는 경로 ----------
  function smooth(pts, closed) {
    const n = pts.length; if (n < 2) return "";
    let d = "M" + f(pts[0][0]) + " " + f(pts[0][1]);
    const P = (i) => closed ? pts[(i + n) % n] : pts[Math.max(0, Math.min(n - 1, i))];
    const cnt = closed ? n : n - 1;
    for (let i = 0; i < cnt; i++) {
      const p0 = P(i - 1), p1 = P(i), p2 = P(i + 1), p3 = P(i + 2);
      d += " C" + f(p1[0] + (p2[0] - p0[0]) / 6) + " " + f(p1[1] + (p2[1] - p0[1]) / 6) + " " + f(p2[0] - (p3[0] - p1[0]) / 6) + " " + f(p2[1] - (p3[1] - p1[1]) / 6) + " " + f(p2[0]) + " " + f(p2[1]);
    }
    return closed ? d + " Z" : d;
  }
  function ell(cx, cy, rx, ry, o = {}) {
    const n = o.n || 24, a0 = (o.a0 !== undefined ? o.a0 : -Math.PI / 2 + J(0.3)), sw = o.sweep || Math.PI * 2 * 1.035, pts = [];
    for (let i = 0; i <= n; i++) { const a = a0 + i / n * sw, k = 1 + J(0.012); pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]); }
    return smooth(pts, false);
  }
  function cloud(cx, cy, rx, ry, bumps = 11, amp = 0.07) {
    const pts = [], n = bumps * 4;
    for (let i = 0; i < n; i++) { const a = i / n * Math.PI * 2, k = 1 + amp * Math.sin(a * bumps) ; pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]); }
    return smooth(pts, true);
  }
  function poly(pts, r = 0, closed = true, j = 1.1) {
    const P = pts.map((p) => [p[0] + J(j), p[1] + J(j)]), n = P.length;
    if (!r || !closed) return "M" + P.map((p) => f(p[0]) + " " + f(p[1])).join(" L") + (closed ? " Z" : "");
    let d = "";
    for (let i = 0; i < n; i++) {
      const p = P[i], a = P[(i - 1 + n) % n], b = P[(i + 1) % n];
      const la = Math.hypot(a[0] - p[0], a[1] - p[1]) || 1, lb = Math.hypot(b[0] - p[0], b[1] - p[1]) || 1;
      const ra = Math.min(r, la / 2), rb = Math.min(r, lb / 2);
      d += (i ? " L" : "M") + f(p[0] + (a[0] - p[0]) * ra / la) + " " + f(p[1] + (a[1] - p[1]) * ra / la) + " Q" + f(p[0]) + " " + f(p[1]) + " " + f(p[0] + (b[0] - p[0]) * rb / lb) + " " + f(p[1] + (b[1] - p[1]) * rb / lb);
    }
    return d + " Z";
  }
  const rr = (x, y, w, h, r = 12) => poly([[x, y], [x + w, y], [x + w, y + h], [x, y + h]], r);
  const ln = (x1, y1, x2, y2) => `M${f(x1 + J(0.8))} ${f(y1 + J(0.8))} Q${f((x1 + x2) / 2 + J(2))} ${f((y1 + y2) / 2 + J(2))} ${f(x2 + J(0.8))} ${f(y2 + J(0.8))}`;
  const pl = (pts) => smooth(pts.map((p) => [p[0] + J(0.7), p[1] + J(0.7)]), false);
  function tube(pts, w) {
    const L = [], R = [], n = pts.length;
    pts.forEach((p, i) => { const a = pts[Math.max(0, i - 1)], b = pts[Math.min(n - 1, i + 1)]; const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1, nx = -dy / l * w / 2, ny = dx / l * w / 2; L.push([p[0] + nx, p[1] + ny]); R.push([p[0] - nx, p[1] - ny]); });
    return poly(L.concat(R.reverse()), w * 0.4, true, 0.6);
  }

  // ---------- Layer ----------
  class Layer {
    constructor(S, parent, o = {}) {
      this.S = S; this.parent = parent; this.gray = o.gray !== undefined ? o.gray : (parent ? parent.gray : false);
      this.stat = o.stat !== undefined ? o.stat : (parent ? parent.stat : false);
      this.fillMul = o.fillMul !== undefined ? o.fillMul : (parent ? parent.fillMul : 1);
      this.g = mk("g", {}, parent ? parent.lg : S.svg);
      this.fg = mk("g", {}, this.g); this.lg = mk("g", {}, this.g);
      this.div = document.createElement("div");
      this.div.style.cssText = "position:absolute;left:0;top:0;width:1920px;height:1080px;transform-origin:0 0;pointer-events:none;";
      (parent ? parent.div : S.tdiv).appendChild(this.div);
      this.win = null; this.xff = null; this.cur = { tx: 0, ty: 0, ox: 0, oy: 0, r: 0, s: 1 }; this.A = 1;
      S.layers.push(this);
    }
    sub(o) { return new Layer(this.S, this, o); }
    vis(a, b, mode = "fade") { this.win = [a, b, mode]; return this; }
    xf(fn) { this.xff = fn; return this; }
    ink() { return this.gray ? GRAYINK : INK; }
    col(c) { return this.gray && c[0] === "#" ? toGray(c) : c; }
    map(px, py) {
      const c = this.cur, a = c.r * Math.PI / 180, x = px - c.ox, y = py - c.oy;
      let X = c.ox + (x * Math.cos(a) - y * Math.sin(a)) * c.s + c.tx, Y = c.oy + (x * Math.sin(a) + y * Math.cos(a)) * c.s + c.ty;
      return this.parent ? this.parent.map(X, Y) : [X, Y];
    }
    apply(t) {
      const b = Object.assign({ x: 0, y: 0, s: 1, r: 0, o: 1, ox: 960, oy: 540 }, this.xff ? this.xff(t) : {});
      let a = 1, dx = 0, sc = 1;
      if (this.win) {
        const [A, B, mode] = this.win, din = eo(seg(t, A, A + 0.45)), dout = eo(seg(t, B - 0.45, B));
        if (t < A || t >= B) a = 0; else a = Math.min(din, 1 - dout + (B > 1e8 ? 1 : 0));
        if (mode === "slide") dx = (1 - din) * 120 - dout * 120;
        if (mode === "pop") sc = 0.94 + 0.06 * din;
      }
      this.cur = { tx: b.x + dx, ty: b.y, ox: b.ox, oy: b.oy, r: b.r, s: b.s * sc };
      const tr = `translate(${f(b.x + dx)} ${f(b.y)}) translate(${b.ox} ${b.oy}) rotate(${f(b.r)}) scale(${(b.s * sc).toFixed(4)}) translate(${-b.ox} ${-b.oy})`;
      const o = a * b.o;
      this.A = o * (this.parent ? this.parent.A : 1);
      this.g.setAttribute("transform", tr);
      this.div.style.transform = `translate(${f(b.x + dx)}px,${f(b.y)}px) translate(${b.ox}px,${b.oy}px) rotate(${f(b.r)}deg) scale(${(b.s * sc).toFixed(4)}) translate(${-b.ox}px,${-b.oy}px)`;
      const show = o > 0.002;
      this.g.style.display = show ? "" : "none"; this.div.style.display = show ? "" : "none";
      this.g.style.opacity = o.toFixed(3); this.div.style.opacity = o.toFixed(3);
    }
    // 펜으로 그려지는 선
    line(d, s, dur = 0.5, o = {}) {
      const w = o.w || 6;
      const el = mk("path", { d, pathLength: 1, fill: "none", stroke: this.col(o.c || INK).replace(INK, this.ink()), "stroke-width": w, "stroke-linecap": "round", "stroke-linejoin": "round", "stroke-dasharray": 1, "stroke-dashoffset": 1 }, o.under ? this.fg : this.lg);
      if (this.gray && (!o.c || o.c === INK)) el.setAttribute("stroke", GRAYINK);
      if (o.c === ORG) el.setAttribute("stroke", ORG);
      const it = { el, s: this.stat ? -99 : s, dur, len: el.getTotalLength(), pen: o.pen !== false, L: this };
      this.S.items.push(it); return it;
    }
    // 색 한 겹 (선이 다 그려진 뒤 0.3초)
    fill(d, col, s, op = 0.35, dur = 0.45) {
      const c = this.col(col);
      const el = mk("path", { d, fill: c, stroke: "none", opacity: 0 }, this.fg);
      const o = Math.min(0.85, (this.gray ? Math.max(op, 0.42) : op) * this.fillMul);
      const it = { el, s: this.stat ? -99 : s, dur, op: o }; this.S.fills.push(it); return it;
    }
    shape(d, s, dur, col, o = {}) {
      const it = this.line(d, s, dur, o);
      if (col) this.fill(d, col, s + dur + 0.3, o.op || 0.35);
      it.end = s + dur + 0.3 + 0.45; return it;
    }
    dot(x, y, r, s, col) {
      const c = this.col(col || INK).replace(INK, this.ink());
      const el = mk("path", { d: ell(x, y, r, r, { n: 8 }), fill: this.gray ? GRAYINK : c, stroke: "none", opacity: 0 }, this.lg);
      this.S.fills.push({ el, s: this.stat ? -99 : s, dur: 0.12, op: 1 });
    }
    // 글자 (한 글자씩)
    text(str, o = {}) {
      const size = o.size || 120, font = FONTS[o.font || "pen"];
      const d = document.createElement("div");
      d.style.cssText = `position:absolute;white-space:pre;font-family:"${font}",sans-serif;font-size:${size}px;line-height:1.1;color:${this.gray ? GRAYINK : (o.c || INK)};${o.weight ? "font-weight:" + o.weight + ";" : ""}`;
      const chars = []; let k = 0; const s = this.stat ? -99 : (o.s || 0), gap = o.gap || 0.06;
      for (const ch of str) {
        const sp = document.createElement("span"); sp.textContent = ch; sp.style.cssText = "display:inline-block;opacity:0;"; d.appendChild(sp);
        chars.push({ sp, t: s + k * gap }); if (ch !== " ") k++;
      }
      this.div.appendChild(d);
      const w = d.offsetWidth, x = o.anchor === "c" ? o.x - w / 2 : o.anchor === "r" ? o.x - w : o.x, y = o.y - size * 0.6;
      d.style.left = x + "px"; d.style.top = y + "px";
      const T = { chars, s, end: s + k * gap + 0.14, x, y, size, L: this, d, w,
        box(i0 = 0, i1 = chars.length - 1) { const a = chars[i0].sp, b = chars[i1].sp; return { x: x + a.offsetLeft, y: y, w: b.offsetLeft + b.offsetWidth - a.offsetLeft, h: size * 1.1 }; } };
      this.S.texts.push(T); return T;
    }
    underline(bx, s, dur = 0.5, o = {}) {
      const y = bx.y + bx.h * 0.93, x0 = bx.x - 6, x1 = bx.x + bx.w + 6;
      return this.line(`M${f(x0)} ${f(y)} Q${f((x0 + x1) / 2)} ${f(y + 14)} ${f(x1)} ${f(y - 6)}`, s, dur, { c: ORG, w: 11 });
    }
    circleMark(bx, s, dur = 0.7, px = 34, py = 14) {
      const cx = bx.x + bx.w / 2, cy = bx.y + bx.h * 0.55, rx = bx.w / 2 + px, ry = bx.h / 2 + py, pts = [];
      for (let i = 0; i <= 30; i++) { const a = -2.3 + i / 30 * Math.PI * 2.12, k = 1 + 0.05 * (i / 30) + J(0.01); pts.push([cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)]); }
      return this.line(smooth(pts, false), s, dur, { c: ORG, w: 10 });
    }
  }

  // ---------- Scene ----------
  class Scene {
    constructor(dur) {
      this.dur = dur; this.items = []; this.fills = []; this.texts = []; this.layers = []; this.hooks = [];
      this.stage = document.getElementById("stage");
      this.svg = document.getElementById("svg"); this.tdiv = document.getElementById("tdiv"); this.penEl = document.getElementById("pen");
      this.root = new Layer(this, null, {});
    }
    layer(o) { return new Layer(this, this.root, o); }
    on(fn) { this.hooks.push(fn); }
    render(t) {
      this.layers.forEach((L) => L.apply(t));
      let pen = null, penS = -1;
      this.items.forEach((it) => {
        const p = qo(seg(t, it.s, it.s + it.dur));
        it.el.setAttribute("stroke-dashoffset", (1 - p).toFixed(4));
        it.el.style.visibility = p <= 0 ? "hidden" : "visible";
        if (it.pen && p > 0 && p < 1 && it.L.A > 0.3 && it.s >= penS) { penS = it.s; const q = it.el.getPointAtLength(p * it.len); pen = it.L.map(q.x, q.y); }
      });
      this.fills.forEach((it) => { it.el.setAttribute("opacity", (it.op * eo(seg(t, it.s, it.s + it.dur))).toFixed(3)); });
      this.texts.forEach((T) => {
        T.chars.forEach((q, i) => { const p = eo(seg(t, q.t, q.t + 0.14)); q.sp.style.opacity = p; q.sp.style.transform = `translateY(${((1 - p) * 10).toFixed(1)}px)`; });
        if (T.L.A > 0.3 && t > T.s && t < T.end && T.s >= penS) {
          let i = 0; T.chars.forEach((q, k) => { if (q.t <= t) i = k; });
          const sp = T.chars[i].sp; penS = T.s;
          pen = T.L.map(T.x + sp.offsetLeft + sp.offsetWidth * 0.8, T.y + T.size * 0.95);
        }
      });
      this.hooks.forEach((h) => h(t));
      if (pen) { this.penEl.style.opacity = 1; this.penEl.style.transform = `translate(${f(pen[0])}px,${f(pen[1])}px)`; } else this.penEl.style.opacity = 0;
    }
    start() {
      const tl = gsap.timeline({ paused: true }), P = { t: 0 };
      tl.to(P, { t: this.dur, duration: this.dur, ease: "none", onUpdate: () => this.render(P.t) });
      this.render(0); window.__timelines = window.__timelines || {}; window.__timelines["promo"] = tl; window.__S = this;
    }
  }

  // ---------- 주인공 (50대, 둥근 얼굴, 짧은 머리, 동그란 안경, 셔츠) ----------
  const SKIN = "#F2B8B0", SHIRT = "#8EC3E6", HAIR = "#8E877C", BEIGE = "#E3D3B0", SKY = "#A8D2EA", PINK = "#F2B8B0";
  function person(L, o) {
    const sc = o.sc || 1.6, cx = o.cx, cy = o.cy, s = o.s || 0, T = (x, y) => [cx + x * sc, cy + y * sc];
    const TL = (pts) => pts.map((p) => T(p[0], p[1]));
    const botY = o.bottom !== undefined ? o.bottom : 1100;
    const L1 = L.sub();
    let t = s;
    // 몸통(셔츠) — 먼저
    const bY = (botY - cy) / sc;
    const left = [[-18, 78], [-60, 92], [-122, 118], [-150, 168], [-156, 240], [-158, bY]];
    const right = left.map((p) => [-p[0], p[1]]);
    // 셔츠 닫힌 도형
    const sd = poly(TL(left.concat(right.slice().reverse())), 0, true, 0.9);
    const shirt = L1.line(smooth(TL(left), false), t + 0.5, 0.7); L1.line(smooth(TL(left.map((p) => [-p[0], p[1]])), false), t + 0.5, 0.7);
    L1.fill(sd, SHIRT, t + 1.5);
    // 칼라·단추
    L1.line(poly(TL([[-18, 76], [-2, 112], [-36, 104]]), 0, true, 0.6), t + 1.2, 0.3);
    L1.line(poly(TL([[18, 76], [2, 112], [36, 104]]), 0, true, 0.6), t + 1.3, 0.3);
    L1.line(ln(...T(0, 112), ...T(0, bY)), t + 1.4, 0.4, { pen: false });
    [150, 210, 270].forEach((y, i) => { if (cy + y * sc < botY - 20) L1.dot(...T(0, y), 5 * sc / 1.6, t + 1.6 + i * 0.05); });
    // 목
    L1.line(ln(...T(-17, 58), ...T(-18, 82)), t + 0.45, 0.2, { pen: false }); L1.line(ln(...T(17, 58), ...T(18, 82)), t + 0.45, 0.2, { pen: false });
    // 머리
    const head = ell(...T(0, 0), 58 * sc, 62 * sc, { n: 28 });
    L1.line(head, t, 0.7); L1.fill(head, SKIN, t + 1.0);
    // 귀
    L1.line(pl([T(-57, -6), T(-71, 2), T(-69, 16), T(-57, 22)]), t + 0.6, 0.25, { pen: false });
    L1.line(pl([T(57, -6), T(71, 2), T(69, 16), T(57, 22)]), t + 0.65, 0.25, { pen: false });
    // 머리카락 (짧게)
    const hairOut = [[-58, -10], [-57, -42], [-36, -64], [0, -72], [36, -64], [57, -42], [58, -10]];
    const hairIn = [[52, -18], [46, -34], [20, -46], [-6, -48], [-30, -42], [-48, -28], [-52, -16]];
    L1.line(smooth(TL(hairOut), false), t + 0.55, 0.5);
    L1.line(smooth(TL(hairIn), false), t + 0.8, 0.4, { pen: false });
    L1.fill(smooth(TL(hairOut.concat(hairIn)), true), HAIR, t + 1.4, 0.4);
    // 안경
    [-26, 26].forEach((dx, k) => L1.line(ell(...T(dx, 4), 20 * sc, 19 * sc, { n: 14 }), t + 0.95 + k * 0.12, 0.35, { w: 5 }));
    L1.line(`M${f(T(-6, 0)[0])} ${f(T(-6, 0)[1])} Q${f(T(0, -5)[0])} ${f(T(0, -5)[1])} ${f(T(6, 0)[0])} ${f(T(6, 0)[1])}`, t + 1.2, 0.15, { w: 5, pen: false });
    L1.line(ln(...T(-46, 2), ...T(-58, 0)), t + 1.25, 0.15, { w: 4, pen: false }); L1.line(ln(...T(46, 2), ...T(58, 0)), t + 1.25, 0.15, { w: 4, pen: false });
    // 코, 팔자주름(50대)
    L1.line(pl([T(1, 12), T(-5, 24), T(3, 27)]), t + 1.3, 0.25, { w: 4, pen: false });
    L1.line(pl([T(-30, 28), T(-27, 38), T(-22, 44)]), t + 1.4, 0.2, { w: 3.5, pen: false }); L1.line(pl([T(30, 28), T(27, 38), T(22, 44)]), t + 1.4, 0.2, { w: 3.5, pen: false });
    // 표정 (여러 개 시간대)
    const faces = o.faces || [{ e: "smile", a: -1, b: 1e9, look: [0, 0] }];
    faces.forEach((F, fi) => {
      const FL = L.sub(); FL.vis(F.a, F.b, "fade");
      const t0 = fi === 0 ? t + 1.35 : F.a + 0.05, lk = F.look || [0, 0];
      [-26, 26].forEach((dx, k) => FL.dot(...T(dx + lk[0] * 7, 4 + lk[1] * 6), 4.8 * sc / 1.6 * 1.0, t0 + k * 0.05));
      const e = F.e;
      const brow = { smile: [[-42, -24], [-26, -30], [-12, -24]], worry: [[-42, -16], [-26, -26], [-10, -32]], up: [[-42, -27], [-26, -34], [-12, -27]], flat: [[-42, -22], [-26, -24], [-12, -22]] }[F.brow || (e === "worry" ? "worry" : e === "grin" || e === "wow" ? "up" : "smile")];
      FL.line(smooth(TL(brow), false), t0 + 0.1, 0.2, { w: 5, pen: false });
      FL.line(smooth(TL(brow.map((p) => [-p[0], p[1]])), false), t0 + 0.15, 0.2, { w: 5, pen: false });
      const mouth = { smile: [[-20, 34], [0, 44], [20, 34]], grin: null, worry: [[-16, 42], [-6, 36], [6, 42], [16, 36]], flat: [[-14, 40], [14, 40]], o: null, tired: [[-16, 42], [0, 38], [16, 44]] }[e];
      if (e === "grin") { const g = poly(TL([[-24, 32], [24, 32], [18, 50], [0, 54], [-18, 50]]), 8, true, 0.5); FL.line(g, t0 + 0.25, 0.3, { w: 5 }); FL.fill(g, "#F2A3A0", t0 + 0.6, 0.45); }
      else if (e === "o") { FL.line(ell(...T(0, 42), 8 * sc, 10 * sc, { n: 10 }), t0 + 0.25, 0.25, { w: 5 }); }
      else FL.line(smooth(TL(mouth), false), t0 + 0.25, 0.3, { w: 5.5 });
      if (e === "grin" || e === "smile") { FL.line(ln(...T(-40, 26), ...T(-34, 22)), t0 + 0.4, 0.15, { w: 3.5, pen: false }); FL.line(ln(...T(40, 26), ...T(34, 22)), t0 + 0.4, 0.15, { w: 3.5, pen: false }); }
      if (e === "worry") FL.line(pl([T(66, -30), T(72, -14), T(66, -4)]), t0 + 0.4, 0.2, { w: 4, pen: false });
    });
    // 팔
    (o.arms || []).forEach((A) => {
      const AL = L.sub(); if (A.win) AL.vis(A.win[0], A.win[1], "fade");
      const td = tube(TL(A.pts), 40 * sc / 1.6 * 1.0), a0 = A.s !== undefined ? A.s : t + 1.8;
      AL.line(td, a0, 0.6, { pen: A.pen !== false }); AL.fill(td, SHIRT, a0 + 0.9, 0.35);
      if (A.hand) { const h = ell(...T(A.hand[0], A.hand[1]), 20 * sc / 1.6, 19 * sc / 1.6, { n: 10 }); AL.line(h, a0 + 0.55, 0.3); AL.fill(h, SKIN, a0 + 1.15, 0.4); }
    });
    return { T, end: t + 2.2 };
  }

  // ---------- 로봇 (대리 = 무료 AI / 부장 = 클로드) ----------
  function robot(L, o) {
    const sc = o.sc || 1.4, cx = o.cx, cy = o.cy, s = o.s || 0, T = (x, y) => [cx + x * sc, cy + y * sc], TL = (p) => p.map((q) => T(q[0], q[1]));
    const boss = o.kind === "boss", col = boss ? "#BFA8E0" : "#A8D2EA";
    const R = L.sub();
    // 몸통
    const body = rr(...T(-86, 66), 172 * sc, (o.bodyH || 170) * sc, 24 * sc);
    R.shape(body, s + 0.4, 0.7, col);
    // 가슴 라벨판
    R.line(rr(...T(-56, 96), 112 * sc, 52 * sc, 10 * sc), s + 1.0, 0.4, { w: 4.5, pen: false });
    // 머리
    R.line(ln(...T(0, -62), ...T(0, -92)), s + 0.1, 0.2, { pen: false }); R.line(ell(...T(0, -102), 10 * sc, 10 * sc, { n: 10 }), s + 0.25, 0.2, { w: 5, pen: false });
    const head = rr(...T(-76, -62), 152 * sc, 124 * sc, 30 * sc);
    R.shape(head, s, 0.7, col);
    R.line(rr(...T(-92, -22), 14 * sc, 44 * sc, 6), s + 0.7, 0.2, { w: 5, pen: false }); R.line(rr(...T(78, -22), 14 * sc, 44 * sc, 6), s + 0.75, 0.2, { w: 5, pen: false });
    R.line(ln(...T(-10, 62), ...T(-10, 68)), s + 0.5, 0.1, { pen: false });
    // 눈·입 (표정은 상태별)
    const E = o.exprs || [{ e: "ok", a: -1, b: 1e9 }];
    E.forEach((X, i) => {
      const F = L.sub(); F.vis(X.a, X.b, "fade"); const t0 = i === 0 ? s + 1.0 : X.a + 0.05;
      [-30, 30].forEach((dx, k) => {
        if (X.e === "stuck") { F.line(ell(...T(dx, -14), 14 * sc, 14 * sc, { n: 12 }), t0 + k * 0.08, 0.3, { w: 5 }); F.dot(...T(dx + 3, -16), 4.5 * sc / 1.4, t0 + 0.3); }
        else if (X.e === "idea") { F.line(ell(...T(dx, -14), 14 * sc, 14 * sc, { n: 12 }), t0 + k * 0.08, 0.3, { w: 5 }); F.dot(...T(dx + 4, -18), 5.5 * sc / 1.4, t0 + 0.3); }
        else { F.line(pl([T(dx - 13, -12), T(dx, -26), T(dx + 13, -12)]), t0 + k * 0.08, 0.25, { w: 5.5 }); }
      });
      const mouth = X.e === "stuck" ? [[-18, 30], [-6, 24], [6, 32], [18, 26]] : X.e === "idea" ? [[-22, 24], [0, 42], [22, 24]] : [[-18, 30], [0, 38], [18, 30]];
      F.line(smooth(TL(mouth), false), t0 + 0.3, 0.3, { w: 5.5 });
      if (X.e === "stuck") { const sw = poly(TL([[70, -50], [62, -30], [78, -30]]), 6, true, 0.3); F.line(sw, t0 + 0.5, 0.25, { w: 4.5, pen: false }); F.fill(sw, "#A8D2EA", t0 + 0.9, 0.5); }
    });
    // 넥타이·배지 (부장)
    if (boss) {
      const tie = poly(TL([[-12, 68], [12, 68], [18, 92], [0, 104], [-18, 92]]), 3, true, 0.5);
      R.line(tie, s + 1.2, 0.35, { w: 4.5 }); R.fill(tie, "#F2B8B0", s + 1.9, 0.5);
      const tie2 = poly(TL([[-18, 92], [18, 92], [26, 190], [0, 214], [-26, 190]]), 4, true, 0.5);
      R.line(tie2, s + 1.4, 0.45, { w: 4.5 }); R.fill(tie2, "#F2B8B0", s + 2.1, 0.5);
    }
    // 팔
    (o.arms || []).forEach((A) => {
      const AL = L.sub(); if (A.win) AL.vis(A.win[0], A.win[1], "fade");
      const td = tube(TL(A.pts), 30 * sc / 1.4), a0 = A.s !== undefined ? A.s : s + 1.6;
      AL.line(td, a0, 0.5, { w: 5.5 }); AL.fill(td, col, a0 + 0.8, 0.4);
      if (A.hand) { const h = ell(...T(A.hand[0], A.hand[1]), 15 * sc / 1.4, 15 * sc / 1.4, { n: 10 }); AL.line(h, a0 + 0.45, 0.25, { w: 5, pen: false }); }
    });
    return { T, TL, end: s + 2.2 };
  }

  // 펜 아이콘
  function penIcon() {
    return `<svg id="pen" width="90" height="90" viewBox="0 0 90 90" style="position:absolute;left:0;top:0;opacity:0;overflow:visible;z-index:20"><g transform="rotate(-38 0 0)"><path d="M0 0 L14 -9 L84 -9 L84 9 L14 9 Z" fill="#1F1D1A"/><path d="M0 0 L14 -9 L14 9 Z" fill="#f2e6cf" stroke="#1F1D1A" stroke-width="2"/><path d="M0 0 L5 -3 L5 3 Z" fill="#1F1D1A"/><rect x="60" y="-9" width="6" height="18" fill="#F6A93B"/></g></svg>`;
  }

  window.HQ = { Scene, Layer, person, robot, penIcon, smooth, ell, cloud, poly, rr, ln, pl, tube, mk, INK, ORG, PAPER, SKIN, SHIRT, HAIR, BEIGE, SKY, PINK, eo, seg, clamp, qo, J, f };
})();
