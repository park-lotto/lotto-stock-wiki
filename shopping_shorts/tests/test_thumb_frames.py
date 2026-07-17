"""등분 프레임 추출(설계 §프레임 추출은 등분이다).

장면전환 감지(extract_frames)와 달리 **항상 n장**이 나오고 ts를 함께 준다.
ffmpeg를 스텁해 시각 계산만 검증한다(실 ffmpeg는 Task 3 라이브 검증에서 본다).
"""
import pytest

from shopping_shorts import frame_extract


def test_grid_frames_returns_n_with_timestamps(tmp_path, monkeypatch):
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 23.5)
    calls = []

    def fake_at(video_path, dest_dir, timestamp_sec, filename="frame_hint.jpg"):
        calls.append(round(timestamp_sec, 3))
        p = tmp_path / filename
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(frame_extract, "extract_frame_at", fake_at)
    out = frame_extract.extract_grid_frames("v.mp4", tmp_path, n=10)

    assert len(out) == 10                      # 항상 n장 — 빈 리스트 케이스가 없다
    ts = [t for _, t in out]
    assert ts == sorted(ts)                    # 오름차순
    gaps = [round(b - a, 3) for a, b in zip(ts, ts[1:])]
    assert len(set(gaps)) == 1                 # 등간격


def test_grid_frames_skips_zero_and_end(tmp_path, monkeypatch):
    """0초(검은 첫프레임)와 정확히 끝(범위 밖)은 피한다 — 등분점은 구간 중앙."""
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 20.0)
    monkeypatch.setattr(frame_extract, "extract_frame_at",
                        lambda v, d, t, filename="f.jpg": ((d / filename).write_bytes(b"x"), d / filename)[1])
    ts = [t for _, t in frame_extract.extract_grid_frames("v.mp4", tmp_path, n=4)]
    assert ts[0] > 0
    assert ts[-1] < 20.0


def test_grid_frames_unique_filenames(tmp_path, monkeypatch):
    """파일명이 겹치면 마지막 한 장만 남는다 — 10장이 다 살아있어야 한다."""
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 30.0)
    monkeypatch.setattr(frame_extract, "extract_frame_at",
                        lambda v, d, t, filename="f.jpg": ((d / filename).write_bytes(b"x"), d / filename)[1])
    paths = [p for p, _ in frame_extract.extract_grid_frames("v.mp4", tmp_path, n=10)]
    assert len({p.name for p in paths}) == 10


def test_grid_frames_short_video_still_returns_n(tmp_path, monkeypatch):
    """1.2초짜리라도 n장 — 등분이라 길이와 무관하게 개수가 보장된다."""
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 1.2)
    monkeypatch.setattr(frame_extract, "extract_frame_at",
                        lambda v, d, t, filename="f.jpg": ((d / filename).write_bytes(b"x"), d / filename)[1])
    assert len(frame_extract.extract_grid_frames("v.mp4", tmp_path, n=10)) == 10


def test_grid_frames_raises_when_duration_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: None)
    with pytest.raises(RuntimeError):
        frame_extract.extract_grid_frames("v.mp4", tmp_path, n=10)


def test_grid_frames_skips_failed_extraction(tmp_path, monkeypatch):
    """extract_frame_at은 실패 시 None을 준다(기존 계약) — 그 자리는 빠지고 나머지는 산다."""
    monkeypatch.setattr(frame_extract, "_probe_duration", lambda p: 20.0)
    seq = {"i": 0}

    def flaky(v, d, t, filename="f.jpg"):
        seq["i"] += 1
        if seq["i"] == 2:
            return None
        p = d / filename
        p.write_bytes(b"x")
        return p

    monkeypatch.setattr(frame_extract, "extract_frame_at", flaky)
    out = frame_extract.extract_grid_frames("v.mp4", tmp_path, n=4)
    assert len(out) == 3  # 실패 1장 제외, 나머지 3장만 남음
