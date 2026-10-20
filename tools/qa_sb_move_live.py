# -*- coding: utf-8 -*-
"""관제 221 점검: 2단계 스토리보드 장면 카드 ▲▼(위·아래 칸으로 옮기기) — 라이브 실제 작업으로 연다.

    py tools/qa_sb_move_live.py <work_id>            # 배포본
    py tools/qa_sb_move_live.py <work_id> --local    # produce.html 만 이 트랙 파일로 바꿔 끼워(배포 전)

★저장은 막는다: /api/ 의 GET 아닌 요청은 전부 끊는다(작업·보드가 안 바뀐다).
잰다: 실제 마우스로 ▼를 누르면 ① 화면에서 그 장면이 아래 칸 맨 앞으로 가고 ② 3단계로 넘기는 보드(sbCurBoard)에도
      같은 칸에 실리고 ③ ▲로 되돌리면 위 칸 끝으로 돌아오는가. 첫 칸엔 ▲, 끝 칸엔 ▼가 없어야 한다.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.live_admin import admin_page  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STATE = """()=>{const ek=SB.view,bd=SB.made[ek];const rows=[...document.querySelectorAll('#s2Storyboard .sb-row, .sb-row')].filter(r=>r.querySelector('.sb-cth'));
  return {ek,n:bd.slots.length,ord:bd.slots.map((s,i)=>sbLiveIds(ek,i,s)),board:sbCurBoard(ek,bd).slots.map(s=>s.ids),
    up:rows.map(r=>r.querySelectorAll('.sb-mv[title^="위 칸"]').length),down:rows.map(r=>r.querySelectorAll('.sb-mv[title^="아래 칸"]').length)}}"""


def main(work, local):
    fails = []
    with admin_page("produce", viewport=(1600, 1000)) as pg:
        if local:
            body = open(os.path.join(ROOT, "shopping_shorts/static/produce.html"), encoding="utf-8").read()
            pg.route("**/produce?*", lambda r: r.fulfill(status=200, content_type="text/html; charset=utf-8", body=body)
                     if r.request.resource_type == "document" else r.continue_())
        blocked = []
        pg.route("**/api/**", lambda r: (blocked.append(r.request.url.split("/api/")[1][:60]), r.abort()) if r.request.method != "GET" else r.continue_())
        pg.goto("https://shoppingshorts.duckdns.org/produce?work=" + work, wait_until="domcontentloaded")
        pg.wait_for_function("typeof SB!=='undefined'&&SB.view&&SB.made&&SB.made[SB.view]&&document.querySelectorAll('.sb-cc').length>0", timeout=60000)
        pg.evaluate("window.saveWork=()=>{}")      # 자동저장도 끈다(이중 안전)
        pg.evaluate("jump(1)")                     # 2단계(대본생성) 화면으로
        pg.wait_for_function("[...document.querySelectorAll('.sb-cc')].some(x=>x.offsetParent)", timeout=30000)
        pg.wait_for_timeout(800)
        before = pg.evaluate(STATE)
        row = next((i for i, ids in enumerate(before["ord"]) if ids and i < before["n"] - 1), None)
        if row is None:
            print("옮길 장면이 있는 칸이 없다"); return 1
        if any(before["up"][0:1]):
            fails.append("첫 칸에 ▲가 있다")
        if before["down"] and before["down"][-1]:
            fails.append("끝 칸에 ▼가 있다")
        moved = before["ord"][row][0]
        card = pg.locator(".sb-row").filter(has=pg.locator(".sb-cth")).nth(row).locator(".sb-cc").first
        card.scroll_into_view_if_needed()
        dn = card.locator('.sb-mv[title^="아래 칸"]')
        if not dn.count():
            fails.append("%d번 칸 첫 장면에 ▼ 버튼이 없다" % (row + 1))
        else:
            dn.click(); pg.wait_for_timeout(700)
            mid = pg.evaluate(STATE)
            if moved in mid["ord"][row] or mid["ord"][row + 1][:1] != [moved]:
                fails.append("▼ 뒤 화면 칸 목록이 틀림: %s → %s" % (before["ord"][row:row + 2], mid["ord"][row:row + 2]))
            if mid["board"][row + 1][:1] != [moved] or moved in mid["board"][row]:
                fails.append("3단계로 넘기는 보드에 안 실림: %s" % mid["board"][row:row + 2])
            others = [i for i in range(before["n"]) if i not in (row, row + 1)]
            if any(mid["ord"][i] != before["ord"][i] for i in others):
                fails.append("다른 칸이 바뀜")
            dom_first = pg.evaluate("i=>{const r=[...document.querySelectorAll('.sb-row')].filter(r=>r.querySelector('.sb-cth'))[i];return r.querySelectorAll('.sb-cc').length}", row + 1)
            if dom_first != len(mid["ord"][row + 1]):
                fails.append("화면 카드 수(%d)와 칸 목록(%d)이 다름" % (dom_first, len(mid["ord"][row + 1])))
            back = pg.locator(".sb-row").filter(has=pg.locator(".sb-cth")).nth(row + 1).locator(".sb-cc").first.locator('.sb-mv[title^="위 칸"]')
            back.click(); pg.wait_for_timeout(700)
            end = pg.evaluate(STATE)
            if end["ord"][row + 1] != before["ord"][row + 1] or end["ord"][row][-1:] != [moved]:
                fails.append("▲로 되돌림이 틀림: %s" % end["ord"][row:row + 2])
            print(json.dumps({"row": row + 1, "moved": moved, "before": before["ord"][row:row + 2], "after_down": mid["ord"][row:row + 2],
                              "after_up": end["ord"][row:row + 2], "blocked_posts": sorted(set(blocked))}, ensure_ascii=False))
        pg.screenshot(path=os.path.join(os.environ.get("TEMP", "."), "sbmove_%s%s.png" % (work, "_local" if local else "")))
        if pg.errors:
            fails.append("페이지 오류: %s" % pg.errors)
    print("통과" if not fails else "실패 %d\n- " % len(fails) + "\n- ".join(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], "--local" in sys.argv))
