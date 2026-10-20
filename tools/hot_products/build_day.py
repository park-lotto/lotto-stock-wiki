"""하루 비교 빌드 — 최신 스냅샷과 그 전 스냅샷(12시간 이상 앞, 없으면 바로 앞)을 자동으로 골라 사이트별 '하루 변화'를 잰다.
build3.py(10-19 두 장 박아 넣은 시안용)를 대신한다. 출력 꼴은 v3_data.json 과 같다 → build4.py 가 그대로 읽는다.

사이트별 판매 속도(같은 사이트 안 백분위로 정렬):
  테무  = 누적 판매 증가 ÷ 시간            (실제 판매수)
  1688  = 월 판매량 (+ 하루 사이 월판매 증가) (실제 판매수)
  아마존 = 리뷰 증가 ÷ 시간 × 30            (리뷰 1개 ≈ 판매 30개, 강사 공식)
  네이버 = 구매순 순위(높을수록) + 순위 상승 가산, 리뷰 증가 표시
  쿠팡  = 카테고리 베스트 순위 + 순위 상승 가산 (쿠팡은 판매수를 안 준다)
분류: 10-19 사람 라벨(work/cls2_*·classified) → 이미 자동 분류한 것(work/cls_auto.json) → 처음 보는 상품만 classify.py
실행: cd work && py -I ../build_day.py   → work/day_data.json (+ 새 키워드는 work/kws.json 에 덧붙임 → enrich.py)"""
import glob, json, os, sys
sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__)); W = os.path.join(HERE, "work")
sys.path.insert(0, HERE)
import classify, gkeys

def snaps(prefix):
    fs = sorted(glob.glob(os.path.join(W, "snaps", prefix)))
    return [json.load(open(f, encoding="utf-8")) for f in fs]

def pick(ss):
    """최신 B, 그리고 B 보다 12시간 이상 앞선 것 중 가장 늦은 A(없으면 바로 앞)"""
    if not ss: return None, None
    B = ss[-1]; older = [s for s in ss[:-1] if B["at"] - s["at"] >= 12 * 3600]
    return (older[-1] if older else (ss[-2] if len(ss) > 1 else None)), B

main = [s for s in snaps("2*.json")]; cps = snaps("cp_*.json")
A, B = pick(main); CA, CB = pick(cps)
pairs = [(A, B)] + ([(CA, CB)] if CB else [])
print("비교:", [(a["ts"] if a else None, b["ts"]) for a, b in pairs])

# 분류 — 사람 라벨 → 자동 분류 캐시 → 새로 분류
CLS = {t.strip(): lab for t, _, lab in classify.labeled()}
old_c = json.load(open(os.path.join(W, "classified.json"), encoding="utf-8"))
for line in open(os.path.join(W, "titles.tsv"), encoding="utf-8").read().split("\n"):
    i, t = line.split("\t", 1)
    if i in old_c and t.strip() not in CLS: CLS[t.strip()] = dict(old_c[i], wow=None, kw="")
AUTO_P = os.path.join(W, "cls_auto.json")
AUTO = json.load(open(AUTO_P, encoding="utf-8")) if os.path.exists(AUTO_P) else {}
todo = {}
for _, b in pairs:
    for x in b["items"]:
        t = x["title"].strip()
        need_kw = t in CLS and CLS[t]["cat"] != "제외" and not CLS[t].get("kw")      # 첫 분류(classified.json)는 키워드가 없다 → 키워드만 받는다
        if t and (t not in CLS or need_kw) and t not in AUTO: todo[t] = {"id": t, "title": t, "list": x["list"]}
if todo:
    print("처음 보는 상품 분류", len(todo))
    AUTO.update(classify.classify(list(todo.values()), classify.examples(classify.labeled()), gkeys.gemini_keys()))
    json.dump(AUTO, open(AUTO_P, "w", encoding="utf-8"), ensure_ascii=False)

EN = json.load(open(os.path.join(W, "enrich.json"), encoding="utf-8"))
items, seen = [], set()
for a, b in pairs:
    hrs = (b["at"] - a["at"]) / 3600 if a else None
    prev = {(x["id"], x["list"]): x for x in (a["items"] if a else [])}
    prev_any = {x["id"]: x for x in (a["items"] if a else [])}
    for x in b["items"]:
        if x["id"] in seen: continue                          # 같은 상품이 여러 목록에 있으면 처음 것만
        seen.add(x["id"])
        t = x["title"].strip(); c = CLS.get(t) or AUTO.get(t) or {"cat": "제외", "why": "미분류", "wow": 0, "kw": ""}
        if not c.get("kw") and t in AUTO: c = dict(c, kw=AUTO[t].get("kw", ""), wow=c.get("wow") if c.get("wow") is not None else AUTO[t].get("wow"))   # 분류는 사람 것, 키워드만 자동
        o_item = prev.get((x["id"], x["list"])) or {}; o = o_item.get("m", {}); m = x["m"]
        r = {"site": x["site"], "list": x["list"], "rank": x["rank"], "title": x["title"], "img": x["img"], "price": x["price"], "url": x["url"],
             "cat": c["cat"], "why": c.get("why", ""), "wow": c.get("wow"), "kw": c.get("kw") or "", "ad": x["ad"], "tags": [],
             "new": a is not None and x["id"] not in prev_any, "rank_up": None}
        if x["ad"]: r["cat"], r["why"] = "제외", "광고 상품"
        if o_item.get("rank") and x.get("rank"): r["rank_up"] = o_item["rank"] - x["rank"]
        speed = None
        if x["site"] == "temu" and m.get("sold") is not None:
            if o.get("sold") is not None and hrs:
                speed = (m["sold"] - o["sold"]) / hrs; r["tags"].append(f"🔥 하루 +{round(speed * 24):,} 판매")
            r["tags"].append(f"누적 {m['sold']:,}")
        elif x["site"] == "1688":
            ms, mom = m.get("month_sales") or 0, str(m.get("mom") or "-")
            speed = ms / 720; r["tags"].append(f"📦 월 {ms:,}개")
            if o.get("month_sales") is not None and ms - o["month_sales"]: r["tags"].append(f"하루 {ms - o['month_sales']:+,}")
            if mom not in ("-", ""): r["tags"].append(f"📈 전월比 {mom}")
        elif x["site"] == "amazon":
            d = (m["reviews"] - o["reviews"]) if m.get("reviews") is not None and o.get("reviews") is not None else None
            if d and hrs: r["tags"].append(f"리뷰 하루 +{round(d / hrs * 24):,}"); speed = d / hrs * 30
            else: speed = 0
            if m.get("reviews"): r["tags"].append(f"⭐ {m.get('score')} · 리뷰 {m['reviews']:,}")
        elif x["site"] in ("naver", "coupang"):
            speed = max(0, 101 - (x["rank"] or 100)) / 10 + max(0, r["rank_up"] or 0) / 5
            arrow = "" if r["rank_up"] in (None, 0) else (f" ▲{r['rank_up']}" if r["rank_up"] > 0 else f" ▼{-r['rank_up']}")
            r["tags"].append(f"{x['list']} {x['rank']}위{arrow}" + (" 🆕" if r["new"] else ""))
            if x["site"] == "naver" and m.get("reviews"):
                dr = (m["reviews"] - o["reviews"]) if o.get("reviews") is not None and m["reviews"] < 99999 else None
                r["tags"].append(f"리뷰 {m['reviews']:,}{'+' if m['reviews'] >= 99999 else ''}" + (f" (하루 +{dr:,})" if dr else ""))
        r["speed"] = speed
        e = EN.get(r["kw"], {})
        r["search"], r["trend"] = e.get("search_month"), e.get("trend_up")
        items.append(r)

def pct(vals):
    s = sorted(v for v in vals if v is not None)
    return lambda v: (sum(1 for t in s if t <= v) / len(s)) if (v is not None and s) else 0
by = {}
for r in items: by.setdefault(r["site"], []).append(r["speed"])
P = {k: pct(v) for k, v in by.items()}
for r in items: r["sc"] = {"speed": round(P[r["site"]](r["speed"]) * 100)}

ok = [r for r in items if r["cat"] != "제외"]
kws = json.load(open(os.path.join(W, "kws.json"), encoding="utf-8"))
new_kw = sorted({r["kw"] for r in ok if r["kw"] and r["kw"] not in EN and r["kw"] not in kws})
if new_kw: json.dump(kws + new_kw, open(os.path.join(W, "kws.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump(items, open(os.path.join(W, "day_data.json"), "w", encoding="utf-8"), ensure_ascii=False)
print("전체", len(items), "| 쇼츠 가능", len(ok), "| 새로 들어온", sum(r["new"] for r in ok), "| 검색수 잴 새 키워드", len(new_kw))
for s in ("naver", "coupang", "1688", "temu", "amazon"):
    v = sorted([r for r in ok if r["site"] == s], key=lambda r: -r["sc"]["speed"])
    print(f"  {s:<8}{len(v):>4} | 상위:", [(r["kw"] or r["title"][:10], " · ".join(r["tags"][:1])) for r in v[:3]])
