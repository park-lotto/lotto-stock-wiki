"""믹스 job이 더블클릭으로 쌍둥이가 되지 않는지 — 2026-08-19 실측 사고의 가드.

라이브에서 mix_jobs가 30ms 간격으로 **쌍으로** 생겼다(최근 7일 7쌍). 화면이 어느 쪽을
보는지 어긋나 "미리보기가 끊긴다"로 보였고, 그보다 render 크레딧이 두 번 나갔다.
"""
import time

from shopping_shorts.store import Store


def _mk(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_같은_대본_소스로_연속_생성하면_앞_job을_돌려준다(tmp_path):
    st = _mk(tmp_path)
    urls, script = ["https://x/1", "https://x/2"], "확정 대본"
    st.create_mix_job("job_a", urls, 30, "free", given_script=script, customer_id=0)
    assert st.recent_same_mix_job(0, urls, script) == "job_a"


def test_대본이_다르면_새_job이다(tmp_path):
    st = _mk(tmp_path)
    urls = ["https://x/1"]
    st.create_mix_job("job_a", urls, 30, "free", given_script="대본1", customer_id=0)
    assert st.recent_same_mix_job(0, urls, "대본2") is None


def test_소스가_다르면_새_job이다(tmp_path):
    st = _mk(tmp_path)
    st.create_mix_job("job_a", ["https://x/1"], 30, "free", given_script="s", customer_id=0)
    assert st.recent_same_mix_job(0, ["https://x/2"], "s") is None


def test_다른_고객의_job은_재사용하지_않는다(tmp_path):
    st = _mk(tmp_path)
    urls = ["https://x/1"]
    st.create_mix_job("job_a", urls, 30, "free", given_script="s", customer_id=0)
    assert st.recent_same_mix_job(7, urls, "s") is None


def test_창_밖의_오래된_job은_재사용하지_않는다(tmp_path):
    """★SQL datetime('now')로 자르려다 'T' > ' ' 문자열비교 함정에 빠질 뻔했다 —
    그러면 몇 시간 전 job도 '방금 것'으로 재사용된다. within_sec=0으로 그 경계를 지킨다."""
    st = _mk(tmp_path)
    urls = ["https://x/1"]
    st.create_mix_job("job_a", urls, 30, "free", given_script="s", customer_id=0)
    time.sleep(1.1)
    assert st.recent_same_mix_job(0, urls, "s", within_sec=0) is None
    assert st.recent_same_mix_job(0, urls, "s", within_sec=60) == "job_a"


def test_대본_없는_job도_짝이_맞는다(tmp_path):
    """given_script는 빈 값이면 NULL로 저장된다 — IFNULL 처리가 빠지면 여기서 샌다."""
    st = _mk(tmp_path)
    urls = ["https://x/1"]
    st.create_mix_job("job_a", urls, 30, "free", given_script=None, customer_id=0)
    assert st.recent_same_mix_job(0, urls, "") == "job_a"
