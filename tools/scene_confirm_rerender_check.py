# -*- coding: utf-8 -*-
"""3단계 [완성본 만들기] 재렌더 판정 시험(관제 288) — 라이브 서버 판정(/api/mix/status preview_stale)을 그대로 쓴다.

    py tools/scene_confirm_rerender_check.py <낡은 job> <최신 job> [--inject]

관리자로 scene_lab.html?job=… 을 열고(저장·렌더 POST 는 전부 막는다), 완성본 칸에 영상을 넣은 채 _askRender 를 부른다.
  --inject : 트랙의 scene_lab.html 에서 _askRender 를 떼어 페이지에 덮어쓴다(배포 전 시험). 없으면 라이브 코드 그대로.
기대: 낡은 job = 영상을 비우고 렌더 길로 간다(부모가 없으니 '제작소 화면에서 열어야' 안내) / 최신 job = 영상 그대로(재렌더 0).
고치기 전 코드(라이브, --inject 없이) = 두 job 모두 영상 그대로 → 낡은 job 에서 실패해야 시험이 무언가를 잰다.
"""
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from tools.live_admin import admin_page  # noqa: E402


def _local_ask_render():
    s = open(os.path.join(ROOT, "shopping_shorts", "static", "scene_lab.html"), encoding="utf-8").read()
    i = s.index("async function _askRender(){")
    j = s.index("\nfunction _cfEnable", i)
    return s[i:j]


def run(job, inject):
    posts = []

    def setup(pg):
        def guard(route):
            if route.request.method != "GET":
                posts.append(route.request.url.split("?")[0][-60:])
                return route.abort()
            return route.continue_()
        pg.route("**/*", guard)

    with admin_page(f"scene_lab.html?job={job}", setup=setup) as pg:
        for _ in range(30):
            try:
                if pg.evaluate("() => !!(window.DATA && DATA.beats && DATA.beats.length)"):
                    break
            except Exception:
                pass
            time.sleep(1)
        if inject:
            pg.evaluate("(src) => { (0, eval)(src); }", _local_ask_render())
        pg.evaluate("""() => { const b = document.getElementById('confirmBody');
            b.innerHTML = '<video src="/api/produce/mix/preview/' + SL.job + '"></video>'; }""")
        pg.evaluate("() => _askRender()")
        time.sleep(4)
        r = pg.evaluate("""() => { const b = document.getElementById('confirmBody');
            return {video: !!b.querySelector('video'), text: (b.innerText || '').trim().slice(0, 60)}; }""")
        r["posts"] = posts
        return r


def main():
    stale_job, fresh_job = sys.argv[1], sys.argv[2]
    inject = "--inject" in sys.argv
    fails = []
    a = run(stale_job, inject)
    print("낡은 job", stale_job, a)
    if a["video"]:
        fails.append("낡은 완성본인데 영상을 그대로 둠(재렌더 안 함)")
    b = run(fresh_job, inject)
    print("최신 job", fresh_job, b)
    if not b["video"]:
        fails.append("최신 완성본인데 영상을 비움(불필요한 유료 재렌더)")
    print("결과:", "통과" if not fails else f"실패 {fails}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
