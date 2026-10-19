"""시안 v3 데이터 — 스냅샷 2장 + 분류(cat·wow·kw) + 키워드 지표(검색수·추세·유튜브)를 합쳐 점수를 매긴다."""
import json, math, sys
sys.stdout.reconfigure(encoding="utf-8")
A = json.load(open("snaps/20261019_2015.json", encoding="utf-8"))
B = json.load(open("snaps/20261019_2113.json", encoding="utf-8"))
HRS = (B["at"] - A["at"]) / 3600
EN = json.load(open("enrich.json", encoding="utf-8"))

# 상품명 → 분류
CLS = {}
for k, f in ((0, "cls2_0_v2.json"), (1, "cls2_1.json"), (2, "cls2_2.json")):
    c = json.load(open(f, encoding="utf-8"))
    for line in open(f"titles2_{k}.tsv", encoding="utf-8").read().split("\n"):
        i, _, t = line.split("\t", 2)
        if i in c: CLS[t.strip()] = c[i]
old_c = json.load(open("classified.json", encoding="utf-8"))
for line in open("titles.tsv", encoding="utf-8").read().split("\n"):
    i, t = line.split("\t", 1)
    if i in old_c and t.strip() not in CLS:
        CLS[t.strip()] = dict(old_c[i], wow=None, kw="")

prev = {(x["id"], x["list"]): x for x in A["items"]}
items, seen = [], set()
for x in B["items"]:
    key = (x["id"], x["list"])
    if x["id"] in seen: continue            # 같은 상품이 여러 목록에 있으면 처음 것만
    seen.add(x["id"])
    c = CLS.get(x["title"].strip(), {"cat": "제외", "why": "미분류", "wow": 0, "kw": ""})
    m, o = x["m"], (prev.get(key) or {}).get("m", {})
    r = {"site": x["site"], "list": x["list"], "rank": x["rank"], "title": x["title"], "img": x["img"], "price": x["price"],
         "url": x["url"], "cat": c["cat"], "why": c.get("why", ""), "wow": c.get("wow"), "kw": c.get("kw") or "", "ad": x["ad"], "tags": []}
    if x["ad"]:
        r["cat"], r["why"] = "제외", "광고 상품"
    speed = None
    if x["site"] == "temu" and m.get("sold") is not None:
        d = (m["sold"] - o["sold"]) if o.get("sold") is not None else None
        if d is not None: speed = d / HRS; r["tags"].append(f"🔥 시간당 +{round(speed)} 판매")
        r["tags"].append(f"누적 {m['sold']:,}")
        if m.get("badge"): r["tags"].append(m["badge"])
    elif x["site"] == "1688":
        ms, mom = m.get("month_sales") or 0, str(m.get("mom") or "-")
        speed = ms / 720                     # 월 판매 → 시간당
        r["tags"].append(f"📦 월 {ms:,}개")
        if mom not in ("-", ""): r["tags"].append(f"📈 전월比 {mom}")
        if m.get("released"): r["tags"].append(m["released"])
        r["mom"] = int(mom.rstrip("%+").replace(",", "")) if mom.rstrip("%+").replace(",", "").isdigit() else None
    elif x["site"] == "amazon":
        d = (m["reviews"] - o["reviews"]) if m.get("reviews") is not None and o.get("reviews") is not None else None
        if d: r["tags"].append(f"리뷰 시간당 +{d}")
        if m.get("reviews"): r["tags"].append(f"⭐ {m.get('score')} · 리뷰 {m['reviews']:,}")
        speed = (d or 0) * 30                # 리뷰 1개 ≈ 판매 30개(강사 공식)
    elif x["site"] == "naver":
        r["tags"].append(f"{x['list']} 구매순 {x['rank']}위")
        if m.get("reviews"): r["tags"].append(f"⭐ {m.get('score')} · 리뷰 {m['reviews']:,}{'+' if m['reviews'] >= 99999 else ''}")
        speed = max(0, 101 - x["rank"]) / 10
    r["speed"] = speed
    e = EN.get(r["kw"], {})
    r["search"], r["trend"], r["vs_peak"], r["yt_med"], r["yt_sum"] = e.get("search_month"), e.get("trend_up"), e.get("vs_peak"), e.get("yt_views_med"), e.get("yt_views_sum")
    items.append(r)

# 점수: 사이트 안 판매속도 백분위 · 검색수(로그) · 신박함 · 쇼츠 기회(검색 많은데 영상 조회 적음)
def pct(vals):
    s = sorted(v for v in vals if v is not None)
    return lambda v: (sum(1 for t in s if t <= v) / len(s)) if (v is not None and s) else 0
by_site = {}
for r in items: by_site.setdefault(r["site"], []).append(r["speed"])
P = {k: pct(v) for k, v in by_site.items()}
for r in items:
    sp = P[r["site"]](r["speed"])
    dem = min(1, math.log10((r["search"] or 1)) / 5)                  # 10만 = 1.0
    if r["trend"] is not None and r["trend"] > 10: dem = min(1, dem + 0.1)
    wow = (r["wow"] or 0) / 3
    opp = 0
    if r["search"] and r["yt_sum"] is not None:
        opp = max(0, min(1, (math.log10(r["search"] + 1) - math.log10(r["yt_sum"] / 1000 + 1)) / 4 + 0.5))
    r["sc"] = {"speed": round(sp * 100), "demand": round(dem * 100), "wow": round(wow * 100), "opp": round(opp * 100)}
    r["sc"]["total"] = round(0.35 * sp * 100 + 0.25 * dem * 100 + 0.25 * wow * 100 + 0.15 * opp * 100)

ok = [r for r in items if r["cat"] != "제외"]
print("전체", len(items), "쇼츠 가능", len(ok), "광고 제외", sum(r["ad"] for r in items))
for s in ("naver", "1688", "temu", "amazon"):
    v = [r for r in ok if r["site"] == s]
    print(s, len(v), "| 상위:", [(r["kw"] or r["title"][:12], r["sc"]["total"]) for r in sorted(v, key=lambda r: -r["sc"]["total"])[:4]])
json.dump(items, open("v3_data.json", "w", encoding="utf-8"), ensure_ascii=False)
