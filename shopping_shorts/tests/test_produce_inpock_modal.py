"""📦 인포크 등록 — **새 탭**으로 연다(2026-08-18). iframe 방식은 폐기했다.

### 왜 iframe이 성립하지 않는가 (실측으로 확정 — 다시 시도하지 마라)

프레임 삽입 자체는 막히지 않는다: `link.inpock.co.kr`은 X-Frame-Options·CSP·meta CSP·
프레임버스팅이 **하나도 없다**. 실제로 틀 안에서 436개 엘리먼트가 렌더된다.

진짜 벽은 **쿠키**다. 인포크가 발급하는 쿠키 11개가 **전부 `SameSite=Lax`**이고
`SameSite=None`이 **0개**다(실측). Lax는 크로스사이트 iframe에 아예 안 실린다 →
인포크 탭에서는 로그인 상태인데 **틀 안에서만** "로그인 정보가 만료되었습니다"가 뜬다.
로그아웃 후 재로그인해도 새 쿠키도 Lax라 소용없다(사장님 실제로 겪음).

부수적으로 로그인 API(`link-rest.inpock.co.kr`)도 자기 도메인 Origin만 허용한다
(우리 도메인엔 `Access-Control-Allow-Origin`이 안 온다) → 틀 안 로그인 시도는
"네트워크 오류 💦"로 끝난다.

→ **우리가 고칠 수 있는 게 아니다.** 인포크가 `SameSite=None; Secure`로 바꾸지 않는 한
   틀 안에서 로그인 상태를 쓸 수 없다. 새 탭이 유일한 방법이고, 원래 방식이 옳았다.
"""
import pathlib
import re
import shutil
import subprocess
import tempfile

import pytest

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")


def _html():
    return PRODUCE.read_text(encoding="utf-8")


def test_iframe_modal_is_gone():
    """iframe 모달의 잔해가 남아 있으면 안 된다 — 다음 사람이 되살리게 된다."""
    html = _html()
    for dead in ('id="inpockModal"', 'id="inpockFrame"', 'id="inpockModalBar"',
                 "inpockFrameReload", "gen-box-wide"):
        assert dead not in html, dead


def test_reason_is_recorded_in_the_code():
    """왜 iframe을 안 쓰는지 코드에 남아 있어야 한다(같은 시도 반복 방지)."""
    html = _html()
    assert "SameSite=Lax" in html or "SameSite" in html


def test_opens_inpock_in_a_new_tab():
    """★window.open의 반환값으로 성공을 판정하지 않는다.

    `noopener`를 주면 window.open은 **성공해도 null**을 돌려준다(사양). 그걸 실패로 보면
    창이 멀쩡히 열렸는데 "팝업 차단" 경고가 뜬다 — 실측으로 잡은 버그다.
    대신 rel=noopener를 단 <a>를 만들어 클릭한다(보안은 유지, 판정은 브라우저에 맡긴다).
    """
    html = _html()
    body = html.split("async function inpockModalOpen(")[1].split("\n}")[0]
    assert "link.inpock.co.kr" in body
    assert "_blank" in body
    assert "noopener" in body
    assert "a.click()" in body
    assert "window.open(" not in body      # 반환값 판정으로 되돌아가지 않게 못 박는다


def test_open_refuses_when_no_link():
    """올릴 링크가 없으면 열지 않는다.

    상품이 있어도 url·partner_url이 둘 다 비면 final_link가 빈 문자열이라
    (coupang_partners.final_link) 버튼은 그려지고 링크만 없다. 그대로 열면 헛걸음이다.
    """
    html = _html()
    body = html.split("async function inpockModalOpen(")[1].split("\n}")[0]
    guard = body.split("const copied")[0]
    assert "if(!link)" in guard
    assert "return;" in guard
    assert "stepName(" in guard          # 단계 번호를 손으로 안 적는다(0순위-B)


def test_manual_open_link_stays_as_fallback():
    """자동으로 열리지 않아도(팝업 차단 등) 손으로 열 링크가 박스에 남아 있어야 한다."""
    html = _html()
    box = html.split("async function refreshInpock(")[1].split("function inpockCopy(")[0]
    assert "인포크만 열기" in box
    assert 'target="_blank"' in box


def test_copy_result_is_checked_not_assumed():
    """복사 성공을 '됐다고 치지' 않는다 — 실패하면 화면이 실패라고 말해야 한다.

    clipboard API는 비보안 컨텍스트·권한 거부에서 조용히 실패한다. 실패했는데
    '복사됨'이라고 띄우면 사장님이 빈 클립보드로 붙여넣게 된다.
    """
    html = _html()
    fn = html.split("async function inpockCopyChecked(")[1].split("// 📦 인포크에 등록")[0]
    assert "return true" in fn and "return false" in fn
    assert "execCommand" in fn                       # 막혔을 때 옛 방식으로 한 번 더
    body = html.split("async function inpockModalOpen(")[1].split("\n}")[0]
    assert "copied ?" in body or "copied?" in body    # 그 결과로 문구가 갈린다


def test_manual_fallbacks_remain():
    """자동이 막혀도 사람이 손으로 할 길이 남아 있어야 한다."""
    html = _html()
    box = html.split("async function refreshInpock(")[1].split("function inpockCopy(")[0]
    assert "inpockCopy()" in box            # 링크만 복사
    assert 'target="_blank"' in box         # 인포크만 열기
    assert "inpock_registered" in box       # 등록 완료 체크


def test_product_guidance_points_at_where_the_ui_actually_is():
    """상품이 없을 때 "어디로 가라"가 실제 UI 위치와 같아야 한다.

    상품 확정 UI(#coupangSlot)는 2026-08-18 쿠파스 트랙이 3단계 → 8단계 SEO로 이사했다.
    안내가 옛 자리를 가리키면 '가라는 곳이 빈 화면'이 된다.
    """
    html = _html()
    seo_panel = html.split('<section class="panel" data-step="5">')[1].split("</section>")[0]
    assert 'id="coupangSlot"' in seo_panel

    box = html.split("async function refreshInpock(")[1].split("function inpockCopy(")[0]
    assert "stepName('seo')" in box and "stepName('mix')" not in box
    guard = html.split("async function inpockModalOpen(")[1].split("const copied")[0]
    assert "stepName('seo')" in guard and "stepName('mix')" not in guard


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_produce_inline_js_syntax_ok(tmp_path):
    """제작소가 통째로 안 열리던 SyntaxError 사고 방지(기존 관례와 동일).

    ★`node --check`에 파일로 넘긴다 — `-e`는 윈도우 명령줄 상한(WinError 206)에 걸린다.
    """
    html = _html()
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    js = tmp_path / "inline.js"
    js.write_text("\n;\n".join(blocks), encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
