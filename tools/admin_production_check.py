# -*- coding: utf-8 -*-
"""오늘 제작 현황(/admin/production) — 자동 갱신이 돌아도 보던 영상이 안 끊기는가(결과물 검사, 관제 167).

2026-10-09 사장님: "몇 초 지나면 계속 새로고침돼서 영상을 보다가 끊긴다". 30초마다 load() → render() 가 목록(#grid)을
innerHTML 로 통째로 다시 그려 <video> 요소가 전부 새로 만들어졌다(재생 중이던 것도).

라이브를 관리자로, 읽기 전용(GET 만 통과)으로 열어 잰다. --local 이면 화면 파일만 이 폴더 것으로 바꿔 끼운다.

    py tools/admin_production_check.py [--local]

재는 것: 영상 하나를 재생 → 갱신(load)을 두 번 돌린다 → ① 그 <video> 요소가 그대로인가 ② 재생이 이어지는가(위치가 늘었나)
③ 화면의 다른 영상 요소가 몇 개 새로 만들어졌나 ④ 갱신 뒤 카드 순서·개수가 서버 목록과 같은가.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_JS = r"""async () => {
  const wait = ms => new Promise(r => setTimeout(r, ms));
  for (let k = 0; k < 40 && !document.querySelector('#grid video'); k++) await wait(500);
  const vids = [...document.querySelectorAll('#grid video')];
  if (!vids.length) return {fatal: '영상이 든 카드가 없다(잴 게 없다)'};
  vids.forEach((v, i) => { v.__mark = i + 1; });
  const v = vids[0]; v.muted = true;
  let playErr = null;
  try { await v.play(); } catch (e) { playErr = String(e).slice(0, 120); }
  await wait(2500);
  const t1 = v.currentTime;
  await load(); await wait(1500);
  await load(); await wait(1500);
  const now = [...document.querySelectorAll('#grid video')];
  const same = document.contains(v) && now.includes(v);
  const t2 = v.currentTime;
  const want = JOBS.filter(j => FILTER === 'all' ? true : FILTER === 'video' ? j.has_video
      : FILTER === 'failed' ? j.status === 'failed' : RUNNING.indexOf(j.status) >= 0).map(j => String(j.job_id));
  const cards = [...document.querySelectorAll('#grid > .job')];
  const got = cards.map(c => c.dataset.id || '');
  return {videos: vids.length, playErr, same, paused: v.paused, t1, t2,
    remade: now.filter(x => !x.__mark).length, kept: now.filter(x => x.__mark).length,
    cards: cards.length, want: want.length, orderOk: got.every(Boolean) ? got.join() === want.join() : null,
    tiles: document.querySelectorAll('#cards .card').length};
}"""


def main(argv):
    local = "--local" in argv
    from playwright.sync_api import sync_playwright
    from tools.live_admin import BASE, admin_cookie
    ck = admin_cookie()
    html = (ROOT / "shopping_shorts" / "static" / "admin_production.html").read_bytes()
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")       # 설치된 크롬 — 완성본(H.264)을 실제로 재생해야 '이어지나'를 잰다
        except Exception:                                 # noqa: BLE001 — 크롬이 없으면 기본 브라우저(재생은 못 할 수 있다)
            b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1600, "height": 1200})
        ctx.add_cookies([{"name": "dash_auth", "value": ck, "domain": "shoppingshorts.duckdns.org", "path": "/",
                          "httpOnly": True, "secure": True, "sameSite": "Lax"}])
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)[:200]))

        def route(r):
            q = r.request
            if q.method != "GET":
                return r.abort()
            if local and q.resource_type == "document" and "/admin/production" in q.url:
                return r.fulfill(status=200, content_type="text/html; charset=utf-8", body=html)
            return r.continue_()

        pg.route("**/*", route)
        pg.goto(BASE + "/admin/production", wait_until="domcontentloaded")
        pg.wait_for_timeout(2500)
        d = pg.evaluate(_JS)
        b.close()
    print("화면:", "이 폴더 admin_production.html" if local else "라이브")
    if d.get("fatal"):
        print("✖", d["fatal"])
        return 1
    played = (not d["playErr"]) and d["t1"] > 0.5
    print("  영상 카드 %d개 · 재생 %s(%.1f초 지점)" % (d["videos"], "됨" if played else "안 됨: %s" % d["playErr"], d["t1"]))
    print("  갱신 2번 뒤: 보던 영상 요소 %s · 멈춤 %s · 위치 %.1f → %.1f초" % ("그대로" if d["same"] else "새로 만들어짐", d["paused"], d["t1"], d["t2"]))
    print("  다른 영상 요소: 그대로 %d · 새로 만들어짐 %d" % (d["kept"], d["remade"]))
    print("  카드 %d개(서버 목록 %d) · 순서 일치 %s · 숫자 타일 %d · 페이지 오류 %d %s" % (
        d["cards"], d["want"], d["orderOk"], d["tiles"], len(errs), errs[:2]))
    ok = d["same"] and d["cards"] == d["want"] and d["orderOk"] is True and d["tiles"] == 5 and not errs \
        and (not played or (not d["paused"] and d["t2"] > d["t1"] + 1.0))
    if not played:
        print("  ⚠️ 이 브라우저에서 재생이 안 돼 '이어지나'는 못 쟀다 — 요소가 그대로인지만 봤다")
    print("✅ 통과 — 갱신이 돌아도 보던 영상이 그대로 이어진다" if ok else "✖ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
