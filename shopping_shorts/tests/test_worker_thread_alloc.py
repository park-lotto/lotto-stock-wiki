"""워커 수 ↔ ffmpeg 스레드 상한 정합 (2026-08-27).

왜 이 테스트가 있나: 워커 개수를 정하는 곳(deploy/worker_autoscale.sh, SHORTS_WORKERS)과
그걸 읽어 스레드를 나누는 곳(video_assemble._default_ffmpeg_threads)이 **다른 이름**을
봤다. 서버 env엔 SHORTS_WORKERS만 있어서, 워커가 8개인데 코드는 계속 3개인 줄 알고
스레드를 산정했다. 이름이 다시 갈리면 여기서 잡는다.
"""
import os
import pytest

from shopping_shorts import video_assemble as va


@pytest.fixture
def clean_env(monkeypatch):
    for k in ("SHORTS_WORKERS", "WORKER_COUNT", "FFMPEG_THREADS"):
        monkeypatch.delenv(k, raising=False)
    return monkeypatch


def test_reads_shorts_workers_the_autoscaler_sets(clean_env):
    """★핵심 회귀: 자동조정 스크립트가 쓰는 이름을 그대로 읽어야 한다."""
    clean_env.setenv("SHORTS_WORKERS", "8")
    assert va._worker_count() == 8


def test_shorts_workers_wins_over_old_name(clean_env):
    """두 이름이 다 있으면 실제로 워커를 띄우는 쪽(SHORTS_WORKERS)이 이긴다."""
    clean_env.setenv("SHORTS_WORKERS", "8")
    clean_env.setenv("WORKER_COUNT", "3")
    assert va._worker_count() == 8


def test_old_name_still_works(clean_env):
    """하위호환 — 옛 이름만 있어도 동작한다."""
    clean_env.setenv("WORKER_COUNT", "5")
    assert va._worker_count() == 5


def test_auto_matches_autoscaler_policy(clean_env, monkeypatch):
    """env가 없을 때의 자동값은 worker_autoscale.sh와 같아야 한다(코어-2, 3~6)."""
    for cores, expect in [(2, 3), (4, 3), (5, 3), (8, 6), (16, 6)]:
        monkeypatch.setattr(os, "cpu_count", lambda c=cores: c)
        assert va._worker_count() == expect, f"{cores}코어에서 {expect} 기대"


def test_typo_falls_back_not_crash(clean_env):
    """오타를 넣어도 죽지 않고 자동계산으로 내려간다."""
    clean_env.setenv("SHORTS_WORKERS", "여덟개")
    assert va._worker_count() >= 3


def test_upper_bound_matches_script(clean_env):
    """스크립트의 안전선(1~12)과 같은 상한."""
    clean_env.setenv("SHORTS_WORKERS", "99")
    assert va._worker_count() == 12


def test_threads_shrink_as_workers_grow(clean_env, monkeypatch):
    """워커가 늘면 인코딩 하나가 잡는 스레드는 줄어야 한다(서로 굶기지 않게)."""
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    clean_env.setenv("SHORTS_WORKERS", "2")
    few = va._default_ffmpeg_threads()
    clean_env.setenv("SHORTS_WORKERS", "8")
    many = va._default_ffmpeg_threads()
    assert few > many, f"워커 2개={few} 8개={many} — 늘었는데 안 줄었다"


def test_four_workers_on_eight_cores_is_exactly_saturated(clean_env, monkeypatch):
    """8코어/4워커면 총 요구가 코어와 정확히 맞는다 — 과점유 판단의 기준점."""
    monkeypatch.setattr(os, "cpu_count", lambda: 8)
    clean_env.setenv("SHORTS_WORKERS", "4")
    assert va._worker_count() * va._default_ffmpeg_threads() == 8
