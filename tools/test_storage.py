# -*- coding: utf-8 -*-
"""저장 층 관제(storage.py) — 순수 판단 부분.

핵심: ① D 가 없거나 규칙 파일이 안 보이면 옮기지 않는다 ② 미커밋 있는 트랙은 계획에서 '건너뜀'으로 표시된다
③ 옛 파일 판정은 mtime·atime 중 늦은 쪽."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import storage
import track
from test_track import repo, _git, _make_track_commit  # noqa: F401 (fixture)


def _map(root):
    return {"외장": {"root": str(root), "규칙": str(root / "_저장규칙.txt"), "보관": "90_보관"},
            "경보": {"warn_gb": 15, "refuse_gb": 3},
            "층": [{"경로": ".tracks/<트랙>", "방법": "park+bundle"}, {"경로": "out/", "방법": "move", "나이_일": 30}]}


def test_external_refused_without_drive_or_rule(tmp_path):
    ok, why = storage.external_ok(_map(tmp_path / "없음"))
    assert not ok and "없다" in why
    d = tmp_path / "D"
    d.mkdir()
    ok, why = storage.external_ok(_map(d))
    assert not ok and "규칙 파일" in why, "다른 디스크가 D 에 물렸을 수 있다 — 규칙 파일이 없으면 옮기지 않는다"
    (d / "_저장규칙.txt").write_text("규칙", encoding="utf-8")
    assert storage.external_ok(_map(d))[0]


def test_old_files_use_latest_of_mtime_and_atime(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("x", encoding="utf-8")
    old = time.time() - 40 * 86400
    os.utime(p, (old, old))
    assert [o["path"] for o in storage.old_files(tmp_path, 30)] == [p]
    os.utime(p, (time.time(), old))          # 최근에 열었으면(atime) 옛 파일이 아니다
    assert storage.old_files(tmp_path, 30) == []


def test_plan_marks_dirty_tracks_as_blocked_and_counts_stale_stages(repo, monkeypatch):
    wt = _make_track_commit(repo, "옛것")
    (wt / "메모.py").write_text("x = 1\n", encoding="utf-8")            # 미커밋 코드 파일
    _make_track_commit(repo, "깨끗")
    monkeypatch.setattr(track, "_last_touch_days", lambda r, n: 30.0)    # 둘 다 30일 무활동으로 본다
    stage = repo / ".tracks" / "_merge-죽은것"
    stage.mkdir()
    (stage / "big.bin").write_bytes(b"0" * 1024)
    items = storage.plan(repo, _map(repo / "D"), 7)
    by = {it["what"].split(" ")[0]: it for it in items}
    assert by[".tracks/옛것"]["block"].startswith("미커밋 1개")
    assert by[".tracks/깨끗"]["block"] == ""
    assert by[".tracks/_merge-죽은것"]["how"] == "delete" and by[".tracks/_merge-죽은것"]["size"] == 1024


def test_apply_tracks_refuses_without_external(repo):
    import pytest
    with pytest.raises(SystemExit):
        storage.apply_tracks(repo, _map(repo / "없는D"), 7, printer=lambda *a: None)
