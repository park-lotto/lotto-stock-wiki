# -*- coding: utf-8 -*-
"""뜯기 재점검 판정기(tools/calcopy/engine/recheck.py) 오판 수리 — 답을 아는 시험(4판 결함 D12).

행은 실제 점검.md 에서 그대로 옮겼다(썰풀다 1_Vt·7DY·ho5G 말투, yummyknow rGFX 아웃트로). 정답: 전부 '맞음'.
옛 판정기(행 전체 글을 정답으로 읽음 · '존댓말' 먼저 · 아웃트로를 틀 다른 구간 전체와 비교)는 4행 모두 '틀림'을 냈다.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools.calcopy.engine import recheck as rc  # noqa: E402

HEAD_S = "| 항목 | 시트로 본 것 | 분석기 | 판정 | 근거 |\n|---|---|---|---|---|\n"
ROWS_TONE = [  # (점검.md 행, 새 결과 존댓말 비율 — engine_뜯기3 실제 값)
    ("| 말투 | 반말 음슴체(~였음, ~는 거, ~다고) | 존댓말 0.0, 음슴체·전언 끝꼴 | 맞음 | 받아쓰기 기반이라 자막 실패와 무관 |", 0.0),
    ("| 말투 | 반말 나레(~거임, ~했는데, ~다는 거) + 인용 존댓말(빼앗깁니다!) | 존댓말 0.286 (받아쓰기 구절 7개) | 맞음 | 받아쓰기로 잰 것이라 자막 실패와 무관 |", 0.182),
    ("| 말투 | 반말(~버림, ~했는데, ~갔다고), 인용만 존댓말 | 존댓말 비율 0.1 | 맞음 | |", 0.1),
]


def test_tone_banmal_rows_are_right():
    for line, pr in ROWS_TONE:
        row = rc.parse_check(HEAD_S + line)[0]
        R = {"script_tone": {"ok": True, "polite_ratio": pr}}
        assert rc.judge_row(R, row)[0] == "맞음", line


def test_tone_polite_still_judged():
    # 반대쪽도 잡아야 한다(mY 점검.md '존댓말 나레' + 비율 0.1 이면 틀림)
    row = rc.parse_check("| 항목 | 정답 | 1판 | 판정 |\n|---|---|---|---|\n| 말투 | 존댓말 나레 | — | 맞음 |")[0]
    assert rc.judge_row({"script_tone": {"ok": True, "polite_ratio": 0.1}}, row)[0] == "틀림"
    assert rc.judge_row({"script_tone": {"ok": True, "polite_ratio": 1.0}}, row)[0] == "맞음"


def test_outro_ignores_opening_hook_card():
    row = rc.parse_check("| 항목 | 분석기 | 정답 | 판정 | 근거 |\n|---|---|---|---|---|\n| 아웃트로 | 언급 없음 | 없음 | 맞음 | |")[0]
    R = {"probe": {"duration": 33.7}, "layout": {"other_frame_segments": [[0.0, 1.5]]}}   # rGFX 실제 값: 훅 카드만
    assert rc.judge_row(R, row)[0] == "맞음"
    R2 = {"probe": {"duration": 33.7}, "layout": {"other_frame_segments": [[0.0, 1.5], [31.5, 33.7]]}}
    assert rc.judge_row(R2, row)[0] == "틀림"                                           # 끝에 붙은 다른 틀은 아웃트로
