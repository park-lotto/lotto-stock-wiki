"""썸네일 canvas 폰트 로드 — 실브라우저에서만 관측되는 결함을 잠근다.

★결함(2026-07-17 실측): 브라우저는 @font-face 폰트를 DOM에서 실제로 "쓸 때만" 로드한다.
canvas의 `ctx.font = '900 96px HCTmon'`는 그 "사용"으로 안 쳐준다 — 미로드 폰트를 지정하면
에러 없이 기본 고딕으로 조용히 대체해서 그린다. produce.html엔 @font-face 22개가 멀쩡히
선언돼 있지만(:56~) 그걸 쓰는 DOM 요소가 canvas뿐이라 영영 로드가 안 됐다 = 폰트 22종
전부가 죽어 있었다(사장님이 뭘 골라도 전부 같은 기본 고딕으로 그려짐).

Node 슬라이스 테스트(test_produce_thumb_ui.py/test_produce_thumb_wire.py)는 document.fonts
로더 자체가 없어 이 결함을 원리적으로 못 잡는다 — ctx.font 문자열은 로드 여부와 무관하게
항상 "정확"해 보인다. 화면을 띄워야만 보인다. 그래서 여기서만 잠근다(가짜 자물쇠 금지).

계약: 5단계 진입(상당) + 레이어에 폰트 지정 + 렌더 후 →
  1) canvas가 그 폰트로 측정한 폭이 sans-serif 폭과 달라야 한다(= 폴백이 아니다).
  2) generateThumb()이 toBlob을 부르는 시점엔 이미 그 폰트가 로드돼 있어야 한다
     (첫 생성부터 맞는 폰트 — "첫 장은 폴백, 두 번째부터 정상"이 되면 더 헷갈린다).

produce.html의 ensureThumbFontsLoaded/document.fonts.load 호출을 지우면 이 두 테스트가
죽는다(실측 완료 — task-6-report.md 참조).
"""
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

pytestmark = pytest.mark.skipif(sync_playwright is None, reason="playwright 미설치")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server():
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "shopping_shorts.app:app",
         "--port", str(port), "--log-level", "warning"],
        cwd=str(REPO_ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 20
        html = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{base}/produce.html", timeout=1) as r:
                    if r.status == 200:
                        html = r.read().decode("utf-8")
                        break
            except OSError:
                time.sleep(0.3)
        assert html is not None, "서버가 뜨지 않았다(20초 타임아웃)"
        # ⚠️ 포트가 우연히 재사용됐으면 curl 200이 남의(낡은) 서버일 수 있다 —
        # 내 픽스 심볼이 실제로 서빙되는지 확인하고서야 테스트를 신뢰한다.
        assert "ensureThumbFontsLoaded" in html, \
            "이 포트가 낡은 빌드를 서빙 중이다(내 픽스 심볼 없음) — 남의 서버일 가능성"
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


_SET_LAYER_JS = """
THUMB_STATE.layers = [{text:'가나다라마바사', font:'TmonMonsori.ttf', size:96,
  color:'#000', outline:null, box:null, rot:0, x:0.5, y:0.5}];
"""


def test_canvas_uses_real_font_not_fallback(live_server):
    """렌더 후 canvas 측정폭이 sans-serif와 달라야 한다 — 같으면 폴백 중이라는 뜻."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{live_server}/produce.html")
        result = page.evaluate("""async () => {
            %s
            await renderThumbCanvas();
            const c = document.createElement('canvas');
            const cx = c.getContext('2d');
            const text = THUMB_STATE.layers[0].text;
            cx.font = '900 96px HCTmon';
            const wFont = cx.measureText(text).width;
            cx.font = '900 96px sans-serif';
            const wSans = cx.measureText(text).width;
            return {wFont, wSans, loaded: document.fonts.check('900 96px HCTmon')};
        }""" % _SET_LAYER_JS)
        browser.close()
    assert result["loaded"] is True, "document.fonts.check가 false — 폰트가 로드되지 않았다"
    assert abs(result["wFont"] - result["wSans"]) > 1.0, (
        f"HCTmon 폭({result['wFont']})이 sans-serif 폭({result['wSans']})과 사실상 같다 "
        "= 캔버스가 기본 고딕으로 폴백해서 그렸다"
    )


def test_generate_thumb_uses_loaded_font_on_first_call(live_server):
    """generateThumb()이 toBlob을 부르는 시점엔 이미 폰트가 로드돼 있어야 한다 —
    아니면 저장되는 PNG 자체가(=최종 산출물, WYSIWYG) 첫 생성만 폴백 폰트로 나간다."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(f"{live_server}/produce.html")
        result = page.evaluate("""async () => {
            %s
            STATE.job_id = 'no-such-job';   // 저장 API가 404를 내도 상관없다 — toBlob 타이밍만 본다
            const cv = document.getElementById('thumbCanvas');
            const origToBlob = cv.toBlob.bind(cv);
            let loadedAtToBlobTime = null;
            cv.toBlob = (cb, type) => {
                loadedAtToBlobTime = document.fonts.check('900 96px HCTmon');
                origToBlob(cb, type);
            };
            await generateThumb();
            return {loadedAtToBlobTime};
        }""" % _SET_LAYER_JS)
        browser.close()
    assert result["loadedAtToBlobTime"] is True, (
        "toBlob 시점에 폰트가 아직 로드 전이었다 — 첫 생성 PNG가 폴백 폰트로 저장된다"
    )
