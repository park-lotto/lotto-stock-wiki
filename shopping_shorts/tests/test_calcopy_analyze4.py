# -*- coding: utf-8 -*-
"""칼카피 뜯기 4판 — 답을 아는 시험(원본 영상 프레임·실제 뜯기 산출물에서 사람이 확인한 정답).

① 극성: 흰 바탕 검정 자막을 bright 로 뒤집던 결함(2026-10-16 썰풀다 LED 수도꼭지 렌더 fill_ratio 0.522 ≥ 0.5).
   픽스처 = 실제 프레임 띠 크롭(`fixtures/calcopy_analyze4/*.png`) — LED 렌더·ZdeZ 원본(검정 글자, 페이블 눈 판정 통과작/점검.md 정답),
   mY·D3 원본(흰 글자+검정 외곽선, 점검.md 정답). 사보타주: captions.CAP_RING_BG_MAX 를 1.01 로 올리면(옛 판정) LED 가 bright 로 실패.
② 자막 띠 고르기: 흰 게시글 틀(yummyknow)에서 그림 칸 사진이 자막 1등을 가져가던 결함.
   픽스처 = engine_뜯기3 실제 후보 표(gBVXQdbzwJU·p8IDs2HdfvY layout.caption_candidates) — 정답(점검.md, 시트):
   자막 = 검정 1줄 ≈578~631 + 누적 2줄째 ≈665~716(창 위 끝에 걸침), 그림 칸(≈730~)은 자막 아님.
③ 외곽선 두께: 굵은 검정 외곽선(핫템 IRFN·RWS ≈13px)을 '외곽선 0px'로 내던 결함 — 바탕 고리(9~15px)가 외곽선 속이었다.
   픽스처 = 원본 띠 크롭(점검.md 정답 '흰 글자 + 검정 외곽선'), 눈금: 고리 밝기 r1..13 ≈ 0, r14~ 영상(35~110).
   사보타주: captions.GLYPH_BG_RING 을 (9, 15) 로 되돌리면 실패.
④ (선택, CALCOPY_REAL_VIDEO=1) 원본 mp4 12초 조각으로 layout1.measure 끝까지 — 띠가 1·2줄을 덮고 극성 dark.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

cv2 = pytest.importorskip("cv2")
from shopping_shorts.channelkit.bench import captions  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "calcopy_analyze4"


def _img(name: str) -> np.ndarray:
    a = cv2.imdecode(np.fromfile(str(FIX / name), np.uint8), cv2.IMREAD_COLOR)   # 한글 경로 — imread 는 못 연다
    assert a is not None, name
    return cv2.cvtColor(a, cv2.COLOR_BGR2RGB)


def _decide(names: list[str]) -> bool:
    stats = [s for s in (captions.fill_stats(_img(n)) for n in names) if s]
    assert stats, names
    return captions.bright_wins(stats)[0]


# ── ① 극성 ────────────────────────────────────────────────────────────────
def test_dark_text_on_white_is_not_bright():
    # 정답: 흰 바탕 검정 자막(LED 렌더 = 통과작 18db9313f, ZdeZ 원본 점검.md '검정, 외곽선·그림자 없음')
    assert _decide(["led_dark_t2.png", "led_dark_t10.png", "led_dark_t18.png"]) is False
    assert _decide(["zdez_dark_t6.png"]) is False


def test_outlined_white_text_on_video_is_bright():
    # 정답: 영상 위 흰 글자 + 검정 외곽선(mY 점검.md '흰·검정 외곽선 5px', D3 '흰·검정 외곽선 굵게')
    assert _decide(["my_bright_t7.png", "my_bright_t11.png"]) is True
    assert _decide(["d3_bright_t3.png"]) is True


# ── ② 자막 띠 고르기(실제 후보 표) ──────────────────────────────────────────
# engine_뜯기3/gBVXQdbzwJU/뜯기.json layout.caption_candidates (pos, band, ink, score)
GBVX = [("below", [1520, 1775], "dark", 0.7), ("above", [67, 175], "dark", 1.0), ("above", [286, 386], "dark", 1.0),
        ("above", [419, 482], "dark", 1.0), ("above", [576, 632], "dark", 18.0), ("above", [286, 482], "dark", 1.0),
        ("inside", [671, 722], "dark", 18.1), ("inside", [694, 722], "dark", 18.1), ("inside", [752, 1369], "bright", 17.93),
        ("inside", [775, 826], "bright", 10.53), ("inside", [851, 916], "bright", 8.87), ("inside", [925, 952], "bright", 10.9),
        ("inside", [959, 1126], "bright", 15.51), ("inside", [1138, 1173], "bright", 11.21), ("inside", [1184, 1259], "bright", 13.7)]
# engine_뜯기3/p8IDs2HdfvY/뜯기.json
P8ID = [("above", [578, 681], "dark", 13.0), ("above", [66, 174], "dark", 1.0), ("above", [285, 365], "dark", 1.0),
        ("above", [416, 475], "dark", 1.0), ("above", [578, 633], "dark", 13.0), ("inside", [687, 722], "dark", 14.67),
        ("inside", [760, 863], "bright", 6.22), ("inside", [1154, 1352], "bright", 11.1), ("inside", [687, 863], "bright", 14.3),
        ("inside", [687, 1044], "bright", 16.51), ("inside", [687, 1352], "bright", 13.72)]


def _rows(t):
    return [{"pos": p, "band": b, "ink": k, "score": s} for p, b, k, s in t]


def test_picture_cell_does_not_win_by_width():
    # 옛 고르기: 점수 5% 안이면 넓은 띠 → 그림 칸 bright [752,1369](17.93)가 자막 dark(18.1)을 이겼다
    best = captions.pick_caption([(r, {}) for r in _rows(GBVX)])
    assert best[1]["ink"] == "dark" and best[1]["band"][1] <= 722


def test_join_two_caption_lines_across_window_edge():
    # 정답 띠 ≈578~716: 위 1줄 후보와 창 안 2줄 후보를 잇는 후보가 생겨야 한다(제목·머리띠 점수 1.0 은 안 이음)
    for table, want in ((GBVX, [576, 722]), (P8ID, [578, 722])):
        js = captions.join_candidates(_rows(table), 1920)
        bands = [j["band"] for j in js if j["ink"] == "dark"]
        assert want in bands, (want, bands)
        assert all(j["free"] for j in js)
        assert not any(j["band"][0] < 500 for j in js)        # 머리띠·제목(67~482)은 잇지 않는다
    # p8ID: 이은 띠가 그림 칸(16.51)보다 높게 재지면 이긴다 — 1등 고르기는 점수 순서
    rows = _rows(P8ID) + [{"pos": "above", "band": [578, 722], "ink": "dark", "score": 27.0, "free": True, "joined": True}]
    best = captions.pick_caption([(r, {}) for r in rows])
    assert best[1]["band"] == [578, 722] and best[1]["ink"] == "dark"
    assert best[1].get("joined") and best[1].get("free")     # 이은 띠 표시가 남아야 좁히기(tighten_band)를 건너뛴다


# ── ③ 외곽선 두께 ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("name", ["irfn_thickol_t6.png", "rws_thickol_t5.png"])
def test_thick_black_outline_measured(name):
    g = captions.glyph_style(_img(name), "bright", [0, 0, 0])
    assert g and g["outline"] and 10 <= g["outline_px"] <= 16, g


@pytest.mark.parametrize("name,lo,hi", [("my_bright_t7.png", 4, 6), ("d3_bright_t3.png", 5, 8)])
def test_known_outline_widths_kept(name, lo, hi):
    # mY 점검.md '외곽선 약 5px', D3 '외곽선 굵게(약 6px)' — 바탕 고리를 바꿔도 그대로여야 한다
    g = captions.glyph_style(_img(name), "bright", [0, 0, 0])
    assert g and lo <= g["outline_px"] <= hi, g


@pytest.mark.parametrize("name", ["led_dark_t10.png", "zdez_dark_t6.png"])
def test_dark_text_on_white_no_outline(name):
    g = captions.glyph_style(_img(name), "dark", [255, 255, 255])
    assert g and g["outline_px"] == 0 and not g["outline"], g


def test_translucent_box_is_not_outline():
    # w-Yg 점검.md '상자 있음(반투명 검정), 흰 글씨 작게' — 글자 둘레 48~55 vs 바탕 76 은 외곽선이 아니라 상자
    g = captions.glyph_style(_img("wyg_box_t9.png"), "bright", [0, 0, 0])
    assert g is None or g["outline_px"] == 0, g


# ── ④ 원본 영상 조각 끝까지(느림 — 켤 때만) ─────────────────────────────────
REAL = Path("C:/숏템_칼카피/yummyknow/mp4/gBVXQdbzwJU.mp4")


@pytest.mark.skipif(os.environ.get("CALCOPY_REAL_VIDEO") != "1" or not REAL.exists() or shutil.which("ffmpeg") is None,
                    reason="CALCOPY_REAL_VIDEO=1 + 원본 mp4 필요")
def test_real_gbvx_clip_caption_band(tmp_path):
    from shopping_shorts.channelkit.bench import probe
    from tools.calcopy.engine import layout1
    clip = tmp_path / "g.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "2", "-i", str(REAL), "-t", "12", "-an", "-c:v", "libx264",
                    "-preset", "veryfast", "-crf", "18", str(clip)], check=True, stdin=subprocess.DEVNULL)
    r = layout1.measure(str(clip), probe.info(str(clip)))
    c = r["vl"]["caption"]
    assert c["ink"] == "dark", c
    assert c["band"][0] <= 590 and c["band"][1] >= 705, c      # 1줄 578~631 + 2줄 665~716
    assert c["band"][1] <= 740, c                              # 그림 칸(≈750~)은 안 먹는다
