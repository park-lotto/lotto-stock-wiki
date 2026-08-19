"""포인트 원장 — 음수 delta=차감. 잔액은 delta 누적합(store.points_balance).

★단위: 내부값은 '포인트×100'이다(pricing.py 참조). points_ledger.delta가
INTEGER라 0.1P를 못 담기 때문. 화면에 보일 때만 pricing.to_display로 나눈다.

★reason: 어디에 썼는지 남긴다. 기본값 "fx_render"는 기존 고급효과 렌더
호출부(app.py:9538)가 인자 없이 부르고 있어 하위호환으로 남긴 것이다.
"""


def balance(store, customer_id):
    return store.points_balance(customer_id)


def add(store, customer_id, amount, reason="add"):
    store.points_add(customer_id, amount, reason)


def deduct(store, customer_id, amount, reason="fx_render"):
    """잔액이 모자라면 아무것도 안 하고 False. 0원 작업은 원장을 안 더럽힌다.

    ★판정과 차감을 store에서 SQL 한 문장으로 처리한다 — 여기서 balance()를
      읽고 add()를 부르면 워커 두 개가 같은 잔액을 보고 **둘 다 통과**한다.
      실측(2026-08-17): 10P에 5P 차감 5개 동시 → 3건 성공, 잔액 -5P."""
    return store.points_try_deduct(customer_id, amount, reason)


def refund(store, customer_id, amount, reason="fx"):
    """실패한 작업을 돌려준다. reason에 _refund가 붙어 충전과 구분된다."""
    if amount <= 0:
        return
    store.points_add(customer_id, amount, f"{reason}_refund")
