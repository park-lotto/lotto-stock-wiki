"""관제 151 확장 점검 — 인스타 밖 5개 플랫폼(유튜브·틱톡·핀터레스트·샤오홍슈·도우인).

확장 로직(userscript/grab_logic.js)을 **진짜 사이트 페이지**(로그아웃)에 주입해 본다. 서버 호출은 가짜 응답.
  · 검색 화면: 오른쪽 '🔎 숏템 검색어' 판이 뜨고, 검색창 값 = 지금 검색어, 5줄 × 5개 언어(25칸)
  · 영상 화면: '🔎 관련 검색어' 상자가 설명글을 읽어 서버에 보내고(언어 = 플랫폼 언어) 칩을 그린다
로그인 벽·캡차로 페이지가 안 열리는 플랫폼은 SKIP으로 따로 적는다(실패와 구분).
사용: py tools/kw_sites_check.py [--shots 폴더] [--logic 다른판.js]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOGIC = (ROOT / "shopping_shorts" / "userscript" / "grab_logic.js").read_text(encoding="utf-8")

STUB = r"""
window.__kwCalls = [];
window.GM_xmlhttpRequest = function (o) {
  var body = {}; try { body = JSON.parse(o.data || "{}"); } catch (e) {}
  window.__kwCalls.push(body);
  var r = {ok: true};
  if (o.url.indexOf("/api/lens/kw/multi") >= 0) {
    r.candidates = [0,1,2,3,4].map(function (i) { return {ko: "검색어" + i, en: "term " + i, ja: "語" + i, zh: "词" + i, ru: "слово" + i}; });
  } else if (o.url.indexOf("/api/lens/kw/en") >= 0) {
    r.main = body.lang === "zh" ? "测试商品" : "amazon test item"; r.related = body.lang === "zh" ? ["相关一", "相关二"] : ["related one", "related two"];
  } else { r = {ok: false}; }
  setTimeout(function () { o.onload({status: 200, responseText: JSON.stringify(r)}); }, 50);
};
"""

CASES = [
    # (플랫폼, 종류, 주소, 기대 검색어 또는 None, 기대 언어)
    ("youtube", "search", "https://www.youtube.com/results?search_query=gear+keychain", "gear keychain", "en"),
    ("youtube", "post", "https://www.youtube.com/shorts/uuLukgLNhSE", None, "en"),
    ("tiktok", "search", "https://www.tiktok.com/search?q=gear%20keychain", "gear keychain", "en"),
    ("tiktok", "post", "https://www.tiktok.com/@fastcopstore/video/7601193451094330646", None, "en"),
    ("pinterest", "search", "https://www.pinterest.com/search/videos/?q=gear%20keychain", "gear keychain", "en"),
    ("pinterest", "post", "https://www.pinterest.com/pin/719872321738808685/", None, "en"),
    ("xiaohongshu", "search", "https://www.xiaohongshu.com/search_result?keyword=%E9%92%A5%E5%8C%99%E6%89%A3", "钥匙扣", "zh"),
    ("douyin", "search", "https://www.douyin.com/search/%E9%92%A5%E5%8C%99%E6%89%A3", "钥匙扣", "zh"),
]

PROBE = """() => {
  const f = document.getElementById('ss-kwfloat'), p = document.getElementById('ss-kwpost');
  return {
    url: location.href,
    float: f ? {input: (f.querySelector('input') || {}).value, cells: f.querySelectorAll('button[type=button]').length - 1} : null,
    post: p ? {chips: [...p.querySelectorAll('.ss-kw-body button')].map(b => b.textContent), text: p.innerText.slice(0, 120)} : null,
    sent: (window.__kwCalls || []).filter(c => c.kind === 'caption').map(c => ({lang: c.lang, text: (c.text || '').slice(0, 80)})),
  };
}"""


def run(shots=None, logic=LOGIC):
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel="chrome")
        ctx = b.new_context(viewport={"width": 1500, "height": 950}, locale="ko-KR", bypass_csp=True)
        ctx.add_init_script(STUB)
        for site, kind, url, q, lang in CASES:
            pg = ctx.new_page()
            r = {"site": site, "kind": kind}
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(6000)
                pg.add_script_tag(content=logic)
                pg.wait_for_timeout(9000 if kind == "post" else 4000)
                r.update(pg.evaluate(PROBE))
                if shots:
                    pg.screenshot(path=str(Path(shots) / f"{site}_{kind}.png"))
            except Exception as e:  # noqa: BLE001
                r["error"] = str(e)[:160]
            pg.close()
            out.append(r)
        b.close()
    return out


def judge(r, q, lang):
    url = r.get("url") or ""
    if r.get("error"):
        return "SKIP", "페이지 오류: " + r["error"][:80]
    if r["kind"] == "search":
        f = r.get("float")
        if not f:
            moved = q and q.replace(" ", "") not in url.replace("+", "").replace("%20", "")
            return ("SKIP" if moved else "FAIL"), ("다른 화면으로 넘어감(로그인·캡차?): " + url[:90]) if moved else "검색 판이 안 떴다"
        if f["input"] != q:
            return "FAIL", f"검색창 값 {f['input']!r} != {q!r}"
        if f["cells"] != 25:
            return "FAIL", f"언어 칸 {f['cells']}개(25여야)"
        return "PASS", "판 + 25칸"
    p = r.get("post")
    if not p:
        return "FAIL", "관련 검색어 상자가 안 떴다"
    sent = r.get("sent") or []
    if not sent:
        return "FAIL", "설명글을 못 읽었다: " + p["text"][:60]
    if sent[0]["lang"] != lang:
        return "FAIL", f"언어 {sent[0]['lang']} != {lang}"
    if not p["chips"]:
        return "FAIL", "칩이 없다: " + p["text"][:60]
    return "PASS", "설명글 '" + sent[0]["text"][:50] + "' → 칩 " + str(len(p["chips"]))


if __name__ == "__main__":
    shots = None
    logic = LOGIC
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    if "--logic" in sys.argv:
        logic = Path(sys.argv[sys.argv.index("--logic") + 1]).read_text(encoding="utf-8")
    res = run(shots, logic)
    bad = 0
    for (site, kind, url, q, lang), r in zip(CASES, res):
        v, why = judge(r, q, lang)
        bad += v == "FAIL"
        print(f"{v:4} {site:11} {kind:6} {why}")
    print("FAIL 있음" if bad else "PASS(SKIP 제외)")
    sys.exit(1 if bad else 0)
