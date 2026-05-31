# -*- coding: utf-8 -*-
"""
URL 수집 + Gemini 분석 — Naver 블로그 등 WebFetch 차단 사이트 우회
사용법:
  python scripts/fetch_and_analyze.py <URL> <분석지시>
  python scripts/fetch_and_analyze.py <URL>  (기본: 전체 내용 추출)
"""
import sys, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.yt_agents.gemini_client import call as gemini_call


def fetch_page(url: str) -> str:
    """Playwright로 페이지 렌더링 후 텍스트 추출"""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
        )
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        time.sleep(2)  # JS 렌더링 대기

        # Naver 블로그: iframe 내부 읽기
        text = ""
        try:
            frame = page.frame(name="mainFrame")
            if frame:
                text = frame.inner_text("body")
        except Exception:
            pass

        if not text:
            text = page.inner_text("body")

        browser.close()
        return text.strip()


def analyze(content: str, prompt: str) -> str:
    """Gemini로 분석"""
    system = "너는 주식 투자 분석 전문가야. 주어진 웹 페이지 내용에서 투자에 유용한 정보를 정확하게 추출해."
    full_prompt = f"{prompt}\n\n--- 페이지 내용 ---\n{content[:12000]}"
    return gemini_call(full_prompt, system=system, temperature=0)


def main():
    if len(sys.argv) < 2:
        print("사용법: python scripts/fetch_and_analyze.py <URL> [분석지시]")
        sys.exit(1)

    url = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else (
        "이 페이지의 모든 중요한 정보를 빠짐없이 추출해줘. "
        "종목명, 섹터, 수치, 날짜 등 구체적인 데이터 위주로 정리해줘."
    )

    print(f"[1/2] 페이지 수집 중: {url}")
    try:
        content = fetch_page(url)
        print(f"      → {len(content)}자 수집 완료")
    except Exception as e:
        print(f"      ✗ 수집 실패: {e}")
        sys.exit(1)

    print("[2/2] Gemini 분석 중...")
    result = analyze(content, prompt)
    print("\n" + "="*60)
    print(result)
    print("="*60)


if __name__ == "__main__":
    main()
