# -*- coding: utf-8 -*-
"""버퍼 올리기 전 한글 파일 이름 → 영어 규칙 이름 시험(사장님 11-04 "한글로 이름 되어 있으면 버퍼 올리기 전에 영어 규칙대로 바꿔").
실제 업로드·예약은 전부 가짜 — 아무것도 안 올라간다. 영상 파일도 임시로 만든다.
    py tools/buffer_name_check.py
기대: ① 한글 이름 영상은 post 가 안 올림(업로드 0) ② rename 이 NN_영어.mp4 + .txt 같이 바꾸고 번호는 폴더(예약·완료 포함) 다음
     ③ 바꾼 뒤엔 올라감 ④ 규칙 밖 영어(대문자·빈칸)는 rename 거절 ⑤ ASCII 이름(볼케이노 moacco_… 등)은 막지 않음."""
import os, sys, tempfile, importlib.util
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("bp", os.path.join(here, "buffer_post.py"))
bp = importlib.util.module_from_spec(spec); spec.loader.exec_module(bp)
fails = []


def check(name, got, want):
    print(("OK  " if got == want else "FAIL"), name, got if got != want else "")
    if got != want:
        fails.append(name)


F = "21(수창) 쓸데수집"
tmp = tempfile.mkdtemp(); d = os.path.join(tmp, F); os.makedirs(os.path.join(d, bp.DONE))
open(os.path.join(d, bp.DONE, "07_old_item.mp4"), "wb").write(b"old")          # 완료 폴더의 마지막 번호 = 07
for nm, body in (("새우깡 리뷰.mp4", b"K" * 1000), ("moacco_cheap-chinese-bread.mp4", b"V" * 1000)):
    open(os.path.join(d, nm), "wb").write(body)
    open(os.path.join(d, nm[:-4] + ".txt"), "w", encoding="utf-8").write("제목\n\n설명\n인포크: [1] 시험 상품")
rows, calls = [], []
bp.DRIVE = tmp
bp._load = lambda p, default: rows if p == bp.LEDGER else {F: "k"}
bp._save_ledger = lambda r: None
bp._probe = lambda p: (20.0, 1080, 1920)
bp._inpock_check = lambda folder, block: None
bp._upload = lambda p: ("r", "http://x")
bp._remove_remote = lambda r: None
bp.cmd_cleanup = lambda a=None: None
bp.buffer_api.channels = lambda k: [{"id": "yt", "service": "youtube", "name": "Y"}]
bp.buffer_api.schedule_video = lambda key, cid, cap, url, due_at=None, **k: (
    calls.append(cid) or {"id": f"p{len(calls)}", "dueAt": due_at})

bp.main(["post", "--folder", F])
check("① 한글 이름은 안 올라감", sorted(r["file"] for r in rows), ["moacco_cheap-chinese-bread.mp4"])
check("⑤ ASCII 이름(볼케이노 예외)은 올라감", "moacco_cheap-chinese-bread.mp4" in [r["file"] for r in rows], True)
check("한글 이름 영상은 꼭대기에 그대로", os.path.isfile(os.path.join(d, "새우깡 리뷰.mp4")), True)

try:
    bp.main(["rename", "--folder", F, "새우깡 리뷰.mp4", "Shrimp Crackers"])
    check("④ 규칙 밖 영어는 거절", "통과함", "거절")
except SystemExit as e:
    check("④ 규칙 밖 영어는 거절", "규칙 밖" in str(e), True)
bp.main(["rename", "--folder", F, "새우깡 리뷰.mp4", "shrimp_crackers"])
check("② 번호 = 완료 폴더 마지막(07) 다음", os.path.isfile(os.path.join(d, "08_shrimp_crackers.mp4")), True)
check("② .txt 도 같이 바뀜", os.path.isfile(os.path.join(d, "08_shrimp_crackers.txt"))
      and not os.path.exists(os.path.join(d, "새우깡 리뷰.txt")), True)

bp.main(["post", "--folder", F])
check("③ 바꾼 뒤엔 올라감", "08_shrimp_crackers.mp4" in [r["file"] for r in rows], True)

print("\n결과:", "전부 통과" if not fails else f"실패 {len(fails)}: {fails}")
sys.exit(1 if fails else 0)
