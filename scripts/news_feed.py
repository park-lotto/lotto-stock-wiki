"""뉴스 매칭 (백그라운드 잡용, 토큰0).
 - 섹터 테마뉴스: 네이버 뉴스 검색 API (테마+맥락어 + 호재랭킹 + 노이즈컷)
 - 종목뉴스:     네이버 증권 종목뉴스 API (큐레이션, 키 불필요)
서버 백그라운드 스레드에서 호출한다.
"""
import os, json, re, urllib.request, urllib.parse
from pathlib import Path

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


def sector_news(code, kw_map=None, top: int = 2) -> list:
    """섹터 테마뉴스: 호재키워드 랭킹 + 정치/날씨 노이즈컷."""
    m = (kw_map or load_keywords()).get(str(code)) or {}
    q = m.get("q")
    if not q:
        return []
    ranked = []
    for it in _search(q, display=15):
        t = _clean(it.get("title", ""))
        if not t or any(w in t for w in NOISE):
            continue
        score = sum(1 for w in HOJAE if w in t)
        pub = it.get("pubDate", "")
        ranked.append((score, t, pub, it.get("originallink") or it.get("link")))
    ranked.sort(key=lambda x: -x[0])
    return [{"title": t, "date": _fmt_rss(p), "url": u, "score": s} for s, t, p, u in ranked[:top]]


def stock_news(code, top: int = 3) -> list:
    """종목뉴스: 네이버 증권 종목뉴스 API (큐레이션·관련뉴스 그룹)."""
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
