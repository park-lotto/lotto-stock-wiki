# -*- coding: utf-8 -*-
"""tools/disk_janitor.py plan() — 지울 것과 절대 지우면 안 되는 것(관제 038)."""
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import disk_janitor as dj  # noqa: E402

DAY = 86400


def _mk(p: Path, age_days: float, now: float, size=10):
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.suffix:
        p.write_bytes(b"x" * size)
    else:
        p.mkdir(exist_ok=True)
        (p / "f.bin").write_bytes(b"x" * size)
    t = now - age_days * DAY
    os.utime(p, (t, t))
    return p


def _iso(now, age_days):
    import datetime as dt
    return dt.datetime.fromtimestamp(now - age_days * DAY, dt.timezone.utc).isoformat()


@pytest.fixture
def world(tmp_path):
    now = time.time()
    d = tmp_path / "data"
    # A
    _mk(d / "find_frames" / "old", 2, now)
    _mk(d / "find_frames" / "fresh", 0.5, now)
    # B
    _mk(d / "yt_relay" / "done_old.mp4", 2, now)
    _mk(d / "yt_relay" / "done_fresh.mp4", 0.5, now)
    _mk(d / "yt_relay" / "pending_old.mp4", 30, now)
    _mk(d / "yt_relay" / "unknown_old.mp4", 8, now)
    _mk(d / "yt_relay" / "unknown_new.mp4", 3, now)
    # C
    _mk(d / "mix_jobs" / "failed_old", 2, now)
    _mk(d / "mix_jobs" / "failed_fresh", 0.2, now)
    _mk(d / "mix_jobs" / "0123456789ab", 2, now)        # 고아(job_id 꼴)
    _mk(d / "mix_jobs" / "orphan_fresh", 0.2, now)
    _mk(d / "mix_jobs" / "_scene_style_lab", 90, now)   # 랩 폴더 — job_id 꼴 아님, 절대 안 지움
    _mk(d / "mix_jobs" / "b1test5ec16a", 90, now)
    # D — done 8일: 조각 셋은 지우고 나머지는 남긴다
    j = d / "mix_jobs" / "done_old"
    for name in ("pvproxy", "capcut", "seg_thumbs", "s0", "s1", "join0", "tts"):
        _mk(j / name, 8, now)
    for f in ("final.mp4", "preview.mp4", "clean_preview.mp4", "final_nocta.mp4", "edit_plan.json"):
        _mk(j / f, 8, now)
    # done 3일 — 아직 아무것도 안 지운다
    _mk(d / "mix_jobs" / "done_new" / "pvproxy", 3, now)
    # 미완(ready_for_review) 60일 — 절대 안 지운다
    _mk(d / "mix_jobs" / "review_old" / "pvproxy", 60, now)
    jobs = {
        "failed_old": ("failed", _iso(now, 2)), "failed_fresh": ("failed", _iso(now, 0.2)),
        "done_old": ("done", _iso(now, 8)), "done_new": ("done", _iso(now, 3)),
        "review_old": ("ready_for_review", _iso(now, 60)),
    }
    relay = {"done_old.mp4": "done", "done_fresh.mp4": "done", "pending_old.mp4": "pending"}
    return d, jobs, relay, now


def _rel(d, cands):
    return sorted(str(c.path.relative_to(d)).replace(os.sep, "/") for c in cands)


def test_plan_picks_exactly_the_regenerable_and_finished(world):
    d, jobs, relay, now = world
    got = _rel(d, dj.plan(d, jobs, relay, now=now))
    assert got == sorted([
        "find_frames/old",
        "yt_relay/done_old.mp4", "yt_relay/unknown_old.mp4",
        "mix_jobs/failed_old", "mix_jobs/0123456789ab",
        "mix_jobs/done_old/pvproxy", "mix_jobs/done_old/capcut", "mix_jobs/done_old/seg_thumbs",
    ])


def test_plan_never_touches_customer_data(world):
    d, jobs, relay, now = world
    got = set(_rel(d, dj.plan(d, jobs, relay, now=now)))
    for keep in ("mix_jobs/done_old/s0", "mix_jobs/done_old/join0", "mix_jobs/done_old/final.mp4",
                 "mix_jobs/done_old/clean_preview.mp4", "mix_jobs/done_old/tts", "mix_jobs/review_old",
                 "mix_jobs/review_old/pvproxy", "mix_jobs/done_new/pvproxy", "yt_relay/pending_old.mp4",
                 "find_frames/fresh", "mix_jobs/failed_fresh", "mix_jobs/orphan_fresh",
                 "mix_jobs/_scene_style_lab", "mix_jobs/b1test5ec16a"):
        assert keep not in got, keep


def test_apply_removes_and_reports_size(world):
    d, jobs, relay, now = world
    cands = dj.plan(d, jobs, relay, now=now)
    total = sum(c.size for c in cands)
    freed, errors = dj.apply(cands)
    assert errors == []
    assert freed == total > 0
    assert not (d / "mix_jobs" / "done_old" / "pvproxy").exists()
    assert (d / "mix_jobs" / "done_old" / "final.mp4").exists()
    assert (d / "mix_jobs" / "review_old" / "pvproxy").exists()


def test_rules_summary_groups_by_rule(world):
    d, jobs, relay, now = world
    s = dj.summarize(dj.plan(d, jobs, relay, now=now))
    assert s.startswith("A ") and "합계 8개" in s
