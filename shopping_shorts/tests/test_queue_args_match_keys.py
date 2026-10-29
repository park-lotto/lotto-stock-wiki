"""관제 286: 자막제거 큐에 동의 표식이 붙어도 화면 판정이 그 작업을 찾는다."""
from shopping_shorts.store import Store


def test_clean_with_consent_args_is_found_and_alive(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.enqueue("clean", {"job_id": "abc", "confirm_clean": True, "confirm_secs": 43.53})
    assert s.queue_status("clean", {"job_id": "abc"}) is not None
    assert s.task_is_alive("clean", {"job_id": "abc"}) is True      # queued = 살아 있음
    assert s.queue_status("clean", {"job_id": "zzz"}) is None


def test_exact_args_still_match(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.enqueue("ai_scene", {"job_id": "j", "beat_idx": 2})
    assert s.task_is_alive("ai_scene", {"job_id": "j", "beat_idx": 2}) is True
    assert s.task_is_alive("ai_scene", {"job_id": "j", "beat_idx": 3}) is False
