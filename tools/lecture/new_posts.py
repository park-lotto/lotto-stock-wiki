# 강의 메뉴의 새 글과 미수집 메뉴를 확인한다. 로그인 프로필은 cafe_prof.py 와 같다.
#   py tools/lecture/new_posts.py
import sys, io, os, json, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from cafe_prof import page, CLUB, naver_in
saved = json.load(open(os.path.join(HERE, "collected_articles.json"), encoding="utf-8"))
have = {a["article"] for a in saved}
MENUS = sorted({a["menu"] for a in saved})
with page(headless=True) as pg:
    pg.goto(f"https://cafe.naver.com/f-e/cafes/{CLUB}/menus/0"); time.sleep(3)
    print("로그인", naver_in(pg))
    if not naver_in(pg): sys.exit(2)
    menus = pg.request.get(f"https://apis.naver.com/cafe-web/cafe2/SideMenuList?cafeId={CLUB}").json()["message"]["result"]["menus"]
    names = {m.get("menuId"): m.get("menuName") for m in menus}
    print("미수집 메뉴", [(i, n) for i, n in names.items() if i and n and i not in MENUS])
    seen = 0
    for mid in MENUS:
        got, pno = [], 1
        while True:
            x = pg.request.get(f"https://apis.naver.com/cafe-web/cafe2/ArticleListV2dot1.json?search.clubid={CLUB}&search.menuid={mid}&search.page={pno}&search.perPage=50&search.queryType=lastArticle").json()
            arts = x.get("message", {}).get("result", {}).get("articleList", [])
            got += arts
            if len(arts) < 50: break
            pno += 1
        seen += len(got)
        for a in got:
            if a.get("articleId") not in have:
                print("새 글", mid, names.get(mid), a.get("articleId"), a.get("subject"))
    print("카페", seen, "저장", len(have))
