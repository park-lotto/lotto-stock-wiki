# -*- coding: utf-8 -*-
"""자막 남음 대조 도구(clean_left_audit.py) — 세기·실물 모드·요약 형식(2026-09-28). 판정 자체는 test_clean_left_beats."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import clean_left_audit as cla


def _r(left=(), pending=(), chosen=(), unknown=(), tier=False):
    return {"left": list(left), "pending": list(pending), "chosen": list(chosen), "unknown": list(unknown),
            "tier_upgrade": tier}


class _MP:
    def __init__(self, res):
        self.res = res

    def clean_left_beats(self, store, job, work):
        return self.res[job["job_id"]]


def _run(tmp_path, monkeypatch, jobs, res, delivered=False):
    monkeypatch.setattr(cla, "OUT", tmp_path / "out")
    cla.run(list(jobs), delivered, mp=_MP(res), store=None, get_job=lambda j: jobs.get(j), work_root=tmp_path)
    return (tmp_path / "out" / "report.txt").read_text(encoding="utf-8")


def test_counts_left_pending_unknown_na(tmp_path, monkeypatch):
    jobs = {"a1b2c3": {"job_id": "a1b2c3"}, "d4e5f6": {"job_id": "d4e5f6"}, "g7h8i9": {"job_id": "g7h8i9"}}
    res = {"a1b2c3": _r(left=[1, 2], chosen=[3]), "d4e5f6": _r(pending=[5, 7], unknown=[9]), "g7h8i9": None}
    rep = _run(tmp_path, monkeypatch, jobs, res)
    assert cla.parse_summary(rep) == {"jobs": 2, "left": 2, "pending": 2, "unknown": 1, "na": 1, "stale": 0}
    assert "a1b2c3 | 자막 남음 [1, 2] | 증분 대기 [] | 원인 미상 [] | 고른 원본 [3]" in rep


def test_tier_upgrade_moves_left_to_pending_in_current_mode(tmp_path, monkeypatch):
    """등급 상향이면 렌더가 정본 대신 전체를 지운다 — 정본 기준 결함 칸도 실제론 지워진다(대기)."""
    jobs = {"a1b2c3": {"job_id": "a1b2c3"}}
    rep = _run(tmp_path, monkeypatch, jobs, {"a1b2c3": _r(left=[1], tier=True)})
    s = cla.parse_summary(rep)
    assert s["left"] == 0 and s["pending"] == 1


def test_delivered_mode_merges_pending_and_skips_stale(tmp_path, monkeypatch):
    """실물 모드: 대기 칸도 원본으로 나갔다(자막 남음에 합침). 렌더 뒤 편집·완성본 없음은 재구성 불가."""
    vp = tmp_path / "final.mp4"
    vp.write_bytes(b"v")
    now = time.time()
    os.utime(vp, (now, now))
    iso_now = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now))
    iso_late = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now + 3600))
    jobs = {"a1b2c3": {"job_id": "a1b2c3", "status": "done", "video_path": str(vp), "updated_at": iso_now},
            "d4e5f6": {"job_id": "d4e5f6", "status": "done", "video_path": str(vp), "updated_at": iso_late},
            "g7h8i9": {"job_id": "g7h8i9", "status": "ready_for_review", "video_path": None, "updated_at": iso_now}}
    res = {"a1b2c3": _r(left=[1], pending=[4]), "d4e5f6": _r(left=[9]), "g7h8i9": _r(left=[9])}
    rep = _run(tmp_path, monkeypatch, jobs, res, delivered=True)
    assert cla.parse_summary(rep) == {"jobs": 1, "left": 2, "pending": 0, "unknown": 0, "na": 0, "stale": 2}


def test_error_is_skip_line_not_silent(tmp_path, monkeypatch):
    class _Boom:
        def clean_left_beats(self, *a):
            raise KeyError("x")
    monkeypatch.setattr(cla, "OUT", tmp_path / "out")
    cla.run(["a1b2c3"], mp=_Boom(), store=None, get_job=lambda j: {"job_id": j}, work_root=tmp_path)
    rep = (tmp_path / "out" / "report.txt").read_text(encoding="utf-8")
    assert "a1b2c3 건너뜀 KeyError" in rep and cla.parse_summary(rep)["jobs"] == 0


def test_main_writes_done_and_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(cla, "OUT", tmp_path / "out")

    def boom(*a, **k):
        raise RuntimeError("db gone")
    monkeypatch.setattr(cla, "run", boom)
    assert cla.main(["abc123"]) == 1
    assert (tmp_path / "out" / "done.txt").read_text(encoding="utf-8").startswith("CLA_DONE rc=1")
    assert "db gone" in (tmp_path / "out" / "crash.txt").read_text(encoding="utf-8")
