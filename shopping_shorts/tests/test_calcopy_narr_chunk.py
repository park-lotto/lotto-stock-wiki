# -*- coding: utf-8 -*-
"""narr_video.chunk_sentence 조각 상한 (관제 097, 10-16 썰풀다 담당 요청).
'꼬리 5자 이하는 앞 조각에 붙이기' 때문에 --chunk 10 인데 16자 조각이 나왔다(rGFX 대본 실문장) → 붙인 결과도 n + CHUNK_SLACK 이하."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.narr_video import CHUNK_SLACK, chunk_sentence  # noqa: E402

RED = "막상 사 먹은 사람들 사이에선 피스타치오 맛은 거의 안 나고 그냥 흔한 초코 맛이라는 말이 돌았다고 함."   # 고치기 전 n=10 → '흔한 초코 맛이라는 말이 돌았다고 함.' 16자


def _n(t):
    return len(t.replace(" ", ""))


def test_tail_merge_respects_cap():
    out = chunk_sentence(RED, 10)
    assert max(map(_n, out)) <= 10 + CHUNK_SLACK, out
    assert " ".join(out).split() == RED.split()           # 낱말 잃거나 순서 바뀌지 않음
    assert all(_n(o.rstrip(".")) > 5 for o in out[-1:]), out   # 꼬리는 여전히 혼자 짧게 남지 않는다(앞 낱말을 넘겨받음)


def test_short_tail_still_merges_when_it_fits():
    assert chunk_sentence("이게 진짜 대박이라 있음.", 10) == ["이게 진짜 대박이라 있음."]
    assert chunk_sentence("그 소식 듣고 나서 처음엔 사양하던 그 팬은 결국 받았음.", 14)[-1] == "그 팬은 결국 받았음."   # 꾸밈 낱말 '그' 넘기기 그대로


def test_all_real_scripts_within_cap():
    """채널 통과 대본 전 줄 × n=10·13·14 — 낱말 하나가 상한보다 긴 경우 말고는 상한 이하."""
    bad = []
    for f in ROOT.glob("channel/*/*/대본.json"):
        try:
            lines = [l["text"] for l in json.loads(f.read_text(encoding="utf-8"))["final"]["lines"]]
        except (KeyError, ValueError, TypeError):
            continue
        for s in lines:
            for n in (10, 13, 14):
                for o in chunk_sentence(s, n):
                    if _n(o) > n + CHUNK_SLACK and len(o.split()) > 1:
                        bad.append((f.parent.name, n, o))
    assert not bad, bad[:5]
