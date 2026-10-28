"""LAB 청소본 없음 → 관리자 시험 전용 미리보기 폴백(2026-09-18). 기본은 종전대로 차단."""
import pytest
from shopping_shorts import scene_style_lab as lab


def _job(tmp_path, with_preview=True):
    tmp_path.mkdir(exist_ok=True)
    pv = tmp_path / "preview.mp4"
    if with_preview:
        pv.write_bytes(b"x")
    return {"job_id": "j1", "edit_plan": {"beats": [{"beat_idx": 0, "text": "a"}]},
            "preview_status": "ready", "preview_path": str(pv)}


def test_default_blocks_without_clean(tmp_path):
    with pytest.raises(lab.LabPreconditionError):
        lab.create_copy("j1", _job(tmp_path), tmp_path)


def test_allow_unclean_uses_preview_and_marks_it(tmp_path):
    c = lab.unclean_preview_contract(_job(tmp_path))
    assert c["kind"] == "final" and c["unclean"] is True and c["path"].endswith("preview.mp4")
    assert lab.unclean_preview_contract(_job(tmp_path / "none", with_preview=False)) is None
