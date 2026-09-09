"""자막제거 키 잔액 바로가기(2026-09-04 사장님 "바로가기탭으로 조회").

업체엔 잔액 API가 없어 숫자 연동은 불가 → 업체 대시보드로 새 탭 링크만 건다.
produce.html은 업체명을 못 쓰므로(test_subclean_ui) 주소는 app.py 한 곳에 두고
화면은 /go/subclean-credits 로 온다. 이 계약이 깨지면 버튼이 죽은 링크가 된다.
"""
import re
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod

HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
GO = 'href="/go/subclean-credits"'


def test_redirect_goes_to_vendor_dashboard(monkeypatch):
    """/go/subclean-credits → 302 → 업체 개발자 대시보드(잔액이 뜨는 페이지)."""
    monkeypatch.setattr(appmod, "_AUTH_ON", False)
    c = TestClient(appmod.app)
    r = c.get("/go/subclean-credits", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://vmake.ai/developers"


def test_icon_button_above_toggle_outside_label():
    """4단계 카드 우상단: 토글 **위**의 아이콘 버튼(2026-09-04 사장님 "아이폰 아이콘 형태").
    ★label 밖에 있어야 한다 — 안에 두면 누를 때 토글이 같이 뒤집힌다. 제목 label은 for=로 묶는다."""
    start = HTML.index('class="hero rise"')
    seg = HTML[start:HTML.index('id="subState"', start)]
    btn = seg.index('id="cleanCreditBtn"')
    assert GO in seg[btn:btn + 200] and 'target="_blank"' in seg[btn:btn + 200]
    assert "크레딧 확인하기" in seg[btn:btn + 400]
    assert " hidden" in seg[btn:btn + 200]                     # 기본은 숨김 — 서버가 켠다
    assert seg.index("</label>") < btn < seg.index('id="subToggle"')   # label 닫힌 뒤, 토글 앞
    assert 'for="subToggle"' in seg
    # ★토글 래퍼는 inline-flex — inline-block이면 .sw-track(span)이 0×0이 돼 트랙이 사라진다(라이브 실측)
    assert ".sw-wrap{position:relative;display:inline-flex;" in HTML
    # 종전 CTA 아래 링크는 옮겨졌다(두 벌이면 하나가 썩는다)
    tail = HTML[HTML.index('id="btnCleanPreview"'):HTML.index('id="cleanPreview" ', HTML.index('id="btnCleanPreview"'))]
    assert GO not in tail


def test_link_in_no_credit_failure_message():
    """크레딧 소진 실패 문구(cleanFailHtml no_credit)에도 같은 링크 — 실패한 자리에서 바로 충전."""
    m = re.search(r"kind === 'no_credit'\)\{(.*?)kind === 'interrupted'", HTML, re.S)
    assert m, "cleanFailHtml no_credit 분기를 못 찾음"
    assert GO in m.group(1)


def test_produce_html_still_has_no_vendor_name():
    """링크를 달아도 화면 파일엔 업체명이 없어야 한다(브랜드 정책 유지)."""
    assert "vmake" not in HTML.lower()
