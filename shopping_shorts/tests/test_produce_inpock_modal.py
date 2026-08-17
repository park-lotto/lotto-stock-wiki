"""📦 인포크링크 등록 모달(2026-08-18) 회귀 가드.

9단계(최종렌더)에서 창을 옮겨 다니지 않고 인포크에 바로 올린다.
실측 근거(이 기능이 성립하는 전제): link.inpock.co.kr은 X-Frame-Options·CSP·meta CSP·
프레임버스팅이 하나도 없고, 로그인 세션 쿠키가 iframe 안에서 유지된다(사장님 계정 실확인).
→ 저쪽이 나중에 프레임 차단을 걸면 이 기능은 죽는다. 그때는 테스트가 아니라 화면이 먼저 알려준다.
"""
import pathlib
import re
import shutil
import subprocess

import pytest

PRODUCE = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")


def _html():
    return PRODUCE.read_text(encoding="utf-8")


def test_modal_markup_present():
    html = _html()
    assert 'id="inpockModal"' in html          # 모달 컨테이너
    assert 'id="inpockFrame"' in html          # 인포크가 뜰 iframe
    assert 'id="inpockModalBar"' in html       # 링크·등록완료 바
    assert "gen-box-wide" in html              # 3단 레이아웃이 눌리지 않을 넓은 변형


def test_modal_follows_existing_gen_bg_convention():
    """새 모달 규약을 만들지 않는다 — pmModal과 같은 .gen-bg/.gen-box/.open을 쓴다."""
    html = _html()
    block = html.split('id="inpockModal"')[1].split("</div>")[0]
    assert "gen-bg" in html.split('id="inpockModal"')[0][-40:]   # class="gen-bg" id="inpockModal"
    assert "gen-box" in block
    assert "inpockModalClose()" in block
    assert ".gen-box-wide{" in html                              # 스타일이 실제로 정의돼 있다


def test_open_close_functions_defined():
    html = _html()
    assert "async function inpockModalOpen(" in html
    assert "function inpockModalClose(" in html
    assert "async function inpockCopyChecked(" in html


def test_button_wired_and_new_tab_link_removed():
    """버튼이 모달을 부르고, 창 밖으로 내보내던 새 탭 링크는 사라져야 한다.

    새 탭 링크가 남아 있으면 '창 옮겨 다니기'가 그대로라 이 작업의 목적이 사라진다.
    """
    html = _html()
    assert 'onclick="inpockModalOpen()"' in html
    assert "인포크에 등록하기" in html
    assert "인포크링크 열기" not in html          # 옛 새 탭 링크 제거 확인


def test_open_refuses_when_no_link():
    """올릴 링크가 없으면 열지 않는다.

    상품이 있어도 url·partner_url이 둘 다 비면 final_link가 빈 문자열이라
    (coupang_partners.final_link) 버튼은 그려지고 링크만 없다. 그대로 열면
    붙여넣을 게 없는 채 인포크만 떠서 헛걸음이 된다.
    """
    html = _html()
    body = html.split("async function inpockModalOpen(")[1].split("function inpockModalClose(")[0]
    guard = body.split("const copied")[0]
    assert "if(!link)" in guard          # 링크 없으면
    assert "return;" in guard            # 열지 않고 되돌아간다
    assert "stepName(" in guard          # 단계 번호를 손으로 안 적는다(0순위-B)


def test_copy_result_is_checked_not_assumed():
    """복사 성공을 '됐다고 치지' 않는다 — 실패하면 화면이 실패라고 말해야 한다.

    clipboard API는 비보안 컨텍스트·권한 거부에서 조용히 실패한다. 실패했는데
    '복사됨'이라고 띄우면 사장님이 빈 클립보드로 붙여넣게 된다.
    """
    html = _html()
    fn = html.split("async function inpockCopyChecked(")[1].split("async function inpockModalOpen(")[0]
    assert "return true" in fn and "return false" in fn      # 성공/실패를 갈라 돌려준다
    assert "execCommand" in fn                                # 막혔을 때 옛 방식으로 한 번 더
    body = html.split("async function inpockModalOpen(")[1].split("function inpockModalClose(")[0]
    assert "copied?" in body                                  # 그 결과로 문구가 갈린다


def test_iframe_src_is_lazy():
    """src를 미리 박아두면 제작소를 열 때마다 인포크를 불러 느려진다."""
    html = _html()
    tag = html.split('id="inpockFrame"')[1].split(">")[0]
    assert "src=" not in tag                                  # 마크업엔 src 없음
    body = html.split("async function inpockModalOpen(")[1].split("function inpockModalClose(")[0]
    assert "if(!frame.src)" in body                            # 열 때 한 번만 넣는다


def test_close_keeps_session():
    """닫을 때 src를 비우면 다시 열 때마다 재로그인 흐름을 탄다 — 살려둬야 한다."""
    html = _html()
    fn = html.split("function inpockModalClose(")[1].split("\n}")[0]
    assert "frame.src=''" not in fn.replace(" ", "")
    assert "refreshInpock()" in fn        # 모달에서 체크한 등록완료를 9단계 박스에 반영


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_produce_inline_js_syntax_ok(tmp_path):
    """제작소가 통째로 안 열리던 SyntaxError 사고 방지(기존 관례와 동일)."""
    html = _html()
    blocks = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S)
    js = tmp_path / "inline.js"
    js.write_text("\n;\n".join(blocks), encoding="utf-8")
    r = subprocess.run([NODE, "--check", str(js)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
