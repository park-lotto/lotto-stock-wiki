"""
네이버 뉴스 전문 수집 + Gemini 주제별 분석
사용: python -m pipeline.naver_news_analyze [--date YYYY-MM-DD]

흐름:
  1. raw/news/{date}_naver_뉴스수집.md → URL 추출
  2. 각 기사 URL 크롤 → 본문 추출
  3. 주제별 묶기
  4. Gemini API로 주제별 분석
  5. out/뉴스분석/{date}_분석.md 저장
"""

import os, sys, re, json, time, urllib.request, urllib.parse
from datetime import date as _date
from pathlib import Path
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

from google import genai
from google.genai import types

# ─── 환경 설정 ─────────────────────────────────────────────────
ROOT = Path(__file__).parent.parent
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")
NAVER_ID     = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")
OUT_DIR      = ROOT / "out" / "뉴스분석"
OUT_DIR.mkdir(parents=True, exist_ok=True)

gemini_client = genai.Client(api_key=GEMINI_KEY)

# ─── 주제 키워드 매핑 ──────────────────────────────────────────
TOPICS = {
    "캐나다잠수함_CPSP":   ["캐나다", "잠수함", "CPSP", "K-원팀", "KSS"],
    "FLNG_삼성중공업":     ["FLNG", "부유식 LNG", "삼성중공업", "코랄", "모잠비크", "델핀"],
    "미해군MRO":           ["미해군", "MRO", "미 해군", "군함", "함정 정비", "필라델피아"],
    "방산_LIG_한화":       ["LIG넥스원", "한화에어로스페이스", "방산", "K방산"],
    "SHIPS법안_무역규제":  ["SHIPS", "Section 301", "관세", "제재", "중국 조선", "MASGA"],
    "한화오션_HD현대":     ["한화오션", "HD현대중공업", "HD현대", "한국조선해양"],
    "시장수급_코스피":     ["코스피", "외인", "기관", "수급", "나스닥", "반도체"],
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}


# ─── 기사 본문 추출 ────────────────────────────────────────────
def fetch_article_body(url: str, timeout: int = 8) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        html = resp.text

        # 네이버 뉴스 본문 패턴
        for pattern in [
            r'<div[^>]+id="dic_area"[^>]*>(.*?)</div>',
            r'<article[^>]*>(.*?)</article>',
            r'<div[^>]+class="[^"]*article_body[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]+class="[^"]*news_end[^"]*"[^>]*>(.*?)</div>',
        ]:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                text = re.sub(r"<[^>]+>", " ", m.group(1))
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) > 100:
                    return text[:3000]

        # fallback: <p> 태그 전체
        paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
        body = " ".join(re.sub(r"<[^>]+>", "", p) for p in paragraphs)
        body = re.sub(r"\s+", " ", body).strip()
        return body[:3000] if len(body) > 100 else ""
    except Exception as e:
        return ""


def clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).replace("&quot;", '"').replace("&amp;", "&").strip()


# ─── 네이버 뉴스 검색 (추가 쿼리용) ───────────────────────────
def search_naver(query: str, display: int = 10) -> list[dict]:
    enc = urllib.parse.quote(query)
    url = f"https://openapi.naver.com/v1/search/news.json?query={enc}&display={display}&sort=date"
    req = urllib.request.Request(url)
    req.add_header("X-Naver-Client-Id", NAVER_ID)
    req.add_header("X-Naver-Client-Secret", NAVER_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8")).get("items", [])
    except Exception:
        return []


# ─── 주제별 기사 수집 + 본문 크롤 ─────────────────────────────
def collect_articles_by_topic() -> dict[str, list[dict]]:
    topic_articles: dict[str, list[dict]] = {t: [] for t in TOPICS}
    seen_urls = set()

    for topic_name, keywords in TOPICS.items():
        query = " OR ".join(keywords[:3])
        print(f"\n[{topic_name}] 검색: {query}")
        items = search_naver(query, display=10)

        for item in items:
            url = item.get("link") or item.get("originallink", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = clean_html(item.get("title", ""))
            desc  = clean_html(item.get("description", ""))
            pub   = item.get("pubDate", "")

            print(f"  크롤: {title[:40]}...", end=" ", flush=True)
            body = fetch_article_body(url)
            if body:
                print(f"({len(body)}자)")
            else:
                print("본문 없음")
                body = desc  # fallback to description

            topic_articles[topic_name].append({
                "title": title,
                "url": url,
                "pub": pub,
                "body": body or desc,
            })
            time.sleep(0.3)

    return topic_articles


# ─── Gemini 주제별 분석 ────────────────────────────────────────
def analyze_with_gemini(topic_name: str, articles: list[dict]) -> str:
    if not articles:
        return "수집된 기사 없음"

    articles_text = "\n\n---\n\n".join(
        f"[{a['pub']}] {a['title']}\n{a['url']}\n{a['body']}"
        for a in articles
    )

    prompt = f"""
다음은 '{topic_name}' 주제의 최신 뉴스 기사들이다.

{articles_text}

---

위 기사들을 읽고 주식 투자자 관점에서 다음 형식으로 정리하라:

## 핵심 팩트 (수치/날짜 포함)
- 팩트 1
- 팩트 2
- ...

## 현재 상황 (시장이 어떻게 보고 있나)
2~3줄

## 수혜 종목과 이유
- 종목명: 이유 (구체적으로)

## 리스크 / 주의사항
- 리스크 1
- ...

## 투자 판단 한 줄 요약
(매수/관망/주시 중 하나 + 이유)

출처와 날짜를 반드시 명시하라. 추측이 아닌 기사 본문 내용만 써라.
"""

    try:
        resp = gemini_client.models.generate_content(
            model="gemini-2.5-pro",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
            ),
        )
        return resp.text
    except Exception as e:
        return f"Gemini 오류: {e}"


# ─── 메인 ──────────────────────────────────────────────────────
def run(target_date: str | None = None):
    today = target_date or _date.today().strftime("%Y-%m-%d")
    print(f"=== 네이버 뉴스 전문 분석 — {today} ===\n")

    topic_articles = collect_articles_by_topic()

    out_path = OUT_DIR / f"{today}_뉴스분석.md"
    lines = [
        f"# 네이버 뉴스 주제별 분석 — {today}",
        f"*Gemini 2.5 Pro + 네이버 뉴스 전문 크롤 · {today}*",
        "",
    ]

    for topic_name, articles in topic_articles.items():
        print(f"\n[Gemini 분석] {topic_name} ({len(articles)}건)...")
        analysis = analyze_with_gemini(topic_name, articles)

        lines.append(f"---\n\n# {topic_name}\n")
        lines.append(f"*기사 {len(articles)}건 분석*\n")
        lines.append(analysis)
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n\n✅ 완료 → {out_path}")
    return str(out_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    run(args.date)
