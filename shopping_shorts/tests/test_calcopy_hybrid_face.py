# -*- coding: utf-8 -*-
"""T1 얼굴 검사 회귀 — 바탕화면 하이브리드 15판 첫 프레임(0.1초)은 전부 ○, 옛 판 첫 프레임(제품·전신)은 반려 (2026-10-18 코디네이터 검증).

10-18 사고: YuNet 에 1080 창을 그대로 넣으면 창을 꽉 채운 근접 얼굴(강민경·함익병·박세리)을 conf 0.7대·틀린 상자로 놓쳐 '얼굴 0개' 거짓 반려.
→ 축소 입력 여러 크기(480·320·240) 검출 뒤 합침. 파일 없는 PC 에선 건너뛴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import thumb  # noqa: E402

DESK = Path("C:/Users/CH/Desktop/칼카피영상/얜샷템/하이브리드")
WORK = Path("C:/숏템_칼카피/yanshottem")
WIN = (0, 420, 1080, 1080)
PIECES = ["강민경포트레틴트_잇썸홈판", "강민경포트레틴트_재미썸홈판", "박세리라프레리_잇썸홈판", "박세리라프레리_재미썸홈판", "안유진eos바닐라로션_재미썸홈판",
          "이영자고렌샤크요가신발_잇썸홈판", "이영자고렌샤크요가신발_재미썸홈판", "장윤정테클라수건_잇썸홈판", "장윤정테클라수건_재미썸홈판",
          "최은경자라로퍼_잇썸홈판", "최은경자라로퍼_재미썸홈판", "한고은채소통_잇썸홈판", "한고은채소통_재미썸홈판", "함익병도브_잇썸홈판", "함익병도브_재미썸홈판"]
# 옛 판 첫 프레임: (연예인, 판, 반려돼야 하나) — 최은경 재미썸 옛 첫 프레임은 제품이 아니라 최은경 얼굴 큰 컷(0.27)이라 통과가 맞다
PREV = [("박세리", "잇썸홈판", True), ("이영자", "잇썸홈판", True), ("이영자", "재미썸홈판", True), ("장윤정", "잇썸홈판", True),
        ("장윤정", "재미썸홈판", True), ("최은경", "잇썸홈판", True), ("최은경", "재미썸홈판", False)]


def _need(p):
    if not Path(p).exists():
        pytest.skip(f"표본 없음: {p}")


@pytest.mark.parametrize("name", PIECES)
def test_desktop_first_frame_has_big_centered_face(name):
    """0.1초 = 연예인 얼굴(코디네이터가 눈으로 확인). 안유진 재미썸 0.1초는 눈 감음 — 얼굴 검출은 ○(표정은 사람이 본다)."""
    f = DESK / f"칼카피_얜샷템_{name}.mp4"
    _need(f); _need(thumb.MODEL)
    det = thumb._detector()
    im = thumb._frame(f, 0.1, WIN)
    ok, why, info = thumb.judge(thumb.faces_of(det, im), im.shape[1], im.shape[0])
    assert ok, (name, why, info)
    assert info["h_frac"] >= thumb.FACE_MIN_FRAC


@pytest.mark.parametrize("celeb,ver,reject", PREV)
def test_old_first_frame_product_or_small_face_is_rejected(celeb, ver, reject):
    f = WORK / f"하이브리드_{celeb}/{ver}/render/final_prev_firstframe.mp4"
    _need(f); _need(thumb.MODEL)
    r = thumb.face_check(f, WIN, None, log=lambda *a: None)
    assert r["ok"] == (not reject), (celeb, ver, r["frames"][0])
