# 대본 스타일별 흐름 틀 점검(2026-10-04 사장님 "그 틀을 대본 스타일별로 점검해봐")
# 서버에서: python3 arc_audit.py  (storyboard_trial.py 의 _families·arc_rank·arc_place 를 그대로 쓴다 — 판단은 거기 한 곳)
# 스타일마다: 칸 → 흐름 순위, 순서가 뒤집힌 곳, 고조·반전·반응을 끼우면 어디로 가나
import json, os, sqlite3, sys
sys.path.insert(0, os.getcwd())
DB = "shopping_shorts/data/reference.db"
from shopping_shorts import storyboard as T   # 판단은 라이브 모듈 한 곳(관제 120)

KO = {0: "훅", 1: "미끼", 2: "불편", 3: "정체", 4: "특징", 5: "고조", 6: "반전", 7: "이점·반응", 8: "마무리"}
db = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
out = []
for n, f, _ in T._families(db):
    roles = f["roles"]
    rk = [T.arc_rank(r) for r in roles]
    inv = [(roles[i], roles[i + 1]) for i in range(len(rk) - 1) if rk[i + 1] < rk[i]]
    sl = [{"slot": r} for r in roles]
    place = {e: T.arc_place(sl, e) for e in ("escalation", "twist", "proof")}
    have = {e: any(r.split("_")[0] in dict(T.EXTRA_KIN)[e] for r in roles) for e in ("escalation", "twist", "proof")}
    out.append({"id": n, "name": f["names"][0] + (" 외 %d" % (len(f["names"]) - 1) if len(f["names"]) > 1 else ""),
                "flow": " → ".join("%s(%s)" % (r, KO[k]) for r, k in zip(roles, rk)), "inversions": inv,
                "place": place, "have": have})
print("RESULT " + json.dumps(out, ensure_ascii=False))
