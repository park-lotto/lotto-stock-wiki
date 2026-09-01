"""자막제거(가장 비싼 단계) 가격이 **누르기 전에** 보이는지.

2026-09-02 라이브 실측:
  5단계 패널 전문에 'P·포인트·크레딧·차감'이 한 글자도 없었다(토글 전/후 모두).
  실제로는 _charge_clean이 선차감(단가표 vmake=5P)하는데, 안내 문구는
  "추가 비용 없이 빨라져요"라 **오히려 무료로 읽혔다**.
  고객이 금액을 처음 보는 곳은 '잔액 부족으로 실패한 뒤'였다.

문자열만 세면 리팩터링에 우연히 통과하므로, 실제 함수를 떼어 **서버 응답 모양대로**
돌려 문구를 확인한다(단가 0 = 내 키 = 무료 안내, 잔액 부족 = 경고).
"""
import json
import pathlib
import shutil
import subprocess

import pytest

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"
NODE = shutil.which("node")
_START = "let _cleanCostCache = null;"
_END = "async function onSubToggle()"

_HARNESS = r"""
'use strict';
let _html = '', _text = '';
const _el = {
  set innerHTML(v){ _html = v; }, get innerHTML(){ return _html; },
  set textContent(v){ _text = v; }, get textContent(){ return _text; },
};
global.document = { getElementById: (id) => (id === 'cleanCost' ? _el : null) };
global.fetch = async () => ({ ok: true, json: async () => PAYLOAD });
"""

_DRIVER = r"""
(async () => { await renderCleanCost();
  console.log(JSON.stringify({html: _html, text: _text})); })();
"""


def _run(tmp_path, payload):
    src = PRODUCE_HTML.read_text(encoding="utf-8")
    frag = src[src.index(_START):src.index(_END)]
    js = tmp_path / "t.js"
    js.write_text("const PAYLOAD = " + json.dumps(payload) + ";\n"
                  + _HARNESS + frag + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_shows_price_before_click(tmp_path):
    """실제로 깎이는 고객(charged=true) — 금액·잔액·부족경고가 다 나와야 한다."""
    got = _run(tmp_path, {"balance": 0.7,
                          "subclean_price": 5, "subclean_charged": True})
    body = got["html"] + got["text"]
    assert "5P" in body, f"단가가 안 보인다: {body!r}"
    assert "차감" in body, f"차감된다는 사실이 안 보인다: {body!r}"
    # 잔액 0.7 < 5 → 지금은 못 돌린다는 것도 미리 알려야 한다
    assert "모자라" in body, f"잔액 부족 경고가 없다: {body!r}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_free_when_server_says_not_charged(tmp_path):
    """★사장님(cid 0)·내 키·관리자 면제 — 단가는 5P여도 한 푼도 안 나간다.

    라이브 실측 2026-09-02: 관리자 계정은 cid 0이라 _charge_clean이 즉시 0을 반환하는데
    /api/settings/points는 vmake=5를 그대로 준다. 단가만 보고 "5P 차감"이라 쓰면
    **안 나가는 돈을 겁주는** 거짓 안내가 된다.
    """
    got = _run(tmp_path, {"balance": 0.7,
                          "subclean_price": 5, "subclean_charged": False})
    body = got["html"] + got["text"]
    assert "차감되지 않" in body, f"무료 안내가 아니다: {body!r}"
    assert "5P" not in body, f"안 나가는 5P를 보여준다: {body!r}"
    assert "모자라" not in body, f"안 깎이는데 잔액 부족을 경고한다: {body!r}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_enough_points_no_warning(tmp_path):
    """잔액이 넉넉하면 경고 없이 금액만 알린다."""
    got = _run(tmp_path, {"balance": 120,
                          "subclean_price": 5, "subclean_charged": True})
    body = got["html"] + got["text"]
    assert "5P" in body and "120P" in body, body
    assert "모자라" not in body, f"멀쩡한데 경고가 뜬다: {body!r}"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_old_server_without_charged_field(tmp_path):
    """subclean_charged가 없는 옛 응답이면 단가만 보고 종전대로 — 회귀 없이 견딘다."""
    got = _run(tmp_path, {"balance": 120, "subclean_price": 5})
    assert "5P" in (got["html"] + got["text"])
    got0 = _run(tmp_path, {"balance": 0, "subclean_price": 0})
    assert "차감되지 않" in (got0["html"] + got0["text"])


def test_produce_html_has_no_vendor_name():
    """★고객 화면엔 벤더명이 한 글자도 없어야 한다 — 내가 여기서 한 번 어겼다.

    가격 안내를 붙이면서 서버 응답 키(prices.vmake)를 그대로 썼다가
    test_no_vmake_anywhere_in_produce_html에 걸렸다. 서버가 중립 이름
    (subclean_price/subclean_charged)으로도 주게 하고 화면은 그걸 쓴다.
    """
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    assert "vmake" not in html and "VMake" not in html
    assert "subclean_price" in html, "중립 이름으로 단가를 읽어야 한다"
