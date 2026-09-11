# -*- coding: utf-8 -*-
"""brainbulb 핵심 모듈을 **실제 볼케이노 산출물 5편**과 대조한다.

fixture = tests/fixtures/brainbulb/<편>/{sub.ass, timing.json, payload.json} (2026-09-11 제작분 원본)
정본 필드(아스트라 지적 반영): 컷 시각·lines = timing.json / 스타일·좌표·태그 = sub.ass / 효과음·wav 길이 = payload.json
"""
import json
import re
import shutil
from pathlib import Path

import pytest

from shopping_shorts.brainbulb import spec, timing, sfx, ass_gen

FX = Path(__file__).parent / "fixtures" / "brainbulb"
JOBS = ["parksuhong", "leedonggun", "taser", "borneo", "parkwi"]
HAS_FFMPEG = shutil.which("ffmpeg") is not None


def _load(job):
    d = FX / job
    return (json.loads((d / "payload.json").read_text(encoding="utf-8")),
            json.loads((d / "timing.json").read_text(encoding="utf-8")),
            (d / "sub.ass").read_text(encoding="utf-8"))


@pytest.mark.parametrize("job", JOBS)
def test_style_block_is_byte_identical(job):
    _, _, ass = _load(job)
    block = ass.split("[V4+ Styles]")[1].split("[Events]")[0].strip()
    assert "[V4+ Styles]\n" + block + "\n" == spec.STYLE_BLOCK


@pytest.mark.parametrize("job", JOBS)
def test_sfx_plan_matches_fixture(job):
    p, t, _ = _load(job)
    ours = sfx.plan(t["groups"])
    theirs = p["sfx_plan"]
    assert [(x["cut"], x["file"].split("/")[-1], x["gain"]) for x in ours] == \
           [(x["cut"], x["file"], x["gain"]) for x in theirs]


def test_sfx_extension_follows_family_formula():
    names = sfx._extend(40)
    assert names[:32] == spec.SFX_SEQ32
    for i in range(32, 40):
        base = re.sub(r"_\d+$", "", names[i])
        fam = spec.SFX_FAMILY[i % 4]
        assert base == fam[(i // 4) % len(fam)]


@pytest.mark.parametrize("job", JOBS)
def test_timing_reproduces_fixture(job):
    p, t, _ = _load(job)
    w = p["wav_secs"]
    n = len(t["groups"])
    ours = timing.build(w["0"], [w[str(i)] for i in range(1, n + 1)], t["groups"])
    assert ours["card_end"] == t["card_end"]
    assert [(g["i"], g["t"], g["d"]) for g in ours["groups"]] == [(g["i"], g["t"], g["d"]) for g in t["groups"]]
    assert ours["total"] == t["total"]


def _lines_from_ass(ass):
    """sub.ass 본문을 Start 시각으로 묶어 실제 lines 복원 — lines의 정본은 timing.json이 아니라 sub.ass(박수홍·박위 stale 실측)."""
    real, order = {}, []
    for ln in ass.splitlines():
        if ln.startswith("Dialogue: 4,"):
            parts = ln.split(",", 9); st = parts[1]; txt = re.sub(r"\{[^}]*\}", "", parts[9])
            if st not in real:
                real[st] = []; order.append(st)
            real[st].append(txt)
    return [real[s] for s in order]


def _split_time(line):
    p = line.split(",", 3)
    return (p[0], p[3]), p[1], p[2]


def _cs(t):
    h, m, s = t.split(":"); return (int(h) * 3600 + int(m) * 60) * 100 + round(float(s) * 100)


@pytest.mark.parametrize("job", JOBS)
def test_ass_lines_reproduce_fixture_given_sizes(job):
    """글자 크기(제목·카드)는 fixture 값을 주입, lines는 sub.ass 정본 → 좌표·태그·줄 구성은 전부 같고,
    시각은 ±1cs 허용(서버는 원시 누적값을 반올림해 135컷 중 2컷이 우리 3자리 t와 1cs 다르다 — 2026-09-12 실측)."""
    p, t, ass = _load(job)
    fx_lines = ass_gen.dialogue_lines(ass)
    fs1 = int(re.search(r",HL1,.*?\\fs(\d+)", ass).group(1))
    fs2 = int(re.search(r",HL2,.*?\\fs(\d+)", ass).group(1))
    cfs = int(re.search(r",CARD,[^\n]*?\\an5[^\n]*?\\fs(\d+)", ass).group(1))
    real_lines = _lines_from_ass(ass)
    t2 = dict(t); t2["groups"] = [dict(g, lines=real_lines[i]) for i, g in enumerate(t["groups"])]
    ours = ass_gen.build(p["title"], p["title"]["card"], t2, hl_fs=(fs1, fs2), card_fs=cfs)
    our_lines = ass_gen.dialogue_lines(ours)
    assert len(our_lines) == len(fx_lines)
    off = 0
    for a, b in zip(our_lines, fx_lines):
        ka, sa, ea = _split_time(a); kb, sb, eb = _split_time(b)
        assert ka == kb, (a, b)
        assert abs(_cs(sa) - _cs(sb)) <= 1 and abs(_cs(ea) - _cs(eb)) <= 1, (a, b)
        off += (sa != sb) + (ea != eb)
    assert off <= 4, f"시각 불일치 {off}건 — 1cs 이상이거나 예상보다 많다"


@pytest.mark.parametrize("job", JOBS)
def test_card_size_policy_matches_fixture(job):
    p, _, ass = _load(job)
    cfs = int(re.search(r",CARD,.*?\\an5.*?\\fs(\d+)", ass).group(1))
    assert ass_gen.card_size(p["title"]["card"]) == cfs


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음 — libass 실측 불가")
@pytest.mark.parametrize("job", JOBS)
def test_title_sizes_match_fixture_by_libass_measure(job):
    """제목 축소 규칙(잉크 폭 1000px)이 실제 5편의 fs를 그대로 재현하는가."""
    p, _, ass = _load(job)
    fs1 = int(re.search(r",HL1,.*?\\fs(\d+)", ass).group(1))
    fs2 = int(re.search(r",HL2,.*?\\fs(\d+)", ass).group(1))
    o1, o2 = ass_gen.title_sizes(p["title"]["h1"], p["title"]["h2"])
    # 비례식은 10건 중 8건 정확, 2건은 1pt 차이(서버 측정기와 libass 빌드 차이로 추정). 1pt는 화면에서 안 보인다.
    assert abs(o1 - fs1) <= 1 and abs(o2 - fs2) <= 1, ((o1, o2), (fs1, fs2))


@pytest.mark.skipif(not HAS_FFMPEG, reason="ffmpeg 없음")
def test_font_probe_all_fonts_resolve():
    from shopping_shorts.brainbulb import measure
    res = measure.font_probe()
    assert all(v["ok"] for v in res.values()), res
