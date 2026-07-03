"""뉴스 매칭 (백그라운드 잡용, 토큰0).
 - 섹터 테마뉴스: 네이버 뉴스 검색 API (테마+맥락어 + 호재랭킹 + 노이즈컷)
 - 종목뉴스:     네이버 증권 종목뉴스 API (큐레이션, 키 불필요)
서버 백그라운드 스레드에서 호출한다.
"""
import os, json, re, urllib.request, urllib.parse
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ROOT = Path(__file__).resolve().parent.parent

# .env 자동 로드 (로컬). 서버는 systemd env로 주입됨.
_env = ROOT / ".env"
if _env.exists():
    for _l in _env.read_text(encoding="utf-8").splitlines():
        if "=" in _l and not _l.startswith("#"):
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

_KW_PATH = ROOT / "pipeline" / "sector_news_keywords.json"

HOJAE = ["수주", "계약", "실적", "급등", "강세", "신고가", "수혜", "호재", "증설", "공급",
         "투자", "최대", "흑자", "전망", "목표주가", "상향", "돌파", "관련주", "테마",
         "출시", "승인", "협력", "합작", "진출", "역대", "훈풍", "기대감"]
NOISE = ["추미애", "이재명", "문재인", "검찰", "취임", "폭염", "날씨", "도지사", "국회",
         "대통령", "장관", "선거", "정당", "부동산 대책"]


def _clean(t: str) -> str:
    t = re.sub(r"<[^>]+>", "", t or "")
    for a, b in [("&quot;", '"'), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&#39;", "'")]:
        t = t.replace(a, b)
    return t.strip()


def load_keywords() -> dict:
    try:
        return json.loads(_KW_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _search(query: str, display: int = 15, sort: str = "date") -> list:
    if not CLIENT_ID or not CLIENT_SECRET:
        return []
    url = (f"https://openapi.naver.com/v1/search/news.json"
           f"?query={urllib.parse.quote(query)}&display={display}&sort={sort}")
    req = urllib.request.Request(url, headers={
        "X-Naver-Client-Id": CLIENT_ID, "X-Naver-Client-Secret": CLIENT_SECRET})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read().decode("utf-8")).get("items", [])
    except Exception:
        return []


MAX_AGE_DAYS = 3   # 이보다 오래된 뉴스는 점수와 무관하게 후순위(신선한 게 없을 때만 노출)


def sector_news(code, kw_map=None, top: int = 2) -> list:
    """섹터 테마뉴스: 최근 MAX_AGE_DAYS 이내 우선 + 그 안에서 호재키워드 랭킹. 정치/날씨 노이즈컷."""
    m = (kw_map or load_keywords()).get(str(code)) or {}
    q = m.get("q")
    if not q:
        return []
    must = m.get("must") or []
    now = datetime.now(timezone.utc)
    # "OO 관련주" 단일쿼리는 약해서 일반 시황만 잡힘(자동차 사례). must의 구체적 종목명
    # (현대차·기아 등)으로 만든 보조쿼리를 추가해 신선한 섹터기사를 확보한다.
    queries = [q]
    named = [w for w in must[1:] if len(w) >= 2][:3]   # must[0]=섹터 일반어라 제외, 이후=종목/고유명
    if named:
        queries.append(" ".join(named[:2]))
    # sort=date + sim 둘 다 조회해 후보 풀 확대 후 must필터로 걸러낸다.
    seen_urls, items = set(), []
    for qq in queries:
        for it in _search(qq, display=15, sort="date") + _search(qq, display=15, sort="sim"):
            u = it.get("originallink") or it.get("link") or it.get("title")
            if u in seen_urls:
                continue
            seen_urls.add(u)
            items.append(it)
    ranked = []
    for it in items:
        t = _clean(it.get("title", ""))
        if not t or any(w in t for w in NOISE):
            continue
        if must and not any(w in t for w in must):
            continue   # 테마 필수어 제목 미포함 → 오매칭 제외
        score = sum(1 for w in HOJAE if w in t)
        pub = it.get("pubDate", "")
        age_days = _age_days(pub, now)
        ranked.append((age_days, score, t, pub, it.get("originallink") or it.get("link")))
    fresh = [r for r in ranked if r[0] <= MAX_AGE_DAYS]
    pool = fresh if fresh else ranked   # 최근 뉴스가 아예 없으면 전체 중 최신순으로 대체
    pool.sort(key=lambda x: (-x[1], x[0]) if fresh else x[0])
    return [{"title": t, "date": _fmt_rss(p), "url": u, "score": s} for age, s, t, p, u in pool[:top]]


def _age_days(pub: str, now: datetime) -> float:
    try:
        d = parsedate_to_datetime(pub)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (now - d).total_seconds() / 86400
    except Exception:
        return 999.0


def _domain(url: str) -> str:
    try:
        net = urllib.parse.urlparse(url).netloc
        return net[4:] if net.startswith("www.") else net
    except Exception:
        return ""


# 언론 관용 약칭(정식명만 요구하면 "삼전"·"하닉" 같은 축약 표기 기사가 다 걸러짐)
_STOCK_ABBREV = {
    "삼성전자": ["삼전"],
    "SK하이닉스": ["하이닉스", "하닉", "SK닉스"],
    "LG에너지솔루션": ["LG엔솔", "엔솔"],
    "삼성바이오로직스": ["삼바"],
    "현대차": ["현차"],
    "기아": ["기아차"],
    "POSCO홀딩스": ["포스코"],
    "한화에어로스페이스": ["한화에어로"],
    "두산에너빌리티": ["두산에너"],
    "SK이노베이션": ["SK이노"],
    "HD현대중공업": ["현대중공업"],
    "HD한국조선해양": ["한국조선해양"],
    "NAVER": ["네이버"],
}


def stock_news(code, name: str = "", top: int = 3) -> list:
    """종목뉴스: 종목명으로 네이버 뉴스검색(최신+정확도 합산, 호재랭킹, 노이즈컷+관련성필터).
    네이버증권 '종목뉴스' 탭은 커버리지 적은 종목엔 무관한 시황 잡뉴스로 채우는 경우가
    많아(예: SK스퀘어 → 코스피 지수 기사만) 검색 기반으로 전환. 검색만으로는 "코스피" 같은
    고빈도 시황 기사가 여전히 섞여들어와 제목에 종목명(+약칭)이 있는 것만 남긴다.
    name 없으면(구버전 호출부 호환) 예전 네이버증권 종목뉴스 API로 폴백."""
    if not name or not name.strip():
        return _stock_news_by_code(code, top)
    name = name.strip()
    cands = {name} | set(_STOCK_ABBREV.get(name, []))
    now = datetime.now(timezone.utc)
    seen_urls, items = set(), []
    for it in _search(name, display=20, sort="date") + _search(name, display=20, sort="sim"):
        u = it.get("originallink") or it.get("link") or it.get("title")
        if u in seen_urls:
            continue
        seen_urls.add(u)
        items.append(it)
    ranked = []
    for it in items:
        t = _clean(it.get("title", ""))
        if not t or any(w in t for w in NOISE):
            continue
        if not any(c in t for c in cands):
            continue   # 제목에 종목명(+약칭) 없음 → 시황 잡뉴스로 판단, 제외
        score = sum(1 for w in HOJAE if w in t)
        pub = it.get("pubDate", "")
        age_days = _age_days(pub, now)
        link = it.get("originallink") or it.get("link") or ""
        ranked.append((age_days, score, t, pub, link))
    fresh = [r for r in ranked if r[0] <= MAX_AGE_DAYS]
    pool = fresh if fresh else ranked   # 최근 뉴스가 아예 없으면 전체 중 최신순으로 대체
    pool.sort(key=lambda x: (-x[1], x[0]) if fresh else x[0])
    return [{"title": t, "src": _domain(u), "date": _fmt_rss(p), "related": 1, "url": u}
            for age, s, t, p, u in pool[:top]]


def _stock_news_by_code(code, top: int = 3) -> list:
    """(구) 네이버증권 종목뉴스 API — 종목명을 모를 때만 쓰는 폴백(큐레이션·관련뉴스 그룹)."""
    cc = str(code).zfill(6)
    url = f"https://m.stock.naver.com/api/news/stock/{cc}?pageSize={top + 3}&page=1"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Referer": "https://m.stock.naver.com/"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            groups = json.load(r)
    except Exception:
        return []
    out = []
    for g in (groups or []):
        it = (g.get("items") or [{}])[0]
        dt = it.get("datetime", "")
        dt = f"{dt[4:6]}/{dt[6:8]} {dt[8:10]}:{dt[10:12]}" if len(dt) >= 12 else dt
        oid, aid = it.get("officeId"), it.get("articleId")
        out.append({"title": _clean(it.get("title", "")), "src": it.get("officeName"),
                    "date": dt, "related": g.get("total", 1),
                    "url": f"https://n.news.naver.com/mnews/article/{oid}/{aid}" if oid and aid else ""})
        if len(out) >= top:
            break
    return out


def _fmt_rss(pub: str) -> str:
    """'Wed, 01 Jul 2026 20:07:00 +0900' → '07/01 20:07'."""
    try:
        from email.utils import parsedate_to_datetime
        d = parsedate_to_datetime(pub)
        return d.strftime("%m/%d %H:%M")
    except Exception:
        return (pub or "")[:16]


if __name__ == "__main__":
    import sys
    kw = load_keywords()
    print("섹터뉴스 신재생:", json.dumps(sector_news("385510", kw), ensure_ascii=False))
    print("종목뉴스 SK이터닉스:", json.dumps(stock_news("475150"), ensure_ascii=False))
