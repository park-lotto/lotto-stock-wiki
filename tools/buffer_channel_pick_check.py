# -*- coding: utf-8 -*-
"""버퍼 계정에 유튜브가 둘일 때 폴더 → 채널 짝 시험(가짜 Buffer, 아무것도 안 올린다). 2026-10-28.
계정마다 유튜브가 둘이 됐다('995_1 썰템쇼'·'995_2 얜샷템'). 옛 코드는 첫 유튜브를 골라 새 채널이 앞에 오면
_1 영상이 _2 채널로 갔다. 고친 _targets: 폴더 이름의 채널명과 같은 유튜브만, 틱톡은 _1(원래 채널) 폴더에만.
    py tools/buffer_channel_pick_check.py          → 결과: 통과 / 실패
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")
from tools import buffer_post as bp

FAKE = [{"service": "youtube", "name": "얜샷템", "id": "Y2"},      # 새 채널이 목록 앞에 온다(10-28 실측 순서)
        {"service": "tiktok", "name": "user677", "id": "T1"},
        {"service": "youtube", "name": "썰템쇼", "id": "Y1"}]
bp.buffer_api.channels = lambda key: FAKE

cases = [("995_1 썰템쇼", ["Y1", "T1"]), ("995_2 얜샷템", ["Y2"]), ("995 썰템쇼", ["Y1", "T1"])]
bad = 0
for folder, want in cases:
    got = [c["id"] for c in bp._targets("k", folder)]
    ok = got == want
    bad += not ok
    print("OK  " if ok else "FAIL", folder, "→", got, "" if ok else f"(기대 {want})")
try:
    bp._targets("k", "995_3 없는채널")
    print("FAIL 없는 채널명인데 멈추지 않았다"); bad += 1
except RuntimeError:
    print("OK   없는 채널명은 멈춘다")
old = next(c for c in FAKE if c["service"] == "youtube")["id"]      # 옛 코드의 선택(첫 유튜브)
print(f"참고: 옛 코드는 '995_1 썰템쇼' 에 {old} 를 골랐다 — {'틀림(시험이 잡는 결함)' if old != 'Y1' else '같음'}")
print("결과:", "통과" if not bad else "실패")
sys.exit(1 if bad else 0)
