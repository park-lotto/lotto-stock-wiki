"""효과음 타점·수동편집(2026-08-21 사장님 "훅에서 다음 넘어갈 때 / 빼거나 다른거 넣거나")."""
from shopping_shorts import scene_match as sm


def _plan():
    return {"beats": [
        {"beat_idx": 0, "role": "hook", "narration": "훅 문장입니다"},
        {"beat_idx": 1, "role": "problem", "narration": "문제 문장입니다"},
    ]}


def _assets():
    return [{"id": 7, "asset_type": "sfx", "role": "훅", "title": "띠용"},
            {"id": 8, "asset_type": "sfx", "role": "본문", "title": "뿅"}]


def test_훅은_전환_타점이_기본이다():
    """이븐쇼핑류가 장면이 바뀌는 순간에 얹는 자리."""
    assert sm._sfx_position("hook") == "transition"


def test_나머지_역할은_마지막_자막이다():
    assert sm._sfx_position("problem") == "last"


def test_통제어휘_밖은_없다():
    assert "middle" not in sm.SFX_POSITIONS
    assert set(sm.SFX_POSITIONS) == {"first", "last", "transition"}


def test_사람이_고른_효과음은_재매칭이_안_덮는다():
    """대본이 바뀔 때마다 재매칭이 도는데 덮으면 '바꿨는데 그대로'가 된다."""
    plan = _plan()
    plan["beats"][0]["sfx"] = {"asset_id": 99, "match_type": "manual", "position": "first"}
    out = sm.match_sfx(plan, _assets())
    assert out["beats"][0]["sfx"]["asset_id"] == 99
    assert out["beats"][0]["sfx"]["position"] == "first"


def test_자동배치는_그대로_덮는다():
    plan = _plan()
    plan["beats"][0]["sfx"] = {"asset_id": 1, "match_type": "role", "position": "last"}
    out = sm.match_sfx(plan, _assets())
    assert out["beats"][0]["sfx"]["asset_id"] != 1 or out["beats"][0]["sfx"]["position"] == "transition"


def test_렌더가_전환_타점을_칸_끝으로_계산한다(monkeypatch):
    """position 이름을 렌더가 실제 초로 옮기는 지점 — 여기와 scene_match 중 한쪽만
    늘리면 조용히 기본값(last)으로 떨어진다."""
    import re
    import pathlib
    src = (pathlib.Path(__file__).resolve().parents[1] / "video_assemble.py").read_text(encoding="utf-8")
    # 세 갈래가 모두 있고, transition이 '칸 길이'를 쓰는지 소스로 확인한다
    # (전체 렌더는 ffmpeg가 필요해 단위테스트에서 못 돌린다).
    m = re.search(r'pos = sfx\.get\("position"\)(.*?)sfx_events\.append', src, re.S)
    assert m, "타점 분기를 찾지 못했다"
    body = m.group(1)
    assert 'pos == "first"' in body and "offset = 0.0" in body
    assert 'pos == "transition"' in body and 'offset = b["dur"]' in body
    assert "sum(seg_durs[:-1])" in body, "기본(last) 계산이 사라졌다"
