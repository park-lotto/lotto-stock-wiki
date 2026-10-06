# -*- coding: utf-8 -*-
"""관제 147 라이브 실측 — 1단계 씨앗 + 스토리보드 재료·씨앗 신선도.

관리자 세션(tools/live_admin.admin_page)으로 라이브 화면을 열어:
  ① 작업파일을 열면 화면 seedSync 가 씨앗(AI PICK)에 seedNoAuto 를 다는가 + 1단계 카드 🌱 배지
  ② /prepare → 장면 목록에 담은 영상 전부(씨앗 포함 재료 전체)가 묶이는가
  ③ AI 자동 보드 칸에 씨앗 조각이 0개인가

쓰는 법:  py tools/seed_stage1_live_check.py <work_id> [--wait 300]
끝 코드: 통과 0 / 실패 1
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.live_admin import admin_page  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("work_id")
    ap.add_argument("--wait", type=int, default=300)
    a = ap.parse_args()
    jid = "w:" + a.work_id
    ok = True
    with admin_page("produce?work=" + a.work_id) as pg:
        pg.wait_for_timeout(8000)
        hand = pg.evaluate("(HANDOFF||[]).map(h=>({sc:h.shortcode, use:!!h.useFootage, seed:!!h.seedNoAuto, bb:!!h.bbMain}))")
        seed_code = pg.evaluate("typeof _seedCode==='function' ? _seedCode() : null")
        badges = pg.evaluate("document.querySelectorAll('#poolList .pool-card').length + ':' + "
                             "[...document.querySelectorAll('#poolList .pool-card span')].filter(s=>s.textContent.includes('씨앗')).length")
        print("담은 영상:", json.dumps(hand, ensure_ascii=False))
        print("씨앗(_seedCode):", seed_code, "| 카드:배지 =", badges)
        seeds = [h["sc"] for h in hand if h["seed"]]
        if not seed_code or seeds != [seed_code]:
            print("❌ 씨앗 표식이 씨앗 한 편에만 붙지 않았다"); ok = False
        # 미리 만들기 — 서버가 다 들어왔나·낡았나를 본다
        t0 = time.time()
        res = None
        while time.time() - t0 < a.wait:
            r = pg.evaluate("j=>fetch('/api/produce/storyboard/'+encodeURIComponent(j)+'/prepare',{method:'POST'}).then(r=>r.json())", jid)
            d = pg.evaluate("j=>fetch('/api/produce/storyboard/'+encodeURIComponent(j)).then(r=>r.json())", jid)
            t = (d.get("tasks") or {})
            auto = t.get("board:auto") or {}
            run = any((v or {}).get("state") == "run" for v in t.values())
            print("  %3ds prepare=%s auto=%s run=%s" % (time.time() - t0, r, auto.get("state"), run), flush=True)
            if auto.get("state") == "done" and not run and not r.get("started") and not r.get("busy") and not r.get("waiting"):
                res = d
                break
            pg.wait_for_timeout(10000)
        if not res:
            print("❌ 시간 안에 자동 보드가 안 끝났다"); return 1
        pieces = res.get("pieces") or {}
        st = res.get("state") or {}
        inv = st.get("inventory") or {}
        in_groups = {c for g in inv.get("groups") or [] for c in g.get("ids") or []}
        vids = sorted({p.rsplit("-", 1)[0] for p in pieces})
        cov = sorted({c.rsplit("-", 1)[0] for c in in_groups})
        print("재료 영상:", vids)
        print("장면 목록에 든 영상:", cov, "| mat_sig:", st.get("mat_sig"))
        if set(cov) != set(vids):
            print("❌ 장면 목록에 빠진 영상이 있다"); ok = False
        board = (res.get("tasks") or {}).get("board:auto", {}).get("result") or {}
        ids = [c for x in board.get("slots") or [] for c in (x.get("ids") or [])]
        seed_ids = [c for c in ids if (pieces.get(c) or {}).get("seed")]
        unknown = [c for c in ids if c not in pieces]
        print("자동 보드 칸 %d · 조각 %d · 씨앗 조각 %d · 모르는 번호 %d · seed_sig=%s" % (
            len(board.get("slots") or []), len(ids), len(seed_ids), len(unknown), board.get("seed_sig")))
        if seed_ids:
            print("❌ 자동 보드에 씨앗 조각:", seed_ids); ok = False
        if unknown:
            print("❌ 장면 번호가 아닌 것(묶음 이름 등):", unknown); ok = False
    print("✅ 통과" if ok else "❌ 실패")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
