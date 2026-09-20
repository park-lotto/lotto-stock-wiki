"""한국어 키워드 검색 단일 진입점 — 인스타·틱톡·유튜브(2026-08-17).

`cn_search`(샤오홍슈·도우인)의 형제이고, **사슬 엔진은 같은 것을 쓴다**
(`search_chain`). 즉 "무료 먼저 → 0건이면 다음" 규칙이 두 군데 적히지 않는다.

호출부는 어느 백엔드가 도는지 모른다. 나중에 틱톡 무료 경로(yt-dlp)가 생기면
아래 `_CHAIN`에 한 줄 끼우면 되고, 엔드포인트도 프론트도 안 고친다.

검색어가 CN과 다르다 — 여기는 **한국어(ko)**, cn_search는 중국어(zh)다.
같은 후보 행에서 버튼만 갈린다.
"""
from shopping_shorts import config, kw_backends, search_chain

# 회당 비용(달러). meta로 화면에 노출한다 — 비용이 조용히 새는 걸 막는다.
#   유튜브·인스타는 0원이다(유튜브=무료쿼터 / 인스타=우리 프록시. 프록시 바이트
#   요금은 렌즈가 아니라 프록시 예산에서 나가므로 여기 회당 비용은 0으로 둔다).
#
# 틱톡 = Apify `clockworks/tiktok-scraper` 유료.
# ★2026-08-17 서버 실측: 5건 요청 1회 = **$0.0195** (run usageTotalUsd 직접 확인).
#   개수에 따라 늘어나므로 기본 8건이면 대략 $0.03 언저리다 — 정확한 값이 필요하면
#   Apify 콘솔의 run usageTotalUsd를 다시 재라(여기 숫자를 짐작으로 고치지 마라).
#   참고: 샤오홍슈 $0.098 · 도우인 $0.04005보다는 싸다.
# ⚠️키는 **백엔드 함수 이름**이다(run_chain이 fn.__name__으로 찾는다).
_COST = {"apify_tiktok": 0.0195}

_CHAIN = {
    # ★인스타는 기본으로 **빠져 있다**(2026-09-08 사장님 "인스타는 막고").
    #   Apify는 아니지만 주거용 프록시라 GB 과금이고, 회당 얼마인지 측정된 적이 없다.
    #   되살리려면 KW_SEARCH_INSTAGRAM=1. 켜고 끄는 판단은 config 한 곳에서만 한다.
    "instagram": [kw_backends.instagram],
    # 틱톡도 프록시로 간다 — 다만 **세션이 있어야** 데이터가 온다(2026-08-17 실측:
    # 프록시로 페이지·API 모두 200인데 본문이 비고 로그인 모달이 뜬다).
    # 세션 파일이 생기는 순간 pw_tiktok이 성공하기 시작해 자동으로 $0이 된다 —
    # 샤오홍슈가 그렇게 무료로 돌고 있고, 도우인이 그 반대 상태다.
    # ★유료 폴백(apify_tiktok)은 기본으로 빠진다. 되살리려면 KW_SEARCH_TIKTOK_APIFY=1.
    # ★2026-09-08: 세션을 넣어 **무료 경로가 실제로 살아났다**(사장님 파이어폭스
    #   쿠키 → /home/ubuntu/tiktok_session.json). 서버 실측 pw_tiktok 6건 반환.
    #   즉 지금은 유료 폴백이 꺼져 있어도 틱톡 결과가 정상으로 나온다.
    #   세션이 만료되면 0건이 되므로, 그때 tools/tiktok_session_from_firefox.py 로
    #   다시 뽑으면 된다(코드 수정 불필요).
    "tiktok": [kw_backends.pw_tiktok, kw_backends.apify_tiktok],
    "youtube": [kw_backends.youtube],
    # 핀터레스트(2026-08-29) — 렌즈 시각검색이 영상 핀을 사실상 안 물어와서(실측
    # ko+en 147건 중 0개) 키워드 검색으로 합류한다. 영상탭+영어번역, 비용 0.
    "pinterest": [kw_backends.pinterest_videos],
    # 네이버 클립(2026-08-30) — 국내 숏폼. 비용 0, 로그인·프록시·브라우저 전부 불필요
    # (HTTP 2번: 검색 프래그먼트 → 카드 상세). 조회수·좋아요가 같이 와서
    # **인기순 정렬을 우리가** 한다 — 서버 sort 파라미터는 무시된다(실측).
    "naverclip": [kw_backends.naverclip_videos],
}

# ★위 _CHAIN이 **배선의 정본**이다 — 플랫폼이 조용히 사라지지 않게 원본을 남긴다.
#   (test_real_chain_has_the_four_platforms가 이걸 못박는다.)
_CHAIN_FULL = {p: list(fns) for p, fns in _CHAIN.items()}


def _apply_knobs(chain):
    """돈 나가는 경로를 끈다 (2026-09-08) — 끄는 판단은 config, 반영은 **여기 한 곳**.

    호출부·엔드포인트·프론트는 어느 플랫폼이 도는지 모른 채 그대로 돈다.
    남는 게 0개가 되는 일은 없다(유튜브·핀터레스트·네이버클립엔 노브가 없다).
    """
    out = {p: list(fns) for p, fns in chain.items()}
    if not config.KW_SEARCH_INSTAGRAM:
        out.pop("instagram", None)
    if not config.KW_SEARCH_TIKTOK_APIFY and "tiktok" in out:
        # 유료 백엔드만 뺀다 — 세션이 생기면 pw_tiktok이 그대로 무료로 성공한다.
        out["tiktok"] = [fn for fn in out["tiktok"] if fn is not kw_backends.apify_tiktok]
    return out


_CHAIN = _apply_knobs(_CHAIN_FULL)


# ── 플랫폼별로 **어느 언어로 검색할지** (2026-09-08 사장님 "중국어 영어 일본어까지 배치")
#    ★여기 한 곳에서만 정한다(0순위-B). 백엔드도 프론트도 이 표를 모른다.
#
#    왜 언어를 나누나: 소재 영상은 한국어 검색만으로는 안 나온다. 핀터레스트가 이미
#    같은 이유로 자체 번역을 하고 있었다(실측: '인덕션 테이블' 0건 / 'induction table'
#    12건). 그 판단이 백엔드 하나에 갇혀 있어 나머지 플랫폼은 혜택을 못 봤다.
#
#    ★언어를 늘리면 **호출 수가 그만큼 는다**. 그래서 지금 켜져 있는 플랫폼은 전부
#    무료인 것만이다(유튜브 무료쿼터 · 핀터레스트 · 네이버클립). 유료 경로(인스타
#    프록시·틱톡 Apify)는 config 노브로 꺼져 있어 여기 표와 무관하게 안 돈다.
_LANGS_BY_PLATFORM = {
    # 국내 숏폼 — 한국어만. 영어로 물으면 0건이다.
    "naverclip": ("ko",),
    # 핀터레스트는 **자체적으로** 영어 번역을 한다(kw_backends.pinterest_videos).
    # 여기서 또 번역해 넘기면 같은 판단이 두 곳이 된다 → ko를 주고 그쪽에 맡긴다.
    "pinterest": ("ko",),
    # 유튜브는 무료쿼터라 언어를 늘려도 돈이 안 나간다. 해외 원본 소재가 여기서 나온다.
    "youtube": ("ko", "en", "ja"),
    # 틱톡은 세션이 생기면 무료로 살아난다 — 그때 이 배치가 그대로 적용된다.
    "tiktok": ("ko", "en"),
    # 인스타는 기본 꺼져 있다(프록시 과금). 켜지면 해시태그라 한국어만 의미 있다.
    "instagram": ("ko",),
}


def _kw_for(lang, ko, tr):
    """그 언어의 검색어. 번역이 비면 한국어로 폴백한다(빈 검색어로 나가지 않게)."""
    if lang == "ko":
        return ko
    return (tr.get(lang) or "").strip() or ko


def search(keyword, max_results=10, multilang=True):
    """한국어 키워드 → 플랫폼×언어 병렬 검색.

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {슬롯: {...}}}
    items는 렌즈 카드와 같은 스키마다(cn_backends.normalize 공용).

    multilang=False면 종전처럼 한국어로만 돈다(되돌리기 스위치)."""
    ko = (keyword or "").strip()
    if not ko:
        return {"items": [], "count": 0, "keyword": "", "meta": {}}

    tr = {}
    if multilang:
        try:
            from shopping_shorts import video_analysis
            tr = video_analysis.translate_keyword(ko) or {}
        except Exception:      # noqa: BLE001 — 번역 실패가 검색을 죽이면 안 된다
            tr = {}
        # ★키가 없으면 번역이 **조용히 빈 문자열**로 온다(로컬 실측 2026-09-08:
        #   SHORTS_GEMINI_KEYS 0개 → en='' → 핀터레스트가 한국어로 검색해 0건).
        #   그 경우 _kw_for가 ko로 폴백하므로 종전 동작이 된다 — 나빠지지 않는다.

    slots = {}
    for platform, chain in _CHAIN.items():
        for lang in _LANGS_BY_PLATFORM.get(platform, ("ko",)):
            kw = _kw_for(lang, ko, tr)
            if not kw:
                continue
            # 번역이 원문과 같으면(폴백·영어입력) 같은 검색을 두 번 돌리지 않는다.
            key = platform if lang == "ko" else "%s@%s" % (platform, lang)
            if any(v[1] == kw for k, v in slots.items() if k.split("@")[0] == platform):
                continue
            slots[key] = (chain, kw)

    return search_chain.search_many_kw(slots, max_results, _COST, keyword=ko)
