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
    answers = iter(['{"bad": [1]}', '{"picks": {"1": 4}}'])
    new, v = footage.check_and_repick(groups, cands, [0, 1, 2], [], lambda p, imgs: next(answers), "x",
                                      str(tmp_path), log=lambda *_: None)
    assert new == [0, 4, 2] and v == {"bad": [1], "repicked": 1}
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
    """장면 경계는 슬롯 크롭 기준 + 앞뒤 0.1초 빼기(v002 경계 1프레임 번쩍임 4.33/4.37)."""
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
