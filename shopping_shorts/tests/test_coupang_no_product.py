# -*- coding: utf-8 -*-
"""'살 물건 없음'을 화면이 알아보는가 (2026-09-05 사장님 "해봐").

■ 왜 필요한가 (실측)
캡션 근거를 얹어도 **10건 중 4건은 애초에 팔 물건이 없다** — "방충망 닦는 법",
"계양구청 근처 점심 맛집" 같은 영상이다. 판독은 이런 영상에 빈 문자열로 답하도록
프롬프트에 박아뒀는데, 화면이 `if (!name) return;`으로 **조용히 건너뛰어**
그냥 '쿠팡검색' 버튼이 남았다 → 사장님이 눌러 보고 헛수고한다.

■ 못 박는 것
  - 서버가 '살 물건 없음'을 **명시**한다(no_product) — ""는 "아직 안 됨"과 못 가른다.
  - products의 기존 규약(빈 문자열=없음)은 **안 바뀐다**(옛 호출부 보호).
  - ★프리워밍 필터가 캡션만 있는 카드를 **안 자른다** — 종전엔 it.thumbnail을 요구해
    서버·모델을 고쳐놓고도 브라우저에서 잘려 도착조차 안 했다.
"""
import re
import pathlib

import pytest

STATIC = pathlib.Path(__file__).resolve().parents[1] / "static"


def _sidebar():
    return (STATIC / "sidebar.js").read_text(encoding="utf-8")


# ── 서버: '살 물건 없음'을 명시하는가 ──────────────────────────────────────

def test_batch_reports_no_product(monkeypatch, tmp_path):
    """빈 제품명은 no_product에 담겨 온다 — 화면이 '아직 안 됨'과 가를 수 있어야 한다."""
    from shopping_shorts import app as a, product_name
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    monkeypatch.setattr(a, "DB_PATH", str(db))
    Store(str(db))
    monkeypatch.setattr(product_name, "identify_shop_many",
                        lambda items, db_path, **k: {"A": "무선 노래방 마이크", "B": ""})
    r = a.api_coupang_identify_batch({"items": [
        {"shortcode": "A", "thumbnail": "https://x/a.jpg", "caption": "마이크"},
        {"shortcode": "B", "thumbnail": "https://x/b.jpg", "caption": "맛집 소개"}]})
    assert r["ok"]
    assert r["no_product"] == ["B"], r
    # ★기존 규약은 그대로 — 옛 호출부가 깨지면 안 된다
    assert r["products"] == {"A": "무선 노래방 마이크", "B": ""}


def test_batch_no_product_is_empty_when_all_found(monkeypatch, tmp_path):
    """전부 찾았으면 no_product는 빈 목록(있지도 않은 경고를 만들지 않는다)."""
    from shopping_shorts import app as a, product_name
    from shopping_shorts.store import Store
    db = tmp_path / "t.db"
    monkeypatch.setattr(a, "DB_PATH", str(db))
    Store(str(db))
    monkeypatch.setattr(product_name, "identify_shop_many",
                        lambda items, db_path, **k: {"A": "지우개"})
    r = a.api_coupang_identify_batch({"items": [
        {"shortcode": "A", "thumbnail": "https://x/a.jpg", "caption": "지우개"}]})
    assert r["no_product"] == []


# ── 화면: 회색 처리 배선 ───────────────────────────────────────────────────

def test_빈제품명이면_회색으로_내리지_않는다():
    """2026-09-26 사장님 "살 물건 없음은 없애고" — 썸네일·캡션만 본 배치 판정이 말로만 소개하는
    제품(소스·재료)을 자주 놓쳐 멀쩡한 카드가 회색이 됐다. 버튼은 그대로 두고, 대본이 필요한
    카드는 🎬 쿠팡 대본검색이 맡는다. (09-05의 회색 처리는 되돌림 — 이 테스트가 그 계약을 뒤집는다)"""
    sb = _sidebar()
    i = sb.find("window.ssCoupangPrewarm = function")
    assert i > 0
    blk = sb[i:i + 2600]
    assert 'btn.setAttribute("data-noproduct", "1")' not in blk, "회색 '살 물건 없음' 표시가 되살아났다"
    assert '"🛒 살 물건 없음"' not in blk
    # 자료 만료(근거 없음) 표시는 남긴다 — 판독이 틀린 게 아니라 못 본 것이라는 안내
    assert "data-noevidence" in blk


def test_회색버튼은_판독을_다시_안돈다():
    """이미 '없음'으로 판정된 카드를 또 3~8초 기다리게 하지 않는다."""
    sb = _sidebar()
    i = sb.find("function _cfOpen")
    assert i > 0
    # 함수 끝(_cfIdentify 정의 직전)까지를 창으로 잡는다 — 고정 길이는 짧아 끊긴다
    j = sb.find("function _cfIdentify", i)
    assert j > i
    blk = sb[i:j]
    assert "opts.noProduct" in blk, "모달이 noProduct를 안 본다"
    # noProduct 분기가 _cfIdentify()보다 **앞**에 와야 판독을 건너뛴다
    assert blk.index("opts.noProduct") < blk.index("_cfIdentify()"), \
        "noProduct 분기가 판독 뒤에 있어 소용없다"


@pytest.mark.parametrize("page", ["index.html", "collection.html"])
def test_버튼이_noProduct를_모달에_넘긴다(page):
    """배선이 빠지면 모달은 영영 회색인 줄 모른다(0순위-B: 판단은 버튼이 한다)."""
    txt = (STATIC / page).read_text(encoding="utf-8")
    # ⚠️[^}]*로 객체를 잡으면 `${i.shortcode}`의 }에서 끊긴다(실제로 밟았다).
    #   호출 시작점을 찾아 그 뒤 400자를 본다.
    k = txt.find("ssCoupangFind('',")
    assert k > 0, page
    assert "noProduct" in txt[k:k + 400], (page, txt[k:k + 400][:200])


# ── 프리워밍 필터: 캡션만 있는 카드를 자르지 않는가 ────────────────────────

def test_프리워밍이_캡션만있는카드를_안자른다():
    """★서버·모델을 고쳐도 **브라우저 필터**가 it.thumbnail을 요구하면 도착조차 안 한다.

    실제로 그 상태였다(2026-09-05) — 배선 누락은 이렇게 층마다 확인해야 잡힌다."""
    sb = _sidebar()
    m = re.search(r"var todo = \(items \|\| \[\]\)\.filter\(function \(it\) \{ return ([^;]+); \}\)", sb)
    assert m, "프리워밍 필터를 못 찾았다"
    cond = m.group(1)
    assert "it.caption" in cond, cond
    # thumbnail을 **단독 필수**로 요구하면 안 된다
    assert "it.thumbnail &&" not in cond, cond
