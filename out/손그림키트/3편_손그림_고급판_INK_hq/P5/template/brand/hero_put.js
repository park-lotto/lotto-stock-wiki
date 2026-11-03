/* 새 주인공(버텍스 선화 → trace 획) 그리기 — 사람 그리는 판단의 주인은 이 함수 하나(SHOTLIST §4-3).
 * 싣는 순서: brand/hq.js → brand/assets.js → brand/hero_strokes.js → brand/hero_put.js
 * 그림: brand/hero/l_<이름>.png(원본 선, 화면에 보이는 선) · brand/hero/c_<이름>_flat.png(컬러판) — INKHERO.IMG 로 바꿀 수 있다
 * 규칙(사장님 10-29): 한 사람 그리기 1.2~1.8초. 같은 그림을 연달아 두 번 그리지 않는다 — 다음 컷은 stat:true(그려진 채) 또는 표정 교체.
 *
 * INKHERO.put(L, name, o) → { root, end, T }
 *   o = { x, y        : 두 눈 사이가 올 장면 좌표
 *         sc  (1.7)   : 지금 자산 배율과 같은 뜻 — 머리 높이 = sc×160 px
 *         s   (0)     : 펜 시작 초
 *         dur (1.2)   : 펜 전체 시간(1.2~1.8 안에서)
 *         mir (false) : 좌우 반전(눈 사이 기준 그대로 유지)
 *         stat(false) : true = 이미 그려진 채 등장(정지 교체, 컬러도 즉시)
 *         color("auto"): "auto" = 펜 끝+0.3초부터 0.6초 / 숫자 = 그 초에 시작 / false = 컬러 없음
 *         cdur (0.6)  : 컬러 페이드 시간(P10 컬러 TV 전환은 0.25)
 *         gray(false) : true = 끝까지 회색 / 숫자 = 그 초부터 cdur 동안 회색→컬러(선·컬러판 모두 filter)
 *         win         : [a, b] 이 구간에만 보임(표정 교체: 앞 그림 win:[a,at], 뒤 그림 win:[at,b], stat:true)
 *         fade (0)    : win 경계 페이드 초(0 = 딱 끊기, qkit 식으로 0.12~0.15 줄 때)
 *         mw  (26×k)  : 마스크 획 굵기(장면 px) — 원본 선을 드러내는 붓 폭
 *         order("y")  : "y" = 획 시작 높이 순(머리→얼굴→몸, 사람이 긋는 순서) / "trace" = trace.py 의 가까운 획 잇기 순 }
 *   end = 마지막 획이 끝나는 초, T(px,py) = 그림 1024 좌표 → 장면 좌표
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const mk = (tag, attrs, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
  const clamp = (v) => Math.min(1, Math.max(0, v));
  const RE = /(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g;

  function polyLen(d) {
    const p = []; d.replace(RE, (_, X, Y) => { p.push([+X, +Y]); return ""; });
    let l = 0; for (let i = 1; i < p.length; i++) l += Math.hypot(p[i][0] - p[i - 1][0], p[i][1] - p[i - 1][1]);
    return l;
  }

  const INKHERO = {
    IMG: "brand/hero/",
    put(L, name, o = {}) {
      const ST = (window.HERO_STROKES || {})[name];
      if (!ST) throw new Error("INKHERO: 획 없음 " + name);
      const A = (window.HERO_ANCHOR || {})[name] || ST;
      if (!A.hpx) throw new Error("INKHERO: 눈·머리 측정값 없음 " + name);
      const sc = o.sc || 1.7, k = sc * 160 / A.hpx, sx = o.mir ? -1 : 1;
      const tx = o.x - sx * A.ex * k, ty = o.y - A.ey * k;
      const T = (px, py) => [tx + sx * px * k, ty + py * k];
      const S = L.S, base = name.replace(/^g_/, "");          // 파일: l_<base>.png · c_<base>_flat.png

      const root = L.sub();
      if (o.win) {
        const [a, b] = o.win, fd = o.fade || 0;
        root.xf((t) => {
          if (t < a || t >= b) return { o: 0 };
          if (!fd) return { o: 1 };
          return { o: Math.min(a <= 0 ? 1 : clamp((t - a) / fd), b > 1e8 ? 1 : clamp((b - t) / fd)) };
        });
      }

      // 1) 컬러판 — 선 아래(fg), S.fills 가 opacity 를 돌린다
      const img = mk("image", {
        href: INKHERO.IMG + "c_" + base + "_flat.png", x: 0, y: 0, width: ST.S || 1024, height: ST.S || 1024,
        transform: `translate(${tx.toFixed(1)} ${ty.toFixed(1)}) scale(${(sx * k).toFixed(4)} ${k.toFixed(4)})`,
        opacity: 0, preserveAspectRatio: "none", style: "mix-blend-mode:multiply",
      }, root.fg);
      img.setAttributeNS("http://www.w3.org/1999/xlink", "href", INKHERO.IMG + "c_" + base + "_flat.png");

      // 2) 선 = 원본 선화 PNG(l_<이름>.png) 그 자체. trace 획은 화면에 안 그리고 '마스크'로만 쓴다:
      //    굵은 흰 마스크 획이 dash 로 그려지는 만큼 원본 선이 드러난다(머리카락·곡선이 원본 품질 그대로).
      //    펜 끝 0.2초 동안 마스크 전체를 채워, 획으로 못 잡은 점·짧은 선(10점 미만)까지 마저 드러낸다.
      const defs = S.svg.querySelector("defs") || mk("defs", {}, S.svg);
      const mid = "ihm" + (INKHERO._n = (INKHERO._n || 0) + 1);
      const mask = mk("mask", { id: mid, maskUnits: "userSpaceOnUse", x: -4000, y: -4000, width: 9000, height: 9000 }, defs);
      const lg = mk("g", { mask: `url(#${mid})` }, root.lg);
      const lineImg = mk("image", {
        href: INKHERO.IMG + "l_" + base + ".png", x: 0, y: 0, width: ST.S || 1024, height: ST.S || 1024, preserveAspectRatio: "none",
        transform: `translate(${tx.toFixed(1)} ${ty.toFixed(1)}) scale(${(sx * k).toFixed(4)} ${k.toFixed(4)})`,
      }, lg);
      const topY = (d) => { let m = 1e9; d.replace(RE, (_, X, Y) => { m = Math.min(m, +Y); return ""; }); return m; };
      const src = (o.order || "y") === "y" ? ST.paths.map((d, i) => [topY(d), i, d]).sort((a, b) => a[0] - b[0] || a[1] - b[1]).map((r) => r[2]) : ST.paths;
      const paths = src.map((d) => d.replace(RE, (_, X, Y) => T(+X, +Y).map((v) => v.toFixed(1)).join(" ")));
      const lens = paths.map(polyLen), tot = lens.reduce((a, b) => a + b, 0) || 1;
      const s0 = o.s || 0, dur = o.dur || 1.2, mw = o.mw || 26 * k;
      let cum = 0, end = s0;
      paths.forEach((d, i) => {
        const si = s0 + dur * cum / tot, di = Math.max(0.02, dur * lens[i] / tot);
        if (o.legacy) { root.line(d, o.stat ? -99 : si, di, { w: 5, pen: !o.stat }); cum += lens[i]; end = Math.max(end, si + di); return; }   // 비교용: 옛 방식(꺾은선을 그대로 그림) — 장면에 쓰지 마라
        const el = mk("path", { d, pathLength: 1, fill: "none", stroke: "#fff", "stroke-width": mw.toFixed(1), "stroke-linecap": "round", "stroke-linejoin": "round", "stroke-dasharray": 1, "stroke-dashoffset": 1 }, mask);
        S.items.push({ el, s: o.stat ? -99 : si, dur: di, len: el.getTotalLength(), pen: !o.stat, L: root });
        cum += lens[i]; end = Math.max(end, si + di);
      });
      if (o.legacy) lg.remove();
      const full = mk("rect", { x: -4000, y: -4000, width: 9000, height: 9000, fill: "#fff", opacity: 0 }, mask);
      S.fills.push({ el: full, s: o.stat ? -99 : end - 0.15, dur: o.stat ? 0.01 : 0.2, op: 1 });
      if (o.stat) end = o.win ? o.win[0] : s0;

      // 3) 컬러 들어오는 시점
      const cdur = o.cdur || 0.6;
      const cs = o.color === false ? null : (typeof o.color === "number" ? o.color : (o.stat ? -99 : end + 0.3));
      if (cs !== null) S.fills.push({ el: img, s: cs, dur: o.stat && typeof o.color !== "number" ? 0.01 : cdur, op: 0.9 });
      else img.remove();

      // 4) 회색(P10 컷1): true = 계속 회색 / 숫자 = 그 초부터 cdur 동안 컬러로
      if (o.gray !== undefined && o.gray !== false) {
        const g0 = o.gray === true ? 1e9 : o.gray;
        S.on((t) => { const p = clamp((t - g0) / cdur); root.g.style.filter = p >= 1 ? "" : `grayscale(${(1 - p).toFixed(3)})`; });
      }
      return { root, end, T, k, img, lineImg };
    },
  };
  window.INKHERO = INKHERO;
})();
