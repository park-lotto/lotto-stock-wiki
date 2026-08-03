"""쿠팡 파트너스 연결 — 편집안이 뽑은 affiliate_target(이 영상이 팔 제품)을
실제 쿠팡 상품 URL/파트너스 링크로 잇고, 인포크링크에 올릴 최종 링크를 보관한다.

2026-07-28 수동 1단계로 시작한다. 파트너스 오픈API(상품검색·딥링크 생성)는
"최종 승인된" 파트너스 회원에게만 발급되고, 최종 승인은 실제 판매 실적이
발생해야 넘어간다 — 즉 지금은 검색 API를 쓸 수가 없다(키 유효기간도 180일이라
승인 후에도 만료 관리가 따로 필요하다). 그래서:

  · search_products() → 지금은 "쿠팡 검색 링크"만 돌려준다(사장님이 새 탭에서
                        직접 보고 상품 URL을 복사해 온다). 승인 후 이 함수
                        내부만 실제 API 호출로 갈아끼우면 호출부는 안 바뀐다.
  · to_deeplink()     → 지금은 원본 URL을 그대로 통과시키고 requires_approval을
                        세운다. 파트너스 웹에서 손으로 만든 링크를 붙여넣으면
                        그게 최종 링크가 된다.

search_links.py가 앞서 같은 길을 갔다(외부 API 품질/제약에 막혀 "링크만 만들고
사람이 클릭"으로 전환) — 같은 관례를 따른다.

★링크는 영상 픽셀에 안 들어간다. 상품 확정만 앞단(매칭 검토)에서 하고, 링크는
SEO 설명란·인포크링크 등록에서 꺼내 쓴다.
"""
import re
import urllib.parse

# 파트너스 웹에서 추적 링크를 직접 만드는 화면 — 승인 전엔 여기서 수동 생성한다.
PARTNERS_LINK_PAGE = "https://partners.coupang.com/#affiliate/ws/link"
# 인포크링크(링크인바이오) 관리 화면 — 최종 링크를 버튼으로 올리는 곳.
INPOCK_PAGE = "https://link.inpock.co.kr"

# 공정거래위원회 추천·보증 심사지침상 대가성 고지 문구(설명란·고정댓글 필수).
DISCLOSURE = "이 포스팅은 쿠팡 파트너스 활동의 일환으로, 이에 따른 일정액의 수수료를 제공받습니다."

_SEARCH_ENDPOINT = "https://www.coupang.com/np/search"

# 상품 URL: https://www.coupang.com/vp/products/1234567890?itemId=...&vendorItemId=...
_PRODUCT_RE = re.compile(r"coupang\.com/vp/products/(\d+)")
# 파트너스가 만들어주는 단축 링크 — 상품ID를 못 뽑으므로 그대로 보관한다.
_SHORTEN_RE = re.compile(r"^https?://link\.coupang\.com/\S+$")

# 상품 식별에 실제로 필요한 쿼리만 남긴다. 검색 유입 추적값(searchId·rank 등)은
# 링크만 길게 만들고 상품을 특정하지 않으며, 남기면 같은 상품인지 비교할 때
# 매번 다르게 보인다.
_KEEP_PARAMS = ("itemId", "vendorItemId")


def search_url(keyword):
    """키워드 → 쿠팡 검색결과 페이지 URL(새 탭으로 열어 사람이 고른다)."""
    return f"{_SEARCH_ENDPOINT}?q={urllib.parse.quote((keyword or '').strip())}"


def parse_product_url(url):
    """붙여넣은 URL → {"product_id", "url"}(정규화). 쿠팡 상품/파트너스 단축
    링크가 아니면 None — 엉뚱한 URL이 상품으로 저장되는 걸 입구에서 막는다."""
    url = (url or "").strip()
    if not url:
        return None
    if _SHORTEN_RE.match(url):
        # 파트너스 단축 링크는 이미 완성된 최종 링크라 손대지 않는다.
        return {"product_id": "", "url": url}
    m = _PRODUCT_RE.search(url)
    if not m:
        return None
    parsed = urllib.parse.urlsplit(url)
    kept = [(k, v) for k, v in urllib.parse.parse_qsl(parsed.query) if k in _KEEP_PARAMS]
    clean = urllib.parse.urlunsplit((
        "https", "www.coupang.com", f"/vp/products/{m.group(1)}",
        urllib.parse.urlencode(kept), "",
    ))
    return {"product_id": m.group(1), "url": clean}


def search_products(keyword, limit=10, access_key="", secret_key=""):
    """키워드 → 상품 후보. 승인 전(키 없음)엔 items=[] + search_url만 준다.

    반환 형태를 승인 후와 동일하게 고정해둔다 — 실제 API를 붙일 때 호출부는
    items가 채워지는 것만 보면 된다."""
    kw = (keyword or "").strip()
    if not kw:
        return {"ok": False, "error": "키워드가 비어있습니다", "items": [],
                "search_url": "", "requires_approval": False}
    if not (access_key and secret_key):
        return {
            "ok": True, "items": [], "search_url": search_url(kw),
            "requires_approval": True,
            "notice": "파트너스 오픈API 최종 승인 전이라 자동 검색을 못 합니다 — "
                      "검색 링크를 열어 상품 URL을 복사해 붙여넣으세요.",
        }
    raise NotImplementedError(
        "파트너스 승인 후 구현 — /v2/providers/affiliate_open_api/apis/openapi/"
        "products/search 를 HMAC 서명해 호출하고 items를 채운다."
    )


def to_deeplink(urls, access_key="", secret_key=""):
    """상품 URL 목록 → 파트너스 추적 링크. 승인 전엔 원본을 통과시키고
    requires_approval=True — 파트너스 웹에서 만든 링크를 사람이 붙여넣는다."""
    urls = [u for u in (urls or []) if u]
    if not (access_key and secret_key):
        return [{"original_url": u, "shorten_url": "", "requires_approval": True}
                for u in urls]
    raise NotImplementedError(
        "파트너스 승인 후 구현 — .../openapi/v1/deeplink 를 HMAC 서명해 호출."
    )


def build_product(keyword="", url="", name="", partner_url="", memo=""):
    """UI 입력 → mix_jobs.product_json에 저장할 레코드. 쿠팡 상품/파트너스
    링크가 아니면 ValueError — 저장 시점에 막아야 "등록했는데 링크가 엉뚱함"이
    안 생긴다."""
    parsed = parse_product_url(url)
    if parsed is None:
        raise ValueError("쿠팡 상품 URL이 아닙니다 "
                         "(coupang.com/vp/products/... 또는 link.coupang.com/...)")
    return {
        "keyword": (keyword or "").strip(),
        "name": (name or "").strip(),
        "product_id": parsed["product_id"],
        "url": parsed["url"],
        # 파트너스 웹에서 수동 생성한 추적 링크(승인 후엔 to_deeplink가 채운다).
        "partner_url": (partner_url or "").strip(),
        "memo": (memo or "").strip(),
        # 인포크링크에 실제로 올렸는지 — 자동화 전까진 사람이 체크한다.
        "inpock_registered": False,
    }


def final_link(product):
    """인포크링크에 넣을 최종 URL — 파트너스 링크가 있으면 그걸, 없으면 원본."""
    if not product:
        return ""
    return product.get("partner_url") or product.get("url") or ""


def description_block(product):
    """영상 설명란에 붙일 블록(상품 링크 + 대가성 고지). 상품이 없으면 빈 문자열.

    파트너스 링크가 아직 없으면 원본 상품 URL이 나가는데, 그건 수수료가 안
    붙는다 — 그래도 링크는 넣는다(시청자 편의). 경고는 화면에서 한다."""
    link = final_link(product)
    if not link:
        return ""
    name = (product.get("name") or product.get("keyword") or "상품").strip()
    return f"🛒 {name}\n{link}\n\n{DISCLOSURE}"
