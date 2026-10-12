# -*- coding: utf-8 -*-
"""2단계 스토리보드 — 1단계에서 뺀 영상의 장면이 보드에 남아도 화면이 살아 있는가(결과물 검사).

2026-10-08 사고(work ad37c18f3be7): 스토리보드를 만든 뒤 1단계에서 영상 하나를 빼자, 보드에 남은 그 영상 장면 번호를
그리다 sbCellCards 가 죽어 2단계가 통째로 비었다(옛 재료·스타일 줄은 숨긴 채라 빈 화면).

라이브 작업을 **관리자로, 읽기 전용**(GET 만 통과)으로 열어 잰다. --local 이면 화면 파일만 이 폴더의 produce.html 로
바꿔 끼워(데이터는 라이브 그대로) 배포 전에 같은 작업으로 잰다.

    py tools/storyboard_mock/sb_gone_check.py <work_id> [--local] [--drop <영상 shortcode>] [--shot <png>]

--drop: 그 작업에 뺀 영상 장면이 없을 때(이미 정리됨) 화면 기억에서 그 영상 조각을 지워 같은 상황을 만든다.
뺀 장면이 0개면 **검사하지 않고 실패**로 끝낸다(아무것도 안 재고 통과하지 않게).
"""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_MEASURE = r"""async (drop) => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  for (let k = 0; k < 60 && !(SB.data && SB.data.pieces); k++) await wait(500);
  if (!(SB.data && SB.data.pieces)) return {fatal: '스토리보드 데이터를 못 받았다: ' + (SB.err || '')};
  if (drop) Object.keys(SB.data.pieces).forEach(id => { if (id.startsWith(drop + '-')) delete SB.data.pieces[id]; });
  const P = SB.data.pieces, box = document.getElementById('s2Storyboard');
  const rawGone = (ek, bd) => (bd.slots || []).flatMap((sl, i) => sbOrdOf(ek, i, sl).filter(id => !P[id]));
  const out = {pieces: Object.keys(P).length, tabs: {}, view0: SB.view};
  for (const [ek, bd] of Object.entries(SB.made)) {
    SB.view = ek; let threw = null;
    try { sbRender(); } catch (e) { threw = String(e).slice(0, 120); }
    const gone = rawGone(ek, bd);
    let outIds = null, outErr = null;
    try { outIds = sbCurBoard(ek, bd).slots.flatMap(s => s.ids || []); } catch (e) { outErr = String(e).slice(0, 120); }
    out.tabs[ek] = {gone: gone.length, threw, shown: getComputedStyle(box).display !== 'none', chars: box.innerText.length,
      goneCards: box.querySelectorAll('.sb-cc.gone').length, bar: (box.querySelector('.sb-gonebar') || {}).innerText || '',
      outGone: outIds ? outIds.filter(id => !P[id]).length : null, outErr,
      drawFail: box.querySelectorAll('.sb-drawfail').length,
      // 뺀 장면만 남은 칸에도 채울 후보가 뜨는가(안내가 '후보로 채우라'고 하므로)
      emptyRows: (bd.slots || []).map((sl, i) => [i, sbOrdOf(ek, i, sl)]).filter(([i, a]) => a.length && a.every(id => !P[id])).map(([i]) => i),
      emptyNoCand: (bd.slots || []).map((sl, i) => [i, sbOrdOf(ek, i, sl)]).filter(([i, a]) => a.length && a.every(id => !P[id]))
        .filter(([i]) => { const r = box.querySelectorAll('.sb-row')[i]; return !(r && r.querySelector('.sb-cand')); }).map(([i]) => i)};
  }
  // 초 다시 재기(/picks) 요청에 뺀 장면이 실리는가 — 요청은 바깥에서 막고 본문만 본다
  const ek = Object.keys(SB.made).find(k => rawGone(k, SB.made[k]).length);
  if (ek) { SB.view = ek; try { await sbPicksSync(ek, SB.made[ek]); } catch (e) { out.picksErr = String(e).slice(0, 120); } out.picksTab = ek; }
  out.goneIds = [...new Set(Object.entries(SB.made).flatMap(([k, b]) => rawGone(k, b)))];
  return out;
}"""


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    work = argv[0]
    local = "--local" in argv
    drop = argv[argv.index("--drop") + 1] if "--drop" in argv else ""
    shot = argv[argv.index("--shot") + 1] if "--shot" in argv else ""
    from playwright.sync_api import sync_playwright
    from tools.live_admin import BASE, admin_cookie
    ck = admin_cookie()
    html = (ROOT / "shopping_shorts" / "static" / "produce.html").read_bytes()
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1700, "height": 1000})
        ctx.add_cookies([{"name": "dash_auth", "value": ck, "domain": "shoppingshorts.duckdns.org", "path": "/",
                          "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        errs, picks = [], []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))

        def route(r):
            q = r.request
            if q.method != "GET":                      # 읽기 전용 — 고객·사장님 작업을 건드리지 않는다
                if q.url.endswith("/picks"):
                    picks.append(q.post_data or "")
                return r.abort()
            if local and q.resource_type == "document" and "/produce" in q.url:
                return r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
            return r.continue_()

        pg.route("**/*", route)
        pg.goto(BASE + "/produce?work=" + work, wait_until="domcontentloaded")
        pg.wait_for_timeout(6000)
        alive = pg.evaluate("typeof showPanel === 'function' && typeof SB !== 'undefined'")   # 화면 스크립트가 통째로 죽었나(문법 오류)
        on = alive and pg.evaluate("window.STORYBOARD_ON")
        d = pg.evaluate(_MEASURE, drop) if on else {"fatal": ("이 계정은 스토리보드가 꺼져 있다" if alive else "화면 스크립트가 통째로 죽었다: %s" % errs[:2])}
        if shot and on:                               # 눈으로 볼 2단계 화면(뺀 장면이 있는 탭)
            pg.evaluate("() => { cur = 8; showPanel(); }")
            pg.wait_for_timeout(1500)
            pg.locator("#s2Storyboard").screenshot(path=shot)
        b.close()
    print("화면:", "이 폴더 produce.html" if local else "라이브", "· 작업", work, ("· 지운 척한 영상 " + drop) if drop else "")
    if d.get("fatal"):
        print("✖", d["fatal"])
        return 1
    gone = set(d["goneIds"])
    bad = []
    for ek, t in d["tabs"].items():
        ok = (not t["threw"]) and t["shown"] and t["chars"] > 0 and t["goneCards"] == t["gone"] and t["outGone"] == 0 \
            and (not t["gone"] or str(t["gone"]) in t["bar"]) and not t["drawFail"] and not t["emptyNoCand"]
        print("  탭 %-6s 뺀 장면 %2d · 그리기 %s · 보임 %s(%d자) · 뺀 장면 카드 %s · 내보내는 뺀 장면 %s · 안내 %s" % (
            ek, t["gone"], "죽음(" + t["threw"] + ")" if t["threw"] else "정상", t["shown"], t["chars"], t["goneCards"], t["outGone"],
            "있음" if t["bar"] else "없음") + (" · 장면 없는 칸 %s 중 후보 없는 칸 %s" % (t["emptyRows"], t["emptyNoCand"]) if t["emptyRows"] else ""))
        if not ok:
            bad.append(ek)
    sent = [i for body in picks for s in (json.loads(body).get("slots") or []) for i in (s.get("ids") or []) if i in gone]
    print("  초 다시 재기 요청 %d건 · 그 안의 뺀 장면 %d개" % (len(picks), len(sent)))
    print("  페이지 오류 %d건 %s" % (len(errs), errs[:2]))
    if not gone:
        print("✖ 이 작업엔 뺀 영상 장면이 없다 — 잰 게 없다(--drop <영상>으로 상황을 만들어라)")
        return 1
    if bad or errs or sent or not picks:
        print("✖ 실패 — 탭 %s · 오류 %d · 요청에 실린 뺀 장면 %d · 요청 %d건" % (bad, len(errs), len(sent), len(picks)))
        return 1
    print("✅ 통과 — 뺀 장면 %d개(탭 %d개)가 남아 있어도 전부 그려지고, 내보내는 값에 하나도 안 실린다" % (len(gone), len(d["tabs"])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
