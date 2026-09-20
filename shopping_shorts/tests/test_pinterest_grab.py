"""핀터레스트 원클릭 담기 (2026-09-11 고객 "담기 버튼이 없다").

뿌리: 담기 스크립트가 핀터레스트를 몰랐다(@match·매니페스트·서버 _GRAB_DOMAINS 셋 다 없음).
받기(media_download._download_pinterest)는 이미 있었으니 세 곳을 짝으로 연다.
"""
from pathlib import Path

from shopping_shorts.app import _grab_platform

_ROOT = Path(__file__).resolve().parents[1]


def test_서버가_핀터레스트_주소를_안다():
    assert _grab_platform("https://www.pinterest.com/pin/768074911447008679/") == "pinterest"
    assert _grab_platform("https://kr.pinterest.com/pin/699113542148777443/") == "pinterest"


def test_로더와_확장이_핀터레스트에서_뜬다():
    loader = (_ROOT / "userscript" / "grab.user.js").read_text(encoding="utf-8")
    assert "// @match        https://*.pinterest.com/*" in loader
    assert "@version      2.5.0" in loader, "@match가 바뀌면 버전을 올려야 자동업데이트가 돈다"
    man = (_ROOT / "extension" / "manifest.json").read_text(encoding="utf-8")
    assert '"https://*.pinterest.com/*"' in man


def test_로직에_핀_카드버튼과_플로팅_규칙이_있다():
    logic = (_ROOT / "userscript" / "grab_logic.js").read_text(encoding="utf-8")
    assert "function addPinCardBtns()" in logic and "try{addPinCardBtns();}" in logic
    assert "function syncPinFloat()" in logic and "try{syncPinFloat();}" in logic
    assert "var LOGIC_VER = 20260911;" in logic, "LOGIC_VER를 올려야 옛 로직을 이긴다"
