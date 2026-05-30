"""
유튜브 레퍼런스 영상 수집기
"AI 직원 / 에이전트가 일한다" 유형 떡상 영상 수집

사용법:
    python scripts/fetch_yt_reference.py
    python scripts/fetch_yt_reference.py --headless   # 브라우저 숨기기
    python scripts/fetch_yt_reference.py --out channel/yt/yt_레퍼런스.md
"""

import argparse
import json
import time
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# ── 검색 키워드 ──────────────────────────────────────────────────
QUERIES = [
    # 한국어
    {"q": "AI 직원 자동화 혼자 일한다", "lang": "ko"},
    {"q": "AI 에이전트 자는 동안 자동 분석", "lang": "ko"},
    {"q": "직원 AI 자동화 시스템 만들기", "lang": "ko"},
    # 영어
    {"q": "AI agents working while I sleep", "lang": "en"},
    {"q": "I built 10 AI employees automated system", "lang": "en"},
    {"q": "multi agent AI system build tutorial", "lang": "en"},
    {"q": "AI automation agency build workflow", "lang": "en"},
]

RESULTS_PER_QUERY = 6   # 쿼리당 수집 영상 수
OUT_DEFAULT = "channel/yt/yt_레퍼런스.md"


def parse_views(text: str) -> str:
    """'1.2M views' → '120만' 등 간단 변환"""
    text = text.replace(",", "").strip()
    m = re.search(r"([\d.]+)\s*([KMB]?)", text, re.IGNORECASE)
    if not m:
        return text
    num, unit = float(m.group(1)), m.group(2).upper()
    mul = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(unit, 1)
    val = int(num * mul)
    if val >= 1_000_000:
        return f"{val/1_000_000:.1f}M ({val/10_000:.0f}만)"
    if val >= 1_000:
        return f"{val/1_000:.1f}K ({val/10_000:.2f}만)"
    return str(val)


def collect_videos(page, query: str, max_count: int) -> list[dict]:
    url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    time.sleep(3)

    # 쿠키 팝업 닫기 (있으면)
    try:
        page.click("button:has-text('Accept all')", timeout=3000)
    except Exception:
        pass
    try:
        page.click("button:has-text('동의')", timeout=3000)
    except Exception:
        pass

    # 스크롤해서 영상 로드
    for _ in range(3):
        page.keyboard.press("End")
        time.sleep(1.5)

    videos = []
    renderers = page.query_selector_all("ytd-video-renderer")

    for renderer in renderers[:max_count]:
        try:
            title_el = renderer.query_selector("#video-title")
            title = title_el.inner_text().strip() if title_el else ""
            href = title_el.get_attribute("href") if title_el else ""
            url_full = f"https://www.youtube.com{href}" if href else ""

            channel_el = renderer.query_selector("#channel-name a")
            channel = channel_el.inner_text().strip() if channel_el else ""

            meta_items = renderer.query_selector_all(
                "#metadata-line span.inline-metadata-item"
            )
            views_raw = meta_items[0].inner_text() if len(meta_items) > 0 else ""
            age = meta_items[1].inner_text() if len(meta_items) > 1 else ""
            views = parse_views(views_raw)

            thumb_el = renderer.query_selector("img#img")
            thumb = thumb_el.get_attribute("src") if thumb_el else ""

            # 영상 길이
            duration_el = renderer.query_selector("span.ytd-thumbnail-overlay-time-status-renderer")
            duration = duration_el.inner_text().strip() if duration_el else ""

            if title and url_full:
                videos.append({
                    "title": title,
                    "channel": channel,
                    "views": views,
                    "age": age,
                    "duration": duration,
                    "url": url_full,
                    "thumb": thumb,
                    "query": query,
                })
        except Exception:
            continue

    return videos


def write_markdown(all_videos: list[dict], out_path: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# 유튜브 레퍼런스 — AI 직원/에이전트 영상",
        f"",
        f"> 수집일: {date_str}  |  총 {len(all_videos)}건",
        f"> 키워드: AI 직원 자동화 / AI agents while I sleep / multi agent AI",
        f"",
    ]

    # 쿼리별 섹션
    seen_urls = set()
    by_query: dict[str, list] = {}
    for v in all_videos:
        by_query.setdefault(v["query"], []).append(v)

    for q, videos in by_query.items():
        lines.append(f"## 🔍 `{q}`")
        lines.append("")
        lines.append("| # | 제목 | 채널 | 조회수 | 업로드 | 길이 | 링크 |")
        lines.append("|---|------|------|--------|--------|------|------|")
        idx = 1
        for v in videos:
            if v["url"] in seen_urls:
                continue
            seen_urls.add(v["url"])
            title_short = v["title"][:45] + ("…" if len(v["title"]) > 45 else "")
            lines.append(
                f"| {idx} | {title_short} | {v['channel']} | {v['views']} "
                f"| {v['age']} | {v['duration']} | [링크]({v['url']}) |"
            )
            idx += 1
        lines.append("")

    # 분석 메모 섹션
    lines += [
        "---",
        "",
        "## 📌 기획 참고 메모",
        "",
        "수집된 영상들에서 뽑을 것:",
        "- [ ] 첫 30초 훅 구조 (어떤 문장으로 시작하는가)",
        "- [ ] 썸네일 패턴 (어떤 이미지 + 텍스트 조합)",
        "- [ ] 영상 길이 분포",
        "- [ ] CTA 방식 (댓글/링크/구독)",
        "- [ ] 우리 영상에 쓸 레퍼런스 씬",
        "",
        "---",
        f"*자동 수집: scripts/fetch_yt_reference.py | {date_str}*",
    ]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[저장완료] {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true", help="브라우저 숨기기")
    ap.add_argument("--out", default=OUT_DEFAULT, help="저장 경로")
    args = ap.parse_args()

    base = Path(__file__).parent.parent
    out_path = str(base / args.out)

    all_videos = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()

        for item in QUERIES:
            q = item["q"]
            print(f"\n[검색] {q}")
            try:
                videos = collect_videos(page, q, RESULTS_PER_QUERY)
                print(f"   -> {len(videos)}건 수집")
                all_videos.extend(videos)
            except Exception as e:
                print(f"   [오류] {e}")
            time.sleep(2)

        browser.close()

    print(f"\n총 {len(all_videos)}건 수집 완료")
    write_markdown(all_videos, out_path)

    # JSON도 저장 (추후 분석용)
    json_path = out_path.replace(".md", ".json")
    Path(json_path).write_text(
        json.dumps(all_videos, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[완료] JSON 저장: {json_path}")


if __name__ == "__main__":
    main()
