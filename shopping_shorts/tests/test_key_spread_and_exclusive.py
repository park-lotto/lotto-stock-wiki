# -*- coding: utf-8 -*-
"""후보별 키 분산 + 인스타 세션 독점 가드 (2026-08-05).

배경(실측 job 9c470e54ab97): 후보 3개가 전부 keys[0]으로 나가 3초 안에 같은 키를
연타 → 분당한도(무료등급 15 RPM) 429 3연발 → 스타일 리라이트 3회 재시도가 모두
튕겨 **조용히 원본 폴백**. 사장님 화면엔 A/B/C가 스타일 없이 같은 카피체로 나왔다.
키는 18개가 살아있는데 0번만 두들긴 것.
"""
import threading

from shopping_shorts import edit_plan
from shopping_shorts.store import Store


# ── 1. 후보별 키 분산 ───────────────────────────────────────────────
def _fake_vault_call(used):
    """_vault_call과 같은 시그니처로 '어떤 키를 골랐나'만 기록하는 대역."""
    keys = [f"K{i}" for i in range(18)]

    def call(prompt, schema, max_tries=8, key_offset=0):
        ks = keys
        if key_offset:
            o = int(key_offset) % len(ks)
            ks = ks[o:] + ks[:o]
        used.append(ks[0])
        return {"ok": True}

    return call


def test_후보마다_다른_키로_나간다():
    used = []
    call = _fake_vault_call(used)
    for i in range(3):
        edit_plan._offset_call(call, edit_plan._candidate_key_offset(i))("p", None)
    assert len(set(used)) == 3, f"후보 3개가 같은 키를 쓰면 429가 난다: {used}"


def test_오프셋_없으면_같은_키_수정전_동작():
    used = []
    call = _fake_vault_call(used)
    for _ in range(3):
        call("p", None)
    assert len(set(used)) == 1      # 이게 사고의 원인이었다


def test_key_offset_못받는_call도_안죽는다():
    """테스트·다른 호출부가 넘기는 (prompt, schema)짜리 call에 무조건
    key_offset을 넘기면 TypeError로 대본 생성이 통째로 죽는다."""
    def old_style(prompt, schema):
        return {"ok": True}
    wrapped = edit_plan._offset_call(old_style, 999)
    assert wrapped("p", None) == {"ok": True}


def test_워커가_여러개여도_후보끼리_안겹친다(monkeypatch):
    """워커 3개 × 후보 3개 = 9개 호출이 keys[0]에 몰리면 안 된다."""
    slots = set()
    for pid in (100, 101, 102):
        monkeypatch.setattr(edit_plan.os, "getpid", lambda p=pid: p)
        for i in range(3):
            slots.add(edit_plan._candidate_key_offset(i) % 18)
    assert len(slots) >= 7, f"9개 호출이 7개 이상 키로 갈려야 한다: {sorted(slots)}"


# ── 2. 인스타 세션 독점 ─────────────────────────────────────────────
def test_인스타작업은_동시에_하나만(tmp_path):
    """durfill·prewarm은 인스타 브라우저 세션을 공유한다. 동시에 붙으면
    계정이 플래그된다(제품명검색 트랙 실측: 계정 2개 소실)."""
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("durfill", {"k": "1"})
    st.enqueue("prewarm", {"shortcode": "a", "customer_id": "1"})
    st.enqueue("prewarm", {"shortcode": "b", "customer_id": "2"})
    got = [st.claim_next() for _ in range(3)]
    assert len([g for g in got if g]) == 1, f"1개만 돌아야 한다: {got}"


def test_고객작업은_인스타가_돌아도_안막힌다(tmp_path):
    """★가장 중요 — 가드가 고객을 막으면 본말전도다."""
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("durfill", {"k": "1"})
    st.claim_next()                                  # 인스타 작업 실행 중
    st.enqueue("mix", {"job_id": "J1", "customer_id": "9"})
    got = st.claim_next()
    assert got and got["task"] == "mix", f"고객 mix가 즉시 집혀야 한다: {got}"


def test_인스타작업_끝나면_다음것이_풀린다(tmp_path):
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("durfill", {"k": "1"})
    st.enqueue("prewarm", {"shortcode": "a", "customer_id": "1"})
    first = st.claim_next()
    assert st.claim_next() is None                   # 도는 동안은 막힌다
    st.finish(first["id"], True)
    assert st.claim_next() is not None               # 끝나면 풀린다


def test_워커_동시claim_경합에도_하나만(tmp_path):
    """파이썬으로 먼저 세면 워커 3개가 동시에 '지금 0개'를 보고 셋 다 집는다.
    같은 UPDATE 문 안에서 검사하므로 경합에도 안전해야 한다."""
    db = str(tmp_path / "t.db")
    st = Store(db)
    for i in range(5):
        st.enqueue("prewarm", {"shortcode": f"s{i}", "customer_id": str(i)})
    got, lock = [], threading.Lock()

    def worker():
        j = Store(db).claim_next()
        with lock:
            got.append(j)

    ts = [threading.Thread(target=worker) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len([g for g in got if g]) == 1, f"경합에도 1개만: {got}"


def test_고객작업끼리는_여전히_동시실행(tmp_path):
    """회귀 확인 — 워커 N개면 서로 다른 고객 N명이 동시에 진행돼야 한다."""
    st = Store(str(tmp_path / "t.db"))
    st.enqueue("mix", {"job_id": "A", "customer_id": "1"})
    st.enqueue("render", {"job_id": "B", "customer_id": "2"})
    st.enqueue("preview", {"job_id": "C", "customer_id": "3"})
    got = [st.claim_next() for _ in range(3)]
    assert all(got), f"고객 3명은 동시에 돌아야 한다: {got}"


# ── 2026-08-31 실사고: 키를 늘려도 앞의 몇 개만 쓰고 포기했다 ────────────────

def test_오프셋은_부를때마다_달라진다():
    """★12워커가 전부 keys[0]부터 두들겼다. get_live_keys_cascade는 매번 같은
    순서를 주는데 _vault_call의 key_offset 기본값이 0이었다.
    실측 08-31: 제미니 1,825건 중 429가 816건(45%), 사유는 전부 '분당' 한도.
    키가 모자란 게 아니라 앞쪽 키에 몰린 것이었다."""
    from shopping_shorts import edit_plan
    vals = [edit_plan._auto_key_offset() for _ in range(8)]
    assert len(set(vals)) == 8, f"오프셋이 겹친다 {vals} — 같은 키에 몰린다"
    assert len({v % 10 for v in vals}) == 8, "키 10개 풀에서 서로 다른 자리여야 한다"


def test_키_시도_상한이_넉넉하다():
    """★오늘 사고의 진짜 뿌리. build_edit_plan(max_retries=4)가 그대로
    _vault_call(max_tries=4) → keys[:4]가 돼, 살아있는 키가 33개여도 **앞의 4개만**
    두들기고 포기했다. 그래서 회원 키를 넣어 풀을 11→34개로 늘려도 고객 실패가
    그대로였다(실측 job 96786f4a0e44: "키 4개를 다 돌았는데 결과 없음 — 429").
    성공하면 즉시 반환하므로 크게 잡아도 손해가 없다."""
    import inspect

    from shopping_shorts import edit_plan
    assert edit_plan._KEY_TRY_LIMIT >= 30, "키를 늘려도 앞의 몇 개만 쓰면 소용없다"
    for fn in (edit_plan.build_edit_plan, edit_plan._vault_call, edit_plan._vault_call_once):
        name = "max_retries" if fn is edit_plan.build_edit_plan else "max_tries"
        got = inspect.signature(fn).parameters[name].default
        assert got == edit_plan._KEY_TRY_LIMIT, (
            f"{fn.__name__}의 {name} 기본값이 상한과 어긋난다({got}) — "
            "한 곳에서 정해야 또 4로 돌아가지 않는다")


def test_분당한도만_대기대상이다():
    """분당은 쉬면 풀리고 일일·403은 안 풀린다. 뭉치면 전자를 후자처럼 버린다."""
    from shopping_shorts import edit_plan
    rpm = ("429 RESOURCE_EXHAUSTED Quota exceeded for quota metric "
           "'Generate Content API requests per minute'")
    assert edit_plan._is_per_minute_quota(rpm) is True
    assert edit_plan._is_per_minute_quota("429 ... requests per day") is False
    assert edit_plan._is_per_minute_quota("403 PERMISSION_DENIED") is False
