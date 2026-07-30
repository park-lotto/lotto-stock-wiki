"""렌더 중 자동크롤 양보(2026-07-30).

배경(실측): 최종렌더 8분+ 제보 → 서버 13:21 load average 11.76 / swap 1204MB,
ffmpeg(67.8% CPU)와 Playwright(20.5% CPU·7.4% MEM)가 동시 실행. 렌더가 고장난 게
아니라 자원을 다투다 기어갔다. 그래서 자동크롤이 렌더에 순서를 양보한다.

여기서 못 박는 것: 판정이 렌더 계열만 보고(크롤끼리는 안 막는다), queued까지 세고,
자동크롤 진입점 3개가 실제로 그 판정을 부른다(호출부 누락이면 효과 0).
"""
import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_idle_queue_is_not_busy(store):
    assert store.heavy_job_active() is False


@pytest.mark.parametrize("task", ["render", "mix", "retype", "preview", "clean"])
def test_running_heavy_task_blocks(store, task):
    store.enqueue(task, {"job_id": "j1"})
    assert store.heavy_job_active() is True          # queued 상태부터 막는다


def test_queued_counts_too(store):
    """곧 시작할 렌더 앞에서 크롤이 자리를 잡으면 렌더가 그만큼 밀린다."""
    store.enqueue("render", {"job_id": "j2"})
    assert store.heavy_job_active() is True


def test_non_heavy_tasks_do_not_block(store):
    """크롤·예열끼리는 서로 막지 않는다(렌더만 보호 대상)."""
    store.enqueue("overseas", {})
    store.enqueue("prewarm", {"shortcode": "a"})
    assert store.heavy_job_active() is False


def test_done_task_does_not_block(store):
    with store._conn() as c:
        c.execute("INSERT INTO job_queue(task,args_json,state,created_at) "
                  "VALUES('render','{}','done',datetime('now'))")
    assert store.heavy_job_active() is False


@pytest.mark.parametrize("mod", [
    "scripts.daily_instagram_collect",
    "scripts.daily_instagram_discover",
    "scripts.daily_youtube_collect",
])
def test_auto_crawl_entrypoints_call_the_gate(mod):
    """호출부 누락 방지 — 소스에 heavy_job_active가 있어야 한다.
    (실제 크롤을 태우지 않고 배선만 확인 — 크롤은 네트워크·브라우저라 단위테스트 불가.)"""
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / (mod.replace(".", "/") + ".py")
    src = path.read_text(encoding="utf-8")
    assert "heavy_job_active" in src, f"{mod}에 렌더 양보 가드가 없다"


def test_bg_loops_call_the_gate():
    """app.py의 백그라운드 발굴 루프 2개(xhs·ig)도 가드를 부른다."""
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert src.count("heavy_job_active") >= 2
