"""관제 177 — 담기 버튼 점검: 도우인(검색 격자 카드 📥 · 영상 팝업의 📥 담기 · 검색어 판 1개) + 인스타 격자(📥·설명 줄).

도우인은 로그인·캡차 벽이라 진짜 사이트를 자동으로 못 연다. 그래서 2026-10-11 로그인 화면에서
실측한 카드 구조를 그대로 본뜬 화면을 **douyin.com 주소로** 띄워(요청은 전부 가로채 바깥으로 안 나간다)
확장과 같은 순서로 넣는다: 메인월드(_douyinMainWorld — zip 빌더와 같은 방식으로 잘라냄) → grab_logic.js.

실측 구조(검색 '综合' 격자):
  .Z(absolute, overflow:hidden, 220x293) > [.box(relative) > img] + [.over(absolute, 같은 자리) > .inner(relative)]
  → 📥는 .box 에 붙고, 그 위를 **같은 카드의 형제 칸**(.over)이 덮는다. 영상 번호는 img 의 React fiber 안에만 있다.

보는 것(전부 화면에 실제로 그려진 결과):
  ① 격자: 보이는 카드마다 📥가 보인다(visibility) — 고정 머리에 덮인 카드의 📥만 숨는다
  ② 영상 팝업(?modal_id=): 📥 담기가 화면 안에 보인다 · 검색어 판은 '관련 검색어' 하나만
  ③ 인스타 격자(본뜬 화면): 📥는 보이고 머리에 덮인 줄만 숨는다 · 썸네일 한국어 설명 줄(.ss-card-ko)은 없다
     (옛 로직이 그려 둔 줄도 걷는다 — 2026-10-11 사장님 "썸네일 위쪽에 나오는 설명들 빼")
사용: py tools/grab_cards_check.py [--logic 다른판.js] [--shots 폴더]
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
LOGIC_PATH = ROOT / "shopping_shorts" / "userscript" / "grab_logic.js"

STUB = r"""
window.GM_xmlhttpRequest = function (o) {
  setTimeout(function () { o.onload({status: 200, responseText: JSON.stringify({ok: false})}); }, 30);
};
"""

# 카드 8장(4열 2줄). 첫 줄은 고정 머리(.hdr, 화면 폭)가 윗부분을 덮는다 = 인스타에서 📥가 머리 위로 튀던 모양.
PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>fixture</title><style>
body{margin:0;background:#111;color:#eee;font:14px sans-serif;height:2400px}
.hdr{position:fixed;left:0;top:0;width:100%;height:120px;background:#222;z-index:50}
.grid{position:absolute;left:300px;top:90px;width:1000px}
.card{position:relative;overflow:hidden;width:222px;height:394px;float:left;margin:0 12px 24px 0}
.videoImage{position:relative;width:220px;height:293px}
.Z{position:absolute;left:0;top:0;width:220px;height:293px;overflow:hidden}
.box{position:relative;width:220px;height:293px}
.box img{width:220px;height:293px;display:block}
.over{position:absolute;left:0;top:0;width:220px;height:293px}
.inner{position:relative;width:100%;height:100%}
.modal{position:fixed;left:0;top:0;width:100%;height:100%;background:#000;z-index:900}
.modal video{width:100%;height:100%}
</style></head><body>
<div class="hdr">검색 머리</div>
<div class="grid" id="grid"></div>
<script>
(function () {
  var px = "data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==";
  var g = document.getElementById("grid");
  for (var i = 0; i < 8; i++) {
    var c = document.createElement("div"); c.className = "card search-result-card";
    c.innerHTML = '<div class="videoImage"><div class="Z"><div class="box"><img src="' + px + '"></div>' +
                  '<div class="over"><div class="inner"></div></div></div></div><div class="title">카드 ' + i + '</div>';
    g.appendChild(c);
    // 도우인은 영상 번호를 DOM 에 안 적는다 — React fiber 의 props 안에만 있다(실측: img 에서 5칸 위).
    var img = c.querySelector("img"), f = {memoizedProps: {awemeInfo: {awemeId: "74000000000000000" + (10 + i)}}, return: null};
    for (var k = 0; k < 5; k++) f = {memoizedProps: {className: "x"}, return: f};
    img["__reactFiber$fixture"] = f;
  }
  if (/[?&]modal_id=/.test(location.search)) {
    var m = document.createElement("div"); m.className = "modal";
    m.innerHTML = "<video></video><textarea style='position:absolute;left:-999px'></textarea>";
    document.body.appendChild(m);
  }
})();
</script></body></html>"""

# 인스타 검색 격자 본뜸: 카드 = 게시물 앵커. 첫 줄은 고정 머리에 덮인다. 옛 로직이 그려 둔 설명 줄을 미리 심어 둔다.
IG_PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>fixture</title><style>
body{margin:0;background:#fff;height:2400px}
.hdr{position:fixed;left:0;top:0;width:100%;height:120px;background:#eee;z-index:50}
.grid{position:absolute;left:300px;top:90px;width:960px}
.grid a{display:block;float:left;width:300px;height:400px;margin:0 8px 8px 0;position:relative}
.grid img{width:300px;height:400px;display:block}
</style></head><body><div class="hdr">검색 머리</div><div class="grid" id="grid"></div><script>
(function () {
  var px = "data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw==";
  var g = document.getElementById("grid");
  for (var i = 0; i < 6; i++) {
    var a = document.createElement("a"); a.href = "/reel/Fix" + i + "abc/"; a.className = "card";
    a.innerHTML = '<img src="' + px + '"><div class="ss-card-ko">옛 설명 줄</div>';
    g.appendChild(a);
  }
})();
</script></body></html>"""

IG_PROBE = r"""() => {
  const cards = [...document.querySelectorAll('.grid a')].map(a => { const b = a.querySelector('.ss-card-grab'), r = a.getBoundingClientRect();
    return { top: Math.round(r.top), btn: !!b, vis: b ? getComputedStyle(b).visibility : null }; });
  return { ver: window.__ssGrabVer, cards, ko: document.querySelectorAll('.ss-card-ko').length };
}"""

PROBE = r"""() => {
  const R = e => { const b = e.getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top), Math.round(b.width), Math.round(b.height)]; };
  const onScreen = e => { if (!e) return false; const b = e.getBoundingClientRect(), cs = getComputedStyle(e);
    return cs.display !== 'none' && cs.visibility !== 'hidden' && b.width > 0 && b.top >= 0 && b.bottom <= innerHeight && b.left >= 0 && b.right <= innerWidth; };
  const cards = [...document.querySelectorAll('.card')].map(c => {
    const b = c.querySelector('.ss-card-grab'), r = c.getBoundingClientRect();
    return { top: Math.round(r.top), btn: !!b, vis: b ? getComputedStyle(b).visibility : null, aid: b ? b.getAttribute('data-aid') : null };
  });
  const f = document.getElementById('ss-grab-btn');
  return { ver: window.__ssGrabVer, mw: document.documentElement.getAttribute('data-ss-douyin-mw'), cards,
    float: f ? { rect: R(f), disp: f.style.display, onScreen: onScreen(f) } : null,
    kwfloat: !!document.getElementById('ss-kwfloat'), kwpost: !!document.getElementById('ss-kwpost'), inner: [innerWidth, innerHeight] };
}"""


def main_world_js(logic_text, fn="_douyinMainWorld"):
    """zip 빌더(app._douyin_main_js)와 같은 방식 — 함수 본문을 잘라 즉시실행으로 감싼다."""
    head = "  function " + fn + "() {"
    i = logic_text.find(head)
    if i < 0:
        return ""
    rest = logic_text[i + len(head):]
    end = rest.find("\n  }")
    return "" if end < 0 else "(function () {" + rest[:end] + "\n})();\n"


def run(logic, shots=None):
    main = main_world_js(logic)
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1500, "height": 950}, locale="ko-KR")
        # 바깥으로는 한 건도 안 나간다 — douyin.com 주소만 본뜬 화면으로 답하고 나머지는 끊는다.
        def serve(r):
            u = r.request.url
            if "douyin.com/search/" in u:
                r.fulfill(status=200, content_type="text/html; charset=utf-8", body=PAGE)
            elif "instagram.com/explore/" in u:
                r.fulfill(status=200, content_type="text/html; charset=utf-8", body=IG_PAGE)
            else:
                r.abort()
        ctx.route("**/*", serve)
        ctx.add_init_script(STUB)
        for name, url in (("grid", "https://www.douyin.com/search/test"),
                          ("modal", "https://www.douyin.com/search/test?modal_id=7253754793980628239")):
            pg = ctx.new_page()
            pg.goto(url, wait_until="domcontentloaded")
            pg.add_script_tag(content=main)
            pg.add_script_tag(content=logic)
            pg.wait_for_timeout(5500)            # 로직 tick 2초 × 2
            out[name] = pg.evaluate(PROBE)
            if name == "grid":               # 검색어 판 머리를 두 번 눌러 '원래 자리'로 — 화면 밖으로 떨어지면 안 된다
                where = "() => { const b = document.getElementById('ss-kwfloat').getBoundingClientRect(); return [Math.round(b.left), Math.round(b.top)]; }"
                home = pg.evaluate(where)
                pg.dblclick("#ss-kwfloat > div:first-child > span")
                pg.wait_for_timeout(300)
                out["reset"] = {"home": home, "after": pg.evaluate(where)}
            if shots:
                pg.screenshot(path=str(Path(shots) / f"douyin_{name}.png"))
            pg.close()
        pg = ctx.new_page()
        pg.goto("https://www.instagram.com/explore/search/keyword/?q=fixture", wait_until="domcontentloaded")
        pg.add_script_tag(content=logic)
        pg.wait_for_timeout(5500)
        out["ig"] = pg.evaluate(IG_PROBE)
        if shots:
            pg.screenshot(path=str(Path(shots) / "instagram_grid.png"))
        pg.close()
        b.close()
    out["main_ok"] = bool(main)
    return out


def judge(o):
    res = []
    g, m = o["grid"], o["modal"]
    res.append(("메인월드 스크립트 추출", o["main_ok"] and g["mw"] == "1", f"mw={g['mw']}"))
    made = [c for c in g["cards"] if c["btn"]]
    res.append(("격자: 카드 8장 전부 📥 생성(영상 번호 읽음)", len(made) == 8 and all((c["aid"] or "").isdigit() for c in made), f"{len(made)}/8"))
    low = [c for c in g["cards"] if c["top"] >= 120]            # 머리(120px) 아래 줄
    seen = [c for c in low if c["btn"] and c["vis"] != "hidden"]
    res.append(("격자: 머리에 안 덮인 카드의 📥가 보인다", len(low) > 0 and len(seen) == len(low), f"{len(seen)}/{len(low)}"))
    top = [c for c in g["cards"] if c["top"] < 120 - 8 - 17]    # 📥 가운데(top+25)가 머리 밑에 깔린 줄
    hid = [c for c in top if c["btn"] and c["vis"] == "hidden"]
    res.append(("격자: 고정 머리에 덮인 카드의 📥는 숨는다", len(top) > 0 and len(hid) == len(top), f"{len(hid)}/{len(top)}"))
    res.append(("격자: 검색어 판이 뜬다", g["kwfloat"] and not g["kwpost"], f"판={g['kwfloat']} 상자={g['kwpost']}"))
    rs = o["reset"]
    res.append(("격자: 검색어 판을 두 번 눌러 되돌리면 원래 자리 그대로", rs["home"] == rs["after"], f"{rs['home']} → {rs['after']}"))
    f = m["float"]
    res.append(("영상 팝업: 📥 담기가 화면 안에 보인다", bool(f and f["onScreen"]), json.dumps(f, ensure_ascii=False)))
    res.append(("영상 팝업: 검색어 판은 '관련 검색어' 하나만", m["kwpost"] and not m["kwfloat"], f"판={m['kwfloat']} 상자={m['kwpost']}"))
    ig = o["ig"]
    ilow = [c for c in ig["cards"] if c["top"] >= 120]
    iseen = [c for c in ilow if c["btn"] and c["vis"] != "hidden"]
    res.append(("인스타 격자: 머리에 안 덮인 카드의 📥가 보인다", len(ilow) > 0 and len(iseen) == len(ilow), f"{len(iseen)}/{len(ilow)}"))
    itop = [c for c in ig["cards"] if c["top"] < 120 - 8 - 17]
    ihid = [c for c in itop if c["btn"] and c["vis"] == "hidden"]
    res.append(("인스타 격자: 고정 머리에 덮인 카드의 📥는 숨는다", len(itop) > 0 and len(ihid) == len(itop), f"{len(ihid)}/{len(itop)}"))
    res.append(("인스타 격자: 썸네일 한국어 설명 줄이 없다", ig["ko"] == 0, f"남은 줄 {ig['ko']}개"))
    return res


if __name__ == "__main__":
    logic_path, shots = LOGIC_PATH, None
    a = sys.argv[1:]
    if "--logic" in a:
        logic_path = Path(a[a.index("--logic") + 1])
    if "--shots" in a:
        shots = a[a.index("--shots") + 1]
        Path(shots).mkdir(parents=True, exist_ok=True)
    o = run(logic_path.read_text(encoding="utf-8"), shots)
    rows = judge(o)
    bad = 0
    for name, ok, detail in rows:
        bad += 0 if ok else 1
        print(("PASS" if ok else "FAIL"), "|", name, "|", detail)
    print(f"로직 {o['grid']['ver']} · 실패 {bad}/{len(rows)}")
    sys.exit(1 if bad else 0)
