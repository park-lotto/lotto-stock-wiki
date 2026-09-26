# -*- coding: utf-8 -*-
"""발굴·등록 채널 판매채널 링크(2026-09-26 사장님 "발굴 채널에도 판매채널") + 쿠팡 대본검색 화면 계약."""
import os, tempfile
from pathlib import Path
from shopping_shorts.store import Store
from shopping_shorts import service, instagram_playwright as ip, coupang_query

ROOT = Path(__file__).resolve().parents[1]


def _store():
    d = tempfile.mkdtemp()
    return Store(os.path.join(d, "t.db"))


def test_프로필링크는_external_url_다음_bio_links():
    assert ip.profile_link({"external_url": "https://link.inpock.co.kr/a"}) == "https://link.inpock.co.kr/a"
    assert ip.profile_link({"external_url": "", "bio_links": [{"url": "https://inpk.link/b"}]}) == "https://inpk.link/b"
    assert ip.profile_link({}) == "" and ip.profile_link(None) == ""


def test_발굴채널_링크_저장과_메타():
    st = _store()
    st.add_discovered("shop._.dami", name="shop._.dami")
    assert [c["inpock"] for c in st.discovered_channels() if c["username"] == "shop._.dami"] == [""]
    assert st.set_discovered_inpock("SHOP._.DAMI", "https://link.inpock.co.kr/dami") == 1
    meta = {c["username"]: c for c in st.discovered_channels()}
    assert meta["shop._.dami"]["inpock"] == "https://link.inpock.co.kr/dami"
    # 다시 add해도(이름 갱신) 빈 inpock으로 지워지지 않는다
    st.add_discovered("shop._.dami", name="다미")
    assert {c["username"]: c for c in st.discovered_channels()}["shop._.dami"]["inpock"] == "https://link.inpock.co.kr/dami"
    assert st.set_discovered_inpock("nobody", "https://x") == 0, "등록 안 된 채널은 안 만든다"
    assert st.set_discovered_inpock("shop._.dami", "") == 0


def test_보강은_같은_응답의_링크를_쓴다():
    st = _store()
    st.add_discovered("hamss", name="함은서")
    calls = []
    def fake(users):
        calls.append(list(users))
        return {"hamss": {"followers": 100, "link": "https://link.inpock.co.kr/hamss"}}
    assert service.enrich_discovered_profile("@hamss", store=st, fetch=fake) == 1
    assert calls == [["hamss"]], "프로필은 한 번만 연다"
    assert {c["username"]: c for c in st.discovered_channels()}["hamss"]["inpock"].endswith("/hamss")
    assert service.enrich_discovered_profile("hamss", store=st, fetch=lambda u: {}) == 0
    assert service.enrich_discovered_profile("hamss", store=st, fetch=lambda u: 1 / 0) == 0, "실패는 조용히 0"


def test_판독_프롬프트는_글이_힌트를_이긴다():
    p = coupang_query._EVIDENCE_PROMPT
    assert "대본 > 캡션" in p and "빈 문자열" in p and "후라이팬" in p


def test_화면_계약_대본검색_버튼과_회색제거():
    idx = (ROOT / "static" / "index.html").read_text(encoding="utf-8")
    sb = (ROOT / "static" / "sidebar.js").read_text(encoding="utf-8")
    assert "ssCoupangFind.script(" in idx and "쿠팡 대본검색" in idx
    assert ".btns .cp-script-btn{grid-column:1/-1" in idx
    assert "window.ssCoupangFind.script = function" in sb
    assert "opts.deep && _cfState.sc) _cfDeep()" in sb
    assert 'btn.setAttribute("data-noproduct", "1")' not in sb, "회색 '살 물건 없음' 처리는 뺐다"
    assert ">🎬 대본으로 다시 찾기</button>" in sb and '"🎬 대본으로 다시 찾기"' in sb
    assert '"🎬 영상 보고 정확히"' not in sb, "버튼 문구는 한 이름만"
