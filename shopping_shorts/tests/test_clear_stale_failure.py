"""자막제거가 성공하면 **옛 실패 표시**를 지운다 (2026-08-31 실사고).

전진원님 job: 오전 렌더가 VMake 키 오류로 실패 → 21:55 자막제거는 성공(172초)했는데
화면엔 오전 문구가 그대로 떠 "❌ 매칭 실패"로 보였다. 고객은 최종 렌더를 안 눌렀다.
"""
from shopping_shorts import mix_pipeline as MP
from shopping_shorts.store import Store


def _store(tmp_path):
    return Store(tmp_path / "t.db")


def _job(store, jid, status, error, beats=True):
    store.create_mix_job(jid, ["u0"], 20, "free")
    store.update_mix_job(jid, status=status, error=error,
                         edit_plan={"beats": [{"beat_idx": 0, "narration": "가"}]} if beats
                         else {})


def test_실패로_남은_job의_옛_에러를_지운다(tmp_path):
    st = _store(tmp_path)
    _job(st, "j1", "failed", "[10021] sign not equals client")
    MP._clear_stale_failure(st, "j1")
    j = st.get_mix_job("j1")
    assert j["status"] == "ready_for_review"
    assert not j["error"]


def test_실패가_아니면_건드리지_않는다(tmp_path):
    """진행 중이거나 이미 끝난 job의 상태를 되돌리면 파이프라인이 꼬인다."""
    st = _store(tmp_path)
    for status in ("rendering", "done", "ready_for_review"):
        _job(st, "j_" + status, status, None)
        MP._clear_stale_failure(st, "j_" + status)
        assert st.get_mix_job("j_" + status)["status"] == status


def test_편성이_없으면_되돌리지_않는다(tmp_path):
    """편성 전에 죽은 job은 'ready_for_review'로 부를 수 없다 — 그대로 둔다."""
    st = _store(tmp_path)
    _job(st, "j2", "failed", "소스 다운로드 실패", beats=False)
    MP._clear_stale_failure(st, "j2")
    j = st.get_mix_job("j2")
    assert j["status"] == "failed" and j["error"] == "소스 다운로드 실패"


def test_없는_job이면_조용히_넘어간다(tmp_path):
    MP._clear_stale_failure(_store(tmp_path), "없는job")
