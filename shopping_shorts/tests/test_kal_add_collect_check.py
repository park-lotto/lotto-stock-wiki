"""칼카피 받은 영상 검사(표 #14·#15, Jev 해결 0.79·위험 0.26 · 11-06).

받은 mp4 마다 크기·열림·영상 트랙·오디오 트랙·높이 하한·길이(메타 대비 ±1.5초)·소리 있음을 잰다.
어긋나면 지우고 재수신 최대 2회, 검사 자체가 실패하면 '검사 못 함' = 불통과.
"""
import json
import subprocess
from pathlib import Path

import pytest

from tools.calcopy.engine import kal


def _mk(path: Path, dur=3.0, h=1280, audio=True, silent=False, w=720):
    """ffmpeg 로 진짜 작은 mp4 를 만든다(크기 하한은 시험에서 낮춘다)."""
    a = (["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo" if silent else "sine=frequency=440:sample_rate=44100"] if audio else [])
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate=30", *a,
           "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast", *(["-c:a", "aac", "-shortest"] if audio else []), str(path)]
    subprocess.run(cmd, check=True)


def test_good_file_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(kal, "MIN_FILE_BYTES", 1000)
    p = tmp_path / "v.mp4"
    _mk(p, dur=3)
    assert kal.check_fetched(p, 3) == []


@pytest.mark.parametrize("kw,meta,word", [
    ({"audio": False}, 3, "오디오 트랙"),
    ({"silent": True}, 3, "소리"),
    ({"h": 640, "w": 360}, 3, "높이"),
    ({}, 8, "길이"),
])
def test_bad_files_fail(tmp_path, monkeypatch, kw, meta, word):
    monkeypatch.setattr(kal, "MIN_FILE_BYTES", 1000)
    p = tmp_path / "v.mp4"
    _mk(p, dur=3, **kw)
    why = kal.check_fetched(p, meta)
    assert why and any(word in w for w in why), why


def test_small_and_broken_are_fail_not_pass(tmp_path):
    p = tmp_path / "v.mp4"
    p.write_bytes(b"x" * 10)
    why = kal.check_fetched(p, 3)
    assert any("크기" in w for w in why)
    big = tmp_path / "b.mp4"
    big.write_bytes(b"\0" * (kal.MIN_FILE_BYTES + 10))
    why = kal.check_fetched(big, 3)
    assert any("열림" in w or "검사 못 함" in w for w in why), why      # 검사 못 함 ≠ 통과


def test_meta_duration_from_info_json(tmp_path):
    (tmp_path / "v.info.json").write_text(json.dumps({"duration": 16}), encoding="utf-8")
    assert kal.meta_duration(tmp_path, "v") == 16
    assert kal.meta_duration(tmp_path, "none") is None


def test_collect_refetches_then_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "DATA", tmp_path / "data")
    monkeypatch.setattr(kal, "disk_gate", lambda w: None)
    S = kal.State("s1", "@ch", "우리", 2, "아니오", "v")
    S.d["channel"] = {"top_ids": ["a", "b", "c"]}
    calls = []

    def fake_fetch(base, vid, url, fmt):
        calls.append(vid)
        (base / f"{vid}.mp4").write_bytes(vid.encode())
        (base / f"{vid}.info.json").write_text('{"duration": 3}', encoding="utf-8")
        return 0, ""
    monkeypatch.setattr(kal, "fetch_one", fake_fetch)
    monkeypatch.setattr(kal, "_run", lambda cmd, timeout=0: subprocess.CompletedProcess(cmd, 0, "", ""))
    monkeypatch.setattr(kal, "check_fetched", lambda p, m: [] if p.stem != "b" else ["소리 없음"])
    st, out, note = kal.step_collect(S)
    assert calls.count("b") == 1 + kal.REFETCH_MAX            # 처음 + 재수신 2회
    assert calls.count("a") == 1
    assert st == "done" and out["ids"] == ["a", "c"] and "검사 불통과" in note and "b" in note
    assert not (tmp_path / "data/s1/src/b.mp4").exists()       # 불통과 파일은 남기지 않는다(뜯기에 안 간다)
    assert out["checked"]["b"] == ["소리 없음"]


def test_truncated_file_with_header_first_fails(tmp_path, monkeypatch):
    """머리(moov)가 앞에 있는 파일을 잘라도 ffprobe 는 원래 길이를 말한다 — 끝까지 풀어 본 소리 길이로 잡는다(11-06 실측)."""
    monkeypatch.setattr(kal, "MIN_FILE_BYTES", 1000)
    full = tmp_path / "f.mp4"
    _mk(full, dur=8)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(full), "-c", "copy", "-movflags", "+faststart", str(tmp_path / "fs.mp4")], check=True)
    b = (tmp_path / "fs.mp4").read_bytes()
    cut = tmp_path / "cut.mp4"
    cut.write_bytes(b[: len(b) // 3])
    why = kal.check_fetched(cut, 8)
    assert any("끝까지" in w or "열림" in w for w in why), why
