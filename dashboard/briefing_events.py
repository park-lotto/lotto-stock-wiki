"""장중 시황 브리핑 — 스냅샷 정규화 + 이벤트 디텍터(순수 로직, AI 없음)."""
import time as _time

# ── 임계 상수 (단위 명시) ──────────────────────────────
MIN_INVESTOR_TURN_MW = 30_000   # 300억 (백만원)
PROG_JUMP_MW         = 50_000   # 500억
PROG_FLIP_MIN_MW     = 30_000   # 300억
IDX_NEWHIGH_MARGIN   = 0.0005   # 0.05%
IDX_REBOUND_PCT      = 0.006    # 저점 대비 +0.6%p
IDX_PULLBACK_PCT     = 0.006    # 고점 대비 -0.6%p
NQ_DELTA_PP          = 0.4
NQ_ABS_LEVELS        = [1.0, 2.0]
DECOUPLE_MIN_SLOPE_PP = 0.15
SECTOR_SURGE_PP      = 2.0
SECTOR_LEAD_ABS      = 3.0
EVENT_RECOOLDOWN_S   = 600      # 같은 타입 재발동 최소간격(초)


def _f(v, d=0.0):
    try:
        return float(v)
    except Exception:
        return d


def _sign(x):
    return (x > 0) - (x < 0)


def build_snapshot(mf: dict, sectors: list, j_bars: list, q_bars: list, ts: str) -> dict:
    """market_flow 캐시 + heatmap sectors + 지수 bars → 디텍터용 정규화 snap."""
    mf = mf or {}

    def _idx(k):
        p = mf.get(k) or {}
        return {"price": _f(p.get("price")), "rate": _f(p.get("change_rate"))}

    def _hilo(bars):
        prices = [_f(b.get("price")) for b in (bars or []) if _f(b.get("price")) > 0]
        if not prices:
            return {"day_high": 0.0, "day_low": 0.0}
        return {"day_high": max(prices), "day_low": min(prices)}

    def _inv(k):
        d = mf.get(k) or {}
        return {"외인": _f(d.get("외인")), "기관": _f(d.get("기관"))}

    def _prog(k):
        d = mf.get(k) or {}
        return _f(d.get("합계"))

    return {
        "ts": ts,
        "idx":   {"J": _idx("J_price"), "Q": _idx("Q_price")},
        "hi_lo": {"J": _hilo(j_bars), "Q": _hilo(q_bars)},
        "inv":   {"J": _inv("J_investor"), "Q": _inv("Q_investor")},
        "prog":  {"J": _prog("J_prog"), "Q": _prog("Q_prog")},
        "nq":    {"rate": _f((mf.get("NQ") or {}).get("change_rate"))},
        "sect":  {s.get("name"): _f(s.get("avg_rate")) for s in (sectors or []) if s.get("name")},
    }


def detect_flow(prev: dict, curr: dict) -> list[dict]:
    """투자자 부호전환 + 프로그램 급변. 첫런(prev=None)은 침묵."""
    if not prev:
        return []
    out = []
    for mkt in ("J", "Q"):
        for who in ("외인", "기관"):
            p = (prev.get("inv", {}).get(mkt, {}) or {}).get(who, 0.0)
            c = (curr.get("inv", {}).get(mkt, {}) or {}).get(who, 0.0)
            if p and c and _sign(p) != _sign(c) and abs(c) >= MIN_INVESTOR_TURN_MW:
                side = "순매수" if c > 0 else "순매도"
                nm = "코스피" if mkt == "J" else "코스닥"
                out.append({"type": "investor_flip", "market": mkt, "major": True,
                            "value": c,
                            "label": f"{nm} {who} {('순매도→' if c>0 else '순매수→')}{side} 전환"})
        p = prev.get("prog", {}).get(mkt, 0.0)
        c = curr.get("prog", {}).get(mkt, 0.0)
        flip = (p and c and _sign(p) != _sign(c) and abs(c) >= PROG_FLIP_MIN_MW)
        jump = abs(c - p) >= PROG_JUMP_MW
        if flip or jump:
            nm = "코스피" if mkt == "J" else "코스닥"
            eok = round(c / 100)   # 백만원 → 억
            out.append({"type": "prog_shift", "market": mkt, "major": bool(flip),
                        "value": c, "label": f"{nm} 프로그램 순매수 {eok:+,}억"})
    return out


def detect_index(prev: dict, curr: dict, legstate: dict) -> list[dict]:
    """지수 신고/신저/반등/되돌림. legstate로 leg당 1회. 첫런 침묵."""
    if not prev:
        return []
    out = []
    for mkt in ("J", "Q"):
        c = curr.get("idx", {}).get(mkt, {}) or {}
        hl_prev = prev.get("hi_lo", {}).get(mkt, {}) or {}
        price = c.get("price", 0.0)
        if price <= 0:
            continue
        nm = "코스피" if mkt == "J" else "코스닥"
        ph, pl = hl_prev.get("day_high", 0.0), hl_prev.get("day_low", 0.0)
        if ph > 0 and price > ph * (1 + IDX_NEWHIGH_MARGIN):
            out.append({"type": "index_newhigh", "market": mkt, "major": False,
                        "label": f"{nm} 장중 신고가 경신"})
            legstate[f"{mkt}_leg"] = "up"
        elif pl > 0 and price < pl * (1 - IDX_NEWHIGH_MARGIN):
            out.append({"type": "index_newlow", "market": mkt, "major": False,
                        "label": f"{nm} 장중 신저가 경신"})
            legstate[f"{mkt}_leg"] = "down"
        # 반등: 저점 대비 +REBOUND, 이 저점 기준 아직 반등 미발동
        if pl > 0 and price >= pl * (1 + IDX_REBOUND_PCT) and legstate.get(f"{mkt}_reb") != pl:
            out.append({"type": "index_rebound", "market": mkt, "major": True,
                        "label": f"{nm} 저점 대비 +{IDX_REBOUND_PCT*100:.1f}% 반등, 낙폭 만회"})
            legstate[f"{mkt}_reb"] = pl
        # 되돌림: 고점 대비 -PULLBACK
        if ph > 0 and price <= ph * (1 - IDX_PULLBACK_PCT) and legstate.get(f"{mkt}_pb") != ph:
            out.append({"type": "index_pullback", "market": mkt, "major": True,
                        "label": f"{nm} 고점 대비 -{IDX_PULLBACK_PCT*100:.1f}% 되돌림, 상승분 반납"})
            legstate[f"{mkt}_pb"] = ph
    return out


def detect_nq(prev: dict, curr: dict) -> list[dict]:
    if not prev:
        return []
    p = prev.get("nq", {}).get("rate", 0.0)
    c = curr.get("nq", {}).get("rate", 0.0)
    out = []
    if abs(c - p) >= NQ_DELTA_PP:
        out.append({"type": "nq_move", "major": False,
                    "label": f"나스닥선물 {c:+.2f}% (직전 대비 {c-p:+.2f}%p)"})
    else:
        for lv in NQ_ABS_LEVELS:
            if (p < lv <= c) or (p > -lv >= c):
                out.append({"type": "nq_move", "major": True,
                            "label": f"나스닥선물 {c:+.2f}% (±{lv:.0f}% 돌파)"})
                break
    return out


def _slope(vals):
    """마지막 4개 값의 단순 기울기(첫→끝 변화율 %). 값 부족 시 0."""
    v = [x for x in (vals or [])[-4:] if x]
    if len(v) < 2 or not v[0]:
        return 0.0
    return (v[-1] - v[0]) / v[0] * 100


def detect_decouple(j_bars: list, nq_bars: list) -> list[dict]:
    """우리지수(bars: [{price}]) vs NQ(bars: [float]) 슬로프 부호 엇갈림."""
    js = _slope([_f(b.get("price")) for b in (j_bars or [])])
    ns = _slope([_f(x) for x in (nq_bars or [])])
    if abs(js) < DECOUPLE_MIN_SLOPE_PP or abs(ns) < DECOUPLE_MIN_SLOPE_PP:
        return []
    if _sign(js) == _sign(ns):
        return []
    if ns > 0 and js < 0:
        return [{"type": "decouple", "major": True,
                 "label": "미선물은 오르는데 코스피 약세 — 디커플링"}]
    return [{"type": "decouple", "major": True,
             "label": "미선물 약세인데 코스피 버팀 — 디커플링"}]


def detect_sector(prev: dict, curr: dict, sectors_full: list) -> list[dict]:
    """섹터 직전 대비 급변(+/-2%p) 감지 + top_movers 동봉. news 매칭은 오케스트레이터에서."""
    if not prev:
        return []
    ps = prev.get("sect", {}) or {}
    out = []
    full_by = {s.get("name"): s for s in (sectors_full or [])}
    for name, cav in (curr.get("sect", {}) or {}).items():
        pav = ps.get(name)
        if pav is None:
            continue
        delta = cav - pav
        if abs(delta) >= SECTOR_SURGE_PP:
            full = full_by.get(name, {})
            movers = sorted(
                [{"name": st.get("name"), "rate": _f(st.get("change_rate"))}
                 for st in (full.get("stocks") or []) if _f(st.get("price")) > 0],
                key=lambda m: m["rate"], reverse=True)[:3]
            arrow = "급등" if delta > 0 else "급락"
            out.append({"type": "sector_surge", "sector": name, "delta": round(delta, 1),
                        "avg": round(cav, 1), "major": True, "top_movers": movers,
                        "label": f"{name} 직전 대비 {delta:+.1f}%p {arrow}"})
    return out


def detect_all(prev, curr, sectors_full, j_bars, nq_bars, phase, state) -> list[dict]:
    """페이즈별 디텍터 실행 + 이벤트타입 쿨다운. state={'cooldown':{}, 'leg':{}}."""
    cooldown = state.setdefault("cooldown", {})
    leg = state.setdefault("leg", {})
    evs = []
    if phase in ("intraday", "premarket", "premarket_nxt", "afterhours", "afterhours_night"):
        if phase == "intraday":
            evs += detect_flow(prev, curr)
            evs += detect_index(prev, curr, leg)
            evs += detect_sector(prev, curr, sectors_full)
        evs += detect_nq(prev, curr)
        evs += detect_decouple(j_bars, nq_bars)
    now = _time.time()
    passed = []
    for e in evs:
        key = e.get("type") + ":" + str(e.get("market", "") or e.get("sector", ""))
        last = cooldown.get(key, 0)
        if now - last >= EVENT_RECOOLDOWN_S:
            cooldown[key] = now
            passed.append(e)
    return passed


def flag_noise(event: dict, snaps_after: list) -> bool:
    """발동 후 스냅샷들에서 지표가 임계 아래로 되돌아가거나 반대전환이면 True(의심노이즈).
    Phase0 관측용 근사치 — 최종 판단은 운영자."""
    if not snaps_after:
        return False
    t = event.get("type")
    if t == "investor_flip":
        mkt, val = event.get("market"), event.get("value", 0)
        for s in snaps_after:
            back = (s.get("inv", {}).get(mkt, {}) or {}).get("외인", 0)
            if val and _sign(back) != _sign(val):
                return True
    if t == "sector_surge":
        name = event.get("sector")
        base = event.get("avg", 0) - event.get("delta", 0)
        for s in snaps_after:
            if abs(s.get("sect", {}).get(name, base) - base) < SECTOR_SURGE_PP / 2:
                return True
    return False
