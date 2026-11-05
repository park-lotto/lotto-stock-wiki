"""11-05 박세현 #8643: 윈도 사용자 폴더가 한글이면 OpenCV 가 경로로는 얼굴 모델을 못 연다 — 만들기 한 곳(common.face_detector)이 바이트로 읽는다."""
import shutil
from pathlib import Path

import pytest

from tools.calcopy.hybrid import common as C


def test_face_detector_opens_model_in_korean_folder(tmp_path, monkeypatch):
    src = Path(C.FACE_MODEL)
    if not src.is_file():
        pytest.skip("이 PC 에 얼굴 모델 없음")
    d = tmp_path / "한글사용자" / "models"
    d.mkdir(parents=True)
    dst = d / src.name
    shutil.copyfile(src, dst)
    monkeypatch.setattr(C, "FACE_MODEL", str(dst))
    det = C.face_detector(320, 320)
    assert det is not None
