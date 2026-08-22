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
