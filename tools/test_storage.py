# -*- coding: utf-8 -*-
"""저장 층 관제 v2(storage.py).

핵심: ① D 가 없거나 규칙 파일이 안 보이면 옮기지 않는다 ② 식은 트랙은 폴더를 옮기고 정션을 남기며 그 뒤에서 git 이 된다,
warm 으로 되돌아온다 ③ 이미 정션인 트랙은 계획에 다시 안 뜬다 ④ 옛 파일 판정은 mtime·atime 중 늦은 쪽."""
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import storage
import track
from test_track import repo, _git, _make_track_commit  # noqa: F401 (fixture)


def _map(root):
    root = Path(root)
    return {"외장": {"root": str(root), "규칙": str(root / "_저장규칙.txt"), "트랙": "00_트랙(정션)", "보관": "90_보관"},
            "경보": {"warn_gb": 15, "refuse_gb": 0},
            "층": [{"경로": ".tracks/<트랙> (7일+ 무활동)", "방법": "move+junction"}, {"경로": "out/", "방법": "move", "나이_일": 30}]}


def _external(tmp):
    d = Path(tmp) / "D"
    d.mkdir(exist_ok=True)
    (d / "_저장규칙.txt").write_text("규칙", encoding="utf-8")
    return d


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


def test_plan_lists_idle_tracks_and_stale_stages(repo, monkeypatch):
    wt = _make_track_commit(repo, "옛것")
    (wt / "메모.py").write_text("x = 1\n", encoding="utf-8")            # 미커밋 — 이제 막지 않고 표시만
    _make_track_commit(repo, "깨끗")
    monkeypatch.setattr(track, "_last_touch_days", lambda r, n: 30.0)
    stage = repo / ".tracks" / "_merge-죽은것"
    stage.mkdir()
    (stage / "big.bin").write_bytes(b"0" * 1024)
    items = storage.plan(repo, _map(repo / "D"), 7)
    by = {it["what"].split(" ")[0]: it for it in items}
    assert by[".tracks/옛것"]["how"] == "move+junction" and by[".tracks/옛것"]["note"].startswith("미커밋 1개")
    assert by[".tracks/깨끗"]["note"] == ""
    assert by[".tracks/_merge-죽은것"]["how"] == "delete" and by[".tracks/_merge-죽은것"]["size"] == 1024


@pytest.mark.skipif(os.name != "nt", reason="정션은 윈도우")
def test_move_track_to_external_and_warm_back(repo, tmp_path, monkeypatch):
    d = _external(tmp_path)
    smap = _map(d)
    wt = _make_track_commit(repo, "식은것")
    (wt / "dirty.py").write_text("y = 2\n", encoding="utf-8")
    monkeypatch.setattr(track, "_last_touch_days", lambda r, n: 30.0)

    assert storage.apply_tracks(repo, smap, 7, printer=lambda *a: None) == 1
    assert storage.is_junction(wt), "C 에는 정션이 남아 경로가 그대로 통한다"
    real = d / "00_트랙(정션)" / "식은것"
    assert (real / "dirty.py").exists(), "미커밋 파일도 폴더 통째로 간다(유실 없음)"
    assert _git(wt, "status", "--porcelain").strip().endswith("dirty.py"), "정션 뒤에서 git 이 된다"
    assert storage.cold_tracks(repo) == ["식은것"]
    assert storage.plan(repo, smap, 7) == [] or all("식은것" not in it["what"] for it in storage.plan(repo, smap, 7)), \
        "이미 D 에 있는 트랙은 다시 계획에 뜨지 않는다"

    assert storage.warm_track(repo, smap, "식은것", printer=lambda *a: None)
    assert not storage.is_junction(wt) and (wt / "dirty.py").exists() and not real.exists()
    assert _git(wt, "status", "--porcelain").strip().endswith("dirty.py")


@pytest.mark.skipif(os.name != "nt", reason="정션은 윈도우")
def test_dead_junction_is_reported(repo, tmp_path, monkeypatch):
    d = _external(tmp_path)
    smap = _map(d)
    _make_track_commit(repo, "빠진것")
    monkeypatch.setattr(track, "_last_touch_days", lambda r, n: 30.0)
    storage.apply_tracks(repo, smap, 7, printer=lambda *a: None)
    import shutil
    shutil.rmtree(d / "00_트랙(정션)")                     # D 가 빠진 상황 흉내
    wt = track.worktree_path("빠진것", repo)
    assert storage.dead_junction(wt)
    lines = []
    storage.status(repo, smap, printer=lines.append)
    assert any("죽은 정션" in ln and "빠진것" in ln for ln in lines)
    with pytest.raises(SystemExit):
        storage.warm_track(repo, smap, "빠진것", printer=lambda *a: None)


def test_apply_refuses_without_external(repo):
    with pytest.raises(SystemExit):
        storage.apply_tracks(repo, _map(repo / "없는D"), 7, printer=lambda *a: None)
    with pytest.raises(SystemExit):
        storage.apply_out(repo, _map(repo / "없는D"), printer=lambda *a: None)


def test_apply_out_moves_old_files_by_month(repo, tmp_path):
    d = _external(tmp_path)
    out = repo / "out"
    out.mkdir()
    p = out / "옛보고서.html"
    p.write_text("x", encoding="utf-8")
    old = time.mktime((2026, 6, 15, 12, 0, 0, 0, 0, -1))
    os.utime(p, (old, old))
    (out / "새것.html").write_text("y", encoding="utf-8")
    assert storage.apply_out(repo, _map(d), printer=lambda *a: None) == 1
    assert (d / "90_보관" / "out" / "2026-06" / "옛보고서.html").exists()
    assert not p.exists() and (out / "새것.html").exists()
