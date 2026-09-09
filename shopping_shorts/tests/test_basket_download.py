# -*- coding: utf-8 -*-
"""영상 즐겨찾기 원본 내려받기 게이트 (2026-09-04 사장님 "프로등급만·횟수제한 없음·
영상즐겨찾기 페이지만·파일명 넣고").

소스 검사 + 파일명 함수 단위 검사. 실제 다운로드는 유료 업체/외부망이라 여기서 안 돈다.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
COLLECTION = (ROOT / "static" / "collection.html").read_text(encoding="utf-8")

MARK = '@app.get("/api/mix/basket/download")'


def _handler_body():
    i = APP.index(MARK)
    nxt = APP.find("\n@app.", i + 10)
    return APP[i: nxt if nxt > 0 else i + 4000]


def test_라우트가_프로등급_게이트를_가진다():
    """무료·체험(ranking_only)이 원본을 받아가면 안 된다. 판정은 access_level 한 곳."""
    b = _handler_body()
    assert 'access_level(cid) != "full"' in b
    assert "402" in b and "need_pro" in b


def test_대상_url은_회원_바구니에서만_꺼낸다():
    """클라이언트가 준 url을 그대로 받으면 아무 주소나 서버가 받게 된다(SSRF)."""
    b = _handler_body()
    assert "mix_basket_list(customer_id=cid)" in b
    assert "body.get" not in b            # 클라이언트 url을 신뢰하지 않는다


def test_다운로드는_공용_download_any를_쓴다():
    """플랫폼별 처리를 여기 또 적으면 어떤 건 되고 어떤 건 안 되는 어긋남이 난다(0순위-B)."""
    b = _handler_body()
    assert "download_any(" in b
    assert "_PLAY_CACHE_DIR" in b          # /api/play와 같은 캐시 폴더


def test_파일명을_붙여_내려준다():
    b = _handler_body()
    assert "filename=fname" in b
    assert "_safe_download_name(" in b


def _safe_name():
    i = APP.index("def _safe_download_name")
    j = APP.index(MARK)
    ns = {"re": re}
    exec(APP[i:j], ns)                     # noqa: S102 — 테스트가 그 함수만 떼어 본다
    return ns["_safe_download_name"]


def test_파일명이_경로문자를_지운다():
    f = _safe_name()
    out = f('a/b\c:d*e?f"g<h>i|j')
    assert not set(out[:-4]) & set('/\:*?"<>|')
    assert out.endswith(".mp4")


def test_파일명이_한글과_이모지를_지킨다():
    """한글 제목이 통째로 날아가면 받아놓고 뭐가 뭔지 모른다."""
    assert _safe_name()("다이소 청소 꿀템 ✨").startswith("다이소 청소 꿀템")


def test_파일명이_비면_대체값을_쓴다():
    assert _safe_name()("   ", fallback="sc123") == "sc123.mp4"


def test_파일명_길이를_자른다():
    assert len(_safe_name()("가" * 200)) <= 64


def test_화면_버튼은_등급을_서버에서_받아_켠다():
    """화면이 등급을 스스로 계산하면 서버 게이트와 어긋난다(0순위-B)."""
    assert "CAN_DL" in COLLECTION
    assert "d.level === 'full'" in COLLECTION
    assert "downloadOne(" in COLLECTION


def test_저장_버튼은_즐겨찾기_페이지에만_있다():
    """사장님 지시: 영상 즐겨찾기 페이지만. 랭킹·렌즈(index.html)엔 안 붙인다."""
    other = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    assert "/api/mix/basket/download" not in other
