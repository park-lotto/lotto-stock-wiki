# -*- coding: utf-8 -*-
"""11-05 꿀템샷 회원 편 94a65c1f2077: 무료 엔진(free_clean)이 끝나기만 하면 '지움'으로 세어 영어 박힌 자막이 일그러진 채
완성본 3~6초에 남았다(자동 검사 전부 ○). 지운 결과를 관문④ 검출기로 다시 재서(text_left) 남으면 실패 → 흐림, 다시 보내지 않는다(free_left)."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy import vmake_clean as VC  # noqa: E402

SPOT = {"bands": [{"y0": 0.6, "y1": 0.7, "big": False}]}


def _video(p: Path, text: str | None):
    cv2 = pytest.importorskip("cv2")
    import numpy as np
    w = cv2.VideoWriter(str(p), cv2.VideoWriter_fourcc(*"mp4v"), 30, (540, 960))
    for _ in range(30):
        im = np.full((960, 540, 3), (90, 120, 160), np.uint8)
        if text:
            cv2.putText(im, text, (60, 640), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 3, cv2.LINE_AA)
        w.write(im)
    w.release()
    return p


def test_text_left_in_band_is_caught(tmp_path):
    pytest.importorskip("shopping_shorts.channelkit.vision")
    why = VC.text_left(_video(tmp_path / "left.mp4", "Apparently this stains"), SPOT)
    assert "글자가 남음" in why
    assert VC.hard_fail(why) == "free_left"          # 같은 엔진으로 다시 지우지 않는다 → flow 가 흐림으로 확정


def test_clean_piece_passes(tmp_path):
    pytest.importorskip("shopping_shorts.channelkit.vision")
    assert VC.text_left(_video(tmp_path / "plain.mp4", None), SPOT) == ""


def test_text_outside_band_is_not_counted(tmp_path):
    pytest.importorskip("shopping_shorts.channelkit.vision")
    assert VC.text_left(_video(tmp_path / "plain.mp4", "Apparently this stains"), {"bands": [{"y0": 0.1, "y1": 0.2}]}) == ""


def test_free_clean_does_not_swap_in_when_text_left(tmp_path, monkeypatch):
    src = tmp_path / "a__vm_0.00_3.91.mp4"
    src.write_bytes(b"orig")

    class FE:
        @staticmethod
        def clean_file(f, tmp, spot):
            Path(tmp).write_bytes(b"cleaned")
            return {"frames": 1, "erased": 1}
    import tools.free_subclean as pkg
    monkeypatch.setattr(pkg, "engine", FE, raising=False)
    monkeypatch.setitem(sys.modules, "tools.free_subclean.engine", FE)
    monkeypatch.setattr(VC, "text_left", lambda v, s: "지운 뒤에도 글자가 남음(50%) — 흐림으로")
    swapped = []
    monkeypatch.setattr(VC, "swap_in", lambda f, t: swapped.append(f))
    monkeypatch.setattr(VC, "log_entry", lambda *a, **k: None)
    r = VC.free_clean([src], {"a.mp4": SPOT}, log=lambda s: None)
    assert r["cleaned"] == [] and src.name in r["fail"] and not swapped
    assert src.read_bytes() == b"orig"
