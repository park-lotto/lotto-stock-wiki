"""
유튜브 전체 자막 추출기
한국 10개 + 해외 5개 → 개별 위키 파일 저장

사용법:
    python scripts/fetch_yt_transcripts.py            # 전체 15개
    python scripts/fetch_yt_transcripts.py --id KR-02 # 특정 영상만
    python scripts/fetch_yt_transcripts.py --search   # 먼저 검색 후 목록 업데이트
"""

import argparse
import time
import re
import sys
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

OUT_DIR = Path(__file__).parent.parent / "wiki" / "외부인사이트" / "레퍼런스_영상"

# ── 분석 대상 영상 목록 ─────────────────────────────────────────
VIDEOS = [
    # ══ 한국 채널 10개 — 조회수 상위 선별 ══
    {
        "id": "KR-01",
        "channel": "어비월드 UhBee World",
        "url": "https://www.youtube.com/watch?v=kAwsc5oc2Og",
        "memo": "AI 직원 5명 채용, 인건비 0원 실화 (Manus Skills) | 14만뷰",
    },
    {
        "id": "KR-02",
        "channel": "월텍남",
        "url": "https://www.youtube.com/watch?v=GzGcQzMo_Rw",
        "memo": "업무 전부 자동화, 구글의 역대급 AI 에이전트 | 20만뷰",
    },
    {
        "id": "KR-03",
        "channel": "일잘러 장피엠",
        "url": "https://www.youtube.com/watch?v=c-a4GBOxhXQ",
        "memo": "나의 AI 에이전트 전환기 (클로드 코드, 오픈클로) | 16만뷰",
    },
    {
        "id": "KR-04",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=qDKHEXZ8p6w",
        "memo": "AI 직원 10명이 24시간 일하는 완전 무료 프로그램 | 10만뷰",
    },
    {
        "id": "KR-05",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=Jas_74VZiPE",
        "memo": "AI로 돈 버는 게 막막하다면 무조건 보세요 (NotebookLM+안티그래비티) | 9만뷰",
    },
    {
        "id": "KR-06",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=Gts_7nuf9dQ",
        "memo": "이게 진짜 자동화, AI 직원 10명이 동시에 연구/앱 개발 | 8.7만뷰",
    },
    {
        "id": "KR-07",
        "channel": "콜잇 AI",
        "url": "https://www.youtube.com/watch?v=tv8Dzpd9B6s",
        "memo": "구글이 공개한 미친 AI, 디자이너 없이 혼자 마케팅 | 8.6만뷰",
    },
    {
        "id": "KR-08",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=BZynp51fBRU",
        "memo": "대화형 AI 시대는 끝났다, 구글 에이전트 유튜브 수익화 자동화 | 6.5만뷰",
    },
    {
        "id": "KR-09",
        "channel": "와이스트릿",
        "url": "https://www.youtube.com/watch?v=66coEEnAdSk",
        "memo": "직원 5명 공짜로 고용한 셈, 커서AI 프로그래머 세상 | 5만뷰",
    },
    {
        "id": "KR-10",
        "channel": "CONNECT AI LAB",
        "url": "https://www.youtube.com/watch?v=5KQgXA1hj_g",
        "memo": "구글 AI 자동화: 스티치+안티그래비티로 5인분 혼자 | 3만뷰",
    },
    # ══ 해외 채널 5개 — 조회수 상위 선별 ══
    {
        "id": "EN-01",
        "channel": "Futurepedia",
        "url": "https://www.youtube.com/watch?v=EH5jx5qPabU",
        "memo": "From Zero to First AI Agent in 25 Min (No Coding) | 373만뷰",
    },
    {
        "id": "EN-02",
        "channel": "Liam Ottley",
        "url": "https://www.youtube.com/watch?v=w0H1-b044KY",
        "memo": "How to Build & Sell AI Agents: Ultimate Beginner Guide | 282만뷰 | 구독 79만",
    },
    {
        "id": "EN-03",
        "channel": "Nate Herk AI Automation",
        "url": "https://www.youtube.com/watch?v=Ey18PDiaAYI",
        "memo": "Build & Sell n8n AI Agents (8+ Hour Course, No Code) | 169만뷰 | 구독 76만",
    },
    {
        "id": "EN-04",
        "channel": "Dan Martell",
        "url": "https://www.youtube.com/watch?v=w-XPlC3a2oI",
        "memo": "How to Build a $10M Solo AI Business (Zero Coding) | 66만뷰 | 구독 261만",
    },
    {
        "id": "EN-05",
        "channel": "Chris Koerner",
        "url": "https://www.youtube.com/watch?v=AA-EL571oG4",
        "memo": "I Built an AI Agent That Works While I Sleep | 38만뷰 | 구독 40만",
    },
]


# ── 자막 추출 ────────────────────────────────────────────────────

def open_transcript(page: Page) -> bool:
    """자막 패널 열기 — 여러 방법 시도"""

    # 방법 1: "스크립트 보기" / "Show transcript" 직접 버튼
    for label in [
        "스크립트 보기", "Show transcript", "transcript", "자막",
    ]:
        try:
            btn = page.get_by_role("button", name=re.compile(label, re.IGNORECASE))
            if btn.count() > 0:
                btn.first.click()
                time.sleep(2)
                return True
        except Exception:
            pass

    # 방법 2: 설명 아래 "..." (more actions) → Show transcript
    try:
        page.click("ytd-video-description-transcript-section-renderer button", timeout=3000)
        time.sleep(2)
        return True
    except Exception:
        pass

    # 방법 3: 영상 하단 "..." 메뉴
    try:
        page.click("button[aria-label='More actions'], yt-button-shape button", timeout=3000)
        time.sleep(1)
        for label in ["Show transcript", "스크립트"]:
            try:
                page.get_by_text(label, exact=False).first.click(timeout=2000)
                time.sleep(2)
                return True
            except Exception:
                pass
    except Exception:
        pass

    # 방법 4: 설명 섹션 내 transcript 링크
    try:
        page.click("ytd-structured-description-content-renderer button", timeout=3000)
        time.sleep(2)
        return True
    except Exception:
        pass

    return False


def extract_segments(page: Page) -> list[dict]:
    """열린 자막 패널에서 타임스탬프 + 텍스트 추출"""
    segments = []

    # 패널이 로드될 때까지 대기
    for _ in range(6):
        els = page.query_selector_all("ytd-transcript-segment-renderer")
        if els:
            break
        time.sleep(1)

    els = page.query_selector_all("ytd-transcript-segment-renderer")
    for el in els:
        try:
            ts_el = el.query_selector(".segment-timestamp")
            txt_el = el.query_selector(".segment-text")
            ts = ts_el.inner_text().strip() if ts_el else ""
            txt = txt_el.inner_text().strip() if txt_el else ""
            if txt:
                segments.append({"time": ts, "text": txt})
        except Exception:
            continue

    return segments


def get_meta(page: Page) -> dict:
    """제목·조회수·좋아요·설명 추출"""
    meta = {}

    # 제목
    try:
        el = page.query_selector("h1.ytd-watch-metadata yt-formatted-string")
        meta["title"] = el.inner_text().strip() if el else ""
    except Exception:
        meta["title"] = ""

    # 조회수
    try:
        el = page.query_selector("span.view-count")
        meta["views"] = el.inner_text().strip() if el else ""
    except Exception:
        meta["views"] = ""

    # 설명 펼치기
    try:
        page.click("#expand, tp-yt-paper-button#expand", timeout=3000)
        time.sleep(1)
    except Exception:
        pass

    # 설명
    try:
        el = page.query_selector(
            "#description-inline-expander yt-attributed-string, "
            "#description yt-attributed-string"
        )
        meta["description"] = el.inner_text().strip()[:2000] if el else ""
    except Exception:
        meta["description"] = ""

    # 댓글 상위 5개
    for _ in range(3):
        page.keyboard.press("End")
        time.sleep(1.5)
    try:
        comment_els = page.query_selector_all(
            "ytd-comment-thread-renderer #content-text"
        )
        meta["comments"] = [el.inner_text().strip()[:300] for el in comment_els[:5]]
    except Exception:
        meta["comments"] = []

    return meta


# ── 저장 ─────────────────────────────────────────────────────────

def save_wiki(video: dict, meta: dict, segments: list[dict]):
    """개별 위키 파일 저장"""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fname = OUT_DIR / f"ref_{video['id']}_{video['channel'].replace(' ', '_')}.md"

    date_str = datetime.now().strftime("%Y-%m-%d")
    title = meta.get("title") or video["memo"]

    # 자막 → 전체 스크립트 텍스트
    full_script = "\n".join(
        f"[{s['time']}] {s['text']}" for s in segments
    )

    # 자막에서 챕터(타임스탬프가 큰 간격으로 바뀌는 구간) 추정
    # 30초 이상 간격이면 새 섹션으로 간주
    sections = []
    prev_sec = 0
    section_buf = []
    for s in segments:
        try:
            parts = s["time"].replace(":", " ").split()
            secs = sum(int(p) * (60 ** i) for i, p in enumerate(reversed(parts)))
        except Exception:
            secs = prev_sec
        if secs - prev_sec > 45 and section_buf:
            sections.append({"start": section_buf[0]["time"], "lines": section_buf})
            section_buf = []
        section_buf.append(s)
        prev_sec = secs
    if section_buf:
        sections.append({"start": section_buf[0]["time"], "lines": section_buf})

    lines = [
        f"# 레퍼런스 분석: {video['id']} — {video['channel']}",
        "",
        f"> 수집일: {date_str}",
        f"> URL: {video['url']}",
        f"> 메모: {video['memo']}",
        "",
        "---",
        "",
        "## 기본 정보",
        "",
        f"| 항목 | 내용 |",
        f"|------|------|",
        f"| 제목 | {title} |",
        f"| 채널 | {video['channel']} |",
        f"| 조회수 | {meta.get('views', '미확인')} |",
        f"| 자막 세그먼트 수 | {len(segments)}개 |",
        "",
        "---",
        "",
        "## 영상 설명 (앞부분)",
        "",
        "```",
        meta.get("description", "없음")[:800],
        "```",
        "",
        "---",
        "",
        "## 섹션별 구조 (자막 기반 자동 분석)",
        "",
        "> 45초 이상 간격 기준으로 섹션 구분",
        "",
    ]

    for i, sec in enumerate(sections, 1):
        lines.append(f"### 섹션 {i} — [{sec['start']}]")
        lines.append("")
        for seg in sec["lines"][:30]:  # 섹션당 최대 30줄
            lines.append(f"- `{seg['time']}` {seg['text']}")
        if len(sec["lines"]) > 30:
            lines.append(f"  *(이하 {len(sec['lines']) - 30}줄 생략)*")
        lines.append("")

    lines += [
        "---",
        "",
        "## 전체 자막 (원문)",
        "",
        "```",
        full_script[:8000] if full_script else "자막 없음 (비활성화 또는 추출 실패)",
        "```",
        "",
        "---",
        "",
        "## 시청자 댓글 (상위 5개)",
        "",
    ]

    for i, c in enumerate(meta.get("comments", []), 1):
        c_clean = c.replace("\n", " ").strip()
        lines.append(f"**댓글 {i}**: {c_clean}")
        lines.append("")

    lines += [
        "---",
        "",
        "## 구조 분석 메모 (수동 작성란)",
        "",
        "| 항목 | 내용 |",
        "|------|------|",
        "| 훅 방식 | |",
        "| 오프닝 첫 문장 | |",
        "| 본론 구조 | |",
        "| 클라이맥스 타이밍 | |",
        "| CTA 방식 | |",
        "| 잘된 이유 | |",
        "| 우리 영상에 쓸 것 | |",
        "",
    ]

    fname.write_text("\n".join(lines), encoding="utf-8")
    print(f"  [저장] {fname.name}")
    return fname


# ── 인덱스 파일 ────────────────────────────────────────────────

def save_index(results: list[dict]):
    idx_path = OUT_DIR / "인덱스.md"
    date_str = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# AI 직원/에이전트 레퍼런스 영상 인덱스",
        "",
        f"> 수집일: {date_str}",
        "",
        "## 한국 채널",
        "",
        "| ID | 채널 | 조회수 | 자막 | 파일 |",
        "|----|------|--------|------|------|",
    ]
    for r in results:
        if r["id"].startswith("KR"):
            seg_cnt = r.get("seg_count", 0)
            status = "OK" if seg_cnt > 0 else "실패"
            lines.append(
                f"| {r['id']} | {r['channel']} | {r.get('views', '?')} "
                f"| {seg_cnt}줄 ({status}) | [{r['id']}]({r['fname']}) |"
            )

    lines += [
        "",
        "## 해외 채널",
        "",
        "| ID | 채널 | 조회수 | 자막 | 파일 |",
        "|----|------|--------|------|------|",
    ]
    for r in results:
        if r["id"].startswith("EN"):
            seg_cnt = r.get("seg_count", 0)
            status = "OK" if seg_cnt > 0 else "실패"
            lines.append(
                f"| {r['id']} | {r['channel']} | {r.get('views', '?')} "
                f"| {seg_cnt}줄 ({status}) | [{r['id']}]({r['fname']}) |"
            )

    idx_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[인덱스 저장] {idx_path}")


# ── 메인 ─────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--id", help="특정 ID만 실행 (예: KR-02)")
    args = ap.parse_args()

    targets = VIDEOS
    if args.id:
        targets = [v for v in VIDEOS if v["id"] == args.id]
        if not targets:
            print(f"[오류] ID '{args.id}' 없음")
            sys.exit(1)

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = ctx.new_page()

        for i, video in enumerate(targets, 1):
            print(f"\n[{i}/{len(targets)}] {video['id']} {video['channel']}")
            print(f"  URL: {video['url']}")

            try:
                page.goto(video["url"], wait_until="domcontentloaded", timeout=30000)
                time.sleep(4)

                # 쿠키/팝업
                for btn in ["동의", "Accept all", "동의하고 계속하기"]:
                    try:
                        page.click(f"button:has-text('{btn}')", timeout=2000)
                        time.sleep(1)
                    except Exception:
                        pass

                # 메타 추출
                meta = get_meta(page)
                print(f"  제목: {meta.get('title', '?')[:50]}")
                print(f"  조회수: {meta.get('views', '?')}")

                # 자막 패널 열기
                print(f"  자막 열기 시도...")
                opened = open_transcript(page)

                segments = []
                if opened:
                    segments = extract_segments(page)
                    print(f"  자막: {len(segments)}줄 추출")
                else:
                    print(f"  자막: 패널 열기 실패")

                # 저장
                fname = save_wiki(video, meta, segments)
                results.append({
                    **video,
                    "views": meta.get("views", "?"),
                    "seg_count": len(segments),
                    "fname": fname.name,
                })

            except Exception as e:
                print(f"  [오류] {e}")
                results.append({**video, "seg_count": 0, "fname": "", "error": str(e)})

            time.sleep(3)

        browser.close()

    save_index(results)

    print("\n" + "=" * 50)
    print("수집 완료 요약")
    print("=" * 50)
    for r in results:
        status = "OK" if r.get("seg_count", 0) > 0 else "자막없음"
        print(f"  {r['id']} {r['channel'][:20]:20s} | {r.get('views','?'):15s} | {r.get('seg_count',0):4d}줄 | {status}")


if __name__ == "__main__":
    main()
