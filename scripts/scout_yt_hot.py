"""
소재 탐색 직원 — 주식 유튜브 핫클립 자동 발굴 + 자막 저장
사람 개입 없이 완전 자동 실행

흐름:
  1. Playwright → YouTube 검색 → 영상 URL + 조회수 수집
  2. youtube-transcript-api → 자막 추출
  3. 썸네일 공식 분석 + 터진 포인트 추출
  4. wiki/외부인사이트/주식_레퍼런스/ 저장
  5. content_bank.md 업데이트 (기획 직원이 읽는 소재 풀)

사용법:
  python scripts/scout_yt_hot.py           # 전체 실행
  python scripts/scout_yt_hot.py --max 5   # 최대 5개
  python scripts/scout_yt_hot.py --query "주식 6월"
"""
import argparse, re, sys, time, json
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

BASE    = Path(__file__).parent.parent
OUT_DIR = BASE / "wiki" / "외부인사이트" / "주식_레퍼런스"
BANK    = BASE / "channel" / "yt" / "content_bank.md"

# 검색 쿼리 목록 (매 실행마다 돌림)
SEARCH_QUERIES = [
    "주식 6월 올라간다",
    "주식 다음주 매수 급상승",
    "신사임당 주식 최신",
    "달란트투자 최신",
    "주식 AI 자동화 분석",
    "주식 수급 빈집 매매법",
]

THUMB_PATTERNS = {
    "숫자_충격":  r'\d+[만억%배천원]|\d{2,}',
    "시간_압박":  r'6월|5월|다음주|오늘|지금|즉시|임박|며칠|일주일',
    "행동_촉구":  r'사세요|모으세요|사모아라|하세요|보세요|매수하',
    "과장_표현":  r'미친|역대급|폭등|난리|완전|무조건|폭발|대박|충격',
    "대형종목":   r'삼성|SK|LG|현대|NVIDIA|엔비디아|애플|테슬라',
    "비밀_공개":  r'진짜 이유|비밀|몰랐던|들통|밝혀졌|실화|이게 되네',
}

def analyze_title(title: str) -> dict:
    matched = [k for k, p in THUMB_PATTERNS.items() if re.search(p, title)]
    return {"패턴": matched, "공식수": len(matched)}

def fmt_time(sec: float) -> str:
    sec = int(sec)
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def crawl_youtube_videos(query: str, max_results: int = 5) -> list[dict]:
    """Playwright으로 유튜브 검색 → 영상 URL + 제목 + 조회수 수집"""
    from playwright.sync_api import sync_playwright
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        try:
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            page.goto(url, wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

            # 영상 아이템 수집
            items = page.query_selector_all("ytd-video-renderer")
            for item in items[:max_results * 2]:
                try:
                    # 링크 (영상 ID)
                    a = item.query_selector("a#video-title")
                    if not a:
                        continue
                    href = a.get_attribute("href") or ""
                    vid_match = re.search(r"v=([a-zA-Z0-9_-]{11})", href)
                    if not vid_match:
                        continue
                    vid_id = vid_match.group(1)

                    # 제목
                    title = a.inner_text().strip()
                    if not title or len(title) < 5:
                        continue

                    # 조회수 + 날짜
                    meta = item.query_selector("ytd-video-meta-block")
                    meta_text = meta.inner_text() if meta else ""
                    views_match = re.search(r"조회수\s*([\d,]+)", meta_text)
                    views = views_match.group(1) if views_match else "?"

                    results.append({
                        "vid": vid_id,
                        "title": title,
                        "views_raw": views,
                        "meta": meta_text.replace("\n", " ")[:80],
                        "url": f"https://www.youtube.com/watch?v={vid_id}",
                    })
                    if len(results) >= max_results:
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"  크롤링 오류: {e}")
        finally:
            browser.close()
    return results

def fetch_transcript(vid_id: str):
    from youtube_transcript_api import YouTubeTranscriptApi
    api = YouTubeTranscriptApi()
    try:
        tlist = api.list(vid_id)
        for langs in [["ko", "ko-KR"], ["en"]]:
            try:
                t = tlist.find_transcript(langs)
                segs = t.fetch()
                return [{"start": s.start, "text": s.text} for s in segs], t.language_code
            except Exception:
                pass
    except Exception:
        pass
    return [], "none"

def save_video_analysis(video: dict, segs: list, lang: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^\w]", "_", video["vid"])
    fname = OUT_DIR / f"stock_{safe_id}.md"

    title_analysis = analyze_title(video["title"])
    hook_segs = [s for s in segs if s["start"] < 90]
    hook_text = " ".join(s["text"].replace("\n", " ") for s in hook_segs)
    total_sec = segs[-1]["start"] if segs else 0

    lines = [
        f"# {video['title'][:60]}",
        "",
        f"> 수집: {datetime.now().strftime('%Y-%m-%d')}  |  조회수: {video['views_raw']}",
        f"> {video['url']}",
        f"> 메타: {video['meta']}",
        "",
        "## 제목 공식 분석",
        f"매칭 패턴: {', '.join(title_analysis['패턴'])} ({title_analysis['공식수']}/6)",
        "",
        "## 첫 90초 훅",
        "",
        hook_text or "(자막 없음)",
        "",
        "## 전체 자막",
        f"총 길이: ~{fmt_time(total_sec)} | 언어: {lang}",
        "",
    ]
    for seg in segs:
        lines.append(f"`{fmt_time(seg['start'])}` {seg['text'].replace(chr(10), ' ')}")

    lines += [
        "",
        "## 벤치마킹 포인트",
        "| 항목 | 분석 |",
        "|------|------|",
        "| 터진 이유 | |",
        "| 우리 채널 연결 | |",
        "| STOCK BRAIN 소재 유형 | |",
        "",
    ]
    fname.write_text("\n".join(lines), encoding="utf-8")
    return fname

def update_content_bank(new_entries: list[dict]):
    """기획 직원이 읽는 소재 풀 업데이트"""
    BANK.parent.mkdir(parents=True, exist_ok=True)

    existing = BANK.read_text(encoding='utf-8') if BANK.exists() else ""
    today = datetime.now().strftime('%Y-%m-%d')

    new_block = [f"\n## {today} 신규 소재 발굴\n"]
    for e in new_entries:
        a = analyze_title(e["title"])
        new_block.append(
            f"- **[{a['공식수']}/6]** [{e['title'][:50]}]({e['url']})  "
            f"조회수:{e['views_raw']} | 패턴:{','.join(a['패턴'])}"
        )
    new_block.append("")

    BANK.write_text(existing + "\n".join(new_block), encoding='utf-8')
    print(f"  → content_bank.md 업데이트 (+{len(new_entries)}개)")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max",   type=int, default=4, help="쿼리당 최대 영상 수")
    ap.add_argument("--query", type=str, help="단일 검색어")
    ap.add_argument("--no-transcript", action="store_true", help="자막 추출 스킵")
    args = ap.parse_args()

    queries = [args.query] if args.query else SEARCH_QUERIES
    all_videos = []

    print(f"\n{'='*60}")
    print(f"소재 탐색 직원 — 주식 유튜브 핫클립 발굴")
    print(f"{'='*60}")

    for q in queries:
        print(f"\n🔍 검색: '{q}'")
        videos = crawl_youtube_videos(q, max_results=args.max)
        print(f"  {len(videos)}개 발견")
        for v in videos:
            a = analyze_title(v["title"])
            print(f"  [{a['공식수']}/6] {v['title'][:45]}... | {v['views_raw']}")
        all_videos.extend(videos)
        time.sleep(1)

    # 중복 제거
    seen = set()
    unique = []
    for v in all_videos:
        if v["vid"] not in seen:
            seen.add(v["vid"])
            unique.append(v)

    # 공식수 높은 순으로 정렬
    unique.sort(key=lambda x: analyze_title(x["title"])["공식수"], reverse=True)

    print(f"\n{'='*60}")
    print(f"총 {len(unique)}개 고유 영상 발굴 (공식수 높은 순)")
    print(f"{'='*60}")

    saved = []
    for i, v in enumerate(unique, 1):
        a = analyze_title(v["title"])
        print(f"\n[{i}/{len(unique)}] [{a['공식수']}/6] {v['title'][:50]}")
        print(f"  URL: {v['url']}")

        if not args.no_transcript:
            segs, lang = fetch_transcript(v["vid"])
            print(f"  자막: {len(segs)}줄 ({lang})", end=" ")
            if segs:
                fname = save_video_analysis(v, segs, lang)
                print(f"→ {fname.name}")
                saved.append(v)
            else:
                print("→ 자막 없음 (스킵)")
                # 자막 없어도 content_bank엔 추가
                saved.append(v)
            time.sleep(0.8)
        else:
            saved.append(v)

    update_content_bank(saved)

    print(f"\n{'='*60}")
    print(f"완료: {len(saved)}개 처리")
    print(f"저장 위치: {OUT_DIR}")
    print(f"소재 풀: {BANK}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
