# -*- coding: utf-8 -*-
"""숙소 후기 전부 받기 → 꿀팁·볼거리·식사·서비스·주의·와우로 가르기 (관제 239, 숏폼·롱폼 공용 재료).

사용: py tools/travel/collect_reviews.py <여기어때 숙소 주소> <출력폴더>
출력: <출력폴더>/reviews.json (후기 원문 전부) · insights.json (review_insights 결과) · insights.html (사장님 보기용)
판단 주인: 수집 = travel_source.yeogi_reviews / 가르기 = travel_build.review_insights (1차 제미나이→끊기면 하이쿠, 합치기 오푸스)
"""
import html
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from shopping_shorts import travel_build as tb, travel_source as ts  # noqa: E402


def page(detail, ins, n_reviews):
    e = html.escape
    secs = ""
    for c in tb.REVIEW_CATS:
        rows = "".join("<tr><td class=n>%s명</td><td><b>%s</b><div class=q>“%s”</div></td></tr>" % (
            x.get("count", "?"), e(x["item"]), e(x.get("quote", ""))) for x in ins.get(c, []))
        secs += "<h2>%s</h2><table>%s</table>" % (e(c), rows or "<tr><td>없음</td></tr>")
    m = ins.get("_meta", {})
    return """<!doctype html><html lang=ko><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>숙소 후기 분석</title><style>
:root{--bg:#f6f4ef;--card:#fff;--ink:#1d1b18;--sub:#6b655c;--line:#e6e1d8;--acc:#b5532d}
@media (prefers-color-scheme:dark){:root{--bg:#141311;--card:#1d1b19;--ink:#ece8e1;--sub:#a59e93;--line:#34302b;--acc:#e58a62}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,'Malgun Gothic',sans-serif;line-height:1.6}
.w{max-width:900px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0}h2{color:var(--acc);font-size:17px;margin:26px 0 8px}
.s{color:var(--sub);font-size:13px}table{width:100%%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px}
td{padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}.n{white-space:nowrap;color:var(--acc);font-weight:700;width:60px}
.q{color:var(--sub);font-size:13px}</style><div class=w><h1>%s 후기 분석</h1>
<div class=s>%s · 후기 %d개 전부 · 묶음 %s개(제미나이 %s · 하이쿠 %s · 실패 %s) · 합치기 오푸스</div>%s</div></html>""" % (
        e(detail.get("name", "")), e(detail.get("source_label", "")), n_reviews, m.get("chunks"),
        (m.get("map_by") or {}).get("gemini"), (m.get("map_by") or {}).get("haiku"), (m.get("map_by") or {}).get("fail"), secs)


def main():
    url, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    detail = ts.fetch(url)
    t = time.time()
    rv = ts.yeogi_reviews(detail["id"], on_page=lambda p, n: print("후기 %d쪽 %d개" % (p, n), flush=True) if p % 40 == 0 else None)
    (out / "reviews.json").write_text(json.dumps(rv, ensure_ascii=False), encoding="utf-8")
    print("후기 %d개 · %d초" % (len(rv), time.time() - t))
    ins = tb.review_insights(rv, progress=lambda i, n, by: print("묶음 %d/%d %s" % (i, n, by), flush=True))
    (out / "insights.json").write_text(json.dumps(ins, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "insights.html").write_text(page(detail, ins, len(rv)), encoding="utf-8")
    print("끝:", out / "insights.html", ins["_meta"])


if __name__ == "__main__":
    main()
