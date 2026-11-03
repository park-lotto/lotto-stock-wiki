/* Q1~Q4 전용 조립 도구 (공용 _assets·_lib_p 는 건드리지 않는다)
 * - hero(): _assets 주인공을 "몸은 무대처럼 0.3초 페이드(R1) + 머리·팔은 펜" 으로 얹고,
 *           표정 전환(R2)은 표정 묶음(눈썹·눈·입·덤)만 0.12초 out → 0.15초 in 으로 갈아 끼운다(겹침 없음).
 * - stage(): 무대 레이어(stat, 컷 시작에 opacity 로 깔림)
 * - flip / mirrorFace: 화면 오른쪽을 보게 좌우 반전
 */
(function () {
  const A = window.INKASSETS;
  const num = /(-?\d+(?:\.\d+)?)\s(-?\d+(?:\.\d+)?)/g;
  const fx = (n) => (Math.round(n * 10) / 10).toString();
  const mapD = (d, fn) => d.replace(num, (m, x, y) => { const p = fn(+x, +y); return fx(p[0]) + " " + fx(p[1]); });
  const mapItems = (items, fn) => items.map((i) => ({ ...i, d: mapD(i.d, fn) }));
  const flipItems = (items) => mapItems(items, (x, y) => [-x, y]);
  const rotItems = (items, deg, dx = 0, dy = 0) => {
    if (!deg && !dx && !dy) return items;
    const a = deg * Math.PI / 180, c = Math.cos(a), s = Math.sin(a);
    return mapItems(items, (x, y) => [x * c - y * s + dx, x * s + y * c + dy]);
  };
  // 포즈 + 표정 + 각도 (+ 얼굴만 좌우 반전) → 아이템 한 벌
  function compose(o) {
    const look = o.look;
    if (!o.pose) { const F = A.face(o.expr, o.view || "front", { look: look || [0, 0] }); let it = F.items; if (o.faceFlip) it = flipItems(it); return rotItems(it, o.tilt || 0); }
    const B = A.bust(o.pose);
    let fl = look || B.head.look; if (o.faceFlip) fl = [-fl[0], fl[1]];
    let fi = A.face(o.expr, o.view || "front", { look: fl }).items;
    if (o.faceFlip) fi = flipItems(fi);
    fi = rotItems(fi, o.tilt === undefined ? B.head.tilt : o.tilt, B.head.dx, B.head.dy);
    let fr = o.frontKeep !== undefined ? B.front.slice(0, o.frontKeep) : B.front;
    if (o.armRot) { const [px, py] = o.armRot.pivot || [126, 148], a = o.armRot.deg * Math.PI / 180, c = Math.cos(a), sn = Math.sin(a);
      fr = mapItems(fr, (x, y) => [px + (x - px) * c - (y - py) * sn, py + (x - px) * sn + (y - py) * c]); }
    let it = B.back.concat(fi, fr);
    if (o.flip) it = flipItems(it);
    return it;
  }
  const same = (a, b) => a.k === b.k && a.d === b.d;
  // L: 부모 레이어. o: {pose, view, faceFlip, flip, tilt, x, y, sc, s, per, win:[a,b], exprs:[{e, at, look}]}
  function hero(L, o) {
    const ex = o.exprs || [{ e: "hope" }];
    const sets = ex.map((E) => compose({ ...o, expr: E.e, look: E.look || o.look }));
    const n0 = sets[0].length;
    let P = 0; while (P < n0 && sets.every((s) => s[P] && same(s[P], sets[0][P]))) P++;
    let Q = 0; while (Q < n0 - P && sets.every((s) => same(s[s.length - 1 - Q], sets[0][n0 - 1 - Q]))) Q++;
    const s0 = o.s || 0, sc = o.sc || 1.7, x = o.x || 0, y = o.y || 0, per = o.per || 0.075;
    const root = L.sub();
    if (o.win) { const [a, b] = o.win, fi = o.winFade === undefined ? 0.15 : o.winFade, fo = o.winFade === undefined ? 0.12 : o.winFade; root.xf((t) => ({ o: (t < a || t >= b) ? 0 : Math.min(1, fi ? (t - a) / fi : 1, fo ? (b - t) / fo : 1) })); }
    const base = sets[0].slice(0, P), tail = sets[0].slice(n0 - Q);
    // 1) 몸(z<0) — 무대처럼 opacity 로 (R1)
    const body = root.sub({ stat: !!o.bodyStat || true });
    const bAt = o.bodyAt === undefined ? s0 : o.bodyAt;
    body.xf((t) => ({ o: Math.min(1, Math.max(0, (t - bAt) / 0.3)) }));
    const bodyItems = o.headStat ? base : base.filter((i) => (i.z || 0) < 0), headItems = o.headStat ? [] : base.filter((i) => (i.z || 0) >= 0);
    A.draw(body, { items: bodyItems, box: [0, 0, 0, 0] }, { x, y, sc, s: 0 });
    // 2) 머리(펜)
    const pen = o.stat ? root.sub({ stat: true }) : root.sub();
    let r = A.draw(pen, { items: headItems, box: [0, 0, 0, 0] }, { x, y, sc, s: s0 + 0.05, per });
    // 3) 표정 묶음
    const exprLayers = [];
    ex.forEach((E, k) => {
      const mid = sets[k].slice(P, sets[k].length - Q);
      const a = k === 0 ? -1 : E.at, b = k + 1 < ex.length ? ex[k + 1].at : 1e9;
      const EL = k === 0 && (!o.stat || o.exprPen) ? root.sub({ stat: false }) : root.sub({ stat: true });
      EL.xf((t) => {
        let v = 1;
        if (k > 0) v = Math.min(1, Math.max(0, (t - (a + 0.12)) / 0.15)); // 앞 표정 out 0.12 → 이 표정 in 0.15
        if (b < 1e8) v = Math.min(v, Math.max(0, 1 - (t - b) / 0.12));
        return { o: v };
      });
      const rr = A.draw(EL, { items: mid, box: [0, 0, 0, 0] }, { x, y, sc, s: r.end, per: per * 0.8 });
      if (k === 0) r = rr;
      exprLayers.push(EL);
    });
    // 4) 앞팔·손·폰(펜)
    const front = o.stat ? root.sub({ stat: true }) : root.sub();
    const rf = A.draw(front, { items: tail, box: [0, 0, 0, 0] }, { x, y, sc, s: r.end, per });
    return { root, end: rf.end, P, Q, n: n0, T: (px, py) => [x + px * sc, y + py * sc] };
  }
  // 무대: 컷 시작 a 에 0.3초 opacity 로 깔리고 b 에 0.12초 out (b 없으면 계속)
  function stage(L, a, b = 1e9, dur = 0.3) {
    const S = L.sub({ stat: true });
    S.xf((t) => ({ o: (t < a || t >= b) ? 0 : Math.min(1, (t - a) / dur, b < 1e8 ? (b - t) / 0.12 : 1) }));
    return S;
  }
  // 반짝 등장(pop) — 0.2초 scale 0.94→1 + opacity
  function pop(L, a, b = 1e9, cx = 960, cy = 540) {
    const S = L.sub({ stat: true });
    S.xf((t) => { const p = Math.min(1, Math.max(0, (t - a) / 0.2)), e = 1 - Math.pow(1 - p, 3); const out = b < 1e8 ? Math.min(1, Math.max(0, (b - t) / 0.12)) : 1; return { o: (t < a || t >= b) ? 0 : Math.min(e, out), s: 0.94 + 0.06 * e, ox: cx, oy: cy }; });
    return S;
  }
  const asset = (name, o) => (typeof name === "string" ? A.get(name, o) : name);
  function put(L, name, o = {}) { let a = asset(name, o); if (o.flip) a = { ...a, items: flipItems(a.items) }; if (o.drop) a = { ...a, items: a.items.filter((_, i) => !o.drop.includes(i)) }; return A.draw(L, a, o); }
  window.QK = { hero, stage, pop, put, compose, flipItems, rotItems, mapItems };

  // 새 주인공(INKHERO) 자리 잡기: 눈 사이 (x,y) + 그림 전체 높이 H(px) → sc 를 계산해 INKHERO.put 에 넘긴다
  // BOX = l_<이름>.png 잉크 범위 [top, bottom] (1024 기준, 2026-10-29 실측)
  const BOX = { g_f_tired: [139, 890], g_f_point_hope: [155, 848], g_f_frustr_head: [116, 872], g_m_laptop_hope: [118, 918],
    g_m_laptop_tired: [129, 928], g_m_point_hope: [150, 914], g_m_excited: [111, 915] };
  function person(L, name, o) {
    const A = (window.HERO_STROKES || {})[name], B = BOX[name];
    const k = o.H / (B[1] - B[0]), sc = k * A.hpx / 160;
    return window.INKHERO.put(L, name, { ...o, sc, x: o.x, y: o.y });
  }
  const _QK = window.QK; window.QK = { ..._QK, person, BOX };
})();
