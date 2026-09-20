# -*- coding: utf-8 -*-
"""핀터레스트 출처축 필터 — 원본·재업로드 버튼 (2026-09-06 사장님 오픈 준비).

사장님: "테무 아마존도 좋은게 많다 / 아마존 테무를 따로 카테고리화할수있나?"

라이브 실측(서버 reference.db, 2,259건)으로 pin_dest 값이 깨끗하게 갈렸다:

    'Uploaded by user'  804건  ← 링크 없는 원본 (가장 큰 덩어리)
    'instagram.com'     682건  ← 남의 릴스 재업로드 (광고성의 본진)
    'temu.to'/'temu.com' 392건 ← 테무
    'amazon.com'/'amzn.to'/'amzlink.to' 166건 ← 아마존
    (빈값)               27건
    그 외(쇼피·유튜브·핀터레스트 등) 소수

★종전 버튼은 [전체][쇼핑몰][테무][알리][아마존] 다섯이었는데,
  - '알리'는 실측 **1건**뿐이다(핸드오프에도 "aliexpress 축은 통째로 죽었다" 기록).
  - 가장 큰 두 덩어리인 **원본 804건 · 재업로드 682건에 버튼이 아예 없었다**.
  즉 화면에서 2,259건 중 1,486건(66%)을 골라낼 방법이 없었다.

쇼츠 규격 적합도 실측 — 테무를 버릴 게 아니라는 근거:
    테무   94% (5~40초)  ← 가장 높다
    아마존 88%
    원본   88%
    재업   83%

0순위-B: 필터 판정은 index.html의 pinFilter/render 두 곳이 같은 목록을 봐야 한다.
  서버 pinterest_crawl.SHOP_DOMAINS와도 어긋나면 '쇼핑몰'이 서로 다른 걸 뜻하게 된다.
"""
import re
from pathlib import Path

import pytest

HTML = Path(__file__).resolve().parents[1] / "static" / "index.html"


@pytest.fixture(scope="module")
def html():
    return HTML.read_text(encoding="utf-8")


def _buttons(html):
    """핀터레스트 필터 버튼의 data-dest 값 목록."""
    return re.findall(r'class="ftog pinf[^"]*"\s+data-dest="([^"]*)"', html)


def test_원본_버튼이_있다(html):
    """★804건짜리 가장 큰 덩어리 — 종전엔 골라낼 방법이 없었다."""
    assert "uploaded by user" in html.lower(), "원본(Uploaded by user) 필터가 없다"


def test_재업로드_버튼이_있다(html):
    """★682건. 사장님이 '광고 같다'고 하신 것의 본진."""
    btns = _buttons(html)
    assert any("instagram" in b for b in btns), f"재업로드 필터가 없다: {btns}"


def test_테무_아마존은_따로_남는다(html):
    """사장님 지시 '아마존 테무를 따로 카테고리화' — 합치지 말 것."""
    btns = _buttons(html)
    assert any(b == "temu" for b in btns), f"테무 버튼이 사라졌다: {btns}"
    assert any("amazon" in b or "amzn" in b for b in btns), f"아마존 버튼이 사라졌다: {btns}"


def test_전체_버튼은_그대로(html):
    """회귀 방지 — 빈 data-dest가 '전체'다."""
    assert "" in _buttons(html), "전체 버튼(data-dest=\"\")이 없다"


def test_원본_판정이_pin_dest_빈값도_포함하지_않는다(html):
    """'Uploaded by user'와 빈값(27건)은 다르다 — 빈값은 수집 실패라 원본으로 세지 않는다.

    render()의 필터는 `d && want.some(...)`라 pin_dest가 비면 어떤 필터에도 안 걸린다.
    원본 필터가 빈값까지 끌어오면 '원본 804건'이라는 실측과 화면 숫자가 어긋난다.
    """
    m = re.search(r"PLATFORM==='pinterest' && PIN_DEST\)\{(.{0,400}?)\}", html, re.S)
    assert m, "render()의 핀터레스트 필터 블록을 못 찾았다"
    block = m.group(1)
    assert "d &&" in block or "d&&" in block, \
        "pin_dest 빈값 가드가 사라졌다 — 빈값 27건이 필터에 섞인다"


def test_알리_버튼은_없앴다(html):
    """실측 1건뿐인 죽은 축. 버튼이 남아 있으면 눌러도 늘 0건이라 고장으로 보인다."""
    btns = _buttons(html)
    assert not any(b == "aliexpress" for b in btns), \
        f"알리 버튼이 아직 있다(실측 1건뿐인 죽은 축): {btns}"


def test_필터_목록이_두_곳에서_같다(html):
    """0순위-B — pinFilter()와 render()가 같은 PIN_SHOP_KEYS를 본다."""
    assert html.count("PIN_SHOP_KEYS") >= 3, \
        "쇼핑몰 목록이 한 곳에서만 쓰이거나 복제됐다"
