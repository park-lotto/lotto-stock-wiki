# -*- coding: utf-8 -*-
"""channelkit.vision — faces_text.py(소재 화면 자)를 엔진으로 옮긴 것이 **같은 것을 재는지**.

★고정 표본 시험: 안세영 v3 완성본을 자(faces_text.py)로 잰 결과 channel/hotpeople/실측_2026-09-27/ours_anseyo_v3/faces_text.json
  (다른 사람 [19,23,25] · 자막꼴 [1,8,24], 1부터 센 번호)을 엔진 코드가 그대로 내야 한다.
  완성본 mp4(out/ 은 git 밖)나 모델(~/.shortem/models)이 없는 PC에서는 건너뛴다.
"""
import json
import os
import subprocess

import numpy as np
import pytest

from shopping_shorts.channelkit import vision as V

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "channel", "hotpeople", "실측_2026-09-27", "ours_anseyo_v3")
V3_MP4 = os.path.join(ROOT, "out", "hotpeople", "안세영_v3", "out", "final.mp4")
need_models = pytest.mark.skipif(bool(V.models_missing()), reason=f"모델 없음: {V.models_missing()}")


# ── 박힌 자막 줄 합치기 (합성 상자 — 모델 없이) ─────────────────────────────
W, H = 1080, 790


def test_subtitle_like_merges_word_boxes_into_one_row():
    """PP-OCR 은 "완전히 / 망가져 / 버렸죠"를 세 상자로 준다(v3 컷1) — 합쳐야 폭 35%를 넘는다."""
    img = np.zeros((H, W, 3), np.uint8)
    # 합친 폭 480 = 44%. ★자(faces_text)의 합치기는 (y0,x0) 정렬 순서를 탄다 — 이웃이 합쳐지기 전에 먼 상자가 먼저 오면
    #   따로 줄이 된다(자와 같게 옮겼다, 고치면 기준표 §19 숫자와 다른 자가 된다). 여기선 왼→오 순서로 y0 가 커진다.
    words = [(300, 640, 440, 690), (455, 641, 600, 690), (615, 642, 780, 688)]
    rows = V.subtitle_like_text(img, boxes=words)
    assert len(rows) == 1 and rows[0]["n"] == 3
    # 낱말 하나씩 따로 보면 폭이 모자라 아무것도 안 잡힌다 — 합치기가 실제로 하는 일
    assert all(not V._sub_like({"x0": b[0], "x1": b[2], "y0": b[1], "y1": b[3], "n": 2}, W, H) for b in words)


def test_subtitle_like_right_to_left_order_keeps_left_edge():
    """y 우선 정렬이라 왼쪽 상자가 나중에 올 수 있다 — x0 도 갱신해야 한다(빠뜨려 폭 0.17로 나왔던 결함)."""
    img = np.zeros((H, W, 3), np.uint8)
    words = [(470, 640, 780, 690), (300, 642, 455, 692)]                            # 오른쪽이 y 로 먼저
    rows = V.subtitle_like_text(img, boxes=words)
    assert len(rows) == 1 and rows[0]["x0"] == 300


@pytest.mark.parametrize("boxes, why", [
    ([(420, 640, 660, 690)], "상자 하나(코트 바닥 TOTAL, v3 컷10)"),
    ([(300, 100, 440, 150), (455, 100, 600, 150), (615, 100, 780, 150)], "위쪽(점수판)"),
    ([(10, 640, 150, 690), (165, 640, 400, 690)], "왼쪽 치우침(스폰서 보드)"),
    ([(400, 640, 480, 690), (495, 640, 580, 690)], "좁다(폭 < 35%)"),
])
def test_subtitle_like_rejects_non_subtitle_text(boxes, why):
    assert V.subtitle_like_text(np.zeros((H, W, 3), np.uint8), boxes=boxes) == [], why


# ── 누구인가 ────────────────────────────────────────────────────────────────
def _unit(v):
    v = np.asarray(v, np.float32)
    return v / np.linalg.norm(v)


def test_who_thresholds():
    a = _unit(np.r_[1.0, np.zeros(127)])
    same = _unit(np.r_[1.0, 1.0, np.zeros(126)])            # cos 0.707
    unsure = _unit(np.r_[0.3, 1.0, np.zeros(126)])          # cos 0.287
    other = _unit(np.r_[0.1, 1.0, np.zeros(126)])           # cos 0.0995
    big = {"h": 0.3}
    assert V.who(big, same, a) == V.WHO_MAIN
    assert V.who(big, unsure, a) == V.WHO_UNSURE
    assert V.who(big, other, a) == V.WHO_OTHER
    assert V.who({"h": 0.19}, other, a) == V.WHO_SMALL      # 작으면 판정 안 한다(주인공도 cos −0.1~0.1)
    assert V.who(None, None, a) == V.WHO_NONE


def test_protagonist_is_common_across_sources_not_most_frequent_in_one():
    """토크쇼 한 편에 진행자가 계속 나오면 짝 수로는 진행자가 이긴다(우상혁 v001 b_EPLebN4xU).
    groups(출처)를 주면 여러 영상에 공통인 얼굴이 주인공이다."""
    rng = np.random.default_rng(0)
    base_host, base_hero = rng.normal(size=128), rng.normal(size=128)
    host = [_unit(base_host + rng.normal(scale=0.3, size=128)) for _ in range(12)]
    hero = [_unit(base_hero + rng.normal(scale=0.3, size=128)) for _ in range(6)]
    embs = host + hero
    groups = ["talk"] * 12 + ["a", "a", "b", "b", "c", "c"]
    i_nogrp, _, _ = V.protagonist_embedding(embs)
    i_grp, anc, n = V.protagonist_embedding(embs, groups)
    assert i_nogrp < 12                     # 한 영상 기준(faces_text 방식)으론 진행자
    assert i_grp >= 12 and n >= 5           # 출처 기준으론 주인공
    assert V.who({"h": 0.5}, hero[0], anc) == V.WHO_MAIN and V.who({"h": 0.5}, host[0], anc) == V.WHO_OTHER


# ── 실제 모델 ──────────────────────────────────────────────────────────────
def _slot(mp4, t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", mp4, "-frames:v", "1", "-vf", "crop=1080:790:0:483",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(790, 1080, 3).copy()


@need_models
@pytest.mark.skipif(not os.path.exists(V3_MP4), reason="안세영 v3 완성본 없음(out/ 은 git 밖)")
def test_faces_on_array_same_as_facelib_on_file(tmp_path):
    """vision.faces(배열)는 facelib_cv.faces(파일 경로)와 같은 계산이어야 한다(동봉 파일을 고치지 않고 배열로 부르는 대가)."""
    import cv2
    bgr = _slot(V3_MP4, 30.0)
    p = str(tmp_path / "f.png")
    cv2.imwrite(p, bgr)
    V._facelib()
    from shopping_shorts.channelkit.vision import facelib_cv
    assert V.faces(bgr) == facelib_cv.faces(p, score=V.FACE_SCORE)


@need_models
@pytest.mark.skipif(not os.path.exists(V3_MP4), reason="안세영 v3 완성본 없음(out/ 은 git 밖)")
def test_port_measures_same_as_ruler_on_v3():
    """★사보타주 증거: 자(faces_text.py)가 v3에서 잡은 것 — 다른 사람 [19,23,25]·자막꼴 [1,8,24] — 을 엔진이 그대로 낸다.
    컷마다 who 판정 26개가 전부 같아야 한다(주인공·애매·판정불가·얼굴없음까지)."""
    cuts = json.load(open(os.path.join(FIX, "cuts.json"), encoding="utf-8"))["ours_anseyo.mp4"]
    ref = json.load(open(os.path.join(FIX, "faces_text.json"), encoding="utf-8"))["ours_anseyo"]
    ts, ends = [0] + cuts["sub_times"], cuts["sub_times"] + [cuts["dur"]]
    rows = [V.look(_slot(V3_MP4, (a + b) / 2)) for a, b in zip(ts, ends)]
    embs = [(i + 1, r["emb"]) for i, r in enumerate(rows) if r["emb"] is not None]
    k, anc, _ = V.protagonist_embedding([e for _, e in embs])       # faces_text 처럼 한 영상 안에서 주인공
    assert embs[k][0] == ref["anchor"]
    who = [V.who(r["box"], r["emb"], anc) for r in rows]
    assert [i + 1 for i, w in enumerate(who) if w == V.WHO_OTHER] == [19, 23, 25] == ref["other_face_cuts"]
    assert [i + 1 for i, r in enumerate(rows) if r["sub_like"]] == [1, 8, 24] == ref["sub_like_cuts"]
    assert who == [r["who"] for r in ref["rows"]]
    assert [r["face_h"] for r in rows] == [r["face_h"] for r in ref["rows"]]
