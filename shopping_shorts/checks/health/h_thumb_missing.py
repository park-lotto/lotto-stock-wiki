"""썸네일이 안 나오는 플랫폼(B-43, 사장님 제보 ⑤). 카드는 전부 /api/thumb?url=(app.py:9013)을
거치므로 최신 items 30건의 thumbnail을 실제로 받아 본다. 사유를 상태코드로 분류."""
import json
import urllib.parse
import requests
from shopping_shorts.checks.ro import ro_connect
from shopping_shorts.checks.verdict import Sample
from shopping_shorts.checks.health.h_ranking_fresh import PLATFORMS

META = {"name": "썸네일이 안 나오는 플랫폼", "every": "6h", "source": "/api/thumb 실응답"}
SAMPLE_N = 30
MAX_MISSING = 0.10


def measure(ctx):
    base = ctx.get("base_url")
    if not base:
        return [Sample("h_thumb_missing", META["name"], None, None, detail="base_url 없음(HTTP 필요)")]
    try:
        conn = ro_connect(ctx["live_db"])
    except Exception as e:  # noqa: BLE001
        return [Sample("h_thumb_missing", META["name"], None, None, detail=repr(e))]
    out = []
    try:
        for p in PLATFORMS + ("instagram",):
            if p == "instagram":
                row = conn.execute("SELECT items_json AS v FROM last_run WHERE id=1").fetchone()
                items = json.loads(row["v"]) if row else []
            else:
                row = conn.execute("SELECT value AS v FROM settings WHERE key=?", (f"last_run::{p}",)).fetchone()
                items = json.loads(row["v"]).get("items", []) if row and row["v"] else []
            urls = [it.get("thumbnail") for it in items[:SAMPLE_N] if it.get("thumbnail")]
            if not urls:
                out.append(Sample(f"h_thumb_missing::{p}", f"{META['name']} — {p}", None, None, detail="표본 없음"))
                continue
            codes = {}
            for u in urls:
                try:
                    r = requests.get(f"{base}/api/thumb?url={urllib.parse.quote(u, safe='')}", timeout=8,
                                     cookies=ctx.get("cookies") or {})
                    codes[r.status_code] = codes.get(r.status_code, 0) + 1
                except requests.RequestException:
                    codes["timeout"] = codes.get("timeout", 0) + 1
            miss = sum(v for k, v in codes.items() if k != 200) / len(urls)
            out.append(Sample(f"h_thumb_missing::{p}", f"{META['name']} — {p}", round(miss * 100, 1),
                              miss < MAX_MISSING, detail=f"{len(urls)}장 중 사유 {codes}"))
    finally:
        conn.close()
    return out
