# -*- coding: utf-8 -*-
"""뜨거운사람들 채널(channel_presets/hotpeople) — 규칙 판정·자막 시간·렌더 좌표·끝까지 mp4."""
import json
import os
import subprocess

import numpy as np
import pytest
from PIL import Image

from shopping_shorts.channelkit import registry, lint, pipeline  # noqa: F401 — pipeline 은 채널 전환 전에 import(엔진 기본 spec 을 import 때 읽는다, make.py 와 같은 순서)


@pytest.fixture(autouse=True)
def _hp():
    registry.use("hotpeople")
    yield
    registry.use(registry.DEFAULT)


SRC = "안세영은 2023년 세계 선수권 대회에서 금메달을 획득했다. 2024년 하계 올림픽 금메달. 무릎 부상."


def _g(text, mark=False, red=()):
    from shopping_shorts.channel_presets.hotpeople import rules
    return {"lines": rules.layout_lines(text, red), "text": text, "mark": mark, "red": list(red)}


def _script(n=24):
    """원본 비율을 지키는 깨끗한 대본: 사실 훅 · 숫자 자막 ≤25% · 인용 ≥10% · 줄바꿈은 layout_lines."""
    gs = [_g("무릎이 부서져도 멈추지 않은 선수가 있음", mark=True),
          _g("배드민턴 선수 그의 이름 \"안세영\"", red=("안세영",))]
    body = ([_g("\"넌 아직 너무 어려\"")] * 2 + [_g("2023년 세계 선수권 금메달을 따냄")] * 5
            + [_g("그렇게 매일 코트로 나감")] * n)
    gs += body[:max(0, n - 2)]
    return {"person": "안세영", "title": {"h1": "무릎이 부서져도", "h2": "금메달 딴 선수", "emph": 2, "emph_color": "red"},
            "groups": [dict(g, lines=list(g["lines"])) for g in gs],
            "queries": ["An Se-young final", "An Se-young interview", "안세영 금메달"]}


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
        if sheets:
            return '{"desc": {"0": "a", "1": "b", "2": "c"}}'
        return '{"picks": [2, 0, 1]}'
    idx, fixed = footage.pick([{}, {}, {}], [0, 1, 2], ["s.png"], flaky, "x", log=lambda *_: None)
    assert idx == [2, 0, 1] and fixed == 0 and len(calls) == 4      # 503 두 번 → 설명 → 짝짓기

    def dead(prompt, sheets):
        raise RuntimeError("503")
    idx, fixed = footage.pick([{}, {}, {}], [0, 1, 2], ["s.png"], [dead, dead], "x", log=lambda *_: None)
    assert fixed == 3                                   # 전부 메움 → collect가 이걸 보고 멈춘다


def test_check_and_repick_replaces_only_bad(tmp_path):
    from shopping_shorts.channel_presets.hotpeople import footage
    th = tmp_path / "t.jpg"
    Image.new("RGB", (240, 176), (90, 120, 90)).save(th)
    (tmp_path / "footage").mkdir()
    cands = [{"thumb": str(th)} for _ in range(6)]
    groups = [{"text": f"자막{i}"} for i in range(3)]
    # 세 번째 답 = 다시 고른 뒤 최종 검사(2026-09-28 우상혁 v001: 다시 고르고 검사 안 해 토크쇼가 나갔다)
    answers = iter(['{"bad": [1]}', '{"picks": {"1": 4}}', '{"bad": []}'])
    new, v = footage.check_and_repick(groups, cands, [0, 1, 2], [], lambda p, imgs: next(answers), "x",
                                      str(tmp_path), log=lambda *_: None)
    assert new == [0, 4, 2] and v == {"bad": [1], "repicked": 1, "bad_final": []}
    ok = iter(['{"bad": []}'])
    new, v = footage.check_and_repick(groups, cands, [0, 1, 2], [], lambda p, imgs: next(ok), "x", str(tmp_path), log=lambda *_: None)
    assert new == [0, 1, 2] and v["bad"] == []


def test_call_falls_through_on_wrong_shape(monkeypatch):
    """2026-09-25: 에러 없이 온 엉뚱한 답을 받아들여 대체 모델로 안 넘어갔다."""
    from shopping_shorts.channel_presets.hotpeople import footage
    monkeypatch.setattr("time.sleep", lambda *_: None)
    bad = lambda p, i: '{"answer": "몰라"}'
    good = lambda p, i: '{"picks": [1]}'
    assert footage._call([bad, good], "q", [], lambda *_: None, "picks") == {"picks": [1]}
    assert footage._call([bad], "q", [], lambda *_: None, "picks") is None


def test_pick_uses_describe_then_text_match_and_coerces_strings(tmp_path):
    from shopping_shorts.channel_presets.hotpeople import footage
    seen = []

    def reader(prompt, imgs):
        seen.append(len(imgs))
        if "desc" in prompt and imgs:
            return '{"desc": {"0": "market stalls [TEXT]", "1": "woman badminton player on podium with gold medal", "2": "girl child with racket"}}'
        return '{"picks": ["1", "2"]}'                  # 문자열 번호도 받는다
    idx, fixed = footage.pick([{"text": "금메달"}, {"text": "어린 시절"}], [{}, {}, {}], ["s0.png"], reader, "x", log=lambda *_: None)
    assert idx == [1, 2] and fixed == 0
    assert seen == [1, 0]                                # 그림 1장씩 설명 → 글만으로 짝짓기


def test_bgm_start_offset_and_loudness(tmp_path, monkeypatch):
    """원본 실측: 곡을 정해진 지점부터 속도 그대로, -12 LUFS 안팎."""
    from shopping_shorts.channel_presets.hotpeople import render, spec
    d = tmp_path / "bgm"; d.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=30", str(d / "hero.m4a")], check=True)
    monkeypatch.setattr(spec, "POLICY_BGM_DIR", str(d))
    assert render.pick_bgm("안세영") == (str(d / "hero.m4a"), 7.1)       # 있는 곡만 고른다
    (tmp_path / "render").mkdir()
    out, name = render._bgm(10.0, str(tmp_path), "안세영")
    assert name == "hero.m4a@7.1s"
    r = subprocess.run(["ffmpeg", "-i", out, "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True)
    lufs = float([l for l in r.stderr.splitlines() if "Input Integrated" in l][0].split()[2])
    assert -14.5 < lufs < -9.5                                            # 원본 중앙 -12.1


# ── 칼카피 6규칙 (2026-09-28) — 각 테스트는 옛 동작(v002)에서 실패해야 한다 ─────────────────

def _levels(script):
    issues, _ = lint.lint(script, source_text=SRC, do_layout=False)
    return {(i.rule, i.level) for i in issues}


def test_layout_one_line_until_740_and_engine_owns_breaks():
    """칼카피 5: 폭 740px 안이면 한 줄(원본 1줄 24%). v002는 7자마다 끊었다."""
    from shopping_shorts.channel_presets.hotpeople import rules, spec
    from shopping_shorts.channel_presets.hotpeople import script as S
    assert rules.layout_lines("광주에서 자란 소녀") == ["광주에서 자란 소녀"]
    long_ = rules.layout_lines("1996년 이후 끊긴 28년 만의 올림픽 금메달")
    assert len(long_) == 2 and all(rules.ink_width(x) <= spec.SUB_MAX_INK_W for x in long_)
    lr = rules.layout_lines("그의 이름 대한민국 배드민턴 영웅 안세영", red=("배드민턴 영웅",))
    assert any("배드민턴 영웅" in x for x in lr)                       # 빨강 단어는 안 쪼갠다
    s = _script()
    s["groups"][5] = {"lines": ["광주에서", "자란 소녀"], "text": "광주에서 자란 소녀", "mark": False, "red": []}
    assert "hp_lines" in _rules(s)                                   # v002식 조기 줄바꿈 → 반려
    fixed = rules.normalize(s)
    assert fixed["groups"][5]["lines"] == ["광주에서 자란 소녀"] and "hp_lines" not in _rules(fixed)
    assert S.rules is rules                                           # 대본 생성은 같은 함수로 정규화


def test_digit_ratio():
    """칼카피 2: 숫자 자막 원본 18%, v002 73%(19/26) → 반려. 25%까지 통과, 25~30% 경고."""
    s = _script(26)
    assert not {r for r, _ in _levels(s)} & {"hp_digits"}
    for g in s["groups"][10:24]:
        g.update(_g("2023년 세계 선수권 금메달을 따냄"))
    assert ("hp_digits", "reject") in _levels(s)                      # 19/26
    s = _script(26)
    s["groups"][10].update(_g("2023년 세계 선수권 금메달을 따냄"))
    s["groups"][11].update(_g("2023년 세계 선수권 금메달을 따냄"))    # 7/26 = 27%
    lv = _levels(s)
    assert ("hp_digits", "warn") in lv and ("hp_digits", "reject") not in lv


def test_quote_ratio():
    """칼카피 3: 인용 원본 16%, v002 1/26 → 반려. 26개면 3개 이상."""
    s = _script(26)
    assert "hp_quotes" not in _rules(s)
    s["groups"][2].update(_g("주변은 그녀가 너무 어리다고 봄"))
    s["groups"][3].update(_g("주변은 그녀가 너무 어리다고 봄"))
    assert "hp_quotes" in _rules(s)                                   # 이름 인용 포함 2개만 남음


def test_hook_fact_statement():
    """훅: 56편 전수 사실 서술 훅이 11배. v002 첫 자막 «첫 아시안게임 1경기 탈락» → 반려. 인용은 경고(대체안)."""
    s = _script()
    s["groups"][0].update(_g("첫 아시안게임 1경기 탈락", mark=True))
    assert "hp_hook" in _rules(s)
    s["groups"][0].update(_g("\"몸이 망가져도 멈추지 않았음\"", mark=True))
    assert ("hp_hook", "warn") in _levels(s) and "hp_hook" not in _rules(s)
    s["groups"][0].update(_g("한국 배드민턴 역사상 가장 충격적인 사건이 터짐.", mark=True))
    assert not {r for r, _ in _levels(s)} & {"hp_hook"}


def _stroke_px(png):
    a = np.array(Image.open(png).convert("RGBA"))
    ink = (a[:, :, 3] > 128) & (a[:, :, :3].max(axis=2) < 90)
    runs = []
    for m in (ink, ink.T):
        for row in m:
            n = 0
            for v in row:
                if v:
                    n += 1
                elif n:
                    runs.append(n)
                    n = 0
    return float(np.median([r for r in runs if r < 30]))


def test_subtitle_stroke_matches_original(tmp_path):
    """칼카피 4: 원본 획 8px(8~9, glyph_style.py). v002(외곽선 1px)는 11px."""
    from shopping_shorts.channel_presets.hotpeople import render
    w = _stroke_px(render.subtitle(_g("그렇게 매일 코트로 나감"), str(tmp_path / "s.png")))
    assert 7 <= w <= 9.5, w


def test_footage_pick_respects_scene_length():
    """칼카피 1: 자막보다 짧은 장면은 못 고른다 — v002는 1.2초 장면에 2.2초 자막을 붙여 다음 장면이 자막 안으로 들어왔다."""
    from shopping_shorts.channel_presets.hotpeople import footage
    g = [{"text": "그렇게 매일 코트로 나감"}]                         # 2.1초
    short, long_ = {"start": 10.0, "end": 11.2}, {"start": 20.0, "end": 25.0}
    idx, fixed = footage.pick(g, [short, long_], [], lambda p, i: '{"picks": [0]}', "x", log=lambda *_: None)
    assert idx == [1] and fixed == 1
    with pytest.raises(RuntimeError):
        footage.pick(g, [short], [], None, "x", log=lambda *_: None)


def test_scenes_cut_on_slot_crop_with_inset(tmp_path):
    """장면 경계는 슬롯 크롭(render.slot_vf) 기준 + 앞뒤 CLIP_INSET_SEC 여유."""
    from shopping_shorts.channel_presets.hotpeople import footage, spec
    src = str(tmp_path / "two.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:d=5",
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:d=5,negate,hue=h=120",
                    "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:d=5",
                    "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1[o]", "-map", "[o]", src], check=True)
    sc = footage.scenes(src, "v", str(tmp_path / "th"))
    mid = [c for c in sc if 4 < c["start"] < 9]                      # 가운데 장면 5~10초 → 쓸 구간 5.1~9.9
    assert len(mid) == 1, sc
    assert abs(mid[0]["start"] - (5.0 + spec.CLIP_INSET_SEC)) <= 0.05 and abs(mid[0]["end"] - (10.0 - spec.CLIP_INSET_SEC)) <= 0.05, sc


def test_render_refuses_clip_past_scene_end(tmp_path):
    from shopping_shorts.channel_presets.hotpeople import render
    s = _script(3)
    fo = {"cuts": [{"src": "x.mp4", "start": 1.0, "end": 2.0, "url": "t"}] * 3}
    with pytest.raises(RuntimeError, match="장면"):
        render.build(str(tmp_path), s, fo, log=lambda *_: None)


def test_review_catches_cut_inside_subtitle(tmp_path):
    """결과물 검사: 자막 경계 밖 컷을 잡는다. (v002 final.mp4 실측: 13개 잡음)"""
    from shopping_shorts.channel_presets.hotpeople import review
    mp4 = str(tmp_path / "v.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1",
                    "-f", "lavfi", "-i", "testsrc2=s=1080x1920:r=30:d=1,negate",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1[o]", "-map", "[o]", mp4], check=True)
    assert review.inner_cuts(mp4, [2.0]) == [1.0]
    assert review.inner_cuts(mp4, [1.0, 1.0]) == []


def test_bgm_constant_gain_keeps_song_shape(tmp_path, monkeypatch):
    """칼카피 6: 원본은 곡 이득이 평평(페이드·자동조절 없음). 곡의 첫 3초가 6dB 조용하면 결과도 6dB 조용해야 한다.
    옛 동적 loudnorm은 앞을 끌어올려 v002 오프닝이 +2.2 LU 컸다."""
    import re
    import statistics as st
    from shopping_shorts.channel_presets.hotpeople import render, spec
    d = tmp_path / "bgm"
    d.mkdir()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anoisesrc=d=40:c=pink:a=0.3",
                    "-af", "volume='if(lt(t,10),0.5,1)':eval=frame", str(d / "hero.m4a")], check=True)
    monkeypatch.setattr(spec, "POLICY_BGM_DIR", str(d))
    (tmp_path / "render").mkdir()
    out, _ = render._bgm(25.0, str(tmp_path), "x")             # 곡 7.1초부터 → 첫 2.9초가 −6dB
    r = subprocess.run(["ffmpeg", "-nostats", "-i", out, "-af", "ebur128=framelog=info", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    M = [(float(t), float(m)) for t, m in re.findall(r"t:\s*([\d.]+)\s+.*?M:\s*(-?[\d.]+)", r)]
    open_ = st.median(m for t, m in M if 0.5 <= t <= 2.5)
    rest = st.median(m for t, m in M if 4 <= t <= 23)
    assert -7.0 < open_ - rest < -5.0, (open_, rest)
    integ = float(re.findall(r"^\s*I:\s*(-?[\d.]+) LUFS", r, re.M)[-1])
    assert abs(integ - spec.BGM_LUFS) < 1.0


def test_cut_clip_first_frame_has_video(tmp_path):
    """칼카피 1: 컷 첫 프레임에 영상이 있어야 한다. v3 1차 렌더 실측 — -ss 뒤 영상 pts가 0이 아니라
    첫 프레임이 빈 흰 슬롯(평균 248)이었고, 자막 경계마다 컷이 두 번(경계+1프레임) 잡혀 컷 수가 37로 불었다."""
    from shopping_shorts.channel_presets.hotpeople import render, spec
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=25", "-t", "12",
                    "-g", "250", src], check=True)
    bg = render.background(_script()["title"], str(tmp_path / "bg.png"))
    sub = render.subtitle(_script()["groups"][2], str(tmp_path / "s.png"))
    out = str(tmp_path / "c.mp4")
    render.cut_clip(bg, sub, src, 5.37, 2.0, out)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", out, "-frames:v", "2", "-vf",
                          f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    a = np.frombuffer(raw, np.uint8).reshape(-1, spec.SLOT_H, spec.SLOT_W).astype(int)
    assert abs(a[0].mean() - a[1].mean()) < 5, (a[0].mean(), a[1].mean())     # 첫 프레임 = 둘째 프레임(빈 슬롯 아님)


# ── 내용 관문·소스 자·인물 중심 크롭 (2026-09-28 우상혁 v001 사고: verify 23/23 틀림에도 렌더) ─────────────────
def _rows(n=20, **over):
    """관문을 통과하는 완성본 측정값(얼굴 70%·자막꼴 0·다른 사람 0)."""
    rows = [{"i": i, "face": i % 10 < 7, "face_h": 0.3 if i % 10 < 7 else None, "cx_off": 0.02 if i % 10 < 7 else None,
             "who": "주인공" if i % 10 < 7 else "얼굴없음", "sub_like": 0} for i in range(n)]
    for i, kv in over.items():
        rows[int(i[1:])].update(kv)
    return rows


def _blocked(checks):
    return [c["name"][:1] for c in checks if not c["ok"] and c.get("block", True)]


def test_content_gate_passes_clean_and_blocks_each_limit():
    from shopping_shorts.channel_presets.hotpeople import review
    subj = ["main"] * 20
    assert _blocked(review.content_gate(_rows(), subj, [])) == []
    # ⑦ 얼굴 보이는 컷 < 55%
    few = [dict(r, face=r["i"] < 10, who="얼굴없음" if r["i"] >= 10 else r["who"]) for r in _rows()]
    assert _blocked(review.content_gate(few, subj, [])) == ["⑦"]
    # ⑧ 자막꼴 박힌 글자 2컷
    assert _blocked(review.content_gate(_rows(c1={"sub_like": 1}, c8={"sub_like": 2}), subj, [])) == ["⑧"]
    assert _blocked(review.content_gate(_rows(c1={"sub_like": 1}), subj, [])) == []          # 1컷은 허용(원본 3/9편)
    # ⑩ 주인공 자막에 다른 사람 — 다른 인물 자막(other)이면 괜찮다(원본도 조연·상대를 넣는다)
    assert _blocked(review.content_gate(_rows(c3={"who": "다른사람"}), subj, [])) == ["⑩"]
    assert _blocked(review.content_gate(_rows(c3={"who": "다른사람"}), ["main"] * 3 + ["other"] + ["main"] * 16, [])) == []
    # 장면 검사: 최종 틀림 30% 넘음 / 검사 안 함(None) 둘 다 막는다
    assert _blocked(review.content_gate(_rows(), subj, list(range(7)))) == ["장"]
    assert _blocked(review.content_gate(_rows(), subj, None)) == ["장"]


def test_v001_like_review_is_blocked_and_final_not_written(tmp_path):
    """★사보타주 대상: v001 모양(토크쇼 2컷=다른 사람, 장면 검사 23/23 틀림) → out/final.mp4 없음 + FAILED.json 사유."""
    from shopping_shorts.channel_presets.hotpeople import review
    wd = str(tmp_path)
    os.makedirs(os.path.join(wd, "out")); os.makedirs(os.path.join(wd, "render"))
    stale = os.path.join(wd, "out", "final.mp4")
    open(stale, "wb").write(b"old")                                  # 지난 완성본이 남아 있어도 지운다
    un = os.path.join(wd, "render", "unchecked.mp4")
    open(un, "wb").write(b"new")
    checks = [{"name": "크기 1080x1920", "ok": True}] + review.content_gate(
        _rows(24, c1={"who": "다른사람"}, c2={"who": "다른사람"}), ["main"] * 24, list(range(1, 24)))
    rep = {"ok": all(c["ok"] for c in checks if c.get("block", True)), "checks": checks, "sheet": None}
    assert rep["ok"] is False
    assert review.finalize(rep, wd, un) is None
    assert not os.path.exists(stale) and os.path.exists(un)
    fail = json.load(open(os.path.join(wd, "out", "FAILED.json"), encoding="utf-8"))
    assert [w[:1] for w in fail["why"]] == ["⑩", "장"]
    # 통과하면 그때만 옮긴다
    ok = {"ok": True, "checks": [], "sheet": None}
    assert review.finalize(ok, wd, un) == stale and open(stale, "rb").read() == b"new"
    assert not os.path.exists(os.path.join(wd, "out", "FAILED.json"))


def test_review_step_without_anchor_fails_and_writes_no_final(tmp_path):
    """파이프라인 review 단계: 주인공 임베딩이 없으면(=내용 관문을 못 돌면) 막는다 — 조용히 통과 금지."""
    from shopping_shorts.channel_presets.hotpeople import render, steps
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "12", src], check=True)
    s = _script(3)
    fo = {"cuts": [{"src": src, "start": 1.0 + i * 3, "url": "test"} for i in range(3)], "anchor": None,
          "verify": {"bad": [], "repicked": 0, "bad_final": []}}
    d = {"script": {"script": s}, "footage": fo}
    d["render"] = render.build(str(tmp_path), s, fo, log=lambda *_: None)
    assert not os.path.exists(tmp_path / "out" / "final.mp4")            # 렌더는 out/ 에 안 쓴다
    r = steps.review({}, d, str(tmp_path), {"log": lambda *_: None})
    assert r["status"] == "failed" and "내용 관문 실행" in r["fail"]["why"]
    assert not os.path.exists(tmp_path / "out" / "final.mp4") and os.path.exists(tmp_path / "out" / "FAILED.json")


def test_title_block_catches_v001_sources():
    from shopping_shorts.channel_presets.hotpeople import footage
    assert footage.title_blocked("Day 3 Highlights | World Indoor Championships Belgrade 22")
    assert footage.title_blocked("Day 2 Highlights | World Indoor Championships Belgrade 22")
    assert footage.title_blocked("Men's High Jump Final | Tokyo Reflections with the BackStraight Boys (& Girl)")
    assert footage.title_blocked("우상혁 명장면 모음") and footage.title_blocked("스포츠 토크쇼 3회")
    assert footage.title_blocked("Woo Sang-hyeok clears 2.35m to finish 4th in men's high jump final") is None


def test_source_queries_add_korean():
    from shopping_shorts.channel_presets.hotpeople import footage
    q = footage.source_queries({"person": "우상혁", "queries": ["Woo Sang-hyeok high jump", "우상혁 인터뷰"]})
    assert q[:4] == ["우상혁 경기", "Woo Sang-hyeok high jump", "우상혁 인터뷰", "우상혁 하이라이트"]
    assert q.count("우상혁 인터뷰") == 1 and "우상혁 다큐" in q


def test_judge_sources_drops_low_ratio_and_caps():
    from shopping_shorts.channel_presets.hotpeople import footage, spec
    lo = spec.POLICY_SOURCE_MIN_MAIN_RATIO
    wide = spec.POLICY_SOURCE_WIDE_JUDGED_MAX
    per = {"a": {"main_ratio": lo + 0.3, "judged_ratio": 0.5},
           "b": {"main_ratio": lo / 2, "judged_ratio": 0.35},        # 큰 얼굴은 많은데 주인공이 아니다(Day2 종합·토크쇼)
           "c": {"main_ratio": 0.0, "judged_ratio": wide / 2},       # 넓은 경기 중계(파리 결승 0.00) — 증거 없음, 둔다
           "d": {"main_ratio": lo + 0.1, "judged_ratio": 0.4}}
    keep, why = footage.judge_sources(per, cap=2)
    assert keep == ["a", "c"] and "다른 사람 영상" in why["b"] and "상한" in why["d"]     # 상한은 받은 순서로


def test_gather_sources_fetches_more_then_fails_loud(tmp_path, monkeypatch):
    """소스 자(비율은 가짜): 낮은 소스는 버리고 다음 검색어로 더 받는다 · 제목 차단은 안 받는다 · 모자라면 에러."""
    from shopping_shorts.channel_presets.hotpeople import footage, spec
    monkeypatch.setattr(spec, "POLICY_FOOTAGE_MAX_VIDEOS", 3)
    monkeypatch.setattr(spec, "POLICY_SOURCE_MIN_USABLE", 2)
    lo = spec.POLICY_SOURCE_MIN_MAIN_RATIO
    ratio = {"g1": 0.0, "g2": lo * 0.5, "w1": lo + 0.4, "w2": lo + 0.3, "w3": lo + 0.2, "w4": lo + 0.5}
    results = {"우상혁 경기": [("g1", "Men's final"), ("g2", "Athletics day")], "Q1": [("t1", "Day 2 Highlights | Worlds")],
               "우상혁 인터뷰": [("w1", "우상혁 인터뷰"), ("w2", "우상혁 경기")], "우상혁 하이라이트": [("w3", "a"), ("w4", "b")],
               "우상혁 다큐": [("w5", "c")]}
    got = []
    monkeypatch.setattr(footage, "search", lambda q, n, log=print: [{"id": i, "title": t, "duration": 100,
                                                                     "url": f"u/{i}"} for i, t in results.get(q, [])])

    def dl(it, vdir, log=print):
        got.append(it["id"])
        p = os.path.join(vdir, it["id"] + ".mp4")
        open(p, "wb").write(b"x")
        return p
    monkeypatch.setattr(footage, "download", dl)
    monkeypatch.setattr(footage, "source_ruler", lambda vids, wd=None, log=print: {
        "anchor": np.ones(128, np.float32), "anchor_from": ["w1", 0], "support": 3,
        "per": {v["id"]: {"main_ratio": ratio[v["id"]], "frames": 10, "face_h": 0.3} for v in vids}})
    vids, ruler, table = footage.gather_sources({"person": "우상혁", "queries": ["Q1"]}, str(tmp_path), log=lambda *_: None)
    assert [v["id"] for v in vids] == ["w1", "w2", "w3"]          # 받은 순서, 상한 3
    assert "t1" not in got and got == ["g1", "g2", "w1", "w2", "w3", "w4"]     # 제목 차단은 안 받았다 · 상한 차면 멈춤
    st = {r["id"]: r["status"] for r in table}
    assert st["g1"].startswith("버림") and st["t1"].startswith("제목 차단") and st["w4"].startswith("버림(상한")
    # 주인공 소스가 모자라면 에러(조용히 적은 소스로 렌더하지 않는다)
    wd2 = str(tmp_path / "b")
    results2 = {"우상혁 경기": [("g1", "x"), ("g2", "y")], "우상혁 인터뷰": [("w1", "z")]}
    monkeypatch.setattr(footage, "search", lambda q, n, log=print: [{"id": i, "title": t, "duration": 100,
                                                                     "url": f"u/{i}"} for i, t in results2.get(q, [])])
    with pytest.raises(RuntimeError, match="주인공이 나오는 소스 1편"):
        footage.gather_sources({"person": "우상혁", "queries": []}, wd2, log=lambda *_: None)


def test_face_crop_x_math():
    from shopping_shorts.channel_presets.hotpeople import render
    assert render.face_crop_x(1714, 1080, None) == 317                 # 얼굴 없음 = 가운데(ffmpeg 기본과 같다)
    assert render.face_crop_x(1714, 1080, 0.5) == 317
    assert render.face_crop_x(1714, 1080, 0.4) == round(0.4 * 1714 - 540)
    assert render.face_crop_x(1714, 1080, 0.95) == 634 and render.face_crop_x(1714, 1080, 0.02) == 0   # 덮개 밖으로 안 나감
    assert render.face_crop_x(1080, 1080, 0.9) == 0                    # 여유 없으면 그대로


def _white_cx(bgr_or_gray):
    a = np.asarray(bgr_or_gray)
    if a.ndim == 3:
        a = a.max(axis=2)
    ys, xs = np.nonzero(a > 200)
    return xs.mean()


def test_face_crop_same_in_tag_frame_and_render(tmp_path):
    """★0순위-A1a: 태깅 그림(cover_frame→face_crop_x→slot_from_cover)과 렌더(cut_clip crop_x)가 같은 자리를 자른다.
    흰 네모(얼굴 대신)를 원본 x=800에 두면 가운데 크롭에선 슬롯 x≈754, 인물 중심 크롭에선 ≈540(가운데)."""
    from shopping_shorts.channel_presets.hotpeople import render, spec
    src = str(tmp_path / "sq.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30:d=4",
                    "-vf", "drawbox=x=770:y=240:w=60:h=60:color=white:t=fill", "-pix_fmt", "yuv420p", src], check=True)
    cover = render.cover_frame(src, 1.0)
    cx = _white_cx(cover) / cover.shape[1]
    x = render.face_crop_x(cover.shape[1], spec.SLOT_W, cx)
    assert abs(_white_cx(render.slot_from_cover(cover, x)) - spec.SLOT_W / 2) < 4
    assert abs(_white_cx(render.slot_from_cover(cover, render.face_crop_x(cover.shape[1], spec.SLOT_W, None))) - 754) < 6
    bg = render.background(_script()["title"], str(tmp_path / "bg.png"))
    sub = render.subtitle(_script()["groups"][2], str(tmp_path / "s.png"))
    for crop_x, want in ((x, spec.SLOT_W / 2), (None, 754)):
        out = str(tmp_path / f"c_{crop_x}.mp4")
        render.cut_clip(bg, sub, src, 1.0, 1.5, out, crop_x=crop_x)
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "0.5", "-i", out, "-frames:v", "1", "-vf",
                              f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True).stdout
        slot = np.frombuffer(raw, np.uint8).reshape(spec.SLOT_H, spec.SLOT_W)
        assert abs(_white_cx(slot) - want) < 6, (crop_x, _white_cx(slot))


def test_fits_blocks_other_person_and_hardsub_on_main_caption():
    from shopping_shorts.channel_presets.hotpeople import footage
    main, other, scene = {"text": "금메달을 따냄"}, {"text": "코치가 말함", "subject": "other"}, {"text": "경기장", "subject": "scene"}
    c = {"start": 0.0, "end": 9.0}
    assert not footage.fits(dict(c, who="다른사람"), main) and footage.fits(dict(c, who="다른사람"), other)
    assert not footage.fits(dict(c, who="주인공", subtitle_like=True), main)
<<<<<<< HEAD
    assert not footage.fits(dict(c, who="주인공", subtitle_like=True), scene)    # 박힌 자막은 어느 자막에도(관문 ≤1컷과 같은 규칙)
    assert footage.fits(dict(c, who="다른사람"), scene)
=======
    assert footage.fits(dict(c, who="주인공", subtitle_like=True), scene)
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
    assert footage.fits(dict(c, who="판정불가(작음)"), main) and footage.fits(dict(c, who="얼굴없음"), main)
    # 모델이 주인공 자막에 다른 사람 장면을 골라도 버리고 메운다
    cands = [dict(c, who="다른사람"), dict(c, who="주인공")]
    idx, fixed = footage.pick([main], cands, [], lambda p, i: '{"picks": [0]}', "x", log=lambda *_: None)
    assert idx == [1] and fixed == 1


def test_match_prompt_carries_vision_tags():
    from shopping_shorts.channel_presets.hotpeople import footage
    cands = [{"start": 0, "end": 5, "who": "다른사람"}, {"start": 0, "end": 5, "who": "주인공", "subtitle_like": True}]
    p = footage._match_prompt([{"text": "금메달"}, {"text": "코치", "subject": "other"}], {0: "a", 1: "b"}, "x", cands)
    assert "0 (5.0초) [다른 사람]: a" in p and "1 (5.0초) [주인공 얼굴 큼][박힌 자막]: b" in p
    assert "0. [주인공 장면 필수]" in p and "1. [다른 인물 가능]" in p


def test_verify_picks_raises_when_model_silent(tmp_path, monkeypatch):
    """검사 모델이 답을 못 주면 멈춘다(예전엔 None 을 '틀린 칸 없음'으로 읽고 렌더로 넘어갔다)."""
    from shopping_shorts.channel_presets.hotpeople import footage
    monkeypatch.setattr("time.sleep", lambda *_: None)
    th = tmp_path / "t.jpg"
    Image.new("RGB", (240, 176), (90, 120, 90)).save(th)
    (tmp_path / "footage").mkdir()
    cands = [{"thumb": str(th)} for _ in range(3)]

    def dead(p, i):
        raise RuntimeError("503")
    with pytest.raises(RuntimeError, match="장면 검사"):
        footage.check_and_repick([{"text": "a"}] * 3, cands, [0, 1, 2], [], dead, "x", str(tmp_path), log=lambda *_: None)


def test_subject_defaults_to_main():
    from shopping_shorts.channel_presets.hotpeople import rules
    assert rules.subject({}) == "main" and rules.subject({"subject": "OTHER"}) == "other"
    assert rules.subject({"subject": "누구"}) == "main" and rules.subject({"subject": "scene"}) == "scene"
<<<<<<< HEAD


def test_render_plan_seconds_equal_actual_frames(tmp_path):
    """컷 길이는 프레임 단위 한 곳(render.clip_frames)에서 — 계획 경계 = 실제 경계.
    우상혁 v2 실측: -t 반올림이 쌓여 실제 경계가 계획보다 최대 0.117초 늦었고 검수가 진짜 경계 3개를 '자막 안 컷'으로 셌다."""
    from shopping_shorts.channel_presets.hotpeople import render, spec
    src = str(tmp_path / "src.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30", "-t", "12", src], check=True)
    s = _script(3)
    for g, t in zip(s["groups"], ("가" * 15, "가" * 13, "가" * 16)):         # 2.25·2.17·2.28초 = 67.5·65.1·68.4 프레임
        g["text"] = t
    fo = {"cuts": [{"src": src, "start": 1.0 + i * 3, "url": "test"} for i in range(3)]}
    r = render.build(str(tmp_path), s, fo, log=lambda *_: None)
    for c in r["cuts"]:
        n = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                                "stream=nb_read_frames", "-of", "csv=p=0", str(tmp_path / "render" / f"cut_{c['i']:02d}.mp4")],
                               capture_output=True, text=True).stdout.strip())
        assert abs(c["sec"] * spec.FPS - n) < 1e-6, (c, n)


# ── 2026-09-28 우상혁 v2 원인 셋: 복제 프레임 가짜 컷 · 크롭 창 장면 자르기 · 한 장 태깅 ─────────────────────────
def test_split_spans_merges_burst_and_insets():
    from shopping_shorts.channel_presets.hotpeople import footage, spec
    ins = spec.CLIP_INSET_SEC
    sp = footage.split_spans([5.0, 10.0, 10.2, 10.4, 15.0], 0.0, 20.0)       # 10.0~10.4 = 0.2초 간격 덩어리
    assert sp == [(ins, 5 - ins), (5 + ins, 10 - ins), (10.4 + ins, 15 - ins), (15 + ins, 20 - ins)], sp
    assert footage.split_spans([], 336.03 - ins, 347.78 + ins) == [(336.03, 347.78)]     # 변화 없으면 그대로(반올림 흔들림 없음)


def _pan25(path, d=12):
    """25fps 빠른 가로 이동 — fps=30 복제 변환이면 0.2초마다 장면 점수가 튄다(우상혁 v2 6qVV9l0yHnM 재현)."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc2=s=1280x720:r=25:d={d}",
                    "-vf", "scroll=h=0.05", "-pix_fmt", "yuv420p", path], check=True)


def test_25fps_pan_renders_without_false_cuts(tmp_path):
    """★원인(컷 26 > 자막 23): 렌더의 fps=30 이 25fps 소스에서 다섯 장마다 한 장을 복제 → 움직이는 화면에서 검수 자가
    0.2초마다 컷으로 셌다(화면도 끊김). 렌더와 장면 자르기가 같은 사슬(render.clip_vf, 프레임 섞기)이어야 한다."""
    from shopping_shorts.channel_presets.hotpeople import footage, render, review
    src = str(tmp_path / "pan.mp4")
    _pan25(src)
    assert [t for t in footage.scene_changes(src) if t > 0.2] == []           # 장면 자르기도 가짜 변화를 안 본다(첫 장 제외)
    s = _script(3)
    fo = {"cuts": [{"src": src, "start": 0.5 + i * 3.5, "url": "t"} for i in range(3)]}
    r = render.build(str(tmp_path), s, fo, log=lambda *_: None)
    cuts = review.slot_cuts(r["mp4"])
    assert review.inner_cuts(r["mp4"], [c["sec"] for c in r["cuts"]], cuts=cuts) == [], cuts
    assert len(cuts) + 1 <= len(r["cuts"])


def _edge_flip(path):
    """오른쪽 끝(x 1050~1280)만 3초에 검정→흰색. 가운데 크롭(소스 x 236~1043)엔 안 보이고, 오른쪽으로 옮긴 크롭 창엔 보인다."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30:d=6",
                    "-vf", "drawbox=x=1050:y=0:w=230:h=590:color=white:t=fill:enable='gte(t,3)'",
                    "-pix_fmt", "yuv420p", path], check=True)


def test_scene_split_uses_shifted_crop_window(tmp_path, monkeypatch):
    """★원인: 장면 자르기는 가운데 크롭, 렌더는 얼굴 크롭 → 크롭 창에만 보이는 변화가 자막 안으로 샜다(v2 컷5 x=111).
    후보 태깅이 얼굴 크롭 창으로 다시 자르고, 렌더도 같은 함수(render.crop_x)로 창을 정한다."""
    from shopping_shorts.channel_presets.hotpeople import footage, render, spec
    src = str(tmp_path / "edge.mp4")
    _edge_flip(src)
    xh = render.crop_x(src, 0.95, spec.SCENE_DETECT_W, spec.SCENE_DETECT_H)
    assert footage.scene_changes(src) == []
    assert [round(t, 1) for t in footage.scene_changes(src, xh)] == [3.0]
    assert abs(render.crop_x(src, 0.95) - 2 * xh) <= 2                        # 렌더 창 = 장면 자르기 창(크기만 두 배)
    th = tmp_path / "t.jpg"
    Image.new("RGB", (240, 176)).save(th)
    monkeypatch.setattr(footage.vision, "faces", lambda img: [{"x": 0.93, "y": 0.2, "w": 0.04, "h": 0.3, "conf": 0.9}])
    monkeypatch.setattr(footage.vision, "look", lambda slot: {"face": False, "face_h": None, "cx_off": None, "box": None,
                                                              "emb": None, "sub_like": 0})
    c = {"vid": "v", "path": src, "start": 0.1, "end": 5.9, "thumb": str(th)}
    out = footage.tag_candidates([c], None, min_len=1.3, log=lambda *_: None)
    assert out and out[0]["coarse"] == [0.1, 5.9] and (out[0]["start"], out[0]["end"]) == (0.1, 2.9)
    assert out[0]["face_cx"] == 0.95 and out[0]["crop_x"] == render.crop_x(src, 0.95)


def test_tag_candidates_drops_too_short_after_resplit(tmp_path, monkeypatch):
    from shopping_shorts.channel_presets.hotpeople import footage
    src = str(tmp_path / "edge.mp4")
    _edge_flip(src)
    th = tmp_path / "t.jpg"
    Image.new("RGB", (240, 176)).save(th)
    monkeypatch.setattr(footage.vision, "faces", lambda img: [{"x": 0.93, "y": 0.2, "w": 0.04, "h": 0.3, "conf": 0.9}])
    monkeypatch.setattr(footage.vision, "look", lambda slot: {"face": False, "face_h": None, "cx_off": None, "box": None,
                                                              "emb": None, "sub_like": 0})
    c = {"vid": "v", "path": src, "start": 2.0, "end": 4.2, "thumb": str(th)}       # 3초 변화로 0.9·1.1초 조각
    assert footage.tag_candidates([c], None, min_len=1.3, log=lambda *_: None) == []


def test_tag_times_cover_render_window():
    from shopping_shorts.channel_presets.hotpeople import footage, spec
    assert footage.tag_times(10.0, 30.0) == [10.3, round(10 + spec.SUB_SEC_MAX / 2, 2), round(10 + spec.SUB_SEC_MAX - 0.3, 2)]
    ts = footage.tag_times(10.0, 11.4)
    assert ts[0] >= 10.0 and ts[-1] <= 11.4 and len(ts) == 3


def test_combine_tags_any_frame_subtitle_and_other_person():
    """★원인: 태깅은 한 장(시작+0.8), 관문은 컷 가운데 — 자막·로어서드가 그 사이에 떴다(v2 컷1·7)."""
    from shopping_shorts.channel_presets.hotpeople import footage
    from shopping_shorts.channelkit import vision
    a = np.r_[1.0, np.zeros(127)].astype(np.float32)
    other = np.r_[0.0, 1.0, np.zeros(126)].astype(np.float32)

    def lk(h=None, emb=None, sub=0):
        return {"face": h is not None, "face_h": h, "cx_off": 0.0 if h else None,
                "box": {"h": h} if h else None, "emb": emb, "sub_like": sub}
    t = footage.combine_tags([(1.0, lk(0.5, a)), (1.5, lk()), (2.0, lk(0.3, a, sub=1))], a)
    assert t["subtitle_like"] and t["sub_t"] == [2.0] and t["who"] == vision.WHO_MAIN and t["face_h"] == 0.5
    t = footage.combine_tags([(1.0, lk(0.6, a)), (1.5, lk(0.25, other))], a)
    assert t["who"] == vision.WHO_OTHER                                        # 큰 얼굴이 주인공이어도 다른 장에 다른 사람
    assert footage.combine_tags([(1.0, lk()), (2.0, lk())], a)["who"] == vision.WHO_NONE


def test_render_build_takes_window_from_face_cx(tmp_path):
    """렌더 경로(render.build)가 태깅과 같은 함수(render.crop_x)로 창을 정한다 — 얼굴(흰 네모)이 슬롯 가운데로."""
    from shopping_shorts.channel_presets.hotpeople import render, spec
    src = str(tmp_path / "sq.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30:d=12",
                    "-vf", "drawbox=x=770:y=240:w=60:h=60:color=white:t=fill", "-pix_fmt", "yuv420p", src], check=True)
    cover = render.cover_frame(src, 1.0)
    cx = _white_cx(cover) / cover.shape[1]
    s = _script(3)
    fo = {"cuts": [{"src": src, "start": 1.0 + i * 3, "url": "t", "face_cx": cx} for i in range(3)]}
    r = render.build(str(tmp_path), s, fo, log=lambda *_: None)
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "1.0", "-i", r["mp4"], "-frames:v", "1", "-vf",
                          f"crop={spec.SLOT_W}:{spec.SLOT_H}:{spec.SLOT_X}:{spec.SLOT_Y}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                         capture_output=True).stdout
    slot = np.frombuffer(raw, np.uint8).reshape(spec.SLOT_H, spec.SLOT_W)
    assert abs(_white_cx(slot) - spec.SLOT_W / 2) < 6 and r["cuts"][0]["crop_x"] == render.crop_x(src, cx)
=======
>>>>>>> 3eed4f089ea3d76cfb60872628efb619285cc16f
