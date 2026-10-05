# -*- coding: utf-8 -*-
"""상자 담기 배치 전수 점검(사장님 10-05): 만든 스토리보드마다 상자 10개 × (AI가 쓴 장면 / 안 쓴 장면)을 넣어
  ① 훅 → 첫 칸 ② CTA → CTA 칸 있을 때만, 없으면 '못 넣은 장면' ③ 담은 장면이 칸에도 '못 넣은 장면'에도 없는 경우 0 을 잰다.
쓰는 법: py tools/storyboard_mock/audit_role_picks.py %TEMP%/sbtrial_*.json"""
import copy, glob, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
src = open(os.path.join(os.path.dirname(__file__), "..", "storyboard_trial.py"), encoding="utf-8").read()
ns = {}
exec(src[src.index("BOX_SLOTS ="):src.index("def _board(")], ns)
B, apply = ns["BOX_SLOTS"], ns["_apply_role_picks"]
bad = tot = 0
for p in sys.argv[1:] or glob.glob(os.path.join(os.environ.get("TEMP", "."), "sbtrial_*.json")):
    t = json.load(open(p, encoding="utf-8"))
    for k, bd in t["boards"].items():
        used = [c for s in bd["slots"] for c in s.get("ids") or []]
        has_cta = any(str(s["slot"]).lower().split("_")[0] in B["CTA·가격"] for s in bd["slots"])
        out = []
        for box in B:
            for sid in (used[len(used) // 2], "NEW-9"):     # AI가 이미 쓴 장면 / 아무 칸에도 없는 장면
                sl = copy.deepcopy(bd["slots"])
                _, left = apply(sl, "%s: %s" % (box, sid))
                at = [i for i, s in enumerate(sl) if sid in (s.get("ids") or [])]
                inleft = any(x["id"] == sid for x in left)
                ok = bool(at) != inleft
                if box == "훅":
                    ok = ok and at == [0] and sl[0]["ids"][0] == sid
                if box == "CTA·가격":
                    ok = ok and (bool(at) == has_cta)
                tot += 1
                if not ok:
                    bad += 1
                out.append("%s/%s→%s" % (box[:4], "AI" if sid != "NEW-9" else "새", ("칸%d" % (at[0] + 1)) if at else "아래카드"))
        print(os.path.basename(p)[8:20], k, "CTA칸" if has_cta else "CTA없음", "|", " ".join(out))
print("어긋남 %d / %d" % (bad, tot))
sys.exit(1 if bad else 0)
