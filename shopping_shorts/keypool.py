"""회원 키를 공용 풀(제미니·유튜브)에 합류시키는 **유일한 곳**.

★왜 app.py에서 여기로 옮겼나 (2026-08-31 실사고, CLAUDE.md 0순위-B)
  합류 로직이 `app.py:_resync_pools`에 있고 `@app.on_event("startup")`에서만 불렸다.
  그런데 **영상 제작 job은 worker.py(별도 프로세스)에서 돈다** — 워커는 FastAPI
  앱을 안 띄우므로 startup 이벤트가 없고, 그래서 **회원 키를 하나도 몰랐다.**

  실측(08-31): 웹 유닛엔 `[keypool] 제미니 사장님 12 + 회원 44 = 56`이 찍히는데
  워커 유닛 12개엔 24시간 동안 **0건**. 즉 제작소는 사장님 키 12개만으로 돌았고,
  회원이 등록한 44개는 등록만 된 채 놀았다. 같은 날 제미니 호출 1,825건 중
  816건(45%)이 429로 튕겼다.

  워커가 app.py를 통째로 import하게 만들 수는 없다(무겁고 순환 위험). 그렇다고
  합류 규칙을 워커에 다시 적으면 두 벌이 돼 반드시 어긋난다. 그래서 **양쪽이
  함께 쓰는 중립 모듈**로 뽑았다 — 규칙은 계속 한 곳이다.
"""

import logging

from shopping_shorts import config, keyroute

# ★keyroute.POOLED가 진실이다 — 여기에 서비스를 손으로 또 적지 않는다.
_POOL_REFRESHERS = {
    keyroute.SVC_GEMINI: ("제미니", lambda p: config.refresh_member_gemini_keys(p)),
    keyroute.SVC_YOUTUBE: ("유튜브", lambda p: config.refresh_member_youtube_keys(p)),
}


def resync_pools(store, verbose=False):
    """회원 키를 공용 풀(제미니·유튜브)에 합류시킨다(2026-08-24 사장님 정책).

    회원은 키를 1개만 내고 풀 전체를 무료로 쓴다 — 모자란 용량은 사장님이 채운다.
    ★웹 기동·키 등록·삭제·**워커**가 전부 이 함수를 쓴다. 합류 규칙을 두 군데
      적으면 어긋난다(0순위-B).
    실패해도 호출부를 막지 않는다: 키는 이미 DB에 있고 늦어도 다음 기동에 합류한다."""
    for svc in keyroute.POOLED:
        label, fn = _POOL_REFRESHERS[svc]
        try:
            n_owner, n_member = fn(store.get_pooled_keys(svc))
            if verbose and n_member:
                import sys as _sys
                print(f"[keypool] {label} 사장님 {n_owner} + 회원 {n_member} "
                      f"= {n_owner + n_member}개", file=_sys.stderr)
            elif n_member:
                logging.info("%s 공용풀 갱신: 사장님 %d + 회원 %d",
                             label, n_owner, n_member)
        except Exception as e:      # noqa: BLE001 — 한 서비스가 실패해도 나머지는 갱신
            logging.warning("%s 공용풀 갱신 실패(%s) — 다음 기동에 반영된다",
                            label, type(e).__name__)
