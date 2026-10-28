# -*- coding: utf-8 -*-
"""관제 220 점검: 3단계 소스별 한 줄 목록의 ◀ ▶ 버튼 — 라이브 실제 작업 데이터로 연다.

    py tools/qa_palnav_live.py <job_id>            # 배포본 그대로
    py tools/qa_palnav_live.py <job_id> --local    # scene_lab.html 만 이 트랙 파일로 바꿔 끼워(배포 전) 같은 검사

읽기만 한다(소스별 보기로 바꾸고 버튼을 누르기만 — 칸 편성은 안 건드린다).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.live_admin import admin_page  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(job, local):
    with admin_page("produce", viewport=(1600, 1000)) as pg:
        if local:
            body = open(os.path.join(ROOT, "shopping_shorts/static/scene_lab.html"), encoding="utf-8").read()
            pg.route("**/scene_lab.html*", lambda route: route.fulfill(status=200, content_type="text/html; charset=utf-8", body=body))
        pg.goto("https://shoppingshorts.duckdns.org/scene_lab.html?job=" + job, wait_until="domcontentloaded")
        pg.wait_for_function("document.querySelectorAll('#palette .seg').length>0", timeout=60000)
        pg.evaluate("setGroupMode('src')")
        pg.wait_for_timeout(800)
        rows = pg.evaluate("""()=>[...document.querySelectorAll('#palette .palrowwrap')].map(w=>{const r=w.querySelector('.thumbs.oneline');
            return {max:r?r.scrollWidth-r.clientWidth:-1,l:!!w.querySelector('.palnav.l:not([hidden])'),r:!!w.querySelector('.palnav.r:not([hidden])'),n:w.querySelectorAll('.palnav').length}})""")
        out = {"rows": len(rows), "with_buttons": sum(1 for r in rows if r["n"] == 2), "scrollable": sum(1 for r in rows if r["max"] > 1)}
        fails = []
        if not rows or out["with_buttons"] != len(rows):
            fails.append("줄마다 버튼 2개가 아님: %s" % rows)
        for r in rows:
            if r["max"] > 1 and (r["l"] or not r["r"]):
                fails.append("넘칠 줄인데 처음 상태가 ◀숨김·▶보임이 아님: %s" % r)
            if r["max"] <= 1 and (r["l"] or r["r"]):
                fails.append("안 넘치는 줄에 버튼이 보임: %s" % r)
        idx = next((i for i, r in enumerate(rows) if r["max"] > 1), None)
        if idx is not None:
            wrap = pg.locator("#palette .palrowwrap").nth(idx)
            wrap.scroll_into_view_if_needed()
            wrap.locator(".palnav.r").click()            # 실제 마우스 클릭(사람이 누른 것과 같은 길)
            pg.wait_for_timeout(900)
            after = pg.evaluate("""i=>{const w=document.querySelectorAll('#palette .palrowwrap')[i],r=w.querySelector('.thumbs.oneline');
                return {left:r.scrollLeft,width:r.clientWidth,max:r.scrollWidth-r.clientWidth,l:!w.querySelector('.palnav.l').hidden}}""", idx)
            out["after_right"] = after
            if after["left"] < min(after["max"] - 1, after["width"] * 0.5):   # 한 번에 보이는 폭의 절반 이상(남은 게 그보다 적으면 끝까지)
                fails.append("▶를 눌러도 충분히 안 넘어감: %s" % after)
            if not after["l"]:
                fails.append("넘긴 뒤 ◀가 안 나타남")
            for _ in range(40):                      # 끝까지 넘겨 ▶가 숨는지
                b = wrap.locator(".palnav.r")
                if b.is_hidden():
                    break
                b.click(); pg.wait_for_timeout(450)
            out["right_hidden_at_end"] = wrap.locator(".palnav.r").is_hidden()
            if not out["right_hidden_at_end"]:
                fails.append("끝에 닿아도 ▶가 남아 있음")
            wrap.locator(".palnav.l").click(); pg.wait_for_timeout(900)
            out["back_left"] = pg.evaluate("i=>document.querySelectorAll('#palette .palrowwrap')[i].querySelector('.thumbs.oneline').scrollLeft", idx)
        else:
            fails.append("넘치는 줄이 없어 누르기 검사를 못 함(소스가 짧은 작업)")
        pg.screenshot(path=os.path.join(os.environ.get("TEMP", "."), "palnav_%s%s.png" % (job, "_local" if local else "")))
        if pg.errors:
            fails.append("페이지 오류: %s" % pg.errors)
        print(json.dumps(out, ensure_ascii=False))
        print("통과" if not fails else "실패 %d\n- " % len(fails) + "\n- ".join(fails))
        return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--local" in sys.argv))
