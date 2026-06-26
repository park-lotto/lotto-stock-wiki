"""
Gemini 웹UI 자동화 — YouTube 링크 → 데일리 브리핑 생성
사용법: python scripts/gemini_briefing_playwright.py --url "https://www.youtube.com/..."
"""
import argparse, os, sys, time, re
sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CHROME_PROFILE = r"C:\Users\TheRose\AppData\Local\Google\Chrome\User Data"
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "out")

PROMPT_TEMPLATE = """{youtube_url}

너는 글로벌 매크로 경제와 미국 증시를 분석하는 '수석 투자 전략가'이자 '데일리 시황 에디터'이다.

위 미국 증시 라이브 영상의 대본(트랜스크립트)을 바탕으로, 오늘 시장에서 일어난 모든 핵심 정보를 빠짐없이 담은 [데일리 마켓 브리핑 보고서]를 작성해 줘.

투자자들이 오늘 장의 '돈의 흐름'과 '리스크'를 명확히 파악할 수 있도록, 아래의 5가지 섹션에 맞춰 최대한 구체적인 수치와 맥락을 포함해 정리해야 해.

---

### [보고서 작성 구조]

1. 📊 시장 전반적 분위기 및 매크로 지표
   - **지수 종가 및 장세:** 다우, 나스닥, S&P 500, 러셀2000 등 주요 지수의 마감 분위기와 장중 변동성(휩소 유무).
   - **시장 내부 수치:** 당일 상승 종목수 vs 하락 종목수 비율, 공포와 탐욕 지수(공탐 수치), 빅스(VIX) 지수, 국채 금리 및 달러 인덱스 동향.
   - **핵심 경제 지표:** 당일 발표된 매크로 지표(PCE, CPI, GDP, 실업수당, 내구재 등)의 구체적인 수치와 시장 예상치 대비 결과, 이에 대한 시장의 해석.
   - **연준 위원 발언:** 영상에 등장한 연준 인사(파월, 윌리엄스, 굴스비 등)의 발언 요약 및 금리 전망 변화.

2. 🛒 섹터별 흐름 및 돈의 이동 (순환매 분석)
   - **강세 섹터/테마:** 오늘 가장 돈이 몰리고 상승세를 탄 섹터와 그 상승 원인.
   - **약세 섹터/테마:** 오늘 부진했거나 급락한 섹터와 그 하락 원인.
   - **시장의 서사(내러티브):** 순환매(Rotation)의 방향성 기술.

3. 📢 주요 기업별 핵심 이슈 및 뉴스 (B2B / B2C)
   - **실적 및 가이던스 발표 기업:** 당일 실적을 발표한 기업의 수치(매출, EPS)와 시장 반응.
   - **빅테크 및 주요 개별 기업 이슈:** 주요 기업의 당일 뉴스(가격 인상, 인력 이탈, 규제, 투자 의견 상/하향 등).
   - **진행자의 기업 해석:** 엇갈리게 해석한 맥락 정리.

4. 🚨 중동/지정학 리스크 및 원자재 속보
   - **중동 및 지정학적 이슈:** 팩트와 [카더라/추론] 구분하여 기록.
   - **원자재 동향:** 유가(WTI, 브렌트유), 금, 은, 천연가스, 리튬 가격 움직임.

5. 🔮 내일 장 주요 스케줄 및 투자자 체크포인트
   - **다음 일정:** 내일 발표될 중요 경제 지표 및 실적 발표 일정.
   - **마켓 한줄평:** 진행자의 한줄 요약 및 투자 멘탈 관리 조언.

---

### [작성 규칙]
- 진행자가 "카더라"라고 언급한 부분은 **[카더라/추론]** 말머리를 달아 기록.
- 맥스페인, 콜/풋 비율, 감마 플립 수치 등 옵션 데이터 수치 정확히 기재.
- 불릿포인트(·), 줄바꿈, 볼드체로 가독성 확보."""


def run(youtube_url: str, headless: bool = False):
    prompt = PROMPT_TEMPLATE.format(youtube_url=youtube_url)
    date_str = datetime.now().strftime("%Y%m%d")

    print("🚀 Chrome 실행 중...")

    CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    import subprocess
    # Chrome을 원격 디버깅 포트와 함께 직접 실행
    proc = subprocess.Popen([
        CHROME_EXE,
        "--remote-debugging-port=9222",
        f"--user-data-dir={CHROME_PROFILE}",
        "--profile-directory=Default",
        "--start-maximized",
        "https://gemini.google.com/app",
    ])
    print("Chrome 기동 중... 3초 대기")
    time.sleep(4)

    with sync_playwright() as p:
        # 실행 중인 Chrome에 연결
        browser = p.chromium.connect_over_cdp("http://localhost:9222")
        # 기존 탭 사용 또는 새 탭
        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        # ── 1. Gemini 열기 ──────────────────────────────
        print("📂 gemini.google.com 접속...")
        page.goto("https://gemini.google.com/app", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)

        # ── 2. 입력창 찾기 ──────────────────────────────
        print("✏️  입력창 찾는 중...")
        input_selectors = [
            'div[contenteditable="true"]',
            'textarea[placeholder]',
            'rich-textarea div[contenteditable]',
            '.ql-editor',
            '[data-placeholder]',
        ]
        input_box = None
        for sel in input_selectors:
            try:
                el = page.wait_for_selector(sel, timeout=5000)
                if el:
                    input_box = el
                    print(f"  입력창 발견: {sel}")
                    break
            except PWTimeout:
                continue

        if not input_box:
            # 스크린샷으로 현재 상태 확인
            page.screenshot(path="gemini_debug.png")
            print("❌ 입력창을 찾지 못했습니다. gemini_debug.png 확인")
            browser.close()
            return

        # ── 3. 프롬프트 입력 ────────────────────────────
        print("📝 프롬프트 입력 중...")
        input_box.click()
        time.sleep(0.5)

        # 클립보드를 통해 붙여넣기 (한글+긴 텍스트 안정적)
        page.evaluate(f"""
            const el = document.querySelector('div[contenteditable="true"], rich-textarea div[contenteditable]');
            if (el) {{
                el.focus();
            }}
        """)

        # 텍스트를 클립보드에 복사 후 붙여넣기
        page.evaluate(f"""
            async function copyText() {{
                await navigator.clipboard.writeText({repr(prompt)});
            }}
            copyText();
        """)
        time.sleep(0.5)
        input_box.press("Control+v")
        time.sleep(2)

        # ── 4. 전송 ─────────────────────────────────────
        print("📤 전송 중...")
        # Enter 키 또는 전송 버튼
        send_selectors = [
            'button[aria-label*="Send"]',
            'button[aria-label*="전송"]',
            'button[data-testid="send-button"]',
            'mat-icon[fonticon="send"]',
        ]
        sent = False
        for sel in send_selectors:
            try:
                btn = page.wait_for_selector(sel, timeout=3000)
                if btn:
                    btn.click()
                    sent = True
                    print(f"  전송 버튼 클릭: {sel}")
                    break
            except PWTimeout:
                continue

        if not sent:
            input_box.press("Enter")
            print("  Enter 키로 전송")

        # ── 5. 응답 대기 ─────────────────────────────────
        print("⏳ Gemini 응답 대기 중 (최대 5분)...")
        print("   (9시간 영상 분석이라 시간이 걸릴 수 있습니다)")

        # 응답 완료 감지: 로딩 스피너가 사라질 때까지
        try:
            # 로딩 시작 대기
            time.sleep(5)

            # 응답 완료 대기 (로딩 인디케이터 소멸)
            page.wait_for_selector(
                'model-response .response-content, .response-container, [data-response-index]',
                timeout=300000
            )
            # 스트리밍 완료 대기 (타이핑 애니메이션)
            time.sleep(10)

        except PWTimeout:
            print("⚠️  응답 대기 시간 초과 — 현재까지 받은 내용으로 저장")

        # ── 6. 응답 텍스트 추출 ──────────────────────────
        print("📋 응답 추출 중...")
        response_text = ""

        extract_selectors = [
            'model-response .markdown',
            '.response-content',
            'message-content',
            '[data-response-index] .markdown',
            '.conversation-container model-response',
        ]
        for sel in extract_selectors:
            try:
                elements = page.query_selector_all(sel)
                if elements:
                    # 마지막 응답 (가장 최근)
                    last = elements[-1]
                    response_text = last.inner_text()
                    if len(response_text) > 200:
                        print(f"  응답 추출 성공: {len(response_text)}자 ({sel})")
                        break
            except Exception:
                continue

        if not response_text:
            # 전체 페이지에서 추출 시도
            response_text = page.evaluate("""
                () => {
                    const responses = document.querySelectorAll('model-response, .response-content, .markdown');
                    if (responses.length > 0) {
                        return responses[responses.length - 1].innerText;
                    }
                    return '';
                }
            """)

        if not response_text:
            page.screenshot(path="gemini_response_debug.png")
            print("❌ 응답 추출 실패. gemini_response_debug.png 확인")
            browser.close()
            return

        # ── 7. 저장 ─────────────────────────────────────
        os.makedirs(OUT_DIR, exist_ok=True)
        out_path = os.path.join(OUT_DIR, f"briefing_{date_str}_yt_gemini.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# 데일리 마켓 브리핑 — {date_str}\n\n")
            f.write(f"*소스: {youtube_url}*\n\n")
            f.write(response_text)

        print(f"\n✅ 저장 완료: {out_path}")
        print(f"   글자수: {len(response_text):,}자")

        browser.close()
        proc.terminate()
        return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="https://www.youtube.com/live/UmA5KqY66cQ", help="YouTube URL")
    parser.add_argument("--headless", action="store_true", help="브라우저 숨기기")
    args = parser.parse_args()

    result = run(args.url, args.headless)
    if result:
        import subprocess
        subprocess.Popen(["code", result])
