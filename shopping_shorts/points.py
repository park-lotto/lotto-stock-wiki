"""고급효과 렌더 포인트 — 원장(ledger) 합산 방식. 음수 delta=차감."""


def balance(store, customer_id):
    return store.points_balance(customer_id)


def add(store, customer_id, amount):
    store.points_add(customer_id, amount, "add")


def deduct(store, customer_id, amount):
    if store.points_balance(customer_id) < amount:
        return False
    store.points_add(customer_id, -amount, "fx_render")
    return True


def refund(store, customer_id, amount):
    store.points_add(customer_id, amount, "fx_refund")
