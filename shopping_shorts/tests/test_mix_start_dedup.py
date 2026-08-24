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


# ── 2026-08-24: 위 조회형 가드가 **경쟁 상태에서 뚫렸다** ──────────────────────
# 실측(cid=57, 김용덕): 08-23 2쌍 · 08-24 5쌍. render 크레딧 10회가 나갔는데 실제 영상은 5개.
# 뿌리는 "조회 → (과금) → 기록" 순서다 — 0.03~0.17초 차이로 들어온 두 요청이 **둘 다**
# 조회를 통과했다(그 시점엔 상대가 아직 mix_jobs에 없다). 그래서 판단을 조회가 아니라
# **INSERT 성공 여부**(claim_mix_request)로 옮겼다.


def test_동시에_들어온_같은_요청은_딱_하나만_이긴다(tmp_path):
    """★핵심 회귀 테스트. 조회형 가드는 여기서 반드시 깨진다(둘 다 통과)."""
    import threading

    db = str(tmp_path / "t.db")
    Store(db)                                   # 스키마 먼저 만든다
    urls, script = ["https://x/1", "https://x/2"], "확정 대본"
    n = 8
    barrier = threading.Barrier(n)
    won_flags, lock = [], threading.Lock()

    def one(i):
        st = Store(db)
        barrier.wait()                          # n개가 같은 순간 출발
        fp, won, _ = st.claim_mix_request(50, urls, script)
        if won:
            time.sleep(0.15)                    # 실제 코드의 과금 구간을 흉내낸다
            st.attach_mix_claim(fp, "job%d" % i)
        with lock:
            won_flags.append(won)

    ts = [threading.Thread(target=one, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert sum(won_flags) == 1, "과금이 %d번 일어난다" % sum(won_flags)


def test_진_요청은_이긴_쪽의_job을_받는다(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    urls, script = ["https://x/1"], "s"
    fp1, won1, _ = st.claim_mix_request(50, urls, script)
    assert won1
    fp2, won2, _ = st.claim_mix_request(50, urls, script)
    assert not won2 and fp2 == fp1
    st.attach_mix_claim(fp1, "job_a")
    assert st.get_mix_claim_job(fp2) == "job_a"


def test_과금이_거절되면_같은_요청을_다시_보낼_수_있다(tmp_path):
    """release를 빼먹으면 그 고객은 30초 동안 같은 대본으로 **재시도조차 못 한다**."""
    st = Store(str(tmp_path / "t.db"))
    urls, script = ["https://x/1"], "s"
    fp, won, _ = st.claim_mix_request(50, urls, script)
    assert won
    st.release_mix_claim(fp)
    _, won2, _ = st.claim_mix_request(50, urls, script)
    assert won2


def test_job이_붙은_선점표는_release로_지워지지_않는다(tmp_path):
    """이미 접수돼 파이프라인이 도는 job의 선점표를 지우면 중복이 다시 열린다."""
    st = Store(str(tmp_path / "t.db"))
    urls, script = ["https://x/1"], "s"
    fp, _, _ = st.claim_mix_request(50, urls, script)
    st.attach_mix_claim(fp, "job_a")
    st.release_mix_claim(fp)
    assert st.get_mix_claim_job(fp) == "job_a"


def test_다른_고객_다른_대본은_서로_막지_않는다(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    urls = ["https://x/1"]
    assert st.claim_mix_request(50, urls, "대본A")[1]
    assert st.claim_mix_request(50, urls, "대본B")[1]
    assert st.claim_mix_request(51, urls, "대본A")[1]


def test_창_밖의_오래된_선점표는_새_요청을_막지_않는다(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    urls, script = ["https://x/1"], "s"
    assert st.claim_mix_request(50, urls, script, within_sec=30)[1]
    time.sleep(0.2)
    assert st.claim_mix_request(50, urls, script, within_sec=0.1)[1]
