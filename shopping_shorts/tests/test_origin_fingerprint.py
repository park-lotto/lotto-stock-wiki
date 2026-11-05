# -*- coding: utf-8 -*-
"""rules.fingerprint 비교 창 길이(98 #117) — 받아쓰기 한 낱말만 달라도 진짜 원본 줄을 놓치지 않는다.
10-26 실측: 이미숙 기미앰플 벤치 ↔ 원본 uOj3ix7qCj8 — 옛 판(창 +4 고정)은 1줄만 맞아 '원본 확정 못 함'으로 멈췄다."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tools.calcopy.hybrid import rules as RU  # noqa: E402


def _words(text, t0):
    return [[t0 + i * 0.3, w] for i, w in enumerate(text.split())]


ORIGIN = (_words("오늘 뭐 하는지 알아? 날씨가 좋아서 라운딩 왔어요", 10.0)
          + _words("빛 좀 갚으면 귀까지 바를게. 이게 진짜 좋아", 119.0)
          + _words("기능성 화장품 잘못 쓰면은 막 딱딱 따끔 하고", 121.9)
          + _words("덕분에 아주 요즘에 이것 때문에 자신감 있게 친다", 169.0))


def test_one_word_asr_slip_still_matches():
    # 벤치 받아쓰기: '바를게'→'말릴게', '자신감 있게 친다'→'자신감이 깨친다' (실제 위스퍼 오독)
    bench = [{"text": "빛 좀 갚으면 귀까지 말릴게. 덕분에 아주 요즘에 이것 때문에 자신감이 깨친다."}]
    got = RU.fingerprint(bench, ORIGIN)
    ts = sorted(round(m["origin_t"]) for m in got)
    assert len(got) >= 3, got
    assert all(115 <= t <= 175 for t in ts), ts


def test_unrelated_origin_does_not_match():
    bench = [{"text": "빛 좀 갚으면 귀까지 말릴게. 덕분에 아주 요즘에 이것 때문에 자신감이 깨친다."}]
    other = _words("오늘은 김치찌개를 끓여 볼게요 돼지고기 듬뿍 넣고 두부도 넣어요 맛있겠죠", 5.0)
    assert RU.fingerprint(bench, other) == []
