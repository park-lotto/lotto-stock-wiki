"""
Gemini Deep Research 자동화
Chrome 프로필(로그인 상태) → Gemini Deep Research → 결과 저장

사용법:
  python channel/tools/gemini_deepresearch.py --brief channel/yt/brief_순환매_20260604.md
  python channel/tools/gemini_deepresearch.py --brief channel/yt/brief_순환매_20260604.md --output channel/yt/script_순환매_deep.md
"""
import argparse, time
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

CHROME_USER_DATA = r"C:\Users\TheRose\AppData\Local\Google\Chrome\User Data"
GEMINI_URL = "https://gemini.google.com/app"

WAIT_RESEARCH_MIN = 120   # 딥리서치 최소 대기(초)
WAIT_RESEARCH_MAX = 600   # 최대 대기(초)


def load_brief(path: str) -> str:
    f = Path(path)
    if not f.exists():
        raise FileNotFoundError(f"브리프 파일 없음: {path}")
    return f.read_text(encoding="utf-8")


def run(brief_path: str, output_path: str = None):
    brief_text = load_brief(brief_path)
    brief_file = Path(brief_path)

    prompt = f"""아래 브리프를 기반으로 Deep Research를 수행하고, 한국 주식 유튜브 구어체 대본을 작성해주세요.
브리프에 제시된 각도와 반전 포인트를 중심으로 실시간 웹 검색으로 최신 데이터를 보강하세요.

{brief_text}

출력 형식:
씬번호 | 예상시간 | 핵심대사 (감정선 포함) | 화면설명
(8씬, 총 8~10분 분량)"""

    print(f"[brief] {brief_file.name}")
    print(f"[chrome] {CHROME_USER_DATA}")
    print("[launching] Chrome 프로필로 Gemini 실행 중...")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            user_data_dir=CHROME_USER_DATA,
            channel="chrome",
            headless=False,
            args=["--start-maximized"],
            no_viewport=True,
        )

        page = ctx.new_page()
        page.goto(GEMINI_URL, wait_until="domcontentloaded", timeout=30000)
        print("[page] Gemini 로드 완료")
        time.sleep(3)

        # ── Deep Research 모델 선택 ──────────────────────────────
        _select_deep_research(page)

        # ── 프롬프트 입력 ────────────────────────────────────────
        _type_prompt(page, prompt)

        # ── 전송 ─────────────────────────────────────────────────
        _submit(page)

        # ── 딥리서치 완료 대기 ───────────────────────────────────
        print(f"[waiting] Deep Research 진행 중... (최대 {WAIT_RESEARCH_MAX//60}분)")
        result = _wait_and_extract(page, WAIT_RESEARCH_MAX)

        ctx.close()

    # ── 저장 ─────────────────────────────────────────────────────
    if not output_path:
        stem = brief_file.stem.replace("brief_", "script_") + "_deep"
        output_path = str(brief_file.parent / f"{stem}.md")

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")
    print(f"\n[done] 저장 완료 → {out}")
    return result


# ── 내부 헬퍼 ────────────────────────────────────────────────────

def _select_deep_research(page):
    """Deep Research 모드 선택"""
    try:
        # 모델 선택 버튼 (Gemini 버전 선택 드롭다운)
        model_btn = page.locator("button[aria-label*='model'], button[aria-label*='Gemini'], [data-test-id='model-selector']").first
        if model_btn.is_visible(timeout=5000):
            model_btn.click()
            time.sleep(1)

        # Deep Research 옵션 클릭
        deep = page.locator("text=Deep Research, [aria-label*='Deep Research'], li:has-text('Deep Research')").first
        if deep.is_visible(timeout=5000):
            deep.click()
            print("[model] Deep Research 선택 완료")
            time.sleep(2)
            return
    except Exception:
        pass

    # 폴백: 텍스트로 찾기
    try:
        page.get_by_text("Deep Research", exact=False).first.click()
        print("[model] Deep Research 선택 (폴백)")
        time.sleep(2)
    except Exception:
        print("[warn] Deep Research 버튼 못 찾음 — 수동으로 선택하세요 (10초 대기)")
        time.sleep(10)


def _type_prompt(page, text: str):
    """입력창에 프롬프트 입력"""
    selectors = [
        "div[contenteditable='true']",
        "textarea[placeholder]",
        "rich-textarea",
        "[data-placeholder]",
    ]
    box = None
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=3000):
                box = el
                break
        except Exception:
            continue

    if box is None:
        raise RuntimeError("입력창을 찾을 수 없습니다")

    box.click()
    time.sleep(0.5)
    # 클립보드로 붙여넣기 (긴 텍스트는 type보다 빠름)
    page.evaluate(f"""
        navigator.clipboard.writeText({repr(text)}).then(() => {{
            document.execCommand('paste');
        }});
    """)
    time.sleep(1)
    # 폴백: fill
    try:
        if not box.inner_text():
            box.fill(text)
    except Exception:
        pass
    print(f"[input] 프롬프트 입력 완료 ({len(text)}자)")


def _submit(page):
    """전송 버튼 클릭 또는 Enter"""
    try:
        send = page.locator("button[aria-label*='Send'], button[aria-label*='전송'], button[data-test-id='send-button']").first
        if send.is_visible(timeout=3000):
            send.click()
            print("[submit] 전송 버튼 클릭")
            return
    except Exception:
        pass
    page.keyboard.press("Enter")
    print("[submit] Enter 전송")
    time.sleep(2)


def _wait_and_extract(page, max_sec: int) -> str:
    """딥리서치 완료될 때까지 폴링 후 텍스트 추출"""
    deadline = time.time() + max_sec
    dot = 0

    while time.time() < deadline:
        time.sleep(5)
        dot += 1
        if dot % 6 == 0:
            elapsed = int(time.time() - (deadline - max_sec))
            print(f"  ... {elapsed}초 경과")

        # 완료 감지: 로딩 스피너 사라짐 + 응답 컨테이너 존재
        loading = page.locator("[aria-label*='loading'], .loading-spinner, [data-is-loading='true']")
        try:
            still_loading = loading.count() > 0 and loading.first.is_visible(timeout=1000)
        except Exception:
            still_loading = False

        # 응답 텍스트 확인
        resp = page.locator("model-response, .model-response-text, [data-message-author-role='model']").last
        try:
            text = resp.inner_text(timeout=2000).strip()
            if len(text) > 500 and not still_loading:
                print(f"\n[extract] 응답 확인 ({len(text)}자)")
                return text
        except Exception:
            pass

    # 타임아웃 — 그래도 있는 것 가져오기
    print("\n[timeout] 최대 대기 초과 — 현재까지 내용 추출")
    try:
        return page.locator("model-response, .model-response-text").last.inner_text(timeout=5000)
    except Exception:
        return "[추출 실패] 브라우저에서 수동으로 복사하세요"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gemini Deep Research 자동화")
    parser.add_argument("--brief",  required=True, help="브리프 파일 경로")
    parser.add_argument("--output", default=None,  help="출력 파일 경로")
    args = parser.parse_args()
    run(args.brief, args.output)
