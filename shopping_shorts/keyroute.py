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
SVC_BUFFER = "buffer"      # SNS 예약발행. 고객이 자기 Buffer 개인 키를 넣는다
SVC_TYPECAST = "typecast"  # 목소리 두 번째 백엔드. 프리셋 model_id가 `ssfm-*`면 이쪽으로 나간다

SERVICES = (SVC_GEMINI, SVC_VMAKE, SVC_ELEVENLABS, SVC_TYPECAST, SVC_YOUTUBE,
            SVC_SERPAPI, SVC_BUFFER)

# ★등록은 받지만 **실제 호출에 쓰이는** 서비스는 아직 이 둘뿐이다(2026-08-17 실측).
#   - vmake     : job의 customer_id → mix_pipeline._vmake_keys → keys_for (목록 전체)
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
# ★buffer는 **사장님 키가 아예 없다.** 고객이 자기 키를 넣어야만 되는 서비스다
#   (Buffer는 제3자 OAuth가 안 열려 우리가 대신 발행할 수 없다 — buffer_api.py 참조).
#   그래서 폴백이 없고, 우리 돈이 나가지도 않는다(발행은 고객의 Buffer 요금제로 나간다).
#   ★2026-08-31 typecast 배선 완료 → WIRED에 넣었다.
#     일레븐랩스와 **같은 경로**를 탄다: synthesize_tts(customer_id=…) →
#     _synthesize_typecast → typecast_tts.api_key(customer_id) → keys_for.
#     호출부는 이미 customer_id를 흘리고 있었고(일레븐랩스 배선 때 뚫린 길),
#     타입캐스트 분기만 그 인자를 버리고 config 키를 쓰고 있었다.
WIRED = (SVC_VMAKE, SVC_SERPAPI, SVC_ELEVENLABS, SVC_TYPECAST, SVC_GEMINI,
         SVC_YOUTUBE, SVC_BUFFER)

# ★공용 풀 모델(2026-08-24 사장님 결정) — 이 서비스들은 회원 키를 **우리 풀에 합류**시키고
#   회원은 풀 전체를 무료로 쓴다. 키 1개만 받는데 그 1개로만 돌리면 곧바로 한도에 걸려
#   "부담 줄이려 1개만 받은" 취지가 뒤집히기 때문이다.
#   나머지(vmake·serpapi·elevenlabs·typecast)는 **개인 전용**이다 — 회원이 자기 돈으로 결제하는
#   서비스라 남의 키를 쓰면 안 되고, 자기 키만 쓴다(폴백 없음).
POOLED = (SVC_GEMINI, SVC_YOUTUBE)

# ★호출부가 **키 하나만** 쓰는 서비스(tts._api_key가 keys[0]만 집는다).
#   여기서만 **나중에 등록한 키를 앞에** 둔다.
# ⚠️vmake는 2026-08-29부터 **목록 전체를 쓴다**(mix_pipeline._vmake_clean이 소진된 키를
#   건너뛰고 다음 키로 넘긴다). 그래도 이 목록에 남겨 둔다 — 새로 등록한 키를 **먼저**
#   시도하는 게 맞기 때문이다(갈아끼우려고 등록한 키가 뒤에 있으면 옛 키를 먼저 태운다).
#   왜: get_customer_keys_plain은 ORDER BY id라 가장 오래된 키가 keys[0]이다.
#   그래서 키를 갈아끼우려고 새로 등록해도 옛 키가 계속 쓰인다.
#   실사고(2026-08-28 cid 57): 크레딧 떨어진 Vmake 계정을 버리고 새 계정
#   키를 등록했는데, 옛 키(id=45)가 먼저라 자막제거가 계속 빈 계정을
#   때려 [60002]로 실패했다. 화면엔 두 키가 다 'ok'라 고객은 이유를 모른다.
#   ⚠️ serpapi는 **넣지 마라** — 거긴 키 개수만큼 한도를 주고(_lens_key_count)
#     목록 전체를 쓴다. 순서를 뒤집을 이유가 없다.
SINGLE_KEY = (SVC_VMAKE, SVC_ELEVENLABS, SVC_TYPECAST)


def uses_single_key(service):
    """호출부가 keys[0] 하나만 쓰는 서비스인가. 판단은 여기 한 곳(0순위-B)."""
    return service in SINGLE_KEY


def is_pooled(service):
    """회원 키가 공용 풀에 합류하는 서비스인가. 판단은 여기 한 곳(0순위-B)."""
    return service in POOLED


# ★개인 키가 **없으면 아예 못 쓰는** 서비스(2026-09-01 사장님 확정).
#   "v메이크랑 tts는 없으면 못하게 막아"
#
#   왜 생겼나(실사고): 회원이 개인 키를 안 내면 **사장님 키로 조용히 나가고**
#   포인트만 깎였다. 회원들은 "다 개인 API키로 쓴다"고 알고 있었고 아무도 포인트
#   얘기를 못 들었다. 포인트가 남은 회원(유영창 9,500P·이정훈 105,530P …)은 계속
#   사장님 일레븐랩스·VMake 계정을 태웠고, 잔액이 떨어진 회원만 402로 막혀
#   "어떤 사람은 되고 어떤 사람은 안 되는" 상태가 됐다.
#   실측(2026-09-01): 최근 30일 제작 46명 중 **16명이 TTS 키 없이** 86건을 만들었다.
#
#   그래서 폴백을 없앤다 — 키가 없으면 **기능 자체가 안 열린다**. 포인트로 때우는
#   길을 막아야 회원이 키를 등록한다.
#   ⚠️ gemini·youtube는 여기 넣지 마라. 저긴 공용 풀 정책(키 1개 받고 무료)이라
#      회사 키로 도는 게 **의도된 거래**다.
REQUIRE_OWN_KEY = (SVC_VMAKE, SVC_ELEVENLABS, SVC_TYPECAST)

#: 차단 안내에 쓸 사람 말 이름 — 화면이 서비스 코드를 그대로 보여주면 안 된다.
#   ★업체명을 쓰지 마라(브랜드 정책 — test_subclean_ui가 produce.html을 검사한다).
#     이 문구는 서버가 만들어 그 화면에 그대로 실린다.
SERVICE_LABEL = {
    SVC_VMAKE: "자막 지우기",
    SVC_ELEVENLABS: "목소리(ElevenLabs)",
    SVC_TYPECAST: "목소리(타입캐스트)",
    SVC_SERPAPI: "SerpAPI(렌즈 검색)",
    SVC_BUFFER: "Buffer(SNS 예약)",
    SVC_GEMINI: "제미니",
    SVC_YOUTUBE: "유튜브",
}


# ★차단 면제 명단(2026-09-01 사장님 지정) — "박2/관리자/용석/정훈 4명은 제외한다".
#   이분들은 키를 안 내도 회사 키로 계속 쓰신다(사장님이 비용을 감수하기로 한 계정).
#   실측으로 확정한 cid:
#     4  현경   arte.eum@gmail.com        (customers.admin=1 — 관리자)
#     5  용석   koho851101@gmail.com      ┐ 같은 분의 계정 2개
#     9  용석   851101ys@gmail.com        ┘
#     11 이정훈 aijumpers85@gmail.com
#     12 박2    parklotto20@gmail.com
#   ⚠️ 여기에 cid를 더하면 그 회원의 VMake·TTS 비용을 회사가 계속 부담한다.
#      사장님 지시 없이 늘리지 마라. 빼는 것은 언제든 안전하다.
#   ⚠️ 이름으로 판단하지 마라 — 동명이인이 있다(민정훈 cid 234는 면제 대상이 아니다).
BLOCK_EXEMPT_CIDS = frozenset({4, 5, 9, 11, 12})


def is_block_exempt(customer_id):
    """차단 면제 대상인가. cid 0(사장님)과 지정 명단. 판단은 여기 한 곳(0순위-B)."""
    cid = as_cid(customer_id)
    return (not cid) or (cid in BLOCK_EXEMPT_CIDS)


def requires_own_key(service):
    """개인 키가 없으면 못 쓰는 서비스인가. 판단은 여기 한 곳(0순위-B)."""
    return service in REQUIRE_OWN_KEY


def has_own_key(store, customer_id, service):
    """이 회원이 그 서비스의 **자기 키**를 등록했나. 사장님 키는 세지 않는다."""
    try:
        return bool(store.get_customer_keys_plain(as_cid(customer_id), service))
    except AttributeError:      # store 스텁 — 판단 불가면 '없다'로 보지 않는다(작업을 막지 않게)
        logging.warning("has_own_key: store에 get_customer_keys_plain이 없다 "
                        "(cid=%r, service=%r) — 있음으로 처리한다", customer_id, service)
        return True
    except Exception as e:      # noqa: BLE001 — 조회 실패로 회원을 막으면 안 된다
        logging.warning("has_own_key 조회 실패(있음으로 처리): %r", e)
        return True


def block_reason(store, customer_id, service):
    """개인 키가 없어 막아야 하면 (코드, 사람이 읽는 문구), 아니면 None.

    ★차단 판단은 여기 한 곳뿐이다 — 엔드포인트마다 다시 적으면 어긋난다(0순위-B).
    ★사장님(cid 0)은 막지 않는다: 공용 보이스 굽기·샘플 제작 등 회사 자산 작업이
      여기서 막히면 서비스가 통째로 선다.
    """
    if not requires_own_key(service):
        return None
    if is_block_exempt(customer_id):     # cid 0(사장님) + 지정 면제 명단
        return None
    if has_own_key(store, customer_id, service):
        return None
    label = SERVICE_LABEL.get(service, service)
    return ("need_own_key",
            f"{label} API 키를 등록해야 이용할 수 있어요. "
            f"설정 > 🔑 API 키에서 등록해 주세요.")


def tts_block_reason(store, customer_id):
    """음성(TTS)은 일레븐랩스·타입캐스트 **둘 중 하나만** 있으면 된다.

    ★서비스 하나씩 block_reason을 부르면 "일레븐랩스 없음"으로 막혀, 타입캐스트를
      등록한 회원(실측 4명)이 억울하게 막힌다 — 그래서 음성은 이 함수가 판단한다.
    """
    if is_block_exempt(customer_id):     # cid 0(사장님) + 지정 면제 명단
        return None
    if (has_own_key(store, customer_id, SVC_ELEVENLABS)
            or has_own_key(store, customer_id, SVC_TYPECAST)):
        return None
    return ("need_own_key",
            "음성 생성을 하려면 일레븐랩스 또는 타입캐스트 API 키가 필요해요. "
            "설정 > 🔑 API 키에서 등록해 주세요.")


def uses_customer_key(service):
    """등록한 키가 실제 작업에 쓰이는 서비스인가. 화면 문구도 이걸 봐야
    "등록하면 0P"라는 거짓말이 안 나간다(0순위-B: 판단은 한 곳에서)."""
    return service in WIRED


# ── 붙여넣은 키가 "가려진 키"인가 (2026-08-28 실사고) ────────────────────────
# 두 고객이 같은 실수를 했다: VMake 화면에 **가려져 보이는** 키(`13a08ac2••••*****`)를
# 그대로 복사해 등록했다. 그런데 등록은 성공(status=ok)으로 저장돼 화면엔 "등록 완료"가
# 뜨고, 정작 쓸 때만 서명이 안 맞아 실패했다.
#   실측 cid18 강민희: 키 140자(정상 184) / 라벨 끝 '*****' / 12:48~13:04 6회 전부 실패
#     에러 `[10021] sign not equals client ... Access=13a08ac2eb5f4f` — 그 키가 실제로 쓰였다
#   cid134 최소연도 같은 모양이었다가 재등록으로 정상화됐다(전수 22건 중 1건 남음).
# 잘못된 키를 받아 두는 것이 제일 나쁘다 — 고객은 잘 된 줄 알고 있다가 나중에야 안다.
# 그래서 **등록 시점에** 막는다. 판정은 여기 한 곳(0순위-B) — API·관리자 경로가 같이 쓴다.
MASK_CHARS = "*•●·×✕✱∗"          # 서비스마다 가림문자가 다르다(별·가운뎃점·원)

def masked_key_reason(raw):
    """가려진 키로 보이면 사람이 읽을 이유를, 정상으로 보이면 None을 준다.

    ★길이로는 판정하지 않는다 — 서비스마다 키 길이가 다르고, 새 형식이 나오면
      멀쩡한 키를 막게 된다. **가림문자가 섞였는가**만 본다(오탐이 거의 없다).
    """
    t = (raw or "").strip()
    if not t:
        return None                       # 빈 값은 호출부가 따로 안내한다
    hit = [ch for ch in MASK_CHARS if ch in t]
    if hit:
        return ("가려진 키를 붙여넣으신 것 같아요(‘%s’가 들어 있어요). "
                "발급 화면에서 **전체 키**를 복사해 주세요 — 화면에 점이나 별표로 가려진 "
                "부분은 실제 키가 아닙니다." % hit[0])
    return None


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
    # ★cid 0(관리자 비번 로그인)도 자기 키를 쓴다(2026-08-27 사장님 "내꺼 전용으로").
    #   전엔 `if cid:`라 0이 falsy로 걸려 **개인 키 조회를 통째로 건너뛰고** 항상
    #   공용 env 풀을 썼다. 그래서 사장님이 개인 키를 등록해도 안 쓰였고, 반대로
    #   env에 넣으면 전 회원이 같이 썼다 — "내 전용"이 성립할 자리가 없었다.
    #   ⚠️ as_cid는 None을 안 준다(못 읽으면 0으로 떨어뜨린다) — 그래서 조건을 걸지
    #      않고 **누구든 자기 키를 먼저 본다**. cid만 특별 취급하는 갈래를 없앤 것이
    #      이 수정의 핵심이다(0순위-B: 같은 판단을 두 갈래로 두지 않는다).
    #   ⚠️ store가 이 메서드를 안 가진 경로가 있다(과금·정리 코드가 넘기는 가벼운
    #      스텁 등). 전엔 cid 0이면 호출 자체를 건너뛰어 드러나지 않던 자리다 —
    #      없으면 **조용히 넘기지 말고 로그를 남기고** 공용 키로 간다(종전 동작).
    try:
        mine = store.get_customer_keys_plain(cid, service)
    except AttributeError:
        logging.warning("keys_for: store에 get_customer_keys_plain이 없다"
                        "(cid=%r, service=%r) — 공용 키로 처리한다", cid, service)
        mine = None
    if mine:
        if not is_pooled(service):
            # 키 하나만 쓰는 서비스는 **최신 키를 앞에** 둔다(SINGLE_KEY 주석 참조).
            #   목록은 그대로 다 돌려준다 — 순회하는 호출부가 생겨도 안 깨진다.
            if uses_single_key(service):
                return list(reversed(mine)), True
            return mine, True             # ★개인 전용: 여기서 끝. 공용 키를 안 섞는다
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
