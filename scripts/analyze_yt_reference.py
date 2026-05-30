"""
레퍼런스 영상 구조 분석기
각 영상 페이지 진입 -> 제목/조회수/챕터/설명/댓글 추출
-> channel/yt/yt_레퍼런스_분석.md 저장

사용법:
    python scripts/analyze_yt_reference.py
    python scripts/analyze_yt_reference.py --headless
"""

import argparse
import json
import time
import re
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

# 분석할 영상 목록 (레퍼런스에서 핵심 선별)
TARGET_VIDEOS = [
    # ── 한국 채널 ──
    {
        "id": "KR-01",
        "title": "내 컴퓨터가 혼자 일을 한다 | 코딩 없이 AI 에이전트",
        "channel": "AI 메이킹",
        "url": "https://www.youtube.com/watch?v=JyPCOzBIEjc",
        "lang": "ko",
    },
    {
        "id": "KR-02",
        "title": "AI 직원 10명이 24시간 일하는 완전 무료 프로그램",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=qDKHEXZ8p6w",
        "lang": "ko",
    },
    {
        "id": "KR-03",
        "title": "AI 직원 5명 채용했습니다… 인건비 0원 실화",
        "channel": "어비월드 UhBee World",
        "url": "https://www.youtube.com/watch?v=kAwsc5oc2Og",
        "lang": "ko",
    },
    {
        "id": "KR-04",
        "title": "단순 AI는 끝났습니다. 스스로 생각하고 행동하는 AI 직원 만들기",
        "channel": "노마드 루이스",
        "url": "https://www.youtube.com/watch?v=gPT2lhv9uns",
        "lang": "ko",
    },
    {
        "id": "KR-05",
        "title": "월급 0원으로 24시간 일하는 AI 직원 5명 고용",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=jpd7gYchCbQ",
        "lang": "ko",
    },
    # ── 영어 채널 ──
    {
        "id": "EN-01",
        "title": "I Built an AI Agent That Works While I Sleep",
        "channel": "Chris Koerner",
        "url": "https://www.youtube.com/watch?v=AA-EL571oG4",
        "lang": "en",
    },
    {
        "id": "EN-02",
        "title": "I Automated My AI Agent to work while I Sleep",
        "channel": "Flutter Agentic",
        "url": "https://www.youtube.com/watch?v=hFINPt2s6Wc",
        "lang": "en",
    },
    {
        "id": "EN-03",
        "title": "I Built a New AI System in 3 Hours",
        "channel": "Nate Herk",
        "url": "https://www.youtube.com/watch?v=Q4iEslmyMyM",
        "lang": "en",
    },
    {
        "id": "EN-04",
        "title": "How to Build a $10M Solo AI Business (Zero Coding)",
        "channel": "Dan Martell",
        "url": "https://www.youtube.com/watch?v=w-XPlC3a2oI",
        "lang": "en",
    },
    {
        "id": "EN-05",
        "title": "This AI Does Your Job While You Sleep",
        "channel": "Julia McCoy",
        "url": "https://www.youtube.com/watch?v=azZtbrpl28s",
        "lang": "en",
    },
]


def get_video_data(page, video: dict) -> dict:
    print(f"  [{video['id']}] {video['channel']} 진입 중...")
    page.goto(video["url"], wait_until="domcontentloaded", timeout=30_000)
    time.sleep(4)

    # 쿠키/팝업 처리
    for btn_text in ["동의", "Accept all", "OK"]:
        try:
            page.click(f"button:has-text('{btn_text}')", timeout=2000)
            time.sleep(1)
        except Exception:
            pass

    result = {**video}

    # 제목
    try:
        title_el = page.query_selector("h1.ytd-watch-metadata yt-formatted-string")
        result["title_full"] = title_el.inner_text().strip() if title_el else video["title"]
    except Exception:
        result["title_full"] = video["title"]

    # 조회수
    try:
        views_el = page.query_selector("span.view-count")
        result["views"] = views_el.inner_text().strip() if views_el else ""
    except Exception:
        result["views"] = ""

    # 좋아요
    try:
        like_el = page.query_selector("button[aria-label*='좋아요'] span, button[aria-label*='like'] span")
        result["likes"] = like_el.inner_text().strip() if like_el else ""
    except Exception:
        result["likes"] = ""

    # 설명 펼치기
    try:
        more_btn = page.query_selector("#expand, tp-yt-paper-button#expand")
        if more_btn:
            more_btn.click()
            time.sleep(1.5)
    except Exception:
        pass

    # 설명 (챕터 포함)
    try:
        desc_el = page.query_selector("#description-inline-expander, #description")
        result["description"] = desc_el.inner_text().strip()[:3000] if desc_el else ""
    except Exception:
        result["description"] = ""

    # 챕터 추출 (타임스탬프 패턴)
    chapters = re.findall(
        r"(\d+:\d+(?::\d+)?)\s+(.+)", result.get("description", "")
    )
    result["chapters"] = [{"time": c[0], "title": c[1].strip()} for c in chapters[:20]]

    # 댓글 상위 3개
    time.sleep(2)
    try:
        page.keyboard.press("End")
        time.sleep(2)
        comment_els = page.query_selector_all("ytd-comment-thread-renderer #content-text")
        result["top_comments"] = [
            el.inner_text().strip()[:200] for el in comment_els[:3]
        ]
    except Exception:
        result["top_comments"] = []

    print(f"      -> 완료 (조회수: {result.get('views', '?')}, 챕터: {len(result['chapters'])}개)")
    return result


def write_analysis(data_list: list[dict], out_path: str):
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# 레퍼런스 영상 구조 분석",
        "",
        f"> 분석일: {date_str}  |  총 {len(data_list)}개 영상",
        "",
        "---",
        "",
    ]

    for d in data_list:
        lang_tag = "[한국]" if d["lang"] == "ko" else "[영어]"
        lines += [
            f"## {d['id']} {lang_tag} {d['channel']}",
            "",
            f"**제목**: {d.get('title_full', d['title'])}",
            f"**조회수**: {d.get('views', '?')}  |  **좋아요**: {d.get('likes', '?')}",
            f"**URL**: {d['url']}",
            "",
        ]

        # 챕터 (= 영상 구조 그 자체)
        chapters = d.get("chapters", [])
        if chapters:
            lines.append("**챕터 구조 (= 영상 설계도)**")
            lines.append("")
            for c in chapters:
                lines.append(f"- `{c['time']}` {c['title']}")
            lines.append("")
        else:
            lines.append("**챕터**: 없음 (설명에 타임스탬프 미기재)")
            lines.append("")

        # 설명 앞부분 (훅 파악용)
        desc = d.get("description", "")
        if desc:
            first_lines = "\n".join(desc.split("\n")[:8])
            lines += [
                "**설명 첫 부분 (훅 파악)**",
                "",
                "```",
                first_lines,
                "```",
                "",
            ]

        # 댓글
        comments = d.get("top_comments", [])
        if comments:
            lines.append("**시청자 반응 (상위 댓글)**")
            lines.append("")
            for i, c in enumerate(comments, 1):
                c_short = c.replace("\n", " ")[:150]
                lines.append(f"{i}. {c_short}")
            lines.append("")

        lines += ["---", ""]

    # 종합 패턴 분석 섹션
    lines += [
        "## 종합 패턴 분석",
        "",
        "### 챕터 구조 공통점",
        "- [ ] 직접 분석 후 채우기",
        "",
        "### 첫 30초 훅 패턴",
        "- [ ] 직접 분석 후 채우기",
        "",
        "### 썸네일 패턴",
        "- [ ] 직접 분석 후 채우기",
        "",
        "### 우리 영상에 적용할 것",
        "- [ ] 직접 분석 후 채우기",
        "",
        f"*자동 분석: scripts/analyze_yt_reference.py | {date_str}*",
    ]

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[저장완료] {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--out", default="channel/yt/yt_레퍼런스_분석.md")
    ap.add_argument("--ids", nargs="*", help="특정 ID만 분석 (예: KR-01 EN-02)")
    args = ap.parse_args()

    base = Path(__file__).parent.parent
    out_path = str(base / args.out)

    targets = TARGET_VIDEOS
    if args.ids:
        targets = [v for v in TARGET_VIDEOS if v["id"] in args.ids]

    all_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox"],
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

        for i, video in enumerate(targets, 1):
            print(f"\n[{i}/{len(targets)}] 분석 중...")
            try:
                data = get_video_data(page, video)
                all_data.append(data)
            except Exception as e:
                print(f"  [오류] {e}")
                all_data.append({**video, "error": str(e)})
            time.sleep(3)

        browser.close()

    write_analysis(all_data, out_path)

    json_path = out_path.replace(".md", ".json")
    Path(json_path).write_text(
        json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[완료] JSON: {json_path}")


if __name__ == "__main__":
    main()
