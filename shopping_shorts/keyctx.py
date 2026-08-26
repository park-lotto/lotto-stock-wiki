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

class pool:
    """컨텍스트를 물려주는 ThreadPoolExecutor.

    ★왜 필요한가 (2026-08-23 실측 결함)
    contextvar는 **스레드를 건너지 않는다.** 워커가 keyctx.owner(cid)를 열어도
    그 안에서 ThreadPoolExecutor를 만들면 하위 스레드는 주인을 모른다 →
    고객이 등록한 제미나이 키를 무시하고 **회사 키로 돌면서 과금은 면제**되는,
    가장 나쁜 조합이 생긴다(WIRED가 등록만 보고 면제하기 때문).

    submit할 때 지금 컨텍스트를 복사해 넘긴다. map도 내부적으로 submit을 쓰므로
    함께 커버된다. 사용법은 ThreadPoolExecutor와 완전히 같다:

        with keyctx.pool(max_workers=4) as ex:
            list(ex.map(fn, items))
    """

    def __init__(self, max_workers=None, **kw):
        from concurrent.futures import ThreadPoolExecutor
        self._ex = ThreadPoolExecutor(max_workers=max_workers, **kw)

    def submit(self, fn, *a, **kw):
        ctx = contextvars.copy_context()
        return self._ex.submit(ctx.run, fn, *a, **kw)

    def map(self, fn, *iterables, **kw):
        # ThreadPoolExecutor.map은 self.submit을 부르지 않고 내부 구현을 쓰므로
        # 여기서 직접 submit으로 풀어 컨텍스트가 확실히 넘어가게 한다.
        futs = [self.submit(fn, *args) for args in zip(*iterables)]
        return (f.result() for f in futs)

    def shutdown(self, *a, **kw):
        return self._ex.shutdown(*a, **kw)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._ex.shutdown(wait=True)
        return False
