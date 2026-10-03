# -*- coding: utf-8 -*-
"""장면꾸미기 페이지 그림 = 그 페이지 시각의 화면 (2026-10-03 관제 101, 황선희님 817308da1647).

실사고: 한 컷(2.07초)의 앞 1.1초에만 원본 자막이 지나가는데, 편집기는 모든 페이지에 칸 대표 그림 한 장
(자막이 사라진 뒤 순간)을 보여줬다 → 고객이 가림막을 못 넣었고 완성본에서야 자막이 보였다.
잡는 것: ① 완성본 시각 → (그 순간의 컷, 재료 시각) ② 페이지 대표 시각 = 창 한가운데
        ③ 그림 파일이 시각마다 갈린다(같은 칸이라도 다른 페이지는 다른 그림) ④ 미리 뽑기가 시각을 넘긴다
"""
from shopping_shorts import app as A

CUTS = [{"video_id": "s4", "beat_idx": 8, "src": 4.0, "fin": 18.8, "dur": 2.0, "sdur": 2.0},
        {"video_id": "s2", "beat_idx": 8, "src": 7.0, "fin": 20.8, "dur": 1.0, "sdur": 2.0}]      # 뒤 컷은 재료를 2배속으로


def test_cut_at_maps_final_time_into_the_cut_material():
    c, t = A._cut_at(CUTS, 19.3)                    # 앞 컷 0.5초 지점
    assert c["video_id"] == "s4" and abs(t - 4.5) < 1e-6
    c, t = A._cut_at(CUTS, 20.4)                    # 같은 컷의 뒤쪽 — 대표 그림 한 장으로는 못 가르던 자리
    assert c["video_id"] == "s4" and abs(t - 5.6) < 1e-6
    c, t = A._cut_at(CUTS, 21.3)                    # 뒤 컷 0.5초 지점, 재료는 2배속 → 재료 1.0초
    assert c["video_id"] == "s2" and abs(t - 8.0) < 1e-6


def test_cut_at_outside_falls_to_nearest_cut_edge():
    c, t = A._cut_at(CUTS, 18.0)                    # 칸 시작보다 앞(자막 창이 칸 앞 틈을 흡수한 경우)
    assert c["video_id"] == "s4" and abs(t - 4.0) < 1e-6
    c, t = A._cut_at(CUTS, 30.0)
    assert c["video_id"] == "s2" and t < 7.0 + 2.0   # 마지막 프레임을 넘지 않는다
    assert A._cut_at([], 1.0) == (None, None)


def test_page_time_is_the_middle_of_its_window():
    assert abs(A._scene_page_time({"start": 18.82, "end": 19.91}) - 19.365) < 0.011     # '순식간에' 페이지(자막이 보이는 구간)
    assert abs(A._scene_page_time({"start": 19.91, "end": 20.88}) - 20.395) < 0.011     # 같은 칸의 다음 페이지


def test_frame_file_differs_per_page_time(tmp_path, monkeypatch):
    """같은 칸의 두 페이지가 서로 다른 파일(= 다른 순간)을 받는다. 종전엔 칸 번호만 넘겨 둘이 같은 파일이었다."""
    job = {"edit_plan": {"beats": [{"beat_idx": 8, "primary": {"video_id": "s4", "start": 4.0, "end": 6.0}}]}}
    seen = []
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(A, "_clean_frame_src", lambda job, work, i, cut=None, at=None: ({}, None, None, "", False))
    monkeypatch.setattr(A, "_final_cuts", lambda job, work: CUTS)

    def _fake_extract(work, beat, out, **k):
        seen.append((out.name, k.get("seg_spec")))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        return True
    monkeypatch.setattr(A, "_extract_beat_frame", _fake_extract)
    a = A._beatframe_file(job, "j", 8, at=19.36)
    b = A._beatframe_file(job, "j", 8, at=20.40)
    c = A._beatframe_file(job, "j", 8)
    assert len({a.name, b.name, c.name}) == 3
    assert seen[0][1] == {"video_id": "s4", "start": 4.56} and seen[1][1] == {"video_id": "s4", "start": 5.6}
    assert seen[2][1] is None                                    # at 없이 부르면 종전 그대로(칸 그림)


def test_prewarm_passes_page_times(monkeypatch):
    got = []
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i, cut=None, at=None: got.append((i, at)))

    A._prewarm_beatframes({}, "jpw", [(8, 19.36), (8, 20.4), 3])
    import time
    for _ in range(100):                                         # 뒤에서 도는 미리 뽑기가 끝날 때까지
        if "jpw" not in A._PREWARM_BUSY and len(got) == 3:
            break
        time.sleep(0.05)
    assert sorted(got, key=str) == sorted([(8, 19.36), (8, 20.4), (3, None)], key=str)


def test_page_points_are_front_middle_back_inside_the_window():
    """페이지 안 앞·가운데·뒤(관제 104) — 셋 다 창 안쪽이고, 가운데는 기본 그림 시각과 같다."""
    sc = {"start": 18.82, "end": 19.91}
    a, m, b = A._scene_page_points(sc)
    assert 18.82 < a < m < b < 19.91 and m == A._scene_page_time(sc)
    assert abs((a - 18.82) - 0.15) < 0.011 and abs((19.91 - b) - 0.15) < 0.011      # 창 끝에서 0.15초 안쪽
    a, m, b = A._scene_page_points({"start": 1.0, "end": 1.3})                       # 짧은 창은 창 길이의 1/5
    assert abs(a - 1.06) < 0.011 and abs(b - 1.24) < 0.011
