# -*- coding: utf-8 -*-
"""buffer_post 인포크 관문 시험(관제 282, 사장님 10-26 "인포크 없으면 올리지 마라").
업로드·예약·인포크 페이지는 전부 가짜 — 아무것도 안 올라간다.
    py tools/buffer_inpock_gate_check.py [buffer_post.py 경로]
기대: ① '인포크:' 줄 없는 영상 = 안 올림  ② 공개 페이지에 없는 블록 = 안 올림  ③ 비공개·쿠팡 아닌 블록 = 안 올림
     ④ 있는 블록 = 올림 · 장부에 inpock 제목 기록  ⑤ Buffer 글에는 '인포크:' 줄이 안 들어간다"""
import importlib.util
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
here = os.path.dirname(os.path.abspath(__file__))
path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "buffer_post.py")
spec = importlib.util.spec_from_file_location("bp", path)
bp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bp)
fails = []


def check(name, got, want):
    print(("OK  " if got == want else "FAIL"), name, "" if got == want else f"→ {got!r} (기대 {want!r})")
    if got != want:
        fails.append(name)


F = "998_1 꿀템샷"
tmp = tempfile.mkdtemp()
d = os.path.join(tmp, F)
os.makedirs(d)
cases = {
    "no_line": "제목 없음줄\n\n설명",
    "missing": "제목\n\n설명\n인포크: [99] 없는 상품",
    "private": "제목\n\n설명\n인포크: [3] 숨긴 상품",
    "good": "좋은 제목\n\n설명 #쇼츠\n인포크: [10] 조선미녀 맑은쌀 선크림",
}
for i, (nm, txt) in enumerate(cases.items()):
    open(os.path.join(d, nm + ".mp4"), "wb").write(bytes([i]) * 100)
    open(os.path.join(d, nm + ".txt"), "w", encoding="utf-8").write(txt)
rows, sent = [], []
bp.DRIVE = tmp
bp._load = lambda p, default: rows if p == bp.LEDGER else {F: "k"}
bp._save_ledger = lambda r: None
bp._probe = lambda p: (20.0, 1080, 1920)
bp._upload = lambda p: ("r", "http://x")
bp.cmd_cleanup = lambda a=None: None
bp._inpock_blocks = lambda acct: [("[10] 조선미녀 맑은쌀 선크림", "https://link.coupang.com/a/x", True),
                                  ("[3] 숨긴 상품", "https://link.coupang.com/a/y", False)]
bp.buffer_api.channels = lambda k: [{"id": "yt", "service": "youtube", "name": "꿀템샷"}]
bp.buffer_api.schedule_video = lambda key, cid, cap, url, due_at=None, **k: (
    sent.append(cap) or {"id": f"p{len(sent)}", "dueAt": due_at})
bp.main(["post", "--folder", F, "--at", "2099-01-01 10:00", "--gap", "24"])
posted = sorted(r["file"] for r in rows)
check("① 줄 없음 안 올림 / ② 없는 블록 안 올림 / ③ 비공개 안 올림 / ④ 있는 블록만 올림", posted, ["good.mp4"])
check("④ 장부에 인포크 제목", [r.get("inpock") for r in rows], ["[10] 조선미녀 맑은쌀 선크림"])
check("⑤ Buffer 글에 '인포크:' 줄 없음", any("인포크:" in c for c in sent), False)
check("⑤ 제목·설명은 그대로", sent[0] if sent else None, "좋은 제목\n\n설명 #쇼츠")
print("\n결과:", "통과" if not fails else f"실패 {len(fails)}건 — {fails}")
sys.exit(1 if fails else 0)
