"""디스크 자동 정리 — 완성본은 살고 재료만 죽는지 고정한다(2026-08-22).

이 테스트가 지키는 것은 하나다: **고객의 결과물을 지우지 않는다.**
용량을 아끼려다 완성본을 날리면 아낀 것보다 잃는 게 크다.
"""
import os
import time

import pytest

from shopping_shorts import disk_cleanup


class _FakeStore:
    """job_id → status. get_mix_job만 흉내 낸다(정리가 쓰는 유일한 API)."""

    def __init__(self, rows):
        self._rows = rows

    def get_mix_job(self, job_id):
        return self._rows.get(job_id)


def _make_job(root, job_id, *, age_days, status="done", with_final=True):
    d = root / "mix_jobs" / job_id
    (d / "s0").mkdir(parents=True)
    (d / "s0" / "clip.mp4").write_bytes(b"x" * 1000)
    (d / "seg_thumbs").mkdir()
    (d / "seg_thumbs" / "t.png").write_bytes(b"y" * 500)
    (d / "scripts").mkdir()                      # s로 시작하지만 재료가 아니다
    (d / "scripts" / "keep.txt").write_bytes(b"z" * 10)
    if with_final:
        (d / "final.mp4").write_bytes(b"F" * 2000)
        (d / "preview.mp4").write_bytes(b"P" * 300)
    old = time.time() - age_days * 86400
    os.utime(d, (old, old))
    return d


@pytest.fixture()
def data_dir(tmp_path):
    (tmp_path / "mix_jobs").mkdir()
    return tmp_path


def test_completed_video_and_preview_survive(data_dir):
    """무엇을 지우든 완성본과 미리보기는 살아 있어야 한다."""
    d = _make_job(data_dir, "old1", age_days=30)
    store = _FakeStore({"old1": {"status": "done"}})
    disk_cleanup.clean_mix_jobs(data_dir, store=store)
    assert (d / "final.mp4").exists(), "완성본이 지워졌다 — 고객 결과물 유실"
    assert (d / "preview.mp4").exists()


def test_old_source_material_is_removed(data_dir):
    """오래된 완료 작업의 소스 클립·중간 산출물은 지운다(용량의 대부분)."""
    d = _make_job(data_dir, "old2", age_days=30)
    store = _FakeStore({"old2": {"status": "done"}})
    freed, dirs = disk_cleanup.clean_mix_jobs(data_dir, store=store)
    assert not (d / "s0").exists()
    assert not (d / "seg_thumbs").exists()
    assert dirs == 2 and freed >= 1500


def test_unknown_folder_name_is_kept(data_dir):
    """이름을 모르는 폴더는 남긴다 — 's'로 시작한다고 지우면 scripts가 날아간다."""
    d = _make_job(data_dir, "old3", age_days=30)
    disk_cleanup.clean_mix_jobs(data_dir, store=_FakeStore({"old3": {"status": "done"}}))
    assert (d / "scripts" / "keep.txt").exists()


def test_recent_job_is_untouched(data_dir):
    """보관 기간 안(기본 14일)이면 재료도 그대로 — 고객이 다시 편집할 수 있다."""
    d = _make_job(data_dir, "fresh", age_days=3)
    disk_cleanup.clean_mix_jobs(data_dir, store=_FakeStore({"fresh": {"status": "done"}}))
    assert (d / "s0" / "clip.mp4").exists()


def test_running_job_is_untouched_even_when_old(data_dir):
    """진행 중이면 오래됐어도 손대지 않는다 — 렌더 도중 재료를 빼면 그 작업이 깨진다."""
    d = _make_job(data_dir, "running", age_days=60)
    store = _FakeStore({"running": {"status": "rendering"}})
    disk_cleanup.clean_mix_jobs(data_dir, store=store)
    assert (d / "s0" / "clip.mp4").exists()


def test_dry_run_deletes_nothing_but_reports(data_dir):
    """모의 실행은 크기만 세고 하나도 지우지 않는다."""
    d = _make_job(data_dir, "old4", age_days=30)
    freed, dirs = disk_cleanup.clean_mix_jobs(
        data_dir, store=_FakeStore({"old4": {"status": "done"}}), dry_run=True)
    assert freed > 0 and dirs == 2
    assert (d / "s0" / "clip.mp4").exists()


def test_thumb_cache_trims_oldest_first_to_limit(data_dir):
    """캐시는 나이가 아니라 총량으로 자른다 — 오래 안 쓴 것부터."""
    cache = data_dir / "thumb_cache"
    cache.mkdir()
    for i in range(10):
        p = cache / f"{i}.png"
        p.write_bytes(b"a" * 1024 * 100)         # 100KB × 10 = 1MB
        t = time.time() - (10 - i) * 86400       # 0번이 가장 오래됨
        os.utime(p, (t, t))
    freed, removed = disk_cleanup.trim_thumb_cache(data_dir, max_gb=0.0005)  # ≈512KB
    assert removed >= 4 and freed > 0
    assert not (cache / "0.png").exists(), "가장 오래된 것부터 지워야 한다"
    assert (cache / "9.png").exists(), "최근 것은 남아야 한다"


def test_thumb_cache_under_limit_is_untouched(data_dir):
    cache = data_dir / "thumb_cache"
    cache.mkdir()
    (cache / "a.png").write_bytes(b"a" * 1000)
    assert disk_cleanup.trim_thumb_cache(data_dir, max_gb=1) == (0, 0)
    assert (cache / "a.png").exists()


def test_run_returns_readable_summary(data_dir):
    _make_job(data_dir, "old5", age_days=30)
    msg = disk_cleanup.run(data_dir, store=_FakeStore({"old5": {"status": "done"}}),
                           dry_run=True)
    assert "디스크정리[모의]" in msg and "GB" in msg


# ── 완성 영상 보관 기간(2026-09-07 사장님 확정 7일) ─────────────────────
# 위 테스트들이 "재료 정리는 완성본을 안 건드린다"를 고정한다면, 아래는 그 반대편이다:
# **별도 함수**(clean_final_videos)만이, **자기 보관 기간이 지난** 영상을 지운다.
# 두 기간이 다르다는 것 자체가 규칙이므로 그것도 함께 고정한다.

def _age_file(path, days):
    old = time.time() - days * 86400
    os.utime(path, (old, old))


def test_final_video_deleted_after_keep_days(data_dir):
    """보관 기간이 지난 완성 영상은 지워진다 — 썸네일은 남는다."""
    d = _make_job(data_dir, "old_v", age_days=30)
    (d / "thumb.png").write_bytes(b"T" * 100)
    for n in ("final.mp4", "preview.mp4", "thumb.png"):
        _age_file(d / n, 30)
    store = _FakeStore({"old_v": {"status": "done"}})
    freed, removed = disk_cleanup.clean_final_videos(data_dir, store=store)
    assert not (d / "final.mp4").exists(), "보관 기간이 지난 완성본이 안 지워졌다"
    assert not (d / "preview.mp4").exists()
    assert (d / "thumb.png").exists(), "썸네일까지 지우면 목록 카드가 깨진다"
    assert removed == 2 and freed == 2300


def test_final_video_within_keep_days_survives(data_dir):
    """보관 기간 안이면 손대지 않는다."""
    d = _make_job(data_dir, "new_v", age_days=30)   # 폴더는 오래됐지만
    _age_file(d / "final.mp4", 1)                   # 영상은 어제 만든 것
    _age_file(d / "preview.mp4", 1)
    store = _FakeStore({"new_v": {"status": "done"}})
    assert disk_cleanup.clean_final_videos(data_dir, store=store) == (0, 0)
    assert (d / "final.mp4").exists()


def test_final_video_of_running_job_survives(data_dir):
    """진행 중인 작업의 영상은 나이와 무관하게 남긴다 — 렌더 중 파일을 빼면 깨진다."""
    d = _make_job(data_dir, "busy", age_days=30)
    _age_file(d / "final.mp4", 30)
    store = _FakeStore({"busy": {"status": "rendering"}})
    assert disk_cleanup.clean_final_videos(data_dir, store=store) == (0, 0)
    assert (d / "final.mp4").exists()


def test_final_keep_days_differs_from_material_retention():
    """영상 7일 / 재료 14일 — 두 기간을 하나로 합치면 안 된다(합치면 이 줄이 깨진다)."""
    assert disk_cleanup.FINAL_KEEP_DAYS == 7
    assert disk_cleanup.RETENTION_DAYS == 14


def test_material_cleanup_still_never_touches_video(data_dir):
    """재료 정리는 영상 보관 기간이 지난 뒤에도 영상에 손대지 않는다(역할 분리)."""
    d = _make_job(data_dir, "old_m", age_days=30)
    _age_file(d / "final.mp4", 30)
    store = _FakeStore({"old_m": {"status": "done"}})
    disk_cleanup.clean_mix_jobs(data_dir, store=store)
    assert (d / "final.mp4").exists(), "영상 삭제는 clean_final_videos만 해야 한다"
    assert not (d / "s0").exists(), "재료는 지워졌어야 한다"
