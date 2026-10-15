"""관제 151 화면 점검 — 인스타 영어 검색어(검색창·비슷한 검색어 칩·게시물 관련 검색어).

확장프로그램 로직(userscript/grab_logic.js)을 헤드리스 크롬에 주입해 본다. 서버 호출(/api/lens/kw/en)은
가짜 응답으로 바꾼다(서버 쪽 판단은 video_analysis.english_search_terms를 서버에서 따로 잰다).

  ① 진짜 인스타 릴스 페이지(로그아웃): 설명글을 읽어 관련 검색어 상자가 뜨는가, 칩을 누르면 검색 주소로 가는가
  ② 검색 화면: 인스타는 로그인해야 열려서 **흉내 페이지**로 본다(제목 = 검색어 글자) —
     제목이 검색창으로 바뀌는가, 비슷한 검색어 칩, 한글 입력 → 영어 주소로 이동

★②는 진짜 인스타 화면이 아니다. 로그인 화면 확인은 사장님 크롬에서 한다.
사용: py tools/ig_kw_ui_check.py [--shots 폴더]
"""
import json
import sys
import tempfile
from pathlib import Path
from urllib.parse import unquote

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOGIC = (ROOT / "shopping_shorts" / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
REEL = "DeH03R5SbKK"

# 가짜 서버: kind별 응답. 호출 기록을 window.__kwCalls에 남긴다.
STUB = r"""
window.__kwCalls = [];
window.GM_xmlhttpRequest = function (o) {
  var body = {}; try { body = JSON.parse(o.data || "{}"); } catch (e) {}
  window.__kwCalls.push({url: o.url, body: body});
  var r = {ok: true, main: "", related: []};
  if (o.url.indexOf("/api/lens/kw/multi") >= 0) {
    r = {ok: true, candidates: [
      {ko: "생활 꿀템", en: "life hacks gadgets", ja: "便利グッズ", zh: "生活好物", ru: "лайфхаки"},
      {ko: "주방 꿀템", en: "kitchen gadgets", ja: "キッチングッズ", zh: "厨房好物", ru: "кухонные гаджеты"},
      {ko: "자석 양념통", en: "magnetic spice tins", ja: "", zh: "磁吸调料罐", ru: ""},
      {ko: "수납 정리", en: "home organization", ja: "収納", zh: "收纳", ru: "хранение"},
      {ko: "청소 도구", en: "cleaning gadgets", ja: "掃除グッズ", zh: "清洁神器", ru: "уборка"}]};
  } else if (o.url.indexOf("/api/lens/kw/en") >= 0) {
    if (body.kind === "caption") r = {ok: true, main: "amazon baseball cleats", related: ["amazon baseball gear", "baseball cleats", "mlb postseason"]};
    else if (/[ㄱ-힝]/.test(body.text || "")) r = {ok: true, main: "portable range hood", related: ["desktop range hood"]};
    else r = {ok: true, main: (body.text || "").toLowerCase(), related: ["kitchen gadgets", "smart home devices", "cool tech tools", "desk accessories", "cleaning gadgets"]};
  }
  setTimeout(function () { o.onload({status: 200, responseText: JSON.stringify(r)}); }, body.kind === "caption" ? 2500 : 50);
};
"""

FAKE_SEARCH = """<!doctype html><html><head><meta charset=utf-8></head><body>
<main><div style="padding:20px 40px"><div><span style="font-size:18px;font-weight:600">Life hacks gadgets</span></div>
<div style="display:grid;grid-template-columns:repeat(4,200px);gap:4px;margin-top:16px">
""" + "".join(f'<a href="/reel/FAKE{i}/" style="display:block;width:200px;height:260px;background:#ccc"></a>' for i in range(8)) + """
</div></div></main></body></html>"""


def run(shots):
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel="chrome")
        ctx = b.new_context(viewport={"width": 1600, "height": 950}, locale="ko-KR", bypass_csp=True)
        ctx.add_init_script(STUB)
        pg = ctx.new_page()

        # ① 진짜 릴스 페이지
        pg.goto(f"https://www.instagram.com/reel/{REEL}/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(5000)
        pg.add_script_tag(content=LOGIC)
        # 응답을 기다리는 중에 상자가 다시 그려지는 상황(2026-10-07 사장님 화면 '만드는 중…' 멈춤)을 만든다
        pg.wait_for_function("() => (window.__kwCalls || []).some(c => c.body && c.body.kind === 'caption')", timeout=20000)
        pg.evaluate("() => { const p = document.getElementById('ss-kwpost'); if (p) p.remove(); }")
        pg.wait_for_timeout(6000)
        post = pg.evaluate("""() => { const p = document.getElementById('ss-kwpost'); if (!p) return null;
            const r = p.getBoundingClientRect();
            return {chips: [...p.querySelectorAll('button')].map(b => b.textContent), text: p.innerText.slice(0, 120),
                    left: Math.round(r.left), top: Math.round(r.top), w: Math.round(r.width), visible: getComputedStyle(p).display !== 'none',
                    calls: window.__kwCalls.map(c => ({kind: c.body.kind, text: (c.body.text || '').slice(0, 60)}))}; }""")
        res["post"] = post
        if shots:
            pg.screenshot(path=str(Path(shots) / "post.png"))
        if post and post["chips"]:
            pg.click("#ss-kwpost button")
            pg.wait_for_timeout(2500)
            res["post_click_url"] = unquote(pg.url)

        # ② 흉내 검색 화면 — 진짜 인스타 주소로 가로채서 흉내 HTML을 준다
        pg2 = ctx.new_page()
        pg2.route("https://www.instagram.com/explore/search/keyword/**",
                  lambda route: route.fulfill(status=200, content_type="text/html", body=FAKE_SEARCH))
        pg2.goto("https://www.instagram.com/explore/search/keyword/?q=Life%20hacks%20gadgets", wait_until="domcontentloaded")
        pg2.add_script_tag(content=LOGIC)
        pg2.wait_for_timeout(3000)
        bar = pg2.evaluate("""() => { const b = document.getElementById('ss-kwbar'); if (!b) return null;
            const t = b.previousElementSibling;
            return {input: b.querySelector('input').value, chips: [...b.querySelectorAll('button[type=button]')].map(x => x.textContent),
                    enabled: b.querySelectorAll('button[type=button]:not([disabled])').length,
                    title_hidden: !!t && t.style.display === 'none'}; }""")
        res["bar"] = bar
        if shots:
            pg2.screenshot(path=str(Path(shots) / "search.png"), clip={"x": 0, "y": 0, "width": 1000, "height": 260})
        if bar:
            pg2.fill("#ss-kwbar input", "휴대용 레인지후드")
            pg2.click("#ss-kwbar button[type=submit]")
            pg2.wait_for_timeout(2500)
            res["korean_submit_url"] = unquote(pg2.url)
        b.close()
    return res


def check(res):
    fails = []
    post = res.get("post") or {}
    if not post.get("chips"):
        fails.append("① 게시물 관련 검색어 칩이 안 떴다: " + str(post.get("text")))
    elif post["chips"][0] != "amazon baseball cleats":
        fails.append("① 첫 칩이 main이 아니다: " + str(post["chips"]))
    if not any(c.get("kind") == "caption" and len(c.get("text") or "") > 10 for c in post.get("calls") or []):
        fails.append("① 설명글을 서버로 안 보냈다: " + str(post.get("calls")))
    # 로그아웃 브라우저라 검색 주소가 로그인으로 넘어간다 — next=에 같은 검색어가 실렸으면 이동은 맞다.
    if not any(k in (res.get("post_click_url") or "") for k in ("q=amazon baseball cleats", "q=amazon+baseball+cleats")):
        fails.append("① 칩 클릭 이동 주소가 틀렸다: " + str(res.get("post_click_url")))
    bar = res.get("bar") or {}
    if not bar:
        fails.append("② 검색창이 안 생겼다")
    else:
        if bar.get("input") != "Life hacks gadgets":
            fails.append("② 검색창 값이 검색어가 아니다: " + str(bar.get("input")))
        if not bar.get("title_hidden"):
            fails.append("② 원래 제목이 그대로 보인다")
        if len(bar.get("chips") or []) != 25:
            fails.append("② 비슷한 검색어가 5줄×5언어(25칸)가 아니다: " + str(bar.get("chips")))
        if bar.get("enabled") != 23:
            fails.append("② 빈 언어 칸(2개)이 흐리게 안 막혔다: 누를 수 있는 칸 " + str(bar.get("enabled")))
    if "q=portable range hood" not in (res.get("korean_submit_url") or ""):
        fails.append("② 한글 입력 → 영어 주소 이동 실패: " + str(res.get("korean_submit_url")))
    return fails


if __name__ == "__main__":
    shots = None
    if "--logic" in sys.argv:                 # 다른 판의 로직으로 돌려 본다(고치기 전 코드에서 실패하는지 확인용)
        LOGIC = Path(sys.argv[sys.argv.index("--logic") + 1]).read_text(encoding="utf-8")
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    r = run(shots)
    print(json.dumps(r, ensure_ascii=False, indent=1))
    f = check(r)
    print("PASS" if not f else "FAIL\n- " + "\n- ".join(f))
    sys.exit(0 if not f else 1)
