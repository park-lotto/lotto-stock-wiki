# -*- coding: utf-8 -*-
"""장면편집으로 조각을 빼거나 옮겨도, 그 조각이 청소본 어디에든 있으면 재청소 0 (2026-09-22 사장님 job 956a6843cdd5).

실사고: 4단계 청소 뒤 사장님이 장면편집으로 9칸 중 6칸의 조각을 빼거나 다른 칸으로 옮겼다.
칸 단위 판정은 6칸을 '바뀐 장면'으로 보고 25.4초(52크레딧) 재청소를 안내했다. 실제로는 쓰는 조각이
전부 청소본 안에 있었다. → 조각 단위로 청소본에서 찾아 쓴다."""
import json
from pathlib import Path

import pytest

from shopping_shorts import clean_base as cb

DATA = Path(__file__).parent / "data" / "clean_base_job956.json"


@pytest.fixture
def job956(tmp_path):
    d = json.loads(DATA.read_text(encoding="utf-8"))
    base = d["base"]
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base["path"] = str(tmp_path / "final_clean_x.mp4")
    (tmp_path / cb.BASE_FILE).write_text(json.dumps(base), encoding="utf-8")
    return d["edit_plan"], cb.load_base(tmp_path)


def test_real_job_only_truly_uncleaned_beats_change(job956):
    """실데이터: 6칸이 '바뀐 장면'이었던 것이 4칸으로 준다 — 7·8번은 조각을 뺀 것뿐이라 청소본 조각으로 덮인다.
    0·3·4·6번은 청소본에 **한 번도 안 나온** 조각(s0 8.2~9.9, s3 13.5~15.0 등)을 새로 넣어 진짜로 지워야 한다."""
    plan, base = job956
    cov = cb.coverage(plan, base)
    assert [k for k, v in cov.items() if v != "covered"] == [0, 3, 4, 6], cov
    plan2, uncovered, extend = cb.remap_plan(plan, base)
    assert uncovered == [0, 3, 4, 6] and extend == []
    for b in plan2["beats"]:
        if b["beat_idx"] in (0, 3, 4, 6):
            continue
        assert b["scene_override"] and all(m["video_id"] == "clean" for m in b["scene_override"]), b["beat_idx"]
        assert all(m["end"] > m["start"] for m in b["scene_override"])


def test_piece_moved_between_beats_is_covered(tmp_path):
    plan = {"beats": [
        {"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0}, "alternates": []},
        {"beat_idx": 1, "target_seconds": 2.0, "primary": {"video_id": "s1", "seg_id": "b", "start": 5.0, "end": 7.0}, "alternates": []}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan=plan,
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 2.0},
                              {"video_id": "s1", "beat_idx": 1, "src": 5.0, "fin": 2.0, "dur": 2.0}])
    # 사장님이 1번 칸 조각을 0번 칸으로 옮기고, 0번 조각을 뒤로 잘라 씀
    plan["beats"][0]["scene_override"] = [{"video_id": "s1", "seg_id": "b", "start": 5.5, "end": 7.0}]
    plan["beats"][1]["scene_override"] = [{"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0}]
    assert cb.coverage(plan, base) == {0: "covered", 1: "covered"}
    plan2, uncovered, _ = cb.remap_plan(plan, base)
    assert uncovered == []
    assert plan2["beats"][0]["scene_override"] == [{"video_id": "clean", "seg_id": "clean-1", "start": 2.5, "end": 4.0}]
    assert plan2["beats"][1]["scene_override"] == [{"video_id": "clean", "seg_id": "clean-0", "start": 0.0, "end": 2.0}]


def test_piece_outside_clean_is_still_changed(tmp_path):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 2.0, "primary": {"video_id": "s0", "seg_id": "a", "start": 0.0, "end": 2.0}, "alternates": []}]}
    (tmp_path / "final_clean_x.mp4").write_bytes(b"c" * 4096)
    base = cb.save_base(tmp_path, sig="x", path=str(tmp_path / "final_clean_x.mp4"), plan=plan,
                        cuts=[{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 2.0}])
    plan["beats"][0]["scene_override"] = [{"video_id": "s0", "seg_id": "a", "start": 10.0, "end": 12.0}]   # 청소본에 없는 구간
    assert cb.coverage(plan, base) == {0: "changed"}
