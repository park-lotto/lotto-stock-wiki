# -*- coding: utf-8 -*-
"""현장썰 하이브리드 — 원본 영상 속 제품과 '같은 제품'을 찾는다(사장님 10-18 "최선은 같은 제품을 찾는 거야").

구글 렌즈(PC, 로그인된 tools/google_browser 프로필, 무료 — SerpApi 는 유료라 안 씀)에 사진을 올려
  ① 렌즈가 보여 주는 제품 이름·쇼핑 결과(어느 가게든) 를 모으고
  ② 그 안의 coupang.com 링크를 바로 뽑는다.
쿠팡 링크가 없으면 ①의 제품 이름(브랜드·모델)으로 쿠팡검색.py 를 다시 돌린다(테무·알리 등에서 이름 알아내기).
쿠팡 모바일 렌즈는 PC 브라우저에서 m.coupang.com 이 Access Denied(10-18 실측)라 이 길로 간다.

실행: py channel/hottemreport/현장썰하이브리드/렌즈쿠팡.py <사진.jpg> <이름> [<더할 글자>]
결과: 같은 폴더 렌즈_<이름>.json (+ 화면 렌즈_<이름>.png)
"""
import json
import os
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROFILE = os.path.expanduser(r"~\.claude\google_browser_profile")
HERE = Path(__file__).resolve().parent

_JS_UNUSED = r"""()=>{
  const out=[];
  for(const a of document.querySelectorAll('a[href]')){
    const h=a.href; if(!h||h.startsWith('https://www.google.')&&!h.includes('/url?')) continue;
    const t=(a.innerText||a.getAttribute('aria-label')||'').replace(/\s+/g,' ').trim();
    if(t) out.push({href:h,text:t.slice(0,200)});
  }
  return out;
}"""


def main(img, name, extra=""):
    from playwright.sync_api import sync_playwright
    img = str(Path(img).resolve())
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(PROFILE, headless=False, channel="chrome", locale="ko-KR",
                                                   viewport={"width": 1366, "height": 900},
                                                   args=["--disable-blink-features=AutomationControlled"])
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://www.google.com/?hl=ko", wait_until="domcontentloaded", timeout=40000)
        pg.wait_for_timeout(1500)
        # 렌즈 버튼(이미지로 검색) → 파일 올리기 칸
        for sel in ['div[aria-label="이미지로 검색"]', 'div[aria-label="Search by image"]', '[aria-label*="렌즈"]', '[aria-label*="Lens"]']:
            if pg.locator(sel).count():
                pg.locator(sel).first.click()
                break
        pg.wait_for_timeout(1500)
        # 페이지에 file 칸이 여럿이라 첫 칸에 넣으면 안 올라간다(10-18 실측) → '파일을 업로드'를 눌러 뜨는 선택 창으로
        with pg.expect_file_chooser(timeout=15000) as fc:
            pg.get_by_text(re.compile("파일을 업로드|upload a file", re.I)).first.click()
        fc.value.set_files(img)
        pg.wait_for_url(re.compile(r"(lens|search)"), timeout=40000)
        pg.wait_for_timeout(7000)
        if extra:   # 렌즈 결과에 글자 더하기(예: 쿠팡) — 검색칸에 넣고 엔터
            box = pg.locator('textarea, input[type=text]').first
            box.fill(extra)
            box.press("Enter")
            pg.wait_for_timeout(6000)
        for _ in range(6):
            pg.mouse.wheel(0, 1500)
            pg.wait_for_timeout(700)
        html = pg.content()
        (HERE / f"렌즈_{name}.html").write_text(html, encoding="utf-8")
        pg.screenshot(path=str(HERE / f"렌즈_{name}.png"), full_page=False)
        ctx.close()
    # 렌즈 결과는 <a href> 가 아니라 페이지 속 데이터(JSON)에 "주소","제목" 쌍으로 들어 있다(10-18 실측 — 링크 읽기는 0개)
    import html as H
    raw = H.unescape(html)
    seen, rows = set(), []
    for m in re.finditer(r'"(https?://[^"\s]+)","([^"]{4,200})"', raw):
        h, t = m.group(1), m.group(2)
        shop = re.sub(r"^https?://(www\.)?", "", h).split("/")[0]
        if h in seen or re.search(r"google|gstatic|coupangcdn|youtube|googleusercontent", shop) or t.startswith("http"):
            continue
        seen.add(h)
        rows.append({"href": h, "text": t, "shop": shop})
    cp = [r for r in rows if "coupang.com" in r["shop"]]
    res = {"img": img, "extra": extra, "n": len(rows), "coupang": cp, "all": rows}
    (HERE / f"렌즈_{name}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"결과 {len(rows)}개 · 쿠팡 {len(cp)}개")
    for r in cp[:10]:
        print("  [쿠팡]", r["text"][:80], r["href"][:100])
    for r in rows[:25]:
        print("  ", r["shop"][:28].ljust(28), r["text"][:80])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
