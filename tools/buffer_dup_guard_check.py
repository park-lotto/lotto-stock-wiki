# -*- coding: utf-8 -*-
"""buffer_post 중복 장치 시험(2026-10-26) — 실제 업로드·예약은 가짜로 바꿔 아무것도 안 올라간다.
    py tools/buffer_dup_guard_check.py <이미 올린 mp4> <그 폴더명> [<아직 안 올린 mp4>]
기대: 이미 올린 영상 = 원래 이름·바꾼 이름 둘 다 '⛔ 중복' (업로드 0) / 안 올린 영상 = 통과(업로드 1)."""
import os, sys, shutil, tempfile, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bp", os.path.join(here, "buffer_post.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
posted, folder = sys.argv[1], sys.argv[2]
fresh = sys.argv[3] if len(sys.argv) > 3 else None
tmp = tempfile.mkdtemp(); d = os.path.join(tmp, folder); os.makedirs(d)
calls = []
bp.DRIVE = tmp
bp._upload = lambda p: calls.append(os.path.basename(p)) or ("x", "http://x")
bp._remove_remote = lambda r: None
bp.buffer_api.schedule_video = lambda *a, **k: {"id": "fake", "dueAt": "fake"}
bp.cmd_cleanup = lambda a=None: None
bp._save_ledger = lambda rows: None
cases = {os.path.basename(posted): posted, "renamed_same.mp4": posted}
if fresh:
    cases["fresh_" + os.path.basename(fresh)] = fresh
for n, s in cases.items():
    shutil.copy2(s, os.path.join(d, n))
    open(os.path.join(d, os.path.splitext(n)[0] + ".txt"), "w", encoding="utf-8").write("제목\n\n설명")
bp.main(["post", "--folder", folder, "--at", "2099-01-01 10:00"])
shutil.rmtree(tmp)
want = ["fresh_" + os.path.basename(fresh)] if fresh else []
print("업로드 시도:", calls, "→", "통과" if calls == want else "실패")
sys.exit(0 if calls == want else 1)
