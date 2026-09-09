# -*- coding: utf-8 -*-
"""청소본 신선도는 **서명**으로만 본다 — 파일 시각으로 보지 않는다 (2026-09-02).

사장님 제보: "자막제거는 완료라고 뜨는데 장면꾸미기에서 자막이 보여."
실측(이유준님 job 210a0c33c32d): 지금 편성 청소본 17:54:28 vs clean_preview.mp4
17:44:46 → 어제(09-01) 넣은 mtime 조건이 False가 돼 꾸미기가 원본으로 떨어졌다.
편성을 바꿔 재청소하면 새 청소본이 늘 더 새것이라 **항상** 이 창에 걸린다.
"""
import json

import pytest

from shopping_shorts import mix_pipeline as mp


@pytest.fixture()
def job_and_work(tmp_path):
    plan = {"beats": [{"beat_idx": 0, "target_seconds": 3,
                       "segments": [{"video_id": "s0", "start": 0, "end": 3}]}]}
    job = {"edit_plan": plan, "clean_status": "ready",
           "clean_video_path": str(tmp_path / "clean_preview.mp4")}
    (tmp_path / "clean_preview.mp4").write_bytes(b"x" * 2048)
    return job, tmp_path


def _sig_file(job, work, size=2048):
    sig = mp._plan_signature(job["edit_plan"])
    f = work / f"final_clean_{sig}.mp4"
    f.write_bytes(b"y" * size)
    return f


def test_서명파일이_있으면_신선하다(job_and_work):
    job, work = job_and_work
    assert mp.clean_final_matches_plan(job, work) is False   # 아직 청소 안 함
    _sig_file(job, work)
    assert mp.clean_final_matches_plan(job, work) is True


def test_재청소가_더_새것이어도_신선하다(job_and_work):
    """★이게 이번 버그다 — 새 청소본이 clean_preview보다 새것이라고 원본으로 떨어지면 안 된다."""
    import os
    import time
    job, work = job_and_work
    f = _sig_file(job, work)
    old = time.time() - 600
    os.utime(work / "clean_preview.mp4", (old, old))          # 조립본은 10분 전 것
    assert f.stat().st_mtime > (work / "clean_preview.mp4").stat().st_mtime
    assert mp.clean_final_matches_plan(job, work) is True


def test_편성이_바뀌면_신선하지_않다(job_and_work):
    job, work = job_and_work
    _sig_file(job, work)
    job["edit_plan"]["beats"][0]["target_seconds"] = 9        # 편성 변경 → 서명 변경
    assert mp.clean_final_matches_plan(job, work) is False


def test_경로도_함께_준다(job_and_work):
    """판정만 고치고 출처를 그대로 두면 옛 편성 그림이 뜬다 — 판정과 출처는 짝이다."""
    job, work = job_and_work
    assert mp.clean_final_path_for_plan(job, work) is None
    f = _sig_file(job, work)
    assert mp.clean_final_path_for_plan(job, work) == f


def test_소스별청소본은_종전대로(job_and_work):
    job, work = job_and_work
    job["clean_sources"] = {"s0": "/tmp/s0_clean.mp4"}
    assert mp.clean_final_matches_plan(job, work) is True     # 좌표계가 원본과 같다


# ── 원본으로 떨어지지 않는다 (2026-09-02 사장님 "원본 자막이 남아있지 않게 하면 되지") ──

def test_지금편성_청소본이_없으면_옛_청소본이라도_쓴다(job_and_work):
    """장면이 조금 어긋나는 것보다 자막이 보이는 것이 훨씬 나쁘다 — 고객은 그걸
    '자막제거가 안 됐다'로 읽는다(같은 제보 3번: 08-27·09-01·09-02)."""
    job, work = job_and_work
    (work / "final_clean_옛편성서명.mp4").write_bytes(b"z" * 4096)
    assert mp.clean_final_path_for_plan(job, work) is None        # 지금 편성 것은 없다
    alt = mp.clean_any_final_path(job, work)
    assert alt is not None and alt.name.startswith("final_clean_")


def test_청소본이_하나도_없으면_None(job_and_work):
    """자막제거를 안 한 작업 — 그때만 원본이 맞다."""
    job, work = job_and_work
    (work / "clean_preview.mp4").unlink()
    job["clean_video_path"] = str(work / "clean_preview.mp4")
    assert mp.clean_any_final_path(job, work) is None


def test_여러개면_가장_최근_청소본(job_and_work):
    import os
    import time
    job, work = job_and_work
    old = work / "final_clean_옛것.mp4"
    new = work / "final_clean_새것.mp4"
    old.write_bytes(b"a" * 4096)
    new.write_bytes(b"b" * 4096)
    t = time.time()
    os.utime(old, (t - 600, t - 600))
    os.utime(new, (t, t))
    assert mp.clean_any_final_path(job, work) == new
