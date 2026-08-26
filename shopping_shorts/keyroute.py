"""누구의 어떤 키를 쓸지 정하는 **유일한 곳**.

★왜 한 곳인가 (CLAUDE.md 0순위-B)
키를 고르는 판단과 "과금할까"는 짝이다. 따로 적으면 반드시 어긋난다 —
계정과 프록시를 따로 정했다가 5벌로 흩어져 로테이션이 통째로 죽은 실사고가 있다.
그래서 keys_for()가 (키, 사용자키인가)를 **함께** 돌려주고,
should_charge()는 그 두 번째 값을 뒤집기만 한다. 과금을 따로 판단하지 마라.

★폴백 없음 (사장님 확정)
사용자 키가 있으면 그 키만 쓴다. 소진돼도 사장님 키로 안 넘어간다.
넘어가면 "키 등록했는데 사장님 돈이 나가는" 상태가 조용히 생긴다.

★호출할 땐 문자열 대신 아래 SVC_* 상수를 써라. 오타(`"vmakee"`)를 조용히
  "키 없음"으로 처리하면 과금 여부까지 뒤집혀 원인을 못 찾는다.

※ pricing.OP_* 와 이름이 겹쳐 보여도 **다른 축이다.**
  서비스 = 키를 발급하는 곳(vmake·gemini·elevenlabs·youtube)
  작업   = 사용자가 누르는 버튼(vmake·mix·tts·lens·script)
  영상제작 1건(OP_MIX)은 SVC_GEMINI + SVC_ELEVENLABS 둘을 쓴다 — 1:1이 아니다.
"""

import logging

SVC_GEMINI = "gemini"
SVC_VMAKE = "vmake"
SVC_ELEVENLABS = "elevenlabs"
SVC_YOUTUBE = "youtube"
SVC_SERPAPI = "serpapi"

SERVICES = (SVC_GEMINI, SVC_VMAKE, SVC_ELEVENLABS, SVC_YOUTUBE, SVC_SERPAPI)

# ★등록은 받지만 **실제 호출에 쓰이는** 서비스는 아직 이 둘뿐이다(2026-08-17 실측).
#   - vmake     : mix_pipeline.py:1432-1433 job의 customer_id → _vmake_key → keys_for
#   - serpapi   : app.py _lens_api_keys(cid) → 렌즈 호출부 2곳
#   - gemini    : keyroute.gemini_keys()가 유일한 출구. cid는 인자가 아니라
#                 keyctx(요청=미들웨어 / 워커=_owned_job 데코레이터)에서 읽는다.
#                 호출 체인이 3~4겹이라 인자로 흘리면 한 곳만 빠뜨려도 조용히 샌다.
#   ★2026-08-24 elevenlabs 배선 완료 → WIRED에 넣었다.
#     synthesize_line에 customer_id를 받아 synthesize_best(**kw)→synthesize_tts→
#     tts._api_key→keys_for까지 흘린다(하류는 원래 다 뚫려 있었고 여기만 빠져 있었다).
#     호출부 6곳 전부 주인을 넘긴다: 렌더 4곳은 job["customer_id"], 보이스튜닝은
#     _cid(req), 믹스 미리듣기는 job(요청자 아님 — 미리듣기와 최종본이 같은 키를 써야 한다).
#     ⚠️eleven_voices.bake_sample·make_preview는 **공용 보이스 라이브러리** 굽기라
#       일부러 사장님 키(cid 0)로 둔다 — 회원 크레딧으로 공용 자산을 구우면 안 된다.
#   - youtube   : service.py:176·179 yt_search 호출에 customer_id 없음 (아래 회원풀 참조)
#
# ⚠️여기 이름을 옮기기 전에 **호출부에 cid가 진짜 닿는지 먼저 확인해라.**
#   이 목록이 앞서가면 아래 should_charge가 '안 쓰이는 키'로 과금을 면제한다 =
#   회사 키로 돌면서 돈은 안 받는 구멍이 된다(2026-08-17에 실제로 그 상태였다).
# ★2026-08-23 gemini를 뺐던 이유(아래)는 **2026-08-24 정책 변경으로 해소됐다.**
#   [옛 이유] 개인 키가 나가는 곳은 5곳뿐이고 태깅·대본추출은 comment_gen이 회사 풀을
#   인덱스로 직접 돌려서, 면제만 켜면 "회사 키로 돌면서 돈은 안 받는" 구멍이 됐다.
#   [해소] 이제 회원 키가 **회사 풀에 합류**한다(config.refresh_member_gemini_keys).
#   즉 comment_gen이 도는 그 풀 안에 회원 키가 들어 있다 — 회사 키로만 돌던 전제가
#   더는 성립하지 않는다. 사장님 결정: 키 1개 받고 **무료로 쓰게 해준다**(모자란
#   용량은 사장님이 키를 더 만들어 채운다). 의도된 거래라 누수가 아니다.
#   ⚠️단 합류 배선(config.refresh_member_gemini_keys 호출)이 살아 있어야 성립한다.
#     그 호출을 지우면 여기 면제도 같이 빼라 — 안 그러면 08-17 사고가 그대로 재현된다.
WIRED = (SVC_VMAKE, SVC_SERPAPI, SVC_ELEVENLABS, SVC_GEMINI, SVC_YOUTUBE)

# ★공용 풀 모델(2026-08-24 사장님 결정) — 이 서비스들은 회원 키를 **우리 풀에 합류**시키고
#   회원은 풀 전체를 무료로 쓴다. 키 1개만 받는데 그 1개로만 돌리면 곧바로 한도에 걸려
#   "부담 줄이려 1개만 받은" 취지가 뒤집히기 때문이다.
#   나머지(vmake·serpapi·elevenlabs)는 **개인 전용**이다 — 회원이 자기 돈으로 결제하는
#   서비스라 남의 키를 쓰면 안 되고, 자기 키만 쓴다(폴백 없음).
POOLED = (SVC_GEMINI, SVC_YOUTUBE)


def is_pooled(service):
    """회원 키가 공용 풀에 합류하는 서비스인가. 판단은 여기 한 곳(0순위-B)."""
    return service in POOLED


def uses_customer_key(service):
    """등록한 키가 실제 작업에 쓰이는 서비스인가. 화면 문구도 이걸 봐야
    "등록하면 0P"라는 거짓말이 안 나간다(0순위-B: 판단은 한 곳에서)."""
    return service in WIRED


def as_cid(customer_id):
    """cid는 int 0과 문자열 "0"이 섞여 온다(app.py:6813의 2026-07-30 실사고).
    정규화 안 하면 사용자 키를 못 찾고 조용히 사장님 키로 샌다.

    숫자로 못 읽으면 0(사장님)으로 떨어뜨리되 **로그를 남긴다** — 이 경우
    사용자가 키를 등록해뒀어도 조회를 건너뛰고 과금 대상이 되므로,
    조용히 넘기면 "왜 내 키를 안 쓰지"의 원인을 못 찾는다.

    ★공개 함수다 — 과금하는 쪽(mix_pipeline._charge_clean 등)도 같은 규칙으로
      cid를 봐야 한다. 각자 int()를 부르면 같은 판단이 두 곳에 흩어진다(0순위-B)."""
    try:
        return int(customer_id)
    except (TypeError, ValueError):
        logging.warning("cid를 숫자로 못 읽어 0(사장님)으로 처리한다: %r", customer_id)
        return 0


_as_cid = as_cid        # 기존 호출부 하위호환


def _owner_keys(service):
    """사장님(회사) 키. env 기반 서비스(gemini/youtube/elevenlabs)만 다룬다.
    테스트에서 monkeypatch로 갈아끼우는 지점 — keys_for가 서비스 구분 없이
    먼저 여기를 거치므로, 실제 vmake는 여기선 빈 목록이고 keys_for가
    _owner_vmake_key로 대신 채운다(아래 참고)."""
    from shopping_shorts import config
    if service == SVC_GEMINI:
        return list(config.SHORTS_GEMINI_KEYS)
    if service == SVC_YOUTUBE:
        return list(config.YOUTUBE_API_KEYS)
    if service == SVC_ELEVENLABS:
        k = getattr(config, "ELEVENLABS_API_KEY", "")
        return [k] if k else []
    if service == SVC_SERPAPI:
        # 렌즈 검색용. gemini/youtube와 같은 env 다중키 방식(SERPAPI_KEY~_30).
        return list(getattr(config, "SERPAPI_KEYS", []) or [])
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

    모르는 service는 ValueError로 즉시 터진다 — 조용히 ([], False)를 주면
    오타가 "키 없음 + 과금함"으로 둔갑해 원인을 못 찾는다.
    """
    if service not in SERVICES:
        raise ValueError(
            f"모르는 service: {service!r}. keyroute.SVC_* 상수를 써라 "
            f"(가능한 값: {', '.join(SERVICES)})")
    cid = as_cid(customer_id)
    if cid:                                   # cid 0 = 사장님 본인이라 조회 안 함
        mine = store.get_customer_keys_plain(cid, service)
        if mine and not is_pooled(service):
            return mine, True                 # ★개인 전용: 여기서 끝. 사장님 키를 안 섞는다
        if mine:
            # ★공용 풀 모델(gemini·youtube): 자기 키를 냈으면 **풀 전체**를 쓴다.
            #   is_user=True를 그대로 돌려주므로 should_charge가 면제로 이어진다
            #   ("키 1개 내고 무료로 쓴다"는 거래). 풀은 사장님 키 + 전 회원 키.
            pooled = _owner_keys(service)     # 이미 회원 키가 합류돼 있는 목록
            return (pooled or mine), True
    owner = _owner_keys(service)
    if not owner and service == SVC_VMAKE:
        owner = _owner_vmake_key(store)
    return owner, False


def should_charge(store, customer_id, service):
    """포인트를 깎아야 하는가. 사용자 키를 쓰면 안 깎는다.

    ★keys_for의 판단을 그대로 뒤집기만 한다 — 여기서 따로 판단하면 어긋난다.

    ★단 '실제로 안 쓰이는 서비스'는 등록돼 있어도 과금한다(2026-08-17 실사고).
      대본·영상제작은 SVC_GEMINI 기준으로 면제하는데 제미나이 키는 실제 호출에
      안 쓰인다 → 고객이 키만 등록하면 **회사 키로 돌면서 포인트는 0**이었다.
      배선이 끝나 WIRED에 들어가는 순간 이 예외는 저절로 사라진다."""
    # ★관리자 면제(2026-08-25) — 사장님 키로 돌면서 포인트만 면제하는 상태.
    #   cid 57 실사고: 키를 꺼두면 사장님 키로 처리되지만 과금은 계속 됐다.
    #   "내 키 쓰게 해주되 공짜로"라는 사장님 의도를 담는 자리가 여기다.
    #   ★uses_customer_key 검사보다 **먼저** 본다 — 배선 여부와 무관하게 면제여야 한다.
    try:
        if store is not None and as_cid(customer_id) and store.is_point_exempt(customer_id, service):
            return False
    except Exception as e:                      # noqa: BLE001 — 면제 조회 실패로 작업을 막지 않는다
        logging.warning("면제 조회 실패(과금으로 진행): %r", e)
    if not uses_customer_key(service):
        return True
    _, is_user = keys_for(store, customer_id, service)
    return not is_user

def gemini_keys(group="general", customer_id=None):
    """제미나이 호출에 쓸 키 목록. **키를 꺼내는 유일한 출구다.**

    ★2026-08-24 정책 변경(사장님): 제미니는 회원에게 **1개만** 받아 **우리 풀에
      합류**시키고 회원은 무료로 쓴다. 모자란 용량은 사장님이 키를 더 만들어 채운다.

      그래서 "내 키만 쓴다(폴백 없음)"를 **버렸다**. 키 1개만 받는데 그 1개로만
      돌리면 분당 15·하루 500에 곧바로 걸려 회원이 오히려 못 쓴다 — 부담을 줄이려
      1개만 받은 취지가 뒤집힌다. 풀에 넣었으면 풀 전체를 쓰는 게 맞다.

      vmake·serpapi는 종전 그대로 "내 키만"이다(keys_for). 저긴 회원이 자기 돈으로
      결제하는 서비스라 남의 키를 쓰면 안 된다. **제미니만 공용 풀 모델이다.**

    ★합류는 **여기서 하지 않는다.** config.SHORTS_GEMINI_KEYS가 이미 합류된 목록이고
      (app 기동·키 등록/삭제 때 refresh_member_gemini_keys가 다시 만든다), 여기서 또
      DB를 읽어 붙이면 같은 판단이 두 곳에 생겨 반드시 어긋난다(0순위-B).
      매 호출 DB를 읽는 비용도 없앤다.

    ★회원 키는 key_vault의 소진관리(mark_exhausted) 대상이 아니다 — 상태파일이
      인덱스 기반이라 목록이 흔들리면 **엉뚱한 키가 죽은 것으로 기록된다**.
      그래서 합류분은 사장님 키 **뒤에만** 붙는다(config._merge_pool).
    """
    from shopping_shorts import keyctx
    from pipeline.atoms import key_vault

    # cid는 더 이상 '누구 키를 쓸까'를 가르지 않는다(공용 풀). 소진 로그·디버깅용으로만 읽는다.
    _ = as_cid(customer_id if customer_id is not None else keyctx.owner_cid())
    return key_vault.get_live_keys_cascade(group)
