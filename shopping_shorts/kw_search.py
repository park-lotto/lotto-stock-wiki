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
    # ★유료 폴백(apify_tiktok)은 기본으로 빠진다 — 세션 없으면 0건이 되고,
    #   사장님은 새 탭 아이콘(🎵)으로 간다. 되살리려면 KW_SEARCH_TIKTOK_APIFY=1.
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

# ── 노브 적용 (2026-09-08) — 끄는 판단은 config, 반영은 **여기 한 곳**에서만 한다.
#    호출부·엔드포인트·프론트는 어느 플랫폼이 도는지 모른 채 그대로 돈다.
#    남는 게 0개가 되는 일은 없다(유튜브·핀터레스트·네이버클립은 노브가 없다).
if not config.KW_SEARCH_INSTAGRAM:
    _CHAIN.pop("instagram", None)
if not config.KW_SEARCH_TIKTOK_APIFY:
    # 유료 백엔드만 뺀다 — 세션이 생기면 pw_tiktok이 그대로 무료로 성공한다.
    _CHAIN["tiktok"] = [fn for fn in _CHAIN["tiktok"] if fn is not kw_backends.apify_tiktok]


def search(keyword, max_results=10):
    """한국어 키워드 → 인스타+틱톡+유튜브+핀터레스트 결과(플랫폼 병렬).

    반환: {"items": [...], "count": N, "keyword": kw, "meta": {플랫폼: {...}}}
    items는 렌즈 카드와 같은 스키마다(cn_backends.normalize 공용)."""
    return search_chain.search_many(_CHAIN, keyword, max_results, _COST)
