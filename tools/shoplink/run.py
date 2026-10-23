"""영상 1편 → 쿠팡 파트너스 단축링크 + 인포크 링크 블록 + 버퍼 설명란 문구 (관제 259).

사장님(2026-10-23): "인포크랑 쿠파스를 다 자동화" — 우리 파트너스 계정은 최종 승인 전이라 API 가 없고
인포크는 원래 API 가 없다 → 둘 다 로그인된 전용 크롬(tools/google_browser.py 프로필)을 조작한다.
★유튜브에는 손대지 않는다(사장님 조건: 유튜브에 우리 IP 금지). 유튜브 게시는 버퍼가 한다.

  py tools/shoplink/run.py find  "스크럽대디"                 # 쿠팡 후보 5개만 본다(아무것도 안 만든다)
  py tools/shoplink/run.py make  "스크럽대디" --pick 0 --dry   # 링크만 발급, 인포크는 폼만 채우고 저장 안 함
  py tools/shoplink/run.py make  "스크럽대디" --pick 0 --title "샤크들이 서로 싸운 웃는 수세미?!" --desc "..." --tags "#수세미"
      → 인포크 블록(그 계정 기존 형식 "[N] 이름"·"N. 이름", 같은 상품 있으면 재사용) 공개 + 공개 페이지에서 실측 + 설명란 문구 출력·저장

판단 주인
  - 번호·제목 형식: 그 인포크 공개 페이지의 기존 블록('[N] 이름' / 'N. 이름') — inpock_plan(). 같은 상품이 있으면 재사용
  - 설명란 문구: description() 한 곳
"""
import argparse, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PARTNERS = "https://partners.coupang.com/"
INPOCK = "https://link.inpock.co.kr"
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."
# 버퍼 계정 폴더(번호) → 인포크 계정. 사장님 확정 2026-10-23. syospa123 은 우리 채널 것이 아님
INPOCK_BY_CHANNEL = {"987": "shocktem", "950": "streport", "999": "yeshot", "21": "ssldezip",
                     "998": "mtst", "995": "stems", "994": "ssult"}   # ★인포크 프로필명 실측: stems=썰템쇼, ssult=썰템홈샷
OUT_DIR = os.path.expanduser(r"~\.claude\shoplink")          # 장부·이미지(키·개인정보 없음)
LEDGER = os.path.join(OUT_DIR, "ledger.json")


# ── 쿠팡 파트너스 ─────────────────────────────────────────────
def coupang_candidates(pg, keyword, n=5):
    """파트너스 상품검색 결과 앞에서 n개 → [{name, price, image}] (아무것도 만들지 않는다)."""
    pg.goto(f"{PARTNERS}#affiliate/ws/link/0/{urllib.parse.quote(keyword)}", wait_until="domcontentloaded")
    for _ in range(60):                          # 로그인이 풀리면 해시 주소가 로그인 화면으로 넘어간다
        pg.wait_for_timeout(500)
        if "login.coupang.com" in pg.url:
            raise SystemExit("쿠팡 파트너스 로그인이 풀렸다 — 전용 창에서 사장님 로그인('로그인 상태 유지' 체크) 필요")
        if pg.locator(".product-item").count():
            break
    pg.wait_for_selector(".product-item", timeout=15000)
    pg.wait_for_timeout(1500)
    items = pg.evaluate("""n=>[...document.querySelectorAll('.product-item')].slice(0,n).map(e=>({
        name:(e.querySelector('.product-description')||{}).innerText||'',
        price:((e.querySelector('.sale-price')||{}).innerText||'').replace(/\\s+/g,''),
        image:(e.querySelector('.product-picture img')||{}).src||''}))""", n)
    for it in items:
        it["name"] = it["name"].strip()
        it["image"] = it["image"].replace("/212x212ex/", "/492x492ex/")
    return items


def coupang_link(pg, keyword, pick):
    """후보 pick 번째의 '링크 생성' → 우리 계정 단축 URL."""
    items = coupang_candidates(pg, keyword)
    if pick >= len(items):
        raise SystemExit(f"후보가 {len(items)}개뿐이다")
    pg.locator(".product-item").nth(pick).hover()
    pg.locator(".product-item").nth(pick).locator("button.btn-generate-link").click(force=True)
    for _ in range(40):
        pg.wait_for_timeout(500)
        m = re.search(r"https://link\.coupang\.com/a/[A-Za-z0-9]+", pg.inner_text("body"))
        if m:
            return {**items[pick], "link": m.group(0), "keyword": keyword}
    raise SystemExit("단축 URL 이 화면에 안 나왔다")


# ── 인포크 ─────────────────────────────────────────────────
def inpock_account(pg):
    pg.goto(f"{INPOCK}/admin", wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    if "/user/login" in pg.url:
        raise SystemExit("인포크 로그인이 풀렸다 — 전용 창에서 사장님 로그인 필요")
    m = re.search(r"link\.inpock\.co\.kr/([A-Za-z0-9_.]+)", pg.inner_text("body"))
    if not m:
        raise SystemExit("인포크 계정 주소를 못 읽었다")
    return m.group(1)


def inpock_switch(pg, want):
    """전용 창에 로그인해 둔 인포크 계정들 중 want 로 바꾼다(관리 메뉴의 계정 이름 → '계정 선택' 목록)."""
    if inpock_account(pg) == want:
        return want
    pg.goto(f"{INPOCK}/admin/menu", wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    pg.locator("text=/^[a-z0-9_.]{4,}$/ >> visible=true").last.click()
    pg.wait_for_selector("text=계정 선택", timeout=10000)
    items = pg.locator(f"text=/^{re.escape(want)}$/ >> visible=true")
    if not items.count():
        raise SystemExit(f"인포크 계정 {want} 가 이 창에 로그인돼 있지 않다 — '계정 추가'로 로그인 필요")
    items.last.click()
    pg.wait_for_timeout(4000)
    got = inpock_account(pg)
    if got != want:
        raise SystemExit(f"인포크 계정 전환 실패: {got} (원한 것 {want})")
    return got


_NUM_RES = (("[{n}] {name}", re.compile(r"^\[(\d+)\]\s*(.+)$")),      # 대부분 채널(사장님 손 등록 형식)
            ("{n}. {name}", re.compile(r"^(\d+)\.\s*(.+)$")))          # 샥템스토리 형식


def inpock_blocks(account):
    """공개 페이지의 블록 제목 → [(번호, 이름, 형식)]. 번호·형식의 주인 = 사장님이 이미 쓰고 있는 인포크 블록."""
    req = urllib.request.Request(f"{INPOCK}/{account}", headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    out = []
    for t in re.findall(r'"title":"([^"]{1,80})"', html):
        for fmt, rx in _NUM_RES:
            m = rx.match(t.strip())
            if m:
                out.append((int(m.group(1)), m.group(2).strip(), fmt))
                break
    return out


def inpock_plan(account, keyword, product_name):
    """같은 상품이 이미 있으면 그 번호를 그대로 쓰고(등록 안 함), 없으면 최댓값+1·그 계정이 쓰던 형식으로."""
    blocks = inpock_blocks(account)
    words = [w for w in re.split(r"\s+", keyword.strip()) if w]
    for n, name, fmt in blocks:
        if words and all(w in name.replace(" ", "") or w in name for w in words):
            return {"number": n, "title": fmt.format(n=n, name=name), "exists": True}
    fmt = max(("[{n}] {name}", "{n}. {name}"), key=lambda f: sum(1 for b in blocks if b[2] == f)) if blocks else "[{n}] {name}"
    n = max([b[0] for b in blocks] or [0]) + 1
    return {"number": n, "title": fmt.format(n=n, name=short_title(product_name)), "exists": False}


def short_title(name, limit=22):
    """쿠팡 상품명 → 인포크 제목용. 옵션(", 3개입, 1개")은 뺀다. 이름을 지어내지 않는다."""
    base = name.split(",")[0].strip()
    return base if len(base) <= limit else base[:limit].rstrip()


def inpock_add(pg, title, link, image_path, dry=False):
    pg.goto(f"{INPOCK}/admin/block/link/post", wait_until="domcontentloaded")
    pg.wait_for_selector("input[placeholder*='링크 주소']", timeout=30000)
    pg.locator("input[placeholder*='링크 주소']").first.fill(link)
    t = pg.locator("[placeholder*='링크를 잘 나타낼']").first
    t.fill("")
    t.fill(title)
    pg.locator("input[type=file]").first.set_input_files(image_path)
    pg.wait_for_timeout(2500)
    # 이미지를 넣으면 자르기 창이 뜬다 — [취소][선택] 중 '선택'(2026-10-23 실측). 안 누르면 '추가 완료'가 꺼진 채 남는다
    sel = pg.get_by_role("button", name="선택", exact=True)
    if sel.count() and sel.first.is_visible():
        sel.first.click()
        pg.wait_for_timeout(2500)
    if dry:
        return {"saved": False}
    btn = pg.locator("button:has-text('추가 완료')").last
    if not btn.is_enabled():
        raise SystemExit("인포크 '추가 완료'가 꺼져 있다 — 칸(주소·제목·이미지) 중 빈 것이 있다")
    btn.click()
    pg.wait_for_timeout(4000)
    return {"saved": True, "url_after": pg.url}


def inpock_public_has(account, title):
    """공개 페이지 실측 — 로그인 없이 받아 제목이 있는지."""
    req = urllib.request.Request(f"{INPOCK}/{account}", headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "replace")
    return title in html


# ── 버퍼 설명란 ───────────────────────────────────────────────
def description(title, desc, number, account, link, tags):
    """버퍼(=유튜브 설명란) 글. 첫 줄 = 유튜브 제목(buffer_api._yt_title). 쇼츠 설명 링크는 안 눌린다 → 인포크 번호 안내가 본론."""
    return "\n".join([
        title,
        desc,
        "",
        f"🛒 구매링크: 프로필 링크(인포크)에서 '{number}' 검색",
        f"link.inpock.co.kr/{account}",
        f"쿠팡: {link}",
        DISCLOSURE,
        "",
        ("#광고 #shorts " + tags).strip(),
    ])


COOKIES = os.path.join(OUT_DIR, "coupang_cookies.json")   # ★로컬 전용(git·드라이브 금지) — 로그인 세션


def restore_cookies(pg):
    """쿠팡 파트너스 로그인은 세션 쿠키라 크롬을 닫으면 사라진다(2026-10-23 실측: 다음 실행에 로그인 화면).
    그래서 실행 끝에 쿠팡 쿠키를 저장해 두고 다음 실행 처음에 되돌린다."""
    if os.path.exists(COOKIES):
        pg.context.add_cookies(json.load(open(COOKIES, encoding="utf-8")))


def save_cookies(pg):
    cs = [c for c in pg.context.cookies() if "coupang.com" in c.get("domain", "")]
    if cs:
        json.dump(cs, open(COOKIES, "w", encoding="utf-8"))


def download(url, path):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": PARTNERS})
    with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
        f.write(r.read())
    return path


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["find", "make", "login"])
    p.add_argument("keyword", nargs="?", default="")
    p.add_argument("--pick", type=int, default=0)
    p.add_argument("--title", default="")
    p.add_argument("--desc", default="")
    p.add_argument("--tags", default="")
    p.add_argument("--channel", default="", help="버퍼 계정 번호(987·950…) → 그 채널 인포크로 자동 전환")
    p.add_argument("--account", default="", help="인포크 계정을 직접 지정(--channel 이 우선)")
    p.add_argument("--dry", action="store_true", help="쿠팡 링크만 발급, 인포크는 저장 안 함")
    a = p.parse_args(argv)
    from tools.google_browser import google_page
    os.makedirs(OUT_DIR, exist_ok=True)
    with google_page() as pg:
        restore_cookies(pg)
        try:
            run(pg, a)
        finally:
            save_cookies(pg)


def run(pg, a):
        if a.cmd == "login":
            pg.goto(PARTNERS, wait_until="domcontentloaded")
            print("창에서 쿠팡 파트너스 로그인(최대 10분)…", flush=True)
            for _ in range(300):
                time.sleep(2)
                if pg.url.startswith(PARTNERS + "#") and pg.locator("text=로그아웃").count() + pg.locator("text=내 정보").count():
                    break
            print("로그인 확인:", pg.url)
            return
        if a.cmd == "find":
            for i, it in enumerate(coupang_candidates(pg, a.keyword)):
                print(f"[{i}] {it['name']}  {it['price']}")
            return
        prod = coupang_link(pg, a.keyword, a.pick)
        print("쿠팡:", prod["name"], prod["link"])
        want = INPOCK_BY_CHANNEL.get(a.channel) if a.channel else a.account
        if a.channel and not want:
            raise SystemExit(f"채널 {a.channel} 의 인포크 계정이 정해져 있지 않다(INPOCK_BY_CHANNEL)")
        acct = inpock_switch(pg, want) if want else inpock_account(pg)
        if not want:
            raise SystemExit(f"--channel 또는 --account 가 필요하다(지금 로그인된 인포크: {acct})")
        plan = inpock_plan(acct, a.keyword, prod["name"])
        num, title = plan["number"], plan["title"]
        seen = None
        if plan["exists"]:
            res = {"saved": False, "reused": True}
            seen = True
            print("인포크:", acct, "이미 있는 블록을 쓴다 →", title)
        else:
            img = download(prod["image"], os.path.join(OUT_DIR, f"{acct}_{num}.jpg"))
            res = inpock_add(pg, title, prod["link"], img, dry=a.dry)
            print("인포크:", acct, title, res)
            if res["saved"]:
                for _ in range(6):
                    seen = inpock_public_has(acct, title)
                    if seen:
                        break
                    time.sleep(5)
                print("공개 페이지 실측:", "있음" if seen else "없음")
        text = description(a.title or prod["name"], a.desc, num, acct, prod["link"], a.tags)
        print("----- 버퍼 설명란 -----\n" + text)
        rows = json.load(open(LEDGER, encoding="utf-8")) if os.path.exists(LEDGER) else []
        rows.append({"at": datetime.now().isoformat(timespec="seconds"), "keyword": a.keyword, "product": prod["name"],
                     "link": prod["link"], "inpock": acct, "number": num, "title": title,
                     "saved": res["saved"], "public_seen": seen, "dry": a.dry})
        json.dump(rows, open(LEDGER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
