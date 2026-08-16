"""누구의 어떤 키를 쓸지 정하는 **유일한 곳**.

★왜 한 곳인가 (CLAUDE.md 0순위-B)
키를 고르는 판단과 "과금할까"는 짝이다. 따로 적으면 반드시 어긋난다 —
계정과 프록시를 따로 정했다가 5벌로 흩어져 로테이션이 통째로 죽은 실사고가 있다.
그래서 keys_for()가 (키, 사용자키인가)를 **함께** 돌려주고,
should_charge()는 그 두 번째 값을 뒤집기만 한다. 과금을 따로 판단하지 마라.

★폴백 없음 (사장님 확정)
사용자 키가 있으면 그 키만 쓴다. 소진돼도 사장님 키로 안 넘어간다.
넘어가면 "키 등록했는데 사장님 돈이 나가는" 상태가 조용히 생긴다.
"""


def _as_cid(customer_id):
    """cid는 int 0과 문자열 "0"이 섞여 온다(app.py:6813의 2026-07-30 실사고).
    정규화 안 하면 사용자 키를 못 찾고 조용히 사장님 키로 샌다."""
    try:
        return int(customer_id)
    except (TypeError, ValueError):
        return 0


def _owner_keys(service):
    """사장님(회사) 키. env 기반 서비스(gemini/youtube/elevenlabs)만 다룬다.
    테스트에서 monkeypatch로 갈아끼우는 지점 — keys_for가 서비스 구분 없이
    먼저 여기를 거치므로, 실제 vmake는 여기선 빈 목록이고 keys_for가
    _owner_vmake_key로 대신 채운다(아래 참고)."""
    from shopping_shorts import config
    if service == "gemini":
        return list(config.SHORTS_GEMINI_KEYS)
    if service == "youtube":
        return list(config.YOUTUBE_API_KEYS)
    if service == "elevenlabs":
        k = getattr(config, "ELEVENLABS_API_KEY", "")
        return [k] if k else []
    return []


def _owner_vmake_key(store):
    """vmake만 env가 아니라 store 설정에 있다(app.py:2838로 등록한 전역 키)."""
    k = store.get_setting("vmake_api_key", "") or ""
    return [k] if k else []


def keys_for(store, customer_id, service):
    """(쓸 키 목록, 사용자 키인가) 반환.

    사용자 키가 하나라도 있으면 그것만 돌려준다. 없으면 사장님 키.
    둘 다 없으면 ([], False) — 호출부가 "설정 안 됨"으로 처리한다.

    ★사장님 키는 항상 _owner_keys(service)를 먼저 거친다(vmake 포함).
    env 기반 서비스는 여기서 바로 나온다. vmake만 env에 없어서 빈 목록이
    돌아오는데, 그 경우에만 store 설정 기반 _owner_vmake_key로 채운다.
    """
    cid = _as_cid(customer_id)
    if cid:                                   # cid 0 = 사장님 본인이라 조회 안 함
        mine = store.get_customer_keys_plain(cid, service)
        if mine:
            return mine, True                 # ★여기서 끝. 사장님 키를 섞지 않는다
    owner = _owner_keys(service)
    if not owner and service == "vmake":
        owner = _owner_vmake_key(store)
    return owner, False


def should_charge(store, customer_id, service):
    """포인트를 깎아야 하는가. 사용자 키를 쓰면 안 깎는다.

    ★keys_for의 판단을 그대로 뒤집기만 한다 — 여기서 따로 판단하면 어긋난다."""
    _, is_user = keys_for(store, customer_id, service)
    return not is_user
