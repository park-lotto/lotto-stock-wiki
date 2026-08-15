"""캔들에서 '차트 도형'을 숫자로 뽑는다 — AI에게 그림을 보여주지 않기 위해서.

## 왜 이렇게 하나

"하락채널 상단 돌파 후 눌림, 저항 27만 부근" 같은 말을 하려면 AI가 차트를 봐야
할 것 같지만, 그럴 필요가 없다. **코드가 먼저 도형을 뽑고, 그 도형을 글로 적어
넘기면** LLM은 픽셀 없이도 같은 문장을 만든다. 화면 오버레이도 같은 좌표로 그린다.

## ★ 신뢰도를 3층으로 갈라야 한다

    A 사실   이평 배열·RSI·구간 위치·거래대금비·"이 가격을 N번 닿았다"·"이 날 돌파"
             → 반박 불가. 여기서 나오는 말은 안전하다.
    B 계산   추세선·채널 → 파라미터에 좌우된다. **R²를 반드시 함께** 준다.
    C 이름   역헤드앤숄더·컵앤핸들 → 사람마다 다르게 그린다. 오탐이 많다.

**이 모듈은 A와 B만 만든다.** C(패턴 이름)는 일부러 넣지 않았다 — 한 번 잘못
"역헤드앤숄더"라고 말하는 순간 서비스 신뢰가 통째로 무너지기 때문이다.
실측(2026-08-15 삼성전자): 같은 '추세선'인데 고점 연결은 R²=0.15, 저점 연결은
R²=0.97이었다. R² 없이 둘 다 "추세선"이라 부르면 거짓말이 된다.

## 스파이크에서 고친 것

- 스윙이 68개나 잡혀 잔파동까지 도형이 됐다 → 반전 임계를 올리고 최근 구간만 본다
- 지지선에 현재가 -62%짜리 옛 가격이 섞였다 → 현재가 기준 ±25% 밖은 버린다
"""
from __future__ import annotations

# 스윙으로 인정할 최소 반전폭. 낮추면 잔파동까지 도형이 되고, 높이면 큰 그림만 남는다.
SWING_PCT = 0.07
# 지지·저항으로 쓸 가격 범위(현재가 대비). 너무 먼 값은 지금 판단에 쓸모가 없다.
LEVEL_NEAR = 0.25
# 같은 지지·저항으로 묶을 폭(현재가 대비)
LEVEL_BAND = 0.025
# 추세선을 그릴 때 쓰는 최근 스윙 개수
TREND_PTS = 4


def _zigzag(high: list, low: list, pct: float = SWING_PCT) -> list:
    """[(idx, price, +1 고점 / -1 저점)] — pct 이상 반전할 때만 전환점으로 본다."""
    if len(high) < 3:
        return []
    piv, dirn = [], 0
    last_i, last_p = 0, (high[0] + low[0]) / 2
    for i in range(1, len(high)):
        if dirn >= 0 and low[i] < last_p * (1 - pct):
            piv.append((last_i, high[last_i], 1)); dirn, last_i, last_p = -1, i, low[i]
        elif dirn <= 0 and high[i] > last_p * (1 + pct):
            piv.append((last_i, low[last_i], -1)); dirn, last_i, last_p = 1, i, high[i]
        elif dirn >= 0 and high[i] > last_p:
            last_i, last_p = i, high[i]
        elif dirn <= 0 and low[i] < last_p:
            last_i, last_p = i, low[i]
    return piv


def _fit(points: list) -> dict | None:
    """[(x, y)] → 직선. R²를 함께 준다 — 이게 없으면 이 선을 믿을지 알 수 없다."""
    if len(points) < 3:
        return None
    n = len(points)
    sx = sum(x for x, _ in points); sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points); sxy = sum(x * y for x, y in points)
    den = n * sxx - sx * sx
    if den == 0:
        return None
    slope = (n * sxy - sx * sy) / den
    inter = (sy - slope * sx) / n
    mean = sy / n
    ss_tot = sum((y - mean) ** 2 for _, y in points)
    ss_res = sum((y - (slope * x + inter)) ** 2 for x, y in points)
    r2 = 1 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0
    return {"slope": slope, "inter": inter, "r2": round(r2, 2)}


def _ma(vals: list, w: int):
    return sum(vals[-w:]) / w if len(vals) >= w else None


def _rsi(vals: list, w: int = 14):
    if len(vals) < w + 1:
        return None
    d = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    g = [x if x > 0 else 0 for x in d]; l = [-x if x < 0 else 0 for x in d]
    ag, al = sum(g[:w]) / w, sum(l[:w]) / w
    for i in range(w, len(d)):
        ag = (ag * (w - 1) + g[i]) / w
        al = (al * (w - 1) + l[i]) / w
    return round(100 - 100 / (1 + ag / al), 0) if al > 1e-9 else 100.0


def analyze(candles: list) -> dict:
    """캔들 → {ma, rsi, pos, volx, levels[], trends{}, breakout}

    모든 좌표는 candles의 **인덱스**로 준다 — 화면이 그대로 x좌표로 쓴다.
    """
    if len(candles) < 30:
        return {"error": "캔들이 부족합니다"}

    close = [c.get("close") or 0 for c in candles]
    high = [c.get("high") or 0 for c in candles]
    low = [c.get("low") or 0 for c in candles]
    vol = [c.get("value") or 0 for c in candles]
    n = len(close)
    now = close[-1]

    # ── A층: 반박 불가능한 사실들 ──────────────────────────────
    m5, m20, m60 = _ma(close, 5), _ma(close, 20), _ma(close, 60)
    order = ""
    if m5 and m20 and m60:
        order = ("정배열" if m5 > m20 > m60 else
                 "역배열" if m5 < m20 < m60 else "혼조")
    lo, hi = min(low), max(high)
    v_recent = sum(vol[-5:]) / 5 if len(vol) >= 5 else 0
    v_base = sum(vol[-60:]) / min(60, len(vol))

    # ── 지지·저항: 스윙이 여러 번 닿은 가격대 ───────────────────
    piv = _zigzag(high, low)
    band = now * LEVEL_BAND
    groups: list[list[float]] = []
    for _, p, _k in sorted(piv, key=lambda t: t[1]):
        if groups and abs(p - groups[-1][-1]) < band:
            groups[-1].append(p)
        else:
            groups.append([p])
    levels = []
    for gp in groups:
        if len(gp) < 2:
            continue
        price = sum(gp) / len(gp)
        dist = (price / now - 1) if now else 0
        if abs(dist) > LEVEL_NEAR:      # 너무 먼 값은 지금 판단에 쓸모가 없다
            continue
        levels.append({
            "price": round(price),
            "touches": len(gp),
            "kind": "저항" if price > now else "지지",
            "dist_pct": round(dist * 100, 1),
        })
    levels.sort(key=lambda d: (-d["touches"], abs(d["dist_pct"])))
    levels = levels[:4]

    # ── B층: 추세선 (R² 필수) ─────────────────────────────────
    highs = [(i, p) for i, p, k in piv if k > 0][-TREND_PTS:]
    lows = [(i, p) for i, p, k in piv if k < 0][-TREND_PTS:]
    trends = {}
    for name, pts in (("high", highs), ("low", lows)):
        f = _fit(pts)
        if not f:
            continue
        x0, x1 = pts[0][0], n - 1
        y1 = f["slope"] * x1 + f["inter"]
        gap = ((now / y1 - 1) * 100) if y1 else 0
        last_swing = pts[-1][0]
        # ★쓸 수 있는 선인지 함께 판정한다.
        #   실측(2026-08-15 현대차): 저점 연결선 R²=0.99인데 현재가와 +81.8% 벌어졌다.
        #   적합도가 아무리 좋아도 지금 가격에서 그렇게 멀면 판단에 못 쓴다 —
        #   과거 스윙에 맞춘 기울기를 현재까지 외삽하면서 벌어진 것이다.
        usable = (f["r2"] >= 0.5) and (abs(gap) <= 30) and ((n - 1 - last_swing) <= 60)
        trends[name] = {
            "r2": f["r2"],
            "dir": "하락" if f["slope"] < 0 else "상승",
            "x0": x0, "y0": round(f["slope"] * x0 + f["inter"]),
            "x1": x1, "y1": round(y1),
            "gap_pct": round(gap, 1),
            "pts": len(pts),
            "last_swing_ago": n - 1 - last_swing,
            "usable": usable,
            "why_not": ("" if usable else
                        ("적합도 낮음" if f["r2"] < 0.5 else
                         "현재가에서 너무 멂" if abs(gap) > 30 else "최근 스윙이 오래됨")),
        }

    # ── 하락추세선 돌파와 그 뒤 눌림 ───────────────────────────
    breakout = None
    t = trends.get("high")
    if t and t["dir"] == "하락":
        sl = (t["y1"] - t["y0"]) / max(1, (t["x1"] - t["x0"]))
        line = [t["y0"] + sl * (i - t["x0"]) for i in range(n)]
        above = [close[i] > line[i] for i in range(n)]
        cross = [i for i in range(max(1, t["x0"]), n) if above[i] and not above[i - 1]]
        if cross:
            i = cross[-1]
            peak_i = i + max(range(len(close[i:])), key=lambda k: close[i + k])
            breakout = {
                "idx": i, "date": candles[i]["time"],
                "close": close[i], "line": round(line[i]),
                "peak_date": candles[peak_i]["time"], "peak": close[peak_i],
                "pullback_pct": round((now / close[peak_i] - 1) * 100, 1),
            }

    return {
        "ma": {"m5": round(m5) if m5 else None, "m20": round(m20) if m20 else None,
               "m60": round(m60) if m60 else None, "order": order},
        "rsi": _rsi(close),
        "pos": round((now - lo) / (hi - lo) * 100) if hi > lo else 50,
        "range": {"low": round(lo), "high": round(hi)},
        "volx": round(v_recent / v_base, 2) if v_base else None,
        "levels": levels,
        "trends": trends,
        "breakout": breakout,
        "swings": len(piv),
    }


def describe(ta: dict) -> list:
    """구조를 사람 문장으로. LLM에 넘길 때도, 화면에 띄울 때도 이걸 쓴다."""
    if not ta or ta.get("error"):
        return []
    out = []
    ma = ta.get("ma") or {}
    if ma.get("order"):
        out.append(f"이평 {ma['order']} (5일 {ma['m5']:,} · 20일 {ma['m20']:,} · 60일 {ma['m60']:,})")
    if ta.get("rsi") is not None:
        out.append(f"RSI {ta['rsi']:.0f}")
    if ta.get("pos") is not None:
        out.append(f"구간 위치 {ta['pos']}%")
    if ta.get("volx"):
        out.append(f"최근 5일 거래대금이 60일 평균의 {ta['volx']*100:.0f}%")
    for lv in (ta.get("levels") or [])[:3]:
        out.append(f"{lv['kind']} {lv['price']:,} — {lv['touches']}회 접촉 ({lv['dist_pct']:+.1f}%)")
    for k, t in (ta.get("trends") or {}).items():
        nm = "고점 연결선" if k == "high" else "저점 연결선"
        # R²를 반드시 붙인다. 이게 없으면 믿을 선인지 알 수 없다.
        # 못 쓰는 선은 이유를 달아 말한다 — 조용히 빼면 왜 없는지 알 수 없다.
        tail = "" if t.get("usable") else f" ⚠️{t.get('why_not')}"
        out.append(f"{nm}: {t['dir']} (R²={t['r2']}, 종가와 {t['gap_pct']:+.1f}%){tail}")
    b = ta.get("breakout")
    if b:
        pb = b["pullback_pct"]
        # 돌파 후 최고점이 지금이면 눌림이 아니라 '고점 부근'이다.
        state = ("돌파 후 고점 부근" if pb >= -0.5 else f"이후 고점 대비 {pb:+.1f}% 눌림")
        out.append(f"하락추세선 돌파 {b['date']} 종가 {b['close']:,.0f} (선 {b['line']:,}) → {state}")
    return out
