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
