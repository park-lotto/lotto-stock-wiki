"""지금 처리 중인 작업이 **누구 것인가**를 담아두는 곳.

★왜 인자로 안 흘리나
제미나이 키를 실제로 꺼내는 곳은 5개인데(edit_plan·script_generate·seo_generate·
thumb_title·pattern_bank), 그 위로 `_call_json` → `generate_one_style` → app.py 까지
호출 체인이 3~4겹이다. customer_id를 인자로 흘리려면 시그니처를 20곳 넘게 고쳐야 하고,
한 곳이라도 빠뜨리면 **조용히 사장님 키로 새는** 구멍이 된다(vmake에서 실제로 그랬다).

그래서 "누구 작업인가"만 요청/작업 단위로 담아두고, 키를 고르는 쪽이 읽는다.
판단은 여전히 keyroute 한 곳에서만 한다(0순위-B) — 여기는 값을 나르기만 한다.

★스레드·워커 주의
contextvar는 **스레드마다 따로**다. HTTP 요청은 미들웨어가 자동으로 채우지만,
BackgroundTask·스레드풀에서 도는 렌더 워커는 그 컨텍스트를 물려받지 못한다.
그래서 워커 진입점에서 job의 customer_id로 **명시적으로** 열어줘야 한다:

    with keyctx.owner(job.get("customer_id") or 0):
        ...  # 이 블록 안에서 꺼내는 제미나이 키는 그 고객 것

안 열면 0(사장님)으로 떨어진다 — 안전한 쪽으로 실패한다(남의 키를 쓰는 일은 없다).
"""

import contextvars
import logging

_cid = contextvars.ContextVar("shopping_shorts_owner_cid", default=0)


def set_owner(customer_id):
    """지금 스레드/요청의 주인을 정한다. 되돌릴 토큰을 반환."""
    from shopping_shorts import keyroute
    return _cid.set(keyroute.as_cid(customer_id))


def reset_owner(token):
    try:
        _cid.reset(token)
    except ValueError:
        # 다른 컨텍스트에서 만든 토큰 — 되돌릴 게 없다. 조용히 넘기되 흔적은 남긴다.
        logging.debug("keyctx 토큰이 이 컨텍스트 것이 아니라 reset을 건너뛴다")


def owner_cid():
    """지금 작업의 주인. 안 정해졌으면 0(사장님)."""
    return _cid.get()


class owner:
    """with keyctx.owner(cid): — 블록을 벗어나면 원래대로 돌아간다."""

    def __init__(self, customer_id):
        self.customer_id = customer_id
        self._token = None

    def __enter__(self):
        self._token = set_owner(self.customer_id)
        return self

    def __exit__(self, *exc):
        if self._token is not None:
            reset_owner(self._token)
        return False
