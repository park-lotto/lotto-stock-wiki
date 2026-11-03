# -*- coding: utf-8 -*-
"""kal_analyze.match_table fx.pos — 우리 꾸밈 0 편(10-26 잇썸홈 두유노판).
꾸밈 붙은 줄이 0개면 자리 분포(fx.pos)가 정의되지 않는다. 벤치도 거의 꾸밈 없는 채널(꾸밈 없는 줄 중앙 ≥0.9)이면 '해당 없음 → in',
벤치가 꾸밈 많은 채널이면 계속 미달(꾸밈 비율 차는 plain.rate 도 잡지만 fx.pos 도 미달로 남아야 한다 — 코디 10-26 조건 ①)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import kal_analyze as K  # noqa: E402


def _run(monkeypatch, bench_plain, bench_pos, ours_plain=1.0):
    def fake_stats(lines, dur):
        if lines == "B":
            return {"n": 10, "dur": 20.0, "plain.rate": bench_plain, "fx.pos": bench_pos}
        return {"n": 6, "dur": 18.0, "plain.rate": ours_plain, "fx.pos": None}
    base = {k: None for k in ("fx.rate.나레", "fx.rate.원음", "enter.mode.나레", "enter.mode.원음", "speech.cps.나레", "speech.cps.원음",
                              "chunk.chars", "chunk.sec", "narr.share", "transition.rate", "sfx.rate", "sticker.rate", "meme.rate")}
    monkeypatch.setattr(K, "_stats", lambda l, d: {**base, **fake_stats(l, d)})
    monkeypatch.setattr(K, "_ours_lines", lambda o: ("O", 18.0))
    T = K.match_table([{"lines": "B", "dur": 20}] * 3, {"lines": []}, {}, {})
    return next(r for r in T["rows"] if r["key"] == "fx.pos")


def test_fxpos_ours_zero_plain_bench_is_in(monkeypatch):
    r = _run(monkeypatch, bench_plain=0.947, bench_pos={"훅": 1.0, "본문": 0.0, "끝": 0.0})   # 두유노 실측
    assert r["judge"] == "in", r


def test_fxpos_both_zero_is_in(monkeypatch):
    r = _run(monkeypatch, bench_plain=1.0, bench_pos=None)
    assert r["judge"] == "in", r


def test_fxpos_ours_zero_but_bench_decorated_still_fails(monkeypatch):
    r = _run(monkeypatch, bench_plain=0.4, bench_pos={"훅": 0.5, "본문": 0.3, "끝": 0.2})
    assert r["judge"] != "in", r
