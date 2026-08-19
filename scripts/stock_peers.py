"""또래 종목 — "이 종목만 그런가, 업종이 다 그런가"를 가른다.

## 왜 필요한가

`/stock`은 지금 **한 종목만** 본다. 그래서 외국인이 팔면 그게 이 종목 얘기인지
업종 전체 얘기인지 알 수가 없다. 또래를 옆에 세우면 그 자리에서 갈린다.

## 또래를 어디서 얻나 (2026-08-15 실측으로 고름)

후보가 셋 있었는데 하나만 조건을 다 만족했다:

| 후보 | 종목수 | 코드 | 현대차 분류 | 판정 |
|---|---|---|---|---|
| **`watchlist.json`** | 444 | **있음** | **자동차/대형주** ✅ | **채택** |
| `sector_map.json` | 515 | 있음 | **로봇** ❌ | 테마 큐레이션이라 또래가 안 맞는다 |
| `pipeline/atoms/stock_sector_map.json` | 1463 | **없음** | 로봇 ❌ | 코드가 없어 시세를 못 붙인다 |

`watchlist.json`은 **섹터 → 서브섹터 → [{name, code}]** 3단이라 또래 묶음이 이미 들어있다.
git 추적 파일이라 서버에도 그대로 간다(생성기 `watchlist_parser.py`가 읽는 xlsx는 저장소에 없다
— 그래서 파서가 아니라 **결과 json**을 쓴다).

⚠️ **한 종목이 여러 섹터에 걸린다.** 현대차는 `자동차/대형주`(2개)에도 `로봇/기타`(4개)에도 있다.
테마로 끌어온 것(로봇)보다 **본업(자동차)**이 또래로 맞으므로, 섹터 우선순위를 둔다.

⚠️ **서브섹터가 너무 작다.** `자동차/대형주`는 현대차·기아 둘뿐이라 비교가 안 된다.
→ 모자라면 **부모 섹터로 넓힌다**(자동차 전체 34종목). 넓혔으면 화면에 그렇게 적는다.
"""
from __future__ import annotations

import json
import os

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WATCHLIST = os.path.join(_BASE, "watchlist.json")

# 또래로 보여줄 목표 개수. 너무 적으면 비교가 안 되고, 너무 많으면 화면이 표가 된다.
_TARGET = 12

# 테마로 끌어온 섹터보다 **본업 섹터**를 먼저 쓴다.
# 실측: 현대차가 '로봇/기타'에도 들어 있는데 로봇 또래를 보여주면 오해를 부른다.
_THEME_LAST = ("로봇", "우주", "신재생")

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            with open(_WATCHLIST, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}
    return _cache


def find_groups(code: str) -> list[dict]:
    """이 코드가 속한 (섹터, 서브섹터) 전부. 본업 섹터가 앞에 오도록 정렬."""
    code = (code or "").zfill(6)
    hits = []
    for sector, subs in _load().items():
        if not isinstance(subs, dict):
            continue
        for sub, lst in subs.items():
            if any((s.get("code") or "").zfill(6) == code for s in lst or []):
                hits.append({"sector": sector, "sub": sub, "n": len(lst)})
    hits.sort(key=lambda h: (h["sector"] in _THEME_LAST, -h["n"]))
    return hits


def peers(code: str, target: int = _TARGET) -> dict:
    """{found, sector, sub, scope, widened, peers:[{name, code}]}

    scope = '서브섹터' | '섹터' — **어느 범위로 비교하는지 화면에 반드시 적는다.**
    범위를 안 밝히면 "왜 얘가 또래야?"가 나온다.
    """
    code = (code or "").zfill(6)
    groups = find_groups(code)
    if not groups:
        return {"found": False, "peers": [], "reason": "관심종목 목록에 없는 종목입니다"}

    g = groups[0]
    data = _load()
    sub_list = data.get(g["sector"], {}).get(g["sub"], []) or []

    # 서브섹터가 목표보다 작으면 부모 섹터 전체로 넓힌다(넓혔다는 사실을 같이 돌려준다)
    widened = False
    pool = list(sub_list)
    if len(pool) < target:
        widened = True
        seen = {(s.get("code") or "").zfill(6) for s in pool}
        for sub, lst in (data.get(g["sector"]) or {}).items():
            if sub == g["sub"]:
                continue
            for s in lst or []:
                c = (s.get("code") or "").zfill(6)
                if c and c not in seen:
                    seen.add(c)
                    pool.append(s)

    out = []
    for s in pool:
        c = (s.get("code") or "").zfill(6)
        if not c or c == code:          # 자기 자신은 또래가 아니다
            continue
        out.append({"name": s.get("name") or "", "code": c})

    return {
        "found": True,
        "sector": g["sector"],
        "sub": g["sub"],
        "scope": "섹터" if widened else "서브섹터",
        "widened": widened,
        "also": [f'{h["sector"]}/{h["sub"]}' for h in groups[1:]],
        "peers": out[: max(1, target)],
    }


def compare(code: str, target: int = _TARGET) -> dict:
    """또래 + 각자 등락률. 시세는 KIS 멀티조회로 **한 번에** 받는다.

    반복 호출하면 종목 수만큼 왕복이 생긴다 — `get_prices_multi`가 이미 있으니 그걸 쓴다.
    """
    info = peers(code, target)
    if not info.get("found") or not info["peers"]:
        return info

    codes = [p["code"] for p in info["peers"]] + [code]
    try:
        import kis_api
        px = kis_api.get_prices_multi(codes)
    except Exception as e:
        info["error"] = f"{type(e).__name__}: {e}"
        return info

    # ★반환 키는 kis_api.get_prices_multi가 정한 것을 그대로 쓴다:
    #   {code: {"code","name","price","change_rate","change"}}
    # 필드명을 짐작해서 쓰면 값이 조용히 전부 None이 된다(실측으로 한 번 겪음).
    def _px(c: str) -> dict:
        return px.get(c) or px.get(c.zfill(6)) or {}

    def _rate(c: str):
        v = _px(c).get("change_rate")
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    rows = []
    for p in info["peers"]:
        r = _rate(p["code"])
        if r is not None:
            rows.append({
                "name": p["name"] or _px(p["code"]).get("name") or "",
                "code": p["code"],
                "rate": round(r, 2),
                "price": _px(p["code"]).get("price") or 0,
            })
    rows.sort(key=lambda x: x["rate"], reverse=True)

    me = _rate(code)
    rates = [r["rate"] for r in rows]
    avg = round(sum(rates) / len(rates), 2) if rates else None
    # 또래 중 몇 등인가 — '나만 빠지나'를 한 눈에
    rank = None
    if me is not None and rates:
        rank = sum(1 for r in rates if r > me) + 1

    info.update({
        "me": {"code": code, "rate": round(me, 2) if me is not None else None},
        "avg": avg,
        "rank": rank,
        "of": (len(rows) + 1) if rows else None,
        "rows": rows,
    })
    return info
