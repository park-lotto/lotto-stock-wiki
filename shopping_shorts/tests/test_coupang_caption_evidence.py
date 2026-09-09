# -*- coding: utf-8 -*-
"""랭킹 카드 쿠팡 판독이 **캡션**을 근거로 쓰는가 (2026-09-05 사장님 제보).

■ 무엇이 문제였나 (실측)
버튼에 "벽선반"·"청소용 스펀지"·"프라이팬" 같은 범주어가 박혀 쿠팡에서 엉뚱한 게 나왔다.
원인 두 가지가 겹쳐 있었다:
  ① 프리워밍(identify_batch)이 **썸네일 이미지만** 서버로 보냈다 — 캡션은 카드에 이미
     그려져 있는데(index.html) 요청에 안 실려 버려졌다.
  ② 그 판독이 쓰던 product_name._PROMPT는 "자막·문구를 완전히 무시하라"고 지시한다.
     그건 08-04에 **"같은 제품 영상 모으기"**용으로 만든 것이라 범주어가 오히려 맞다.
     쿠팡 검색은 정반대로 **살 물건 하나**를 특정해야 한다.

■ 그래서 못 박는 것
  - 캡션이 판독기까지 실제로 도착한다(배선). 문자열 검사로는 못 잡는다.
  - 해시태그는 근거에서 빠진다(분위기어 오염 방지).
  - 캡션만 있고 썸네일이 없는 카드도 판독 대상이다(종전엔 통째로 빠졌다).
  - ★묶기용 캐시(vision_tags.product)를 건드리지 않는다 — 아카이브 유사도가
    같이 흔들리면 안 된다(0순위-B).
"""
import sqlite3

import pytest

from shopping_shorts import coupang_query, product_name
from shopping_shorts.store import Store


# ── 캡션 본문 정리 ──────────────────────────────────────────────────────────

def test_caption_body_해시태그를_뗀다():
    """'#' 이후는 전부 버린다 — 태그는 분위기어 덩어리다."""
    cap = "못 안 박는 3단 조립식 벽선반 #살림꿀템 #자취템"
    body = coupang_query.caption_body(cap)
    assert "3단 조립식 벽선반" in body
    assert "#" not in body
    assert "살림꿀템" not in body      # 살림꿀템(태그)이 새면 안 된다


def test_caption_body_상투구를_뗀다():
    """'프로필 링크'·'댓글 남겨'·'협찬' 같은 안내줄은 제품과 무관하다."""
    cap = ("댓글 남겨주시면 최저가 링크 보내드려요\n"
           "슬라이더를 밀어 쓰는 지우개예요")
    body = coupang_query.caption_body(cap)
    assert "지우개" in body
    assert "댓글" not in body


def test_caption_body_태그만_있으면_빈문자열():
    """쓸 게 없으면 ''을 준다 → 호출부가 썸네일로만 간다(나빠지지 않는다)."""
    assert coupang_query.caption_body("#살림꿀팁 #주방용품") == ""
    assert coupang_query.caption_body("") == ""
    assert coupang_query.caption_body(None) == ""


def test_caption_body_여러줄을_본다():
    """★hook_harvest는 첫 줄만 본다 — 제품명은 2~3번째 줄에 오는 경우가 많다.

    그래서 그 함수를 재사용하지 않고 여기서 따로 정했다(실측: 첫 줄이
    '댓글 남겨주시면 최저가 링크…'이고 제품 얘기는 그 아래였다)."""
    cap = "이거 진짜 대박\n\n무선 노래방 마이크인데요"
    body = coupang_query.caption_body(cap)
    assert "노래방 마이크" in body


# ── 배선: 캡션이 판독기까지 가는가 ─────────────────────────────────────────

def _payload():
    return [
        {"shortcode": "withboth", "thumbnail": "http://x/a.jpg",
         "caption": "무선 노래방 마이크 #꿀템"},
        {"shortcode": "caponly", "thumbnail": "",
         "caption": "슬라이더 지우개 추천"},
        {"shortcode": "thumbonly", "thumbnail": "http://x/c.jpg", "caption": ""},
        {"shortcode": "nothing", "thumbnail": "", "caption": ""},
    ]


def test_캡션이_모델까지_도착한다(tmp_path, monkeypatch):
    """★배선 테스트 — 문자열 검사가 아니라 판독 함수가 **무엇을 받았는지** 본다."""
    db = str(tmp_path / "t.db")
    Store(db)
    seen = []
    monkeypatch.setattr(product_name, "_identify_shop_one",
                        lambda img, cap: seen.append((bool(img), cap)) or "X")
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes",
                        lambda u: b"IMG" if u else None)

    out = product_name.identify_shop_many(_payload(), db)

    by = {c for _, c in seen}
    assert any("노래방 마이크" in c for c in by), "썸네일+캡션 카드의 캡션이 안 갔다"
    assert any("지우개" in c for c in by), "캡션만 있는 카드가 통째로 빠졌다"
    assert "nothing" not in out, "근거가 아예 없는 카드는 태우면 안 된다"
    assert len(seen) == 3


def test_캡션만_있어도_판독한다(tmp_path, monkeypatch):
    """종전엔 thumbnail이 없으면 통째로 건너뛰었다 — 캡션이 이미지보다 정확할 수 있다."""
    db = str(tmp_path / "t.db")
    Store(db)
    monkeypatch.setattr(product_name, "_identify_shop_one", lambda img, cap: "지우개")
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: None)

    out = product_name.identify_shop_many(
        [{"shortcode": "caponly", "thumbnail": "", "caption": "슬라이더 지우개 추천"}], db)
    assert out.get("caponly") == "지우개"


# ── 캐시: 묶기용을 건드리지 않는다 (0순위-B) ───────────────────────────────

def test_묶기용_product를_건드리지_않는다(tmp_path, monkeypatch):
    """★vision_tags.product는 아카이브 유사도(same_product)가 쓴다.

    쿠팡용 이름을 거기 쓰면 묶기 기준이 조용히 바뀐다 — 별도 칸(shop_product)이어야 한다."""
    db = str(tmp_path / "t.db")
    st = Store(db)
    st.save_product("v1", "벽선반", category="수납")     # 묶기용 기존 값

    monkeypatch.setattr(product_name, "_identify_shop_one",
                        lambda img, cap: "3단 조립식 벽선반")
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: b"IMG")

    product_name.identify_shop_many(
        [{"shortcode": "v1", "thumbnail": "http://x/a.jpg", "caption": "c"}], db)

    with sqlite3.connect(db) as c:
        prod, shop = c.execute(
            "SELECT product, shop_product FROM vision_tags WHERE shortcode=?", ("v1",)).fetchone()
    assert prod == "벽선반", "묶기용 product가 덮였다 — 아카이브 유사도가 흔들린다"
    assert shop == "3단 조립식 벽선반"


def test_캐시되면_다시_안_묻는다(tmp_path, monkeypatch):
    """두 번째 호출에 모델이 0회여야 한다 — 안 그러면 페이지 열 때마다 키를 태운다."""
    db = str(tmp_path / "t.db")
    Store(db)
    calls = []
    monkeypatch.setattr(product_name, "_identify_shop_one",
                        lambda img, cap: calls.append(1) or "X")
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: b"IMG")

    items = [{"shortcode": "v1", "thumbnail": "http://x/a.jpg", "caption": "c"}]
    product_name.identify_shop_many(items, db)
    n1 = len(calls)
    product_name.identify_shop_many(items, db)
    assert n1 == 1 and len(calls) == 1, "캐시가 안 먹었다"


def test_판정실패는_캐시하지_않는다(tmp_path, monkeypatch):
    """None(키 소진·네트워크)은 재시도 대상이다. ''(살 물건 없음)만 확정 저장한다."""
    db = str(tmp_path / "t.db")
    Store(db)
    monkeypatch.setattr(product_name, "_identify_shop_one", lambda img, cap: None)
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: b"IMG")

    product_name.identify_shop_many(
        [{"shortcode": "v1", "thumbnail": "http://x/a.jpg", "caption": "c"}], db)
    assert Store(db).shop_products_map(["v1"]) == {}, "실패를 캐시하면 영영 재시도 못 한다"


def test_살물건없음은_캐시한다(tmp_path, monkeypatch):
    """맛집·방법영상은 ''로 확정 — 다음에 또 태우면 안 된다."""
    db = str(tmp_path / "t.db")
    Store(db)
    monkeypatch.setattr(product_name, "_identify_shop_one", lambda img, cap: "")
    from shopping_shorts import video_analysis
    monkeypatch.setattr(video_analysis, "fetch_thumb_bytes", lambda u: b"IMG")

    product_name.identify_shop_many(
        [{"shortcode": "v1", "thumbnail": "http://x/a.jpg", "caption": "c"}], db)
    assert Store(db).shop_products_map(["v1"]) == {"v1": ""}


# ── 프롬프트 규약 (사보타주로 확인함) ──────────────────────────────────────

def test_쿠팡용_프롬프트는_묶기용과_다르다():
    """★같은 프롬프트를 재사용하면 안 된다.

    묶기용은 자막을 끄고(범주어가 맞다), 쿠팡용은 캡션 글자를 최우선으로 믿는다."""
    assert "무시하라" in product_name._PROMPT          # 묶기용: 자막 무시
    assert "설명 글" in product_name._SHOP_PROMPT           # 쿠팡용: 설명 글을 본다
    assert product_name._SHOP_PROMPT != product_name._PROMPT


def test_쿠팡용_프롬프트가_빈답을_허용한다():
    """맛집·방법영상에 억지 상품명을 짜내면 사장님이 헛클릭한다."""
    assert "빈 문자열" in product_name._SHOP_PROMPT
