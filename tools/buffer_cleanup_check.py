# -*- coding: utf-8 -*-
"""buffer_post cleanup 시험(관제 282, 2026-10-29 — 매시간 정리가 ssh 120초 멈춤으로 10-27 16:36 뒤 한 번도 저장 못 함).
가짜 Buffer·가짜 ssh — 아무것도 안 지우고 안 올린다. 장부도 임시 파일.
    py tools/buffer_cleanup_check.py [buffer_post.py 경로]      # 경로를 주면 그 판본(예: 고치기 전 git show 본)을 시험
기대: ① ssh 가 멈춰도 프로그램이 안 죽고, Buffer 상태(sent/deleted)는 장부에 남는다
     ② error 행의 서버 사본은 안 지운다(Buffer 재시도가 404 나지 않게) · 장부에 끝으로 적지 않는다
     ③ 서버 사본은 ssh 한 번으로 지운다(행마다 접속하지 않는다)
     ④ ssh 가 살아나면 다음 실행에서 남은 사본을 지우고 cleaned 를 적는다
     ⑤ 게시됨인데 G: 예약\\ 에 파일이 없으면 'G:에없음'으로 적는다(조용히 '완료'라고 하지 않는다)"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
here = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "buffer_post.py")
sys.path.insert(0, os.path.dirname(here))
spec = importlib.util.spec_from_file_location("bp", path)
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)
fails = []


def check(name, got, want):
    print(("OK  " if got == want else "FAIL"), name, "" if got == want else f"→ {got!r} (기대 {want!r})")
    if got != want:
        fails.append(name)


tmp = tempfile.mkdtemp()
F = "950 숏템리폿"
d = os.path.join(tmp, "drive", F, "예약")
os.makedirs(d)
open(os.path.join(d, "a.mp4"), "wb").write(b"A")
open(os.path.join(d, "a.txt"), "w", encoding="utf-8").write("제목")
bp.DRIVE = os.path.join(tmp, "drive")
bp.LEDGER = os.path.join(tmp, "ledger.json")
bp.KEYS = os.path.join(tmp, "keys.json")
json.dump({F: "k"}, open(bp.KEYS, "w", encoding="utf-8"))
rows = [
    {"folder": F, "file": "a.mp4", "service": "youtube", "post_id": "p1", "remote": "r1.mp4"},   # sent, G: 에 있음
    {"folder": F, "file": "b.mp4", "service": "youtube", "post_id": "p2", "remote": "r2.mp4"},   # sent, G: 에 없음
    {"folder": F, "file": "c.mp4", "service": "tiktok", "post_id": "p3", "remote": "r3.mp4"},    # error
    {"folder": F, "file": "d.mp4", "service": "youtube", "post_id": "p4", "remote": "r4.mp4"},   # 지운 예약
    {"folder": F, "file": "e.mp4", "service": "youtube", "post_id": "p5", "remote": "r5.mp4"},   # 아직 scheduled
]
json.dump(rows, open(bp.LEDGER, "w", encoding="utf-8"))
status = {"p1": "sent", "p2": "sent", "p3": "error", "p5": "scheduled"}


def fake_status(key, pid):
    if pid not in status:
        raise bp.buffer_api.BufferNotFound(pid)
    return {"status": status[pid]}


bp.buffer_api.post_status = fake_status
ssh_calls = []
hang = [True]


def fake_run(args, **kw):
    if args and args[0] == "ssh":
        ssh_calls.append(args[-1])
        if hang[0]:
            raise subprocess.TimeoutExpired(args, kw.get("timeout"))
        return subprocess.CompletedProcess(args, 0, "", "")
    raise AssertionError(f"예상 못 한 실행: {args}")


bp.subprocess.run = fake_run


def ledger():
    return {r["post_id"]: r for r in json.load(open(bp.LEDGER, encoding="utf-8"))}


# ── 1회차: ssh 가 멈춘다 ──
crashed = None
try:
    bp.main(["cleanup"])
except BaseException as e:   # noqa: BLE001 — 옛 판본은 여기서 죽는다
    crashed = type(e).__name__
L = ledger()
check("① ssh 가 멈춰도 안 죽는다", crashed, None)
check("① sent 상태가 장부에 남는다", (L["p1"].get("final_status"), L["p2"].get("final_status")), ("sent", "sent"))
check("① 지운 예약도 장부에 남는다", L["p4"].get("final_status"), "deleted")
check("① 못 지운 사본은 cleaned 없음", L["p1"].get("cleaned"), None)
check("② error 는 끝으로 안 적는다", L["p3"].get("final_status"), None)
check("② error 사본은 지우려 하지 않는다", any("r3.mp4" in c for c in ssh_calls), False)
check("② 아직 scheduled 는 그대로", L["p5"].get("final_status"), None)
check("⑤ G: 에 있던 a → 완료로 이동", os.path.isfile(os.path.join(bp.DRIVE, F, "완료", "a.mp4")), True)
check("⑤ G: 에 없던 b → 'G:에없음'", L["p2"].get("done_where"), "G:에없음")

# ── 2회차: ssh 살아남 ──
hang[0] = False
ssh_calls.clear()
try:
    bp.main(["cleanup"])
except BaseException as e:   # noqa: BLE001
    crashed = type(e).__name__
L = ledger()
check("③ 서버 사본 지우기 = ssh 1번", len(ssh_calls), 1)
check("④ 남은 사본 r1·r2·r4 를 지운다", sorted(n for n in ("r1.mp4", "r2.mp4", "r4.mp4", "r3.mp4", "r5.mp4")
                                      if ssh_calls and n in ssh_calls[0]), ["r1.mp4", "r2.mp4", "r4.mp4"])
check("④ cleaned 적힘", all(L[p].get("cleaned") for p in ("p1", "p2", "p4")), True)
check("② error 는 여전히 사본 남김", L["p3"].get("cleaned"), None)

print("\n결과:", "통과" if not fails else f"실패 {len(fails)}건 — {fails}")
sys.exit(1 if fails else 0)
