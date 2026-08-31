"""_vault_call이 호출마다 다른 키부터 시작하는가 (2026-08-31 실사고 회귀 방지).

★사고: get_live_keys_cascade는 매번 같은 순서를 준다. 그런데 _vault_call의
  key_offset 기본값이 0이라 대본생성·비트다듬기·장면재선택·태깅이 전부 keys[0]부터
  두들겼고, 워커 12개가 동시에 도니 무료등급 분당 15회를 몇 초 만에 넘겼다.
  실측: 제미니 호출 1,825건 중 816건(45%)이 429. 429 사유는 전부 '분당' 한도,
  '하루' 한도는 0건 — 키가 모자란 게 아니라 앞쪽 키에 몰린 것이 원인이었다.
"""
from shopping_shorts import edit_plan


def _spy():
    seen = []

    def call(prompt, schema, max_tries=8, key_offset=0):
        seen.append(key_offset)
        return {"ok": 1}
    return seen, call


def test_연속호출은_서로_다른_키부터_시작한다(monkeypatch):
    seen, call = _spy()
    monkeypatch.setattr(edit_plan, "_vault_call_once", call)
    for _ in range(8):
        edit_plan._vault_call("p", None)
    assert len(set(seen)) == 8, f"오프셋이 겹친다 {seen} — 같은 키에 몰린다"
    # 키 10개 풀이면 서로 다른 인덱스로 흩어져야 한다
    assert len({o % 10 for o in seen}) == 8


def test_명시적_오프셋은_존중된다(monkeypatch):
    """후보생성 경로가 주는 오프셋을 자동값이 덮어쓰면 그쪽 분산이 깨진다."""
    seen, call = _spy()
    monkeypatch.setattr(edit_plan, "_vault_call_once", call)
    edit_plan._vault_call("p", None, key_offset=5)
    assert seen == [5]
