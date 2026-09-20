"""API 키·무음 폴백·실패율(B-44, 사장님 제보 ④). 재판정하지 않는다(설계 D15) —
api_health.verdict()의 level·problems를 그대로 이력으로 남긴다."""
from shopping_shorts import api_health
from shopping_shorts.checks.verdict import Sample

META = {"name": "API 키·무음 폴백·실패 상태", "every": "15m", "source": "api_health.verdict()"}


def measure(ctx):
    try:
        snap = api_health.snapshot()
        v = api_health.verdict(snap=snap, agg=api_health.aggregates(hours=1))
    except Exception as e:  # noqa: BLE001
        return [Sample("h_api_keys", META["name"], None, None, detail=repr(e))]
    level = v.get("level", "unknown")
    detail = v.get("msg", "") + (" | " + "; ".join(v.get("problems", [])) if v.get("problems") else "")
    ok = None if level == "unknown" else level == "ok"
    return [Sample("h_api_keys", META["name"], {"ok": 0, "warn": 1, "danger": 2}.get(level), ok,
                   detail=detail[:500], evidence_url="/apiwatch")]
