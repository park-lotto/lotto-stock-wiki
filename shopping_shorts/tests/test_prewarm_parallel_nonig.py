# -*- coding: utf-8 -*-
"""소스 추가가 "나중에 한꺼번에" 반영되던 것 (2026-09-02 고객 제보).

증상: 소스를 5개 담으면 하나씩 몇 분 뒤 우르르 붙는다.
실측(reference.db job_queue): 담긴 순서대로 대기 72초 → 536초(9분)까지 계단식.
그런데 **워커는 놀고 있었다** — 25분 구간 총 점유 2,404초(워커 12개 = 용량 18,000초).

★뿌리: `_EXCLUSIVE_TASKS`가 prewarm을 **통째로 동시 1개**로 묶었다. 이유는 인스타
  세션 보호(2026-08-05 계정 2개 소실 사고)인데, 최근 200건 중 인스타는 72건(36%)뿐이고
  나머지 128건(64%)은 틱톡·샤오홍슈·유튜브라 인스타 세션과 아무 상관이 없었다.

계약:
  ① 인스타는 **여전히 동시 하나** — 계정은 IP보다 비싸다(느린 건 고쳐도 죽은 계정은 못 살린다)
  ② 확실한 비인스타(화이트리스트)는 병렬로 나간다
  ③ 모르는 것은 종전처럼 직렬 — 의심스러우면 직렬이 정답
"""
import json

from shopping_shorts.store import Store


def _mk(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _add(st, url, task="prewarm", owner=None):
    st.enqueue(task, {"shortcode": url[-8:], "url": url, "customer_id": owner or "9"})


def test_인스타는_여전히_하나씩만(tmp_path):
    """★이게 깨지면 계정이 죽는다 — 가장 중요한 계약."""
    st = _mk(tmp_path)
    _add(st, "https://www.instagram.com/reel/AAA1/")
    _add(st, "https://www.instagram.com/reel/BBB2/")
    assert st.claim_next() is not None          # 하나는 집는다
    assert st.claim_next() is None, "인스타 두 건이 동시에 나갔다 — 계정이 플래그된다"


def test_비인스타는_병렬로_나간다(tmp_path):
    """틱톡·샤오홍슈는 인스타 세션을 안 쓴다 — 줄 설 이유가 없다."""
    st = _mk(tmp_path)
    _add(st, "https://www.tiktok.com/@a/video/111")
    _add(st, "https://www.xiaohongshu.com/explore/222")
    _add(st, "https://www.youtube.com/shorts/333")
    got = [st.claim_next() for _ in range(3)]
    assert all(g is not None for g in got), f"비인스타가 줄을 섰다: {got}"


def test_인스타가_도는중에도_비인스타는_나간다(tmp_path):
    """제보의 그 상황 — 인스타 한 건이 오래 걸려도 나머지가 굶으면 안 된다."""
    st = _mk(tmp_path)
    _add(st, "https://www.instagram.com/reel/AAA1/")
    _add(st, "https://www.tiktok.com/@a/video/111")
    assert st.claim_next() is not None          # 인스타가 먼저 (FIFO)
    assert st.claim_next() is not None, "인스타가 도는 동안 틱톡까지 막혔다"


def test_모르는_주소는_종전처럼_직렬(tmp_path):
    """화이트리스트에 없으면 인스타일 수 있다 — 의심스러우면 직렬."""
    st = _mk(tmp_path)
    _add(st, "https://example.com/unknown/1")
    _add(st, "https://example.com/unknown/2")
    assert st.claim_next() is not None
    assert st.claim_next() is None, "모르는 주소를 병렬로 내보냈다"


def test_인스타_글자가_섞인_틱톡은_직렬(tmp_path):
    """캡션에 'instagram'이 섞였을 수 있다 — 그런 건 안전하게 직렬로 둔다."""
    st = _mk(tmp_path)
    st.enqueue("prewarm", {"shortcode": "t1", "url": "https://www.tiktok.com/@a/video/1",
                           "caption": "follow me on instagram!", "customer_id": "9"})
    st.enqueue("prewarm", {"shortcode": "t2", "url": "https://www.tiktok.com/@a/video/2",
                           "caption": "instagram 링크", "customer_id": "9"})
    assert st.claim_next() is not None
    assert st.claim_next() is None, "instagram이 섞인 것을 병렬로 내보냈다"
