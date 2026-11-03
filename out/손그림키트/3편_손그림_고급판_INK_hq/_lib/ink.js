/* 숏클 손그림 엔진 (INK_스타일규칙.md) — render(t) 순수 함수 방식 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
  const seg = (t, a, b) => clamp((t - a) / (b - a));
  const eo = (p) => 1 - Math.pow(1 - p, 3);
  const INKC = "#1F1D1A", ORANGE = "#F6A93B", PAPER = "#FBF8F1";
  const TINT = { beige: "#D9C79E", sky: "#9CC6DD", pink: "#E8A9A6", grey: "#8A847A", skin: "#E3C3A2", night: "#6F86A8", sun: "#F2D27A" };
  const el = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };

  class Cut {
    constructor(ink, t0, t1, idx) {
      this.ink = ink; this.t0 = t0; this.t1 = t1; this.idx = idx;
      this.base = t0 + (idx > 0 ? 0.35 : 0.15); // 종이 넘김이 끝난 뒤 그리기 시작
      this.div = document.createElement("div");
      this.div.style.cssText = `position:absolute;left:0;top:0;width:1920px;height:1080px;background:${PAPER};overflow:hidden;z-index:${idx + 1};`;
      ink.stage.insertBefore(this.div, ink.overlay);
      this.svg = el("svg", { width: 1920, height: 1080, viewBox: "0 0 1920 1080" }); this.svg.style.cssText = "position:absolute;left:0;top:0;";
      this.div.appendChild(this.svg);
      this.items = []; this.texts = []; this.anims = []; this.curX = 0;
    }
    group(attrs, parent) { return el("g", attrs || {}, parent || this.svg); }
    // 펜으로 그려지는 선. o.s = 컷 기준 초(그리기 시작 오프셋은 base 에 더해짐)
    path(d, o = {}) {
      const par = o.parent || this.svg, w = o.w || 6;
      let tintEl = null;
      const s = this.base + (o.s || 0), dur = o.dur || 0.5;
      if (o.tint) { // 색 한 겹: 선 안쪽에 연한 수채 35%
        tintEl = el("path", { d, fill: TINT[o.tint] || o.tint, stroke: "none", opacity: 0 }, par);
      }
      const p = el("path", { d, pathLength: 1, fill: o.fill || "none", stroke: o.color || INKC, "stroke-width": w, "stroke-linecap": "round", "stroke-linejoin": "round", "stroke-dasharray": 1, "stroke-dashoffset": 1, opacity: 0 }, par);
      if (o.dash) p.dataset.dash = 1;
      const it = { el: p, tintEl, d, s, dur, len: p.getTotalLength(), pen: o.pen !== false && !o.nopen, tintOp: o.tintOp || 0.38, fillAfter: !!o.fill, gx: o.gx || 0, gy: o.gy || 0, color: o.color };
      this.items.push(it); return it;
    }
    mask(d, s, parent) { const e = el("path", { d, fill: PAPER, stroke: "none", opacity: 0 }, parent || this.svg); (this.masks = this.masks || []).push({ e, s: this.base + s }); return e; }
    // 글자 한 글자씩 써지듯
    text(str, o = {}) {
      const d = document.createElement("div");
      const font = o.font || "NP"; const size = o.size || 120;
      d.style.cssText = `position:absolute;left:${o.x}px;top:${o.y}px;font-family:"${font}",sans-serif;font-size:${size}px;line-height:1.1;white-space:pre;color:${o.color || INKC};letter-spacing:${o.ls || 0}px;${o.weight ? "font-weight:" + o.weight + ";" : ""}${o.rot ? `transform:rotate(${o.rot}deg);transform-origin:0 50%;` : ""}${o.css || ""}`;
      const spans = []; const s = this.base + (o.s || 0), gap = o.gap || 0.05; let k = 0;
      for (const ch of str) {
        const sp = document.createElement(ch === "\n" ? "br" : "span"); if (ch !== "\n") { sp.textContent = ch; sp.style.cssText = "display:inline-block;opacity:0;"; } d.appendChild(sp);
        spans.push({ sp, t: s + k * gap, ch }); if (ch !== " " && ch !== "\n") k++;
      }
      this.div.appendChild(d);
      const T = { d, spans, o, s, end: s + k * gap + 0.12 }; this.texts.push(T); return T;
    }
    // 글자 범위 상자(지금 컷 좌표)
    box(T, i0, i1) {
      const a = T.spans[i0].sp, b = T.spans[i1].sp;
      return { x: T.d.offsetLeft + a.offsetLeft, y: T.d.offsetTop + a.offsetTop, w: b.offsetLeft + b.offsetWidth - a.offsetLeft, h: a.offsetHeight };
    }
    // 형광 주황 동그라미/밑줄 (손으로 그려짐)
    circle(bx, o = {}) {
      const cx = bx.x + bx.w / 2, cy = bx.y + bx.h * 0.55, rx = bx.w / 2 + (o.px || 34), ry = bx.h / 2 + (o.py || 12);
      let d = ""; const n = 70;
      for (let i = 0; i <= n; i++) { const a = -2.2 + i / n * Math.PI * 2.16; const k = 1 + 0.03 * Math.sin(2 * a) + 0.05 * (i / n);
        d += (i ? "L" : "M") + (cx + rx * k * Math.cos(a)).toFixed(1) + " " + (cy + ry * k * Math.sin(a)).toFixed(1); }
      return this.path(d, { s: o.s, dur: o.dur || 0.6, w: 9, color: ORANGE });
    }
    underline(bx, o = {}) {
      const y = bx.y + bx.h * 0.95, x0 = bx.x - 8, x1 = bx.x + bx.w + 8;
      const d = `M${x0} ${y} Q${(x0 + x1) / 2} ${y + 14} ${x1} ${y - 5}`;
      return this.path(d, { s: o.s, dur: o.dur || 0.5, w: 11, color: ORANGE });
    }
    // 변하는 그림: fn(tLocalAbs, cut)
    anim(fn) { this.anims.push(fn); }
  }

  class Ink {
    constructor(stage, dur) {
      this.stage = stage; this.dur = dur; this.cuts = [];
      this.overlay = document.getElementById("overlay");
      this.penEl = document.getElementById("pen");
      this.extra = [];
    }
    cut(t0, t1) { const c = new Cut(this, t0, t1, this.cuts.length); this.cuts.push(c); return c; }
    render(t) {
      const cuts = this.cuts; let pen = null, penS = -1, penCut = null;
      cuts.forEach((c, i) => {
        const nextT = i + 1 < cuts.length ? cuts[i + 1].t0 : 1e9;
        const vis = (i === 0 || t >= c.t0) && t < nextT + 0.45;
        c.div.style.display = vis ? "block" : "none";
        if (!vis) return;
        let x = 0, sh = "none";
        if (i > 0) { const p = eo(seg(t, c.t0, c.t0 + 0.4)); x = (1 - p) * 1920; sh = p < 1 ? "-26px 0 40px rgba(0,0,0,.20)" : "none"; }
        if (i + 1 < cuts.length) { const p = eo(seg(t, nextT, nextT + 0.4)); x = -p * 260; }
        c.div.style.transform = `translateX(${x.toFixed(1)}px)`; c.div.style.boxShadow = sh; c.curX = x;
        // 글자
        c.texts.forEach((T) => {
          T.spans.forEach((q) => {
            const p = eo(seg(t, q.t, q.t + 0.14));
            q.sp.style.opacity = p; q.sp.style.transform = `translateY(${((1 - p) * 14).toFixed(1)}px)`;
          });
          if (t > T.s && t < T.end && T.s > penS) {
            let last = null; T.spans.forEach((q) => { if (q.t <= t && q.ch.trim()) last = q; });
            if (last) { penS = T.s; pen = [c.curX + T.d.offsetLeft + last.sp.offsetLeft + last.sp.offsetWidth * 0.85, T.d.offsetTop + last.sp.offsetTop + last.sp.offsetHeight * 0.75]; }
          }
        });
        // 선
        c.items.forEach((it) => {
          const p = eo(seg(t, it.s, it.s + it.dur));
          it.el.setAttribute("stroke-dashoffset", (1 - p).toFixed(4));
          it.el.setAttribute("opacity", p > 0 ? 1 : 0);
          if (it.fillAfter) it.el.setAttribute("fill-opacity", p >= 1 ? 1 : 0);
          if (it.tintEl) it.tintEl.setAttribute("opacity", (eo(seg(t, it.s + it.dur + 0.1, it.s + it.dur + 0.5)) * it.tintOp).toFixed(3));
          if (it.pen && p > 0 && p < 1 && it.s > penS) { penS = it.s; const q = it.el.getPointAtLength(p * it.len); pen = [c.curX + q.x + it.gx, q.y + it.gy]; }
        });
        (c.masks || []).forEach((m) => m.e.setAttribute("opacity", t >= m.s ? 1 : 0));
        c.anims.forEach((fn) => fn(t, c));
      });
      const P = this.penEl;
      if (pen) { P.style.opacity = 1; P.style.transform = `translate(${pen[0].toFixed(1)}px,${pen[1].toFixed(1)}px)`; } else P.style.opacity = 0;
    }
    start(id) {
      window.__timelines = window.__timelines || {};
      const tl = gsap.timeline({ paused: true }), P = { t: 0 }, self = this;
      tl.to(P, { t: this.dur, duration: this.dur, ease: "none", onUpdate: () => self.render(P.t) });
      this.render(0); window.__timelines[id] = tl;
    }
  }

  // 손으로 그린 듯한 타원 경로 문자열 (변환 T 적용)
  function ell(T, cx, cy, rx, ry, o = {}) {
    const n = o.n || 56, a0 = (o.a0 === undefined ? -90 : o.a0) * Math.PI / 180, sw = (o.sweep || 372) * Math.PI / 180, ph = o.ph || 0; let d = "";
    for (let i = 0; i <= n; i++) {
      const a = a0 + sw * i / n, k = 1 + 0.012 * Math.sin(3 * a + ph) + 0.008 * Math.sin(5 * a + 2 * ph);
      const [x, y] = T(cx + rx * k * Math.cos(a), cy + ry * k * Math.sin(a)); d += (i ? "L" : "M") + x.toFixed(1) + " " + y.toFixed(1);
    }
    return d;
  }
  // [["M",x,y],["C",...],["Q",...],["L",x,y],["Z"]] -> d (변환 적용)
  function P(T, arr) {
    return arr.map((c) => { const k = c[0]; if (k === "Z") return "Z"; let s = k; for (let i = 1; i < c.length; i += 2) { const [x, y] = T(c[i], c[i + 1]); s += x.toFixed(1) + " " + y.toFixed(1) + " "; } return s; }).join("");
  }
  const ID = (x, y) => [x, y];
  const rect = (T, x, y, w, h, r = 0) => r ? P(T, [["M", x + r, y], ["L", x + w - r, y], ["Q", x + w, y, x + w, y + r], ["L", x + w, y + h - r], ["Q", x + w, y + h, x + w - r, y + h], ["L", x + r, y + h], ["Q", x, y + h, x, y + h - r], ["L", x, y + r], ["Q", x, y, x + r, y], ["Z"]])
    : P(T, [["M", x, y], ["L", x + w, y + 1.5], ["L", x + w - 1, y + h], ["L", x + 1, y + h - 1.5], ["Z"]]);
  const line = (T, x1, y1, x2, y2, bow = 3) => P(T, [["M", x1, y1], ["Q", (x1 + x2) / 2 + bow, (y1 + y2) / 2 - bow, x2, y2]]);

  window.INK = { Ink, Cut, el, clamp, seg, eo, INKC, ORANGE, PAPER, TINT, ell, P, ID, rect, line };
})();
