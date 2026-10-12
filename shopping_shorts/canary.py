"""관리자 카나리 스위치(2026-09-18) — 사장님 본인 작업에서만 새 동작을 켠다.

왜: 장면꾸미기 트랙의 대본 쪽 변경(제목형 대본의 화면 제목↔첫 TTS 분리, 제목 글자 한도,
이븐쇼핑 보조제목 22자)은 스타일 스파인을 소비하는 경로 전부에 걸린다. 그대로 main에 올리면
고객이 즉시 새 대본을 받는다. 라이브 워커(믹스·TTS)로 실측하려면 라이브에 올라가야 하는데
고객에게는 옛 동작을 유지해야 하므로, 켜고 끄는 판단을 **이 한 곳**에서만 한다(0순위-B).

켜지는 조건: 요청이 관리자이고 쿠키 ``ss_canary=1``. 제작소 화면이 ``?scene_style_canary=1``로
열릴 때 그 쿠키를 심고, ``=0``이면 지운다. 조건 판정은 ``_auth_guard``가 요청마다 한 번 한다
(keyctx.set_owner와 같은 자리·같은 방식).

⚠️ 워커 프로세스에는 요청이 없어 항상 꺼져 있다. 워커가 스파인을 다시 읽어 대본을 만드는
경로가 생기면 job에 플래그를 실어 와야 한다 — 지금 대본 생성은 웹 프로세스에서만 돈다.
"""
import contextvars

COOKIE = "ss_canary"

_on = contextvars.ContextVar("shopping_shorts_admin_canary", default=False)


def set_active(flag):
    _on.set(bool(flag))


def on():
    return bool(_on.get())


def activate_from_request(request, is_admin):
    """미들웨어 전용 — 관리자 + 쿠키일 때만 켠다. 그 외엔 명시적으로 끈다(요청 간 누수 금지).

    is_admin은 bool 또는 callable. 쿠키가 없으면 판정을 아예 안 부른다 — _is_admin이 DB를
    읽으므로 고객 요청마다 조회가 하나 늘면 안 된다."""
    try:
        flag = (request.cookies.get(COOKIE) == "1")
        if flag:
            flag = bool(is_admin() if callable(is_admin) else is_admin)
    except Exception:
        flag = False
    set_active(flag)
    return flag
