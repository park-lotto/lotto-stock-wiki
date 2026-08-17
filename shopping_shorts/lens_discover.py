"""SerpApi Google Lens로 프레임을 역검색해 유사 동영상(5개 플랫폼)만 추린다.

visual_matches에는 동영상 여부 필드가 없어(2026-07-14 실측: link/source/title/
thumbnail만) link 도메인 화이트리스트로 판별한다. product_identify.py와 같은
google_lens 엔진이지만 용도가 달라(제품명 추론 X, 유사영상 발굴 O) 분리."""
import os
import re
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, quote, parse_qs
from shopping_shorts import serpapi_client
from shopping_shorts.config import SERPAPI_KEY, SERPAPI_KEYS

_LENS_ENDPOINT = "https://serpapi.com/search"
_IMGUR_ENDPOINT = "https://api.imgur.com/3/image"
# imgur 익명 업로드용 Client-ID. 전용 발급분을 IMGUR_CLIENT_ID env로 넣는 걸 권장하고,
# 없으면 공개 테스트 ID로 폴백(2026-07-14 실증 동작). imgur는 Google이 상시 크롤링하는
# 도메인이라 갓 올린 이미지도 렌즈가 즉시 읽는다(우리서버 URL은 인덱싱 지연으로 0개).
# ⚠️ imgur이 2025년부터 신규 앱(전용 Client-ID) 등록을 정책적으로 막아놔서(재개시점
# 미공지, GitHub 이슈 다수) 폴백 ID를 발급받을 수 없다. 게다가 이 공개 테스트 ID는
# gallery-dl·Rimgo 등 무관한 대형 툴도 공유해 남용 시 우리와 무관하게 막힐 위험이 있어
# imgbb를 1순위로 승격했다(아래 upload_frame).
_IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID", "546c25a59c58ad7")
_IMGBB_ENDPOINT = "https://api.imgbb.com/1/upload"
_IMGBB_API_KEY = os.environ.get("IMGBB_API_KEY", "")
_ACCOUNT_ENDPOINT = "https://serpapi.com/account"
# 실잔량 조회 캐시(초). 렌즈 호출마다 SerpApi를 한 번 더 왕복하면 체감지연이 늘어나므로
# 캐시한다. 렌즈 1클릭이 최대 _MAX_CALLS(3)회를 태우니 TTL 동안 최대 그만큼만 어긋난다.
_QUOTA_TTL_S = float(os.environ.get("LENS_QUOTA_TTL", "600"))
_quota_cache = {"at": 0.0, "left": None}
_MAX_ATTEMPTS = 3          # 일시적 'no results'에 대한 재시도 횟수
_RETRY_SLEEP = 2.5         # 재시도 전 대기(초) — 갓 호스팅된 이미지가 인덱싱될 시간

# 플랫폼 판별 — 도메인 접미사 매칭(서브도메인·www 무관). 순서=표시 우선순위.
_PLATFORM_DOMAINS = [
    ("youtube", ("youtube.com", "youtu.be")),
    ("tiktok", ("tiktok.com",)),
    ("instagram", ("instagram.com",)),
    ("xiaohongshu", ("xiaohongshu.com", "xhslink.com")),
    ("douyin", ("douyin.com", "iesdouyin.com")),
]


def account_searches_left(force=False):
    """SerpApi **실잔량**(모든 키의 total_searches_left 합). 못 읽으면 None.

    왜 필요한가 — 우리 `lens_count`는 사장님 클릭 1회당 1만 올리는데 실제로는
    로케일 3벌 × 재시도로 **최대 3회**가 나간다. 2026-08-17 서버 실측:
    우리 카운터 196/500인데 실제 SerpApi는 369/500 소진(남은 131).
    상수 × 키개수로는 이 어긋남을 영영 못 따라잡고, 키가 다 죽는 순간
    렌즈는 '한도 초과' 안내도 없이 조용히 빈손이 된다.

    조회 실패(네트워크·키 오류)는 **None**으로 돌려 호출부가 기존 상수 방식으로
    폴백하게 한다 — 잔량을 못 읽었다고 렌즈를 막아버리면 더 나쁘다."""
    now = time.time()
    if not force and _quota_cache["left"] is not None \
            and now - _quota_cache["at"] < _QUOTA_TTL_S:
        return _quota_cache["left"]
    keys = [k for k in (SERPAPI_KEYS or ([SERPAPI_KEY] if SERPAPI_KEY else [])) if k]
    if not keys:
        return None
    total = 0
    seen = False
    for k in keys:
        try:
            r = requests.get(_ACCOUNT_ENDPOINT, params={"api_key": k}, timeout=15)
            data = r.json() if r.status_code == 200 else None
        except (requests.RequestException, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        left = data.get("total_searches_left")
        if isinstance(left, bool) or not isinstance(left, (int, float)):
            continue       # 문자열·None을 숫자로 넘겨받아 0으로 뭉개지 않는다
        total += max(0, int(left))
        seen = True
    if not seen:
        return None        # 한 키도 못 읽었다 = 모른다 (0이 아니다)
    _quota_cache["at"] = now
    _quota_cache["left"] = total
    return total


def upload_to_imgur(image_bytes, client_id=None):
    """캡처 이미지 바이트 → imgur 익명 업로드 → 공개 URL(실패 시 None).

    Google Lens는 갓 호스팅된 우리서버 이미지를 인덱싱 전이라 못 읽어 0개를 주는데
    (2026-07-14 실측), imgur URL은 상시 크롤링돼 즉시 매칭된다(같은 프레임 59개).
    그래서 렌즈 검색 전 캡처를 imgur로 옮긴다."""
    cid = client_id or _IMGUR_CLIENT_ID
    try:
        r = requests.post(_IMGUR_ENDPOINT,
                          headers={"Authorization": f"Client-ID {cid}"},
                          files={"image": image_bytes}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    if not data.get("success"):
        return None
    return data.get("data", {}).get("link") or None


def upload_to_imgbb(image_bytes, api_key=None):
    """캡처 이미지 바이트 → imgbb 업로드 → 공개 URL(실패 시 None).
    2026-07-14 실측: 프레시 이미지 기준 imgur과 동일하게 대기 0초·즉시 60개 매칭
    (imgur=60/imgbb=60 동시비교). 전용 API키 발급이 열려있어(imgur은 막힘) 1순위로 쓴다."""
    key = api_key or _IMGBB_API_KEY
    if not key:
        return None
    try:
        r = requests.post(_IMGBB_ENDPOINT, data={"key": key},
                          files={"image": image_bytes}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    return data.get("data", {}).get("url") or None


def upload_frame(image_bytes):
    """렌즈 검색용 캡처 프레임 업로드. imgbb(전용키, 1순위) → imgur(공유 공개ID,
    2순위 폴백) 순. 둘 다 실패(키 없음·네트워크 오류 등)하면 None — 호출부(app.py)가
    자체서버 URL로 최종 폴백한다(단, 인덱싱 지연으로 결과가 비어있을 수 있음)."""
    return upload_to_imgbb(image_bytes) or upload_to_imgur(image_bytes)


def _platform_of(link):
    host = urlparse(link or "").netloc.lower()
    for name, domains in _PLATFORM_DOMAINS:
        if any(host == d or host.endswith("." + d) for d in domains):
            return name
    return None


_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]{2,}")
# 캡션에 흔한 무의미 고빈도어 — 남기면 거의 모든 제목과 매칭돼 필터 무력화됨.
_STOPWORDS = {
    "그리고", "진짜", "완전", "오늘", "이거", "저거", "제가", "나만", "너무", "정말",
    "이번", "우리", "해서", "하는", "했어요", "합니다", "있는", "있어요", "같은", "위한",
    "the", "and", "for", "with", "this", "that", "from", "you", "your", "shorts",
}


def _extract_keywords(caption):
    """캡션 → 2자 이상 토큰 집합(불용어 제외). 소스 자체가 짧거나 비어있으면 빈 집합."""
    if not caption:
        return set()
    tokens = _TOKEN_RE.findall(caption.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _title_matches(keywords, title):
    """소스 키워드가 하나라도 제목에 부분포함되면 True, 있는데 하나도 없으면 False.
    소스 키워드 자체가 없으면(캡션 없음/전부 불용어) 판정불가 None — 필터 대상 아님."""
    if not keywords:
        return None
    title_l = (title or "").lower()
    return any(k in title_l for k in keywords)


_IG_PERMALINK_RE = re.compile(r"/(?:p|reel|reels|tv)/[A-Za-z0-9_-]+")


def _is_watchable(platform, link):
    """개별 재생 가능한 영상 URL만 True. 렌즈(Google Lens)는 개별 영상이 아닌 검색·모음·
    SEO 페이지를 섞어 반환한다 — 틱톡 discover/tag/search/music(2026-07-14 실측),
    인스타 /popular/{제목슬러그}·/explore·프로필(2026-07-19 실사고: 이런 URL이 렌즈 즐겨찾기로
    담겨 매칭 단계에서 'Apify 해석 실패'로 배치 전체를 죽였다). 다운로드 가능한 permalink만
    받게 입구에서 거른다.
    - 틱톡: /video/숫자
    - 인스타: /p·/reel·/reels·/tv + 코드(개별 게시물). 그 외(/popular·/explore·프로필)는 배제.
    - 나머지(유튜브·중국플랫폼)는 그대로(대부분 개별 콘텐츠)."""
    path = urlparse(link or "").path.lower()
    if platform == "tiktok":
        return "/video/" in path
    if platform == "instagram":
        return bool(_IG_PERMALINK_RE.search(path))
    return True   # 유튜브·중국플랫폼은 그대로(대부분 개별 콘텐츠)


def is_photo_post(platform, link):
    """영상이 아닐 가능성이 높은 게시물인가(카드뉴스·사진·카러셀). 확정이 아니라 '후보'다.

    사장님 제보(2026-07-30): 렌즈 결과에 인스타 카드뉴스(사진 여러 장)가 많이 섞인다.
    렌즈 visual_matches에는 동영상 여부 필드가 없고(모듈 최상단 주석), 인스타 실조회는
    Apify 유료라 결과마다 확인할 수 없다. 그래서 **URL 경로**라는 공짜 신호를 쓴다:
      /reel·/reels·/tv = 영상 확정 → False
      /p/              = 사진·카러셀이 대부분 → True (요즘 인스타는 영상을 reel로 보낸다)
    ⚠️ /p/에도 옛 동영상 게시물이 있어 완벽하지 않다 → 프론트에서 '하드 제외'가 아니라
    끌 수 있는 토글(기본 켜짐)로 쓴다. 인스타 외 플랫폼은 판정하지 않는다(False):
    틱톡 사진첩(/photo/)은 _is_watchable이 이미 입구에서 거른다."""
    if platform != "instagram":
        return False
    path = urlparse(link or "").path.lower()
    if re.search(r"/(?:reel|reels|tv)/", path):
        return False
    return "/p/" in path


# ── oEmbed 실검증(2026-08-03) ────────────────────────────────────────────────
# 사장님 제보 '렌즈 링크가 다른 영상으로 연결': 구글 렌즈가 페이지의 추천영상 썸네일을
# 그 페이지 URL과 짝지어 반환하는 데이터 어긋남(우리 배선은 무결 — 조사 기록 handoff).
# 틱톡·유튜브는 공식 oEmbed가 무료·무인증이라, 결과 URL을 실조회해 **실제로 열리는
# 영상의 제목·썸네일로 교체**한다 → 보이는 것과 열리는 것이 항상 일치. 404(삭제·비공개)는
# link_ok=False로 표시해 프론트가 숨긴다. 타임아웃·기타 실패는 원본 유지(no-op) —
# 검증 불가가 회수율을 깎으면 안 된다. 인스타는 공개 oEmbed가 없어 대상 외.
_OEMBED_TIMEOUT = 4


def _oembed_endpoint(platform, link):
    if platform == "tiktok":
        return "https://www.tiktok.com/oembed?url=" + quote(link, safe="")
    if platform == "youtube":
        return "https://www.youtube.com/oembed?format=json&url=" + quote(link, safe="")
    return None


def verify_matches(items, keywords=None):
    """틱톡·유튜브 항목을 oEmbed로 실조회해 제목·썸네일을 실제 값으로 교체(in-place).

    제목이 바뀌면 match(키워드 일치)도 실제 제목 기준으로 다시 판정한다."""
    def _one(i):
        ep = _oembed_endpoint(i.get("platform"), i.get("url") or "")
        if not ep:
            return
        try:
            r = requests.get(ep, timeout=_OEMBED_TIMEOUT)
        except requests.RequestException:
            return
        status = getattr(r, "status_code", None)   # 테스트 더블이 상태코드 없이 올 수 있다
        if status == 404:
            i["link_ok"] = False       # 삭제·비공개 — 열면 엉뚱한 피드로 떨어진다
            return
        if status != 200:
            return
        try:
            d = r.json()
        except (ValueError, TypeError):
            return
        if not isinstance(d, dict):
            return
        if d.get("title"):
            i["title"] = d["title"]
            i["match"] = _title_matches(keywords or set(), d["title"])
        if d.get("thumbnail_url"):
            i["thumbnail"] = d["thumbnail_url"]
        i["verified"] = True
    def _safe(i):
        # 검증은 부가기능 — 어떤 예외도 렌즈 검색 자체를 죽이면 안 된다(원본 유지 no-op).
        try:
            _one(i)
        except Exception:
            pass
    targets = [i for i in items if i.get("platform") in ("tiktok", "youtube")]
    if not targets:
        return items
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(_safe, targets))
    return items


# 렌즈 호출 로케일. ko=한국어 자막판, en=자막 없는 해외 원본(2026-08-16 실측).
# 환경변수로 줄이거나 늘릴 수 있다 — SerpApi를 로케일당 1회씩 쓴다.
#   LENS_LOCALES="ko:kr"        → 예전처럼 1회만(한도 아낄 때)
#   LENS_LOCALES="ko:kr,en:us"  → 기본값
_LENS_LOCALES = tuple(
    tuple((p.split(":", 1) + ["kr"])[:2])
    # ⚠️ 중국어는 country=**tw**다. 본토(cn)는 구글이 서비스하지 않아 90초를 끌다
    #    503("We couldn't get valid results")을 뱉는다 — 실측 2026-08-16:
    #      zh-cn/cn  90.3초 → 503, 0건
    #      zh-cn/tw   4.0초 → 200, 60건 ✅
    #    zh 단독(hl=zh)은 400 "Unsupported hl parameter". zh-cn 표기가 맞다.
    for p in os.environ.get("LENS_LOCALES", "ko:kr,en:us,zh-cn:tw").split(",") if p.strip()
) or (("ko", "kr"),)

# ★렌즈 1번 클릭당 SerpApi 호출 **총 상한**(2026-08-16 사장님 "무조건 한번클릭에 3회로").
#   로케일 3벌 × 재시도(_MAX_ATTEMPTS 3) = 최대 9회까지 불어날 수 있어서 뚜껑을 씌운다.
_MAX_CALLS_PER_SEARCH = int(os.environ.get("LENS_MAX_CALLS", "3"))

# ★로케일마다 **최소 1회는 보장**한다(2026-08-16 사장님 "중국어가 얼마나 나올지 보고싶다").
#   상한만 두면 앞 로케일이 재시도로 예산을 다 먹어 뒤 로케일(zh)이 아예 안 돈다
#   — 실제로 그래서 zh가 한 번도 실행되지 않았다. 재시도는 "남는 예산"으로만 한다.
#   즉 로케일이 3개면 각 1회씩은 확보하고, 예산이 남을 때만 빈 결과를 재시도한다.
_RESERVE_PER_LOCALE = True

# 구글렌즈 응답에서 결과가 들어오는 리스트들.
# ★visual_matches만 읽다가 40%를 버리고 있었다(2026-08-16 실측):
#     visual_matches  60건 → 인7 틱6 유6
#     organic_results  8건 → 인3 틱2 유0   ← 안 읽었음
#     short_videos    10건 → 인2 틱3 유4   ← 안 읽었음(숏폼 전용인데!)
#   합치면 인12 틱11 유10 = 19건→33건. **추가 비용 0원**(이미 받은 응답이다).
#   "유튜브·틱톡이 렌즈로 안 나온다"의 진짜 원인이 이것이었다.
_RESULT_FIELDS = ("visual_matches", "organic_results", "short_videos")


# 렌즈에서 잘라낼 길이 기준(초). short_videos 항목엔 duration이 "0:13"·"1:02:33"
# 형태로 온다(실측). 이보다 길면 롱폼으로 보고 아예 결과에서 뺀다 — 렌즈는 숏폼
# 소재를 찾는 자리다. 길이를 모르는 항목(visual_matches·organic_results)은 건드리지
# 않는다(모르는 것을 자르면 멀쩡한 릴스가 통째로 사라진다).
_LONGFORM_MAX_SECS = float(os.environ.get("LENS_LONGFORM_MAX", "180"))
_SHORT_MAX_SECS = 90        # '숏폼만' 토글 기준(다른 모듈과 같은 값)


def _duration_secs(raw):
    """ "0:13" / "1:02:33" / 45 → 초. 못 읽으면 None(=길이 모름, 자르지 않는다)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    parts = str(raw).strip().split(":")
    if not all(p.isdigit() for p in parts) or not 1 <= len(parts) <= 3:
        return None
    secs = 0.0
    for p in parts:                      # 앞에서부터 60배씩 누적 → 시:분:초 모두 처리
        secs = secs * 60 + int(p)
    return secs


def _dedup_key(link):
    """같은 영상인지 판정할 키. 로케일 2벌·필드 3개를 합치므로 중복이 반드시 생긴다.

    ⚠️ 쿼리스트링을 무조건 버리면 **유튜브가 뭉개진다** — 유튜브는 영상 ID가
       경로가 아니라 쿼리(`/watch?v=XXX`)에 있어서, ?앞만 자르면 서로 다른
       영상이 전부 'youtube.com/watch'라는 같은 키가 돼 1개만 남는다
       (2026-08-16 테스트가 잡아냄 — 라이브에 나갔으면 유튜브가 1개로 보였다).
       그래서 유튜브만 v 파라미터를 키에 포함한다."""
    if not link:
        return ""
    parsed = urlparse(link)
    base = f"{parsed.netloc}{parsed.path}".rstrip("/").lower()
    if _platform_of(link) == "youtube":
        vid = parse_qs(parsed.query).get("v", [""])[0]
        if vid:
            return f"{base}?v={vid}"
        # youtu.be/XXX·/shorts/XXX 는 경로에 ID가 있어 base로 충분
    return base


def _lens_call(image_url, keys, hl, country, timeout, budget=None, dead=None):
    """로케일 1개로 구글렌즈 1회 호출 → 결과 dict 리스트(필드 3개 합침).

    budget: [남은 호출 수] 리스트(호출부와 공유). 실제로 SerpApi를 때릴 때마다
    1씩 깎고, 0이 되면 즉시 멈춘다 — 재시도가 예산을 넘어 새지 않게 한다.

    키 로테이션(2026-07-26): 현재 키가 월 한도를 소진하면(429 등) 다음 키로 넘어간다.
    소진이 아닌 진짜 빈 결과("no results")는 같은 키로 재시도(_MAX_ATTEMPTS) — 갓
    호스팅된 이미지가 인덱싱될 시간을 준다. 그래서 재시도는 키별 안쪽 루프로 돈다.

    파라미터가 결과를 좌우한다(2026-07-14 라이브 실측, 6프레임 대조):
      type=visual_matches (별도 엔드포인트) → 많은 프레임에서 0개("no results")
      type 없는 기본 all모드 → 모든 프레임 59~60개 ✅
    즉 type을 넣으면 오히려 깨진다. all모드 응답에서 필드들을 꺼내 쓴다."""
    for key in keys:
        if dead is not None and key in dead:
            continue                     # 이번 검색에서 이미 소진 확인된 키 — 건너뛴다
        params = {"engine": "google_lens", "hl": hl, "country": country,
                  "url": image_url, "api_key": key}
        exhausted = False
        for attempt in range(_MAX_ATTEMPTS):
            if budget is not None:
                if budget[0] <= 0:
                    return []            # 예산 소진 — 더 때리지 않는다
                budget[0] -= 1
            try:
                r = requests.get(_LENS_ENDPOINT, params=params, timeout=timeout)
                data = r.json()
            except (requests.RequestException, ValueError):
                return []
            if serpapi_client.is_exhausted(getattr(r, "status_code", 200), data):
                # ★소진된 키는 **검색을 안 해준다** — 예산을 돌려준다(2026-08-16).
                #   안 그러면 소진 키 하나가 로케일 예산을 먹어치워, 실제로는
                #   ko 한 벌만 돌고 en·zh가 통째로 굶는다(라이브에서 실제로 발생:
                #   ko 69건 / en 0건 / zh 미실행).
                if budget is not None:
                    budget[0] += 1
                if dead is not None:
                    dead.add(key)  # 다음 로케일이 같은 키를 또 찌르지 않게
                exhausted = True   # 이 키 소진 → 바깥 루프에서 다음 키로
                break
            try:
                r.raise_for_status()
            except requests.RequestException:
                return []
            out = []
            for field in _RESULT_FIELDS:
                v = data.get(field)
                if isinstance(v, list):
                    out.extend(m for m in v if isinstance(m, dict))
            if out:
                return out
            if attempt < _MAX_ATTEMPTS - 1:
                time.sleep(_RETRY_SLEEP)   # 인덱싱 대기 후 재시도
        if exhausted:
            continue                       # 다음 키로
        return []                          # 이 키로 처리 완료(결과 없음)
    return []


def search_similar_videos(image_url, api_key=None, timeout=60, source_caption=None, stats=None):
    """공개 이미지 URL → [{platform, url, title, thumbnail, match}]. 5개 동영상 플랫폼만.
    키 없음·호출 실패 시 [].

    match: source_caption 키워드가 결과 제목에 있으면 True, 있는데 없으면 False,
    (캡션 없음 등으로) 판정 자체가 불가하면 None. 렌즈는 시각 유사도만 보기 때문에
    장르는 같지만 다른 주제인 결과가 섞이는 문제(2026-07-14 실측)를 프론트에서
    표시용으로 구분하기 위함 — 결과를 제거하진 않는다(교차언어 플랫폼은 매칭 불가라
    False가 나올 수 있어 하드 필터링하면 회수율이 떨어짐)."""
    # api_key는 문자열 하나 또는 목록. ★사용자 등록키(BYOK)가 오면 그것만 쓴다 —
    # 여기서 사장님 키를 섞으면 keyroute의 "폴백 없음"이 조용히 깨진다(0순위-B).
    if api_key:
        keys = list(api_key) if isinstance(api_key, (list, tuple)) else [api_key]
        keys = [k for k in keys if k]
    else:
        keys = SERPAPI_KEYS or ([SERPAPI_KEY] if SERPAPI_KEY else [])
    if not keys:
        return []
    keywords = _extract_keywords(source_caption)

    # ★로케일 2벌(2026-08-16 사장님 "다른 프로그램은 자막없는 원본을 가져온다").
    #   ko/kr만 쓰면 **한국어 자막판**만 올라온다. en/us는 같은 이미지에 대해
    #   거의 겹치지 않는 **해외 원본**을 준다 — 라이브 실측 2장:
    #     이미지1  ko 19건(한글제목16) / en 16건(한글1·그외14) → 합집합 34건
    #     이미지2  ko 15건(한글8)      / en 24건(한글0·그외24) → 합집합 38건
    #   겹침이 1건 남짓이라 합치면 결과가 두 배가 된다. 대신 SerpApi를 로케일당
    #   1회씩 쓴다(렌즈 1번 = 2회 차감). 아래 _LENS_LOCALES로 조절 가능.
    matches = []
    # ★호출 예산 — 로케일들이 **공유**한다. 재시도까지 합쳐 총 _MAX_CALLS_PER_SEARCH회.
    #   리스트로 넘겨 _lens_call 안에서 깎는다(정수는 값 복사라 안 깎인다).
    budget = [_MAX_CALLS_PER_SEARCH]
    # 이번 검색에서 소진으로 확인된 키 — 로케일마다 같은 죽은 키를 다시 찌르지 않는다
    # (라이브 실측: 로케일 3벌이면 죽은 키를 3번 찔러 왕복만 낭비했다).
    dead = set()
    for i, (hl, country) in enumerate(_LENS_LOCALES):
        if budget[0] <= 0:
            break                        # 예산 소진 → 남은 로케일은 건너뛴다
        # ★뒤 로케일 몫을 남겨둔다 — 앞 로케일의 재시도가 예산을 다 먹으면
        #   zh가 아예 안 돈다(사장님 "중국어가 얼마나 나올지 보고싶다").
        #   남은 로케일 수만큼 예약해두고, 이번 로케일은 나머지만 쓴다.
        reserve = (len(_LENS_LOCALES) - i - 1) if _RESERVE_PER_LOCALE else 0
        allow = max(1, budget[0] - reserve)
        sub = [min(allow, budget[0])]
        got = _lens_call(image_url, keys, hl, country, timeout, sub, dead)
        budget[0] -= (min(allow, budget[0]) - sub[0])   # 실제로 쓴 만큼만 차감
        matches.extend(got)
        if stats is not None and isinstance(stats, dict):
            stats[f"raw_{hl}"] = len(got)
    if stats is not None and isinstance(stats, dict):
        # 실제로 '검색을 해준' 호출 수(소진 키 왕복은 환불되므로 여기 안 잡힌다).
        # 한도에 실제로 찍히는 건 이 숫자다.
        stats["serpapi_calls"] = _MAX_CALLS_PER_SEARCH - budget[0]
    # ★인스타 편차 계측(2026-08-14 사장님 "인스타는 0건이거나 왕창이거나 편차가 심하다").
    #   추측하지 않으려면 어디서 사라지는지 세야 한다. 렌즈 원본(visual_matches) 중
    #   인스타 링크가 몇 개였고, 그중 몇 개가 개별 게시물이 아니라(프로필·/explore·
    #   /popular 슬러그) 입구에서 잘렸고, 몇 개가 카드뉴스(/p/)인지를 응답에 싣는다.
    #   → 0건일 때 "렌즈가 아예 안 물어온 것"인지 "우리가 거른 것"인지 화면에서 갈린다.
    st = stats if isinstance(stats, dict) else {}
    st["raw_total"] = len(matches)
    st["ig_raw"] = 0
    st["ig_dropped_not_post"] = 0
    st["ig_photo"] = 0
    st["cut_photo"] = 0        # 사진·카드뉴스로 잘라낸 수
    st["cut_longform"] = 0     # 롱폼(길이 초과)으로 잘라낸 수
    out = []
    # ★중복 제거 — 로케일 2벌 + 필드 3개를 합치므로 같은 영상이 여러 번 올라온다.
    #   URL 기준(쿼리스트링 제외)으로 처음 것만 남긴다. 안 하면 화면에 같은 카드가
    #   두 번씩 뜬다(ko/en이 같은 영상을 줄 때).
    seen_urls = set()
    for m in matches:
        link = m.get("link") or ""
        platform = _platform_of(link)
        if platform == "instagram":
            st["ig_raw"] += 1
        if not platform or not _is_watchable(platform, link):
            if platform == "instagram":
                st["ig_dropped_not_post"] += 1
            continue
        key_url = _dedup_key(link)
        if key_url in seen_urls:
            continue
        seen_urls.add(key_url)

        # ★사진·롱폼은 **서버에서 잘라낸다** (2026-08-16 사장님 "그냥 자체 커트").
        #   예전엔 프론트 토글로 '가리기'만 해서 개수에는 계속 잡히고, 토글을 끄면
        #   다시 나왔다. 렌즈는 숏폼 소재를 찾는 자리라 애초에 담을 이유가 없다.
        if is_photo_post(platform, link):
            st["cut_photo"] += 1
            if platform == "instagram":
                st["ig_photo"] += 1
            continue
        dur = _duration_secs(m.get("duration"))
        if dur is not None and dur > _LONGFORM_MAX_SECS:
            st["cut_longform"] += 1
            continue

        title = m.get("title", "")
        out.append({
            "platform": platform,
            "url": link,
            "title": title,
            # organic_results엔 thumbnail이 없다(실측) — 없으면 빈 문자열로 두고
            # 프론트가 알아서 처리한다. 있는 필드(visual_matches·short_videos)는 그대로.
            "thumbnail": m.get("thumbnail", ""),
            "match": _title_matches(keywords, title),
            # 위에서 이미 잘라냈으므로 항상 False — 프론트 '🎬 영상만' 토글 호환용으로 남긴다.
            "is_photo": False,
            # 길이를 아는 것만 채운다(short_videos에만 있다). 프론트 '숏폼만' 토글이 본다.
            "is_short": True if dur is None else dur <= _SHORT_MAX_SECS,
            "duration": dur,
        })
    st["merged_total"] = len(matches)
    st["after_dedup"] = len(out)
    return verify_matches(out, keywords=keywords)
