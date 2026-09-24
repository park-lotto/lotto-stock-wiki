# -*- coding: utf-8 -*-
"""뜨거운사람들 채널(channel_presets/hotpeople) — 규칙 판정·자막 시간·렌더 좌표·끝까지 mp4."""
import os
import subprocess

import numpy as np
import pytest
from PIL import Image

from shopping_shorts.channelkit import registry, lint


@pytest.fixture(autouse=True)
def _hp():
    registry.use("hotpeople")
    yield
    registry.use(registry.DEFAULT)


SRC = "안세영은 2023년 세계 선수권 대회에서 금메달을 획득했다. 2024년 하계 올림픽 금메달. 무릎 부상."


def _script(n=24):
    gs = [{"lines": ["\"몸이 망가져도", "멈추지 않았음\""], "text": "\"몸이 망가져도 멈추지 않았음\"", "mark": True, "red": []},
          {"lines": ["배드민턴 선수", "그의 이름 \"안세영\""], "text": "배드민턴 선수 그의 이름 \"안세영\"", "mark": False, "red": ["안세영"]}]
    gs += [{"lines": ["2023년 세계 선수권", "금메달을 따냄"], "text": "2023년 세계 선수권 금메달을 따냄", "mark": False, "red": []}
           for _ in range(n - 2)]
    return {"person": "안세영", "title": {"h1": "무릎이 부서져도", "h2": "금메달 딴 선수", "emph": 2, "emph_color": "red"},
            "groups": gs, "queries": ["An Se-young final", "An Se-young interview", "안세영 금메달"]}


def _rules(script, src=SRC):
    issues, _ = lint.lint(script, source_text=src, do_layout=False)
    return {i.rule for i in lint.rejects(issues)}


def test_clean_script_passes():
    assert _rules(_script()) == set()
    assert [r.id for r in lint.rules()][0] == "formal" and "hp_numbers" in [r.id for r in lint.rules()]


@pytest.mark.parametrize("mutate,rule", [
    (lambda s: s["groups"].__setitem__(0, dict(s["groups"][0], mark=False)), "hp_first_mark"),
    (lambda s: s.__setitem__("groups", s["groups"][:10]), "hp_count"),
    (lambda s: s["groups"][3].__setitem__("lines", ["2019년 세계 선수권", "금메달을 따냄"]) or s["groups"][3].__setitem__("text", "2019년 세계 선수권 금메달을 따냄"), "hp_numbers"),
    (lambda s: s["groups"][4].__setitem__("lines", ["이 줄은 정말 너무너무 길어서 화면을 넘어감", "x"]) or s["groups"][4].__setitem__("text", "이 줄은 정말 너무너무 길어서 화면을 넘어감 x"), "hp_lines"),
    (lambda s: [g.__setitem__("mark", True) for g in s["groups"][:5]], "hp_mark_max"),
    (lambda s: s["groups"][1].__setitem__("red", ["없는말"]), "hp_red"),
    (lambda s: [g.__setitem__("text", g["text"].replace("안세영", "그녀")) or g.__setitem__("lines", [x.replace("안세영", "그녀") for x in g["lines"]]) for g in s["groups"]], "hp_name"),
    (lambda s: s.__setitem__("queries", ["x"]), "hp_queries"),
    (lambda s: s["title"].__setitem__("emph", 3), "hp_headline"),
])
def test_each_rule_catches(mutate, rule):
    s = _script()
    mutate(s)
    assert rule in _rules(s)


def test_sub_seconds_matches_regression():
    from shopping_shorts.channel_presets.hotpeople import rules
    assert rules.sub_seconds("하지만 그는 달랐음.") == round(1.69 + 0.037 * 9, 2)
    assert rules.sub_seconds("짧") == 1.73 and rules.sub_seconds("가" * 80) == 3.1


def _ink_rows(png):
    a = np.array(Image.open(png).convert("RGBA"))
    ink = (a[:, :, 3] > 128) & (a[:, :, :3].max(axis=2) < 90)
    return np.where(ink.any(axis=1))[0], a


def test_subtitle_drawn_at_measured_rows(tmp_path):
    from shopping_shorts.channel_presets.hotpeople import render, spec
    g = _script()["groups"][1]
    rows, a = _ink_rows(render.subtitle(g, str(tmp_path / "s.png")))
    # ★기대값은 spec이 아니라 **원본 실측 숫자**로 적는다 — spec끼리 비교하면 spec이 틀려도 통과한다(2026-09-25 사보타주로 확인)
    assert abs(rows.min() - 1285) <= 6                               # 원본: 첫 줄 잉크 시작 1285(232개 중앙)
    second = rows[rows > rows.min() + 60]
    assert abs(second.min() - (1285 + 80)) <= 8                      # 원본: 줄 간격 80(176개 중앙)
    red = (a[:, :, 0] > 200) & (a[:, :, 1] < 60) & (a[:, :, 3] > 128)
    assert red.sum() > 200                                           # "안세영" 빨강
    m = render.subtitle(_script()["groups"][0], str(tmp_path / "m.png"))
    ma = np.array(Image.open(m).convert("RGB"))
    assert ((abs(ma.astype(int) - spec.MARK_RGB).max(axis=2)) < 6).sum() > 5000   # 형광펜


def test_background_logo_and_headline(tmp_path):
    from shopping_shorts.channel_presets.hotpeople import render, spec
    a = np.array(Image.open(render.background(_script()["title"], str(tmp_path / "bg.png"))).convert("RGB")).astype(int)
    band = a[spec.HEADLINE_Y0:spec.HEADLINE_Y1]
    assert ((band[:, :, 0] > 200) & (band[:, :, 1] < 60)).sum() > 2000     # 빨강 강조 줄
    assert (band.max(axis=2) < 60).sum() > 2000                             # 검정 줄
    assert (abs(a[1700, 540] - (250, 250, 250)).max()) < 4           # 원본 흰 여백
    assert (abs(a[spec.SLOT_Y + 10, 540] - (250, 250, 250)).max()) < 4 and spec.SLOT_Y == 483 and spec.SLOT_H == 790


def test_end_to_end_render_with_fake_footage(tmp_path):
    """네트워크 없이: 가짜 가로 영상 → 컷 3개 렌더 → 슬롯이 채워지고 자막 잉크가 있는지 프레임으로 잰다."""
    from shopping_shorts.channel_presets.hotpeople import render, review
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "12", src], check=True)
    s = _script(3)
    fo = {"cuts": [{"src": src, "start": 1.0 + i * 3, "url": "test"} for i in range(3)]}
    r = render.build(str(tmp_path), s, fo, log=lambda *_: None)
    assert os.path.isfile(r["mp4"])
    rep = review.run(r["mp4"], r, str(tmp_path))
    by = {c["name"]: c for c in rep["checks"]}
    assert by["크기 1080x1920"]["ok"] and by["소리 트랙"]["ok"]
    assert by["슬롯이 빈 컷 0"]["ok"] and by["자막 없는 컷 0"]["ok"] and by["자막 화면 밖 0"]["ok"]
    assert not by["길이 45~75초"]["ok"]                                  # 3컷이라 짧다 — 검사가 실제로 잡는다


def test_glyph_rule_catches_middle_dot():
    """2026-09-25 실측: 주아체에 가운뎃점이 없어 '단식·단체전'이 □로 렌더됐다."""
    s = _script()
    s["groups"][5]["lines"] = ["단식·단체전", "금메달을 따냄"]; s["groups"][5]["text"] = "단식·단체전 금메달을 따냄"
    assert "hp_glyphs" in _rules(s)
    assert "hp_glyphs" not in _rules(_script())


def test_pick_retries_then_fails_loud(monkeypatch):
    from shopping_shorts.channel_presets.hotpeople import footage
    monkeypatch.setattr("time.sleep", lambda *_: None)
    calls = []

    def flaky(prompt, sheets):
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("503 UNAVAILABLE")
        return '{"picks": [2, 0, 1]}'
    idx, fixed = footage.pick([{}, {}, {}], [0, 1, 2], [], flaky, "x", log=lambda *_: None)
    assert idx == [2, 0, 1] and fixed == 0 and len(calls) == 3

    def dead(prompt, sheets):
        raise RuntimeError("503")
    idx, fixed = footage.pick([{}, {}, {}], [0, 1, 2], [], [dead, dead], "x", log=lambda *_: None)
    assert fixed == 3                                   # 전부 메움 → collect가 이걸 보고 멈춘다
