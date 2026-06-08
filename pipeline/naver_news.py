"""
네이버 뉴스 검색 API → raw/news/ 자동 수집
사용: python -m pipeline.naver_news [--date YYYY-MM-DD] [--query 키워드]
"""

import os, sys, json, urllib.request, urllib.parse
from datetime import datetime, date
from pathlib import Path
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# ─── .env 자동 로드 ────────────────────────────────────────────
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

# ─── API 키 설정 ───────────────────────────────────────────────
CLIENT_ID     = os.environ.get("NAVER_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# ─── 저장 경로 ─────────────────────────────────────────────────
ROOT     = Path(__file__).parent.parent
NEWS_DIR = ROOT / "raw" / "news"
NEWS_DIR.mkdir(parents=True, exist_ok=True)

# ─── 기본 쿼리 목록 ────────────────────────────────────────────
DEFAULT_QUERIES = [
    # 조선 섹터 핵심
    ("조선", "한화오션 HD현대중공업 조선"),
    ("조선", "캐나다 잠수함 CPSP K-원팀"),
    ("조선", "삼성중공업 FLNG"),
    ("조선", "미해군 MRO 한국 조선소"),
    ("조선", "미국 중국 조선 관세 제재"),
    ("조선", "SHIPS Act 조선"),
    # 방산/특수선
    ("방산", "LIG넥스원 잠수함"),
    ("방산", "한화에어로스페이스 방산"),
    # 시장 전반
    ("시장", "코스피 외인 기관 수급"),
    ("시장", "미국 나스닥 반도체"),
]


def search_naver(query: str, display: int = 20, sort: str = "date") -> list[dict]:
    """네이버 뉴스 검색 API 호출"""
    if not CLIENT_ID or not CLIENT_SECRET:
        raise EnvironmentError(
            "NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 환경변수가 없습니다.\n"
            "set NAVER_CLIENT_ID=your_id && set NAVER_CLIENT_SECRET=your_secret"
        )

    enc_query = urllib.parse.quote(query)
    url = (
        f"https://openapi.naver.com/v1/search/news.json"
        f"?query={enc_query}&display={display}&sort={sort}"
    )
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", CLIENT_ID)
    req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)

    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data.get("items", [])


def clean_html(text: str) -> str:
    """HTML 태그 제거"""
    import re
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&")


def format_item(item: dict, category: str) -> str:
    title       = clean_html(item.get("title", ""))
    description = clean_html(item.get("description", ""))
    link        = item.get("link", item.get("originallink", ""))
    pub_date    = item.get("pubDate", "")
    return f"### [{title}]({link})\n{pub_date}\n{description}\n"


def run(target_date: str | None = None, extra_query: str | None = None):
    today = target_date or date.today().strftime("%Y-%m-%d")
    queries = list(DEFAULT_QUERIES)
    if extra_query:
        queries.insert(0, ("추가", extra_query))

    out_path = NEWS_DIR / f"{today}_naver_뉴스수집.md"
    lines = [
        f"# 네이버 뉴스 수집 — {today}",
        f"*수집 시각: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Naver Search API*",
        "",
    ]

    total = 0
    for category, query in queries:
        print(f"  검색: {query} ...", end=" ", flush=True)
        try:
            items = search_naver(query, display=10)
        except Exception as e:
            print(f"오류 — {e}")
            continue

        if not items:
            print("결과 없음")
            continue

        print(f"{len(items)}건")
        lines.append(f"## [{category}] {query}")
        lines.append("")
        for item in items:
            lines.append(format_item(item, category))
        total += len(items)

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ 저장: {out_path} ({total}건)")
    return str(out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date",  default=None, help="YYYY-MM-DD (기본: 오늘)")
    parser.add_argument("--query", default=None, help="추가 검색 키워드")
    args = parser.parse_args()
    run(args.date, args.query)
