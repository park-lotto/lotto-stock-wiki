"""인기상품 스냅샷 수집(시안용) — 사이트별 객관 지표 + 광고 표시를 한 형태로 저장.
같은 상품을 시간차로 두 번 찍어 '시간당 판매 증가'를 잰다."""
import json, os, re, sys, time, urllib.request
sys.stdout.reconfigure(encoding="utf-8")
from playwright.sync_api import sync_playwright

TS = time.strftime("%Y%m%d_%H%M")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
OUT = {"ts": TS, "at": time.time(), "items": []}

def add(site, list_name, rank, pid, title, img, price, url, m, ad=False):
    OUT["items"].append({"site": site, "list": list_name, "rank": rank, "id": f"{site}:{pid}", "title": title,
                         "img": img, "price": price, "url": url, "m": m, "ad": bool(ad)})

def num(s):
    s = str(s or "").replace(",", "").replace("+", "").strip()
    mm = re.match(r"([\d.]+)\s*([만천KkMm]?)", s)
    if not mm: return None
    return int(float(mm.group(1)) * {"만": 1e4, "천": 1e3, "K": 1e3, "k": 1e3, "M": 1e6, "m": 1e6, "": 1}[mm.group(2)])

# ── 네이버: 쇼츠가 되는 대분류만, 구매순 일간 ──
NAVER = {"50000008": "생활/건강", "50000004": "가구/인테리어", "50000003": "디지털/가전",
         "50000002": "화장품/미용", "50000005": "출산/육아", "50000007": "스포츠/레저"}
for cid, nm in NAVER.items():
    u = f"https://snxbest.naver.com/api/v1/snxbest/product/rank?ageType=ALL&categoryId={cid}&sortType=PRODUCT_BUY&periodType=DAILY"
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": UA}), timeout=20))
    except Exception as e:
        print("naver", cid, "ERR", e); continue
    for p in d.get("products", []):
        add("naver", nm, p.get("rank"), p.get("productId"), p.get("title"), p.get("imageUrl"), f'{p.get("price")}원', p.get("linkUrl"),
            {"reviews": num(p.get("reviewCount")), "score": p.get("reviewScore")}, p.get("isAd"))
print("naver", sum(1 for x in OUT["items"] if x["site"] == "naver"))

# ── 1688: 신박템이 나오는 2단계 카테고리 × 인기/급상승 ──
C1688 = {"1045059": "USB 신기한템", "122990003": "신기한 장난감", "1556": "생활 일상용품", "122146001": "주방 도구",
         "1514": "청소 도구", "1548": "수납", "653": "주방 가전", "652": "생활 가전", "92": "차량 인테리어",
         "121828001": "반려 용품", "1043171": "뷰티 도구", "50911": "휴대폰 액세서리", "281904": "캠핑", "3305": "정비 공구"}
TEMU_JS = r"""() => [...document.querySelectorAll("a[href*='-g-']")].map(a => {
  let box=a; for(let i=0;i<7&&box.parentElement;i++){ if((box.innerText||'').includes('판매')||(box.innerText||'').includes('원')) {if(box.querySelector('img')) break;} box=box.parentElement; }
  const img=box.querySelector('img'); return {href:a.getAttribute('href'), img: img?(img.currentSrc||img.src):'', text:(box.innerText||'').replace(/[​]+/g,'').replace(/\s+/g,' ').trim().slice(0,400)}; })"""

with sync_playwright() as p:
    ctx = p.firefox.launch_persistent_context(os.path.expanduser("~/.claude/temu_ff_profile"), headless=False,
                                              locale="ko-KR", viewport={"width": 1280, "height": 900})
    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
    box = {}
    pg.on("response", lambda r: box.__setitem__("1688", r) if "ranking.offer.list" in r.url else None)
    for cid, nm in C1688.items():
        for rk, rkn in (("Most_Popular", "인기"), ("TRENDING", "급상승")):
            box.pop("1688", None)
            try:
                pg.goto(f"https://air.1688.com/kapp/1688-global/sales/ranking?rankingName={rk}&countryCode=CN&platform=cbu&cateId={cid}&cateLevel=2", timeout=60000)
                for _ in range(20):
                    if "1688" in box: break
                    pg.wait_for_timeout(500)
                t = box["1688"].text() if "1688" in box else ""
                t = re.sub(r"^[^{]*\(|\)\s*$", "", t.strip())
                s = json.dumps(json.loads(t), ensure_ascii=False) if t else "[]"
                offers = re.findall(r'\{"benefits".*?"whiteBackgroundImage": "[^"]*"\}', s)
                for i, o in enumerate(offers):
                    o = json.loads(o); tags = {x["title"]: x["value"] for x in o.get("subTags", [])}
                    add("1688", f"{nm}·{rkn}", i + 1, o["offerId"], o.get("title"), o.get("mainUrl"), o.get("price"),
                        f'https://detail.1688.com/offer/{o["offerId"]}.html',
                        {"month_sales": num(tags.get("월 판매량")), "mom": tags.get("전월 대비 성장"), "favs": num(tags.get("월간 수집")),
                         "score": tags.get("평가"), "released": o.get("releaseDateFormat")})
            except Exception as e:
                print("1688", cid, rk, "ERR", str(e)[:80])
    print("1688", sum(1 for x in OUT["items"] if x["site"] == "1688"))

    # ── 테무: 베스트셀러를 더보기로 넓게 ──
    pg.goto("https://www.temu.com/kr/channel/best-sellers.html", timeout=60000); pg.wait_for_timeout(6000)
    for _ in range(6):
        pg.mouse.wheel(0, 6000); pg.wait_for_timeout(1500)
        more = pg.get_by_text("더보기", exact=False)
        try:
            if more.count(): more.last.click(timeout=3000); pg.wait_for_timeout(2500)
        except Exception: pass
    seen = set()
    for c in pg.evaluate(TEMU_JS):
        g = re.search(r"-g-(\d+)", c["href"] or "")
        if not g or g.group(1) in seen: continue
        seen.add(g.group(1)); s = c["text"]
        ti = re.search(r"빠르게 보기 (.*?) 새 탭에서 열기", s)
        sold = re.search(r"([\d,.]+만?)\s*판매됨", s); rev = re.search(r"리뷰 ([\d,]+)건", s)
        badge = re.search(r"#(\d+) (베스트셀러 상품|최고 평점) - ([^#]+?)(?= #|$| \1)", s)
        title = re.sub(r"^\W*광고\W*", "", ti.group(1)) if ti else s[:80]
        add("temu", "베스트셀러", len(seen), g.group(1), title, c["img"], (re.search(r"[\d,]+원", s) or [""])[0],
            "https://www.temu.com" + c["href"].split("?")[0] if c["href"].startswith("/") else c["href"].split("?")[0],
            {"sold": num(sold.group(1)) if sold else None, "reviews": num(rev.group(1)) if rev else None,
             "badge": f"#{badge.group(1)} {badge.group(2)} · {badge.group(3).strip()}" if badge else ""},
            ad=bool(re.match(r"^\W*광고", s)) or " 광고 " in s[:40])
    print("temu", sum(1 for x in OUT["items"] if x["site"] == "temu"))

    # ── 알리: 베스트셀러 ──
    pg.goto("https://www.aliexpress.com/p/calp-plus/index.html?categoryTab=us_bestsellers", timeout=60000, wait_until="domcontentloaded"); pg.wait_for_timeout(7000)
    for _ in range(5): pg.mouse.wheel(0, 3000); pg.wait_for_timeout(1500)
    h = pg.content()
    for i, part in enumerate(h.split("card-out-wrapper")[1:]):
        u = re.search(r'href="(//[^"]*?/item/(\d+)\.html)', part)
        if not u: continue
        im = re.search(r'src="((?:https:)?//[^"]+?\.(?:jpg|png|webp|avif)[^"]*)"', part)
        txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", part[:6000])).strip().lstrip('"> ')
        import html as H; txt = H.unescape(txt)
        sold = re.search(r"([\d,]+\+?) 판매", txt); sc = re.search(r" (\d\.\d) ", txt)
        pr = re.search(r"₩ ([\d ,]+?) (?=₩|\d\.\d)", txt)
        add("ali", "베스트셀러", i + 1, u.group(2), re.split(r" -\d+% | ₩ ", txt)[0][:150],
            ("https:" + im.group(1)) if im and im.group(1).startswith("//") else (im.group(1) if im else ""),
            (pr.group(1).replace(" ", "") + "원") if pr else "", "https:" + u.group(1),
            {"sold": num(sold.group(1)) if sold else None, "score": sc.group(1) if sc else None},
            ad=bool(re.search(r"\bAd\b|광고", txt[:200])))
    print("ali", sum(1 for x in OUT["items"] if x["site"] == "ali"))

    # ── 아마존: 쇼츠 분야 베스트셀러 ──
    AMZ = {"home-garden": "홈&주방", "automotive": "자동차", "beauty": "뷰티", "pet-supplies": "반려", "hi": "공구", "electronics": "전자"}
    for slug, nm in AMZ.items():
        try:
            pg.goto(f"https://www.amazon.com/Best-Sellers/zgbs/{slug}", timeout=60000, wait_until="domcontentloaded"); pg.wait_for_timeout(4000)
            for _ in range(3): pg.mouse.wheel(0, 3000); pg.wait_for_timeout(1000)
            rows = pg.evaluate(r"""() => [...document.querySelectorAll('[data-asin]')].map(e => ({asin:e.getAttribute('data-asin'), img:(e.querySelector('img')||{}).src||'', text:(e.innerText||'').replace(/\s+/g,' ').trim()})).filter(x=>x.asin)""")
            for i, r in enumerate(rows):
                s = r["text"]; mm = re.search(r"(.*?) 별 5개 중 ([\d.]+) ([\d,]+)", s)
                pr = re.search(r"KRW ?([\d,]+)|₩ ?([\d,]+)", s)
                add("amazon", nm, i + 1, r["asin"], (mm.group(1) if mm else s)[:150].lstrip("#0123456789 "), r["img"],
                    (next(g for g in pr.groups() if g) + "원") if pr else "", f'https://www.amazon.com/dp/{r["asin"]}',
                    {"reviews": num(mm.group(3)) if mm else None, "score": mm.group(2) if mm else None})
        except Exception as e:
            print("amazon", slug, "ERR", str(e)[:80])
    print("amazon", sum(1 for x in OUT["items"] if x["site"] == "amazon"))
    ctx.close()

os.makedirs("snaps", exist_ok=True)
json.dump(OUT, open(f"snaps/{TS}.json", "w", encoding="utf-8"), ensure_ascii=False)
print("저장", f"snaps/{TS}.json", len(OUT["items"]))
