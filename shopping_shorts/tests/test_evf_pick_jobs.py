# -*- coding: utf-8 -*-
"""영상 관문 비교 대상 선정(2026-10-01 관제 067): 완성본 파일이 최근(3일) 것인 작업만, 최신순 n개."""
import importlib.util, sqlite3, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("evf", ROOT / "tools" / "editor_vs_final_video.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_pick_jobs_keeps_recent_finals_only():
    m = _load()
    con = sqlite3.connect(":memory:")
    con.execute("create table mix_jobs(job_id text, video_path text, preview_status text, updated_at text)")
    now = 1_000_000.0
    rows = [("new1", "/v/new1.mp4", "ready", "2026-10-01T12:00"),
            ("old1", "/v/old1.mp4", "ready", "2026-10-01T11:00"),   # 행은 오늘, 완성본은 열흘 전
            ("new2", "/v/new2.mp4", "ready", "2026-10-01T10:00"),
            ("nopv", "/v/nopv.mp4", "", "2026-10-01T09:00"),         # 미리보기 없음 → 후보 아님
            ("gone", "/v/gone.mp4", "ready", "2026-10-01T08:00")]    # 파일 없음 → 건너뜀
    con.executemany("insert into mix_jobs values (?,?,?,?)", rows)
    mt = {"/v/new1.mp4": now - 3600, "/v/old1.mp4": now - 10 * 86400, "/v/new2.mp4": now - 2 * 86400}
    def mtime(p):
        if p not in mt: raise OSError(p)
        return mt[p]
    assert m._pick_jobs(con, 6, now=now, mtime=mtime) == ["new1", "new2"]
    assert m._pick_jobs(con, 1, now=now, mtime=mtime) == ["new1"]
