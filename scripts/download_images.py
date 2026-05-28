"""
download_images.py — 보고서 내용 기반 이미지 자동 다운로드

핵심 원칙: 고정 매핑 없음. 보고서/텍스트의 핵심 내용을 분석해
그에 가장 맞는 이미지를 동적으로 검색·다운로드.

출처: Wikimedia Commons (CC 라이선스, 상업적 사용 가능)

저장 경로: raw/images/{slug}/

사용법:
  # 직접 검색어 지정
  python scripts/download_images.py --query "SK Hynix HBM4 memory" --n 3

  # HTML 파일에서 핵심 쿼리 자동 추출 후 다운로드
  python scripts/download_images.py --from-html out/report_반도체.html

  # 텍스트 직접 입력 → 쿼리 자동 생성
  python scripts/download_images.py --from-text "HBM4 공급 부족, SK하이닉스 독점, 엔비디아 Blackwell"

  # 검색만 (다운로드 없이 목록 확인)
  python scripts/download_images.py --query "Jensen Huang" --dry-run
"""
import sys, argparse, re, os
sys.stdout.reconfigure(encoding='utf-8')

import requests
from pathlib import Path
from bs4 import BeautifulSoup

BASE   = Path(__file__).parent.parent
OUTDIR = BASE / "raw" / "images"
OUTDIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "StockBrainBot/1.0 (stock analysis; parklotto12@gmail.com)"
}

# ─────────────────────────────────────────────
# 한국어 → 영문 검색어 변환 사전
# 핵심 인물·기업·제품·이슈를 Wikimedia가 잘 찾는 영문으로 매핑
# ─────────────────────────────────────────────
KR_TO_EN = {
    # 인물
    "젠슨황": "Jensen Huang NVIDIA",
    "황인준": "Jensen Huang NVIDIA",
    "젠슨 황": "Jensen Huang NVIDIA",
    "곽노정": "SK Hynix CEO",
    "이재용": "Lee Jae-yong Samsung",
    "정기선": "Chung Ki-sun HD Hyundai",
    "리사수": "Lisa Su AMD CEO",
    "팀쿡": "Tim Cook Apple",
    "일론머스크": "Elon Musk Tesla",

    # 기업
    "엔비디아": "NVIDIA",
    "SK하이닉스": "SK Hynix semiconductor",
    "삼성전자": "Samsung Electronics",
    "삼성": "Samsung Electronics chip",
    "TSMC": "TSMC semiconductor fab",
    "한화에어로스페이스": "Hanwha Aerospace K9",
    "HD현대중공업": "HD Hyundai Heavy Industries shipyard",
    "한화오션": "Hanwha Ocean shipyard",

    # 제품·기술
    "HBM": "HBM High Bandwidth Memory chip",
    "HBM4": "HBM4 memory chip SK Hynix",
    "블랙웰": "NVIDIA Blackwell GPU",
    "Blackwell": "NVIDIA Blackwell GPU datacenter",
    "베라루빈": "NVIDIA Vera Rubin",
    "파운드리": "semiconductor fab cleanroom",
    "조선소": "shipyard container ship",
    "수주잔고": "shipyard order backlog",
    "K9": "K9 self-propelled howitzer",
    "변압기": "power transformer factory",
    "데이터센터": "data center server rack",
    "AI 서버": "AI server datacenter",
    "반도체": "semiconductor chip fab",
    "ESG": "solar energy renewable power",
    "배터리": "battery cell manufacturing",
    "LNG선": "LNG carrier ship",
}

# ─────────────────────────────────────────────
# 텍스트 → 최적 검색 쿼리 자동 생성
# ─────────────────────────────────────────────

def extract_queries_from_text(text: str, max_queries: int = 3) -> list[str]:
    """
    텍스트(한국어/영어 혼용)에서 핵심 키워드를 추출해
    Wikimedia 검색에 최적화된 영문 쿼리 목록을 반환.
    """
    queries = []
    matched_keys = set()

    # 1단계: KR_TO_EN 사전에서 매칭
    for kr, en in KR_TO_EN.items():
        if kr.lower() in text.lower() and en not in matched_keys:
            queries.append(en)
            matched_keys.add(en)
        if len(queries) >= max_queries:
            break

    # 2단계: 영문 키워드 직접 추출 (대문자 시작 단어 + 알려진 패턴)
    if len(queries) < max_queries:
        en_words = re.findall(r'\b[A-Z][A-Za-z]{2,}\b', text)
        en_phrases = []
        known = {"HBM", "NVIDIA", "AMD", "TSMC", "GPU", "AI", "IPO", "ETF",
                 "FOMC", "Fed", "LNG", "ESS", "PCB", "SMR", "MLCC"}
        for w in en_words:
            if w in known and w not in matched_keys:
                en_phrases.append(w + " technology")
                matched_keys.add(w)
        queries.extend(en_phrases[:max_queries - len(queries)])

    if not queries:
        queries = ["semiconductor chip technology"]

    return queries[:max_queries]


def extract_queries_from_html(html_path: Path, max_queries: int = 3) -> list[str]:
    """HTML 파일에서 텍스트 추출 후 쿼리 생성"""
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    # script/style 제거
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return extract_queries_from_text(text, max_queries)


# ─────────────────────────────────────────────
# Wikimedia Commons 검색 + 다운로드
# ─────────────────────────────────────────────

def search_wikimedia(query: str, n: int = 5) -> list[dict]:
    url = "https://commons.wikimedia.org/w/api.php"
    params = {
        "action":       "query",
        "generator":    "search",
        "gsrnamespace": 6,
        "gsrsearch":    query,
        "gsrlimit":     n * 2,
        "prop":         "imageinfo",
        "iiprop":       "url|extmetadata|size|mime",
        "iiurlwidth":   1920,
        "format":       "json",
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})

    results = []
    for page in pages.values():
        ii = page.get("imageinfo", [{}])[0]
        if not ii.get("url"):
            continue
        mime = ii.get("mime", "")
        # 이미지만 (SVG/PNG/JPG)
        if not any(t in mime for t in ["image/jpeg", "image/png", "image/svg", "image/webp"]):
            continue

        meta    = ii.get("extmetadata", {})
        lic     = meta.get("LicenseShortName", {}).get("value", "Unknown")
        artist  = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "Unknown")).strip()
        desc    = re.sub(r"<[^>]+>", "", meta.get("ImageDescription", {}).get("value", "")).strip()[:100]

        results.append({
            "title":   page.get("title", "").replace("File:", ""),
            "url":     ii.get("thumburl") or ii.get("url"),
            "license": lic,
            "artist":  artist,
            "desc":    desc,
        })
    return results[:n]


def download_images(query: str, n: int = 3,
                    save_dir: Path = None, dry_run: bool = False) -> list[dict]:
    slug = re.sub(r'[^\w가-힣]', '_', query)[:40].strip('_')
    save_dir = save_dir or (OUTDIR / slug)

    print(f"\n🔍 검색: '{query}'  (최대 {n}장)")
    items = search_wikimedia(query, n)

    if not items:
        print("  ❌ 결과 없음")
        return []

    if dry_run:
        for i, item in enumerate(items, 1):
            print(f"  [{i}] {item['title'][:60]}")
            print(f"       {item['license']} | {item['artist']}")
        return items

    save_dir.mkdir(parents=True, exist_ok=True)
    saved = []

    for i, item in enumerate(items, 1):
        ext      = Path(item["url"].split("?")[0]).suffix or ".jpg"
        safe     = re.sub(r'[^\w가-힣.-]', '_', item["title"])[:55]
        out_path = save_dir / f"{i:02d}_{safe}{ext}"

        try:
            r = requests.get(item["url"], headers=HEADERS, timeout=20, stream=True)
            r.raise_for_status()
            out_path.write_bytes(r.content)
            item["path"] = str(out_path)
            saved.append(item)
            print(f"  ✅ [{i}] {out_path.name}")
            print(f"       {item['license']} | {item['artist']}")
            if item["desc"]:
                print(f"       {item['desc']}")
        except Exception as e:
            print(f"  ❌ [{i}] 실패: {e}")

    # 저작권 표시 메모
    if saved:
        attr = save_dir / "출처_attribution.txt"
        with attr.open("w", encoding="utf-8") as f:
            f.write(f"검색어: {query}\n출처: Wikimedia Commons\n\n")
            for item in saved:
                f.write(f"파일: {Path(item['path']).name}\n")
                f.write(f"  라이선스: {item['license']}\n")
                f.write(f"  작가: {item['artist']}\n\n")
        print(f"  📄 출처: {attr}")

    return saved


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="보고서 내용 기반 이미지 다운로드")
    parser.add_argument("--query",     default=None, help="직접 검색어 (영문 권장)")
    parser.add_argument("--n",         type=int, default=3, help="장수 (기본 3)")
    parser.add_argument("--from-html", default=None, help="HTML 파일 경로 → 쿼리 자동 추출")
    parser.add_argument("--from-text", default=None, help="텍스트 직접 입력 → 쿼리 자동 추출")
    parser.add_argument("--dry-run",   action="store_true", help="목록만 확인 (다운로드 없음)")
    args = parser.parse_args()

    if args.query:
        # 한국어면 자동 변환 시도
        q = args.query
        for kr, en in KR_TO_EN.items():
            if kr in q:
                print(f"  ℹ️  한국어 감지: '{kr}' → '{en}'")
                q = en
                break
        download_images(q, args.n, dry_run=args.dry_run)

    elif args.from_html:
        path = Path(args.from_html)
        if not path.exists():
            print(f"❌ 파일 없음: {path}")
            return
        queries = extract_queries_from_html(path, max_queries=3)
        print(f"📄 HTML 분석 완료 → 쿼리 {len(queries)}개: {queries}")
        save_dir = OUTDIR / path.stem
        for q in queries:
            download_images(q, args.n, save_dir=save_dir, dry_run=args.dry_run)

    elif args.from_text:
        queries = extract_queries_from_text(args.from_text, max_queries=3)
        print(f"📝 텍스트 분석 완료 → 쿼리 {len(queries)}개: {queries}")
        for q in queries:
            download_images(q, args.n, dry_run=args.dry_run)

    else:
        parser.print_help()
        print("\n💡 예시:")
        print("  python scripts/download_images.py --query 'SK Hynix HBM4'")
        print("  python scripts/download_images.py --from-html out/report_반도체.html")
        print("  python scripts/download_images.py --from-text 'HBM4 공급 부족 SK하이닉스'")

    print(f"\n📁 저장 위치: {OUTDIR}")


if __name__ == "__main__":
    main()
