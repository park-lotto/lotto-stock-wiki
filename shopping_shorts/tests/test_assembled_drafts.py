# -*- coding: utf-8 -*-
"""조립본이 **실제 생성 경로에 붙어 있는가**(2026-08-19).

모듈만 있고 아무도 안 부르면 없는 것과 같다 — 같은 날 썰 재료 배선에서 실제로
그 상태였고, 게이트 플래그도 store 적재를 빠뜨려 라이브에서만 죽었다.
"""
import shopping_shorts.app as app
from shopping_shorts import spine_fill

SUL_SPINE = {
    "id": 56, "name": "유튜브 오용형", "fit_categories": ["오용형"],
    "beat_roles": ["origin", "notice", "twist"],
    "templates": {
        "origin": ["이게 원래는 {본래용도}로 개발된 제품이었음"],
        "notice": ["그런데 사람들은 {속성}을 눈치채고 이걸 엉뚱한 용도로 쓰기 시작하는데"],
        "twist": ["근데 미친 사용법은 따로 있었는데 {용도끝}"],
    },
}
OTHER_SPINE = {"id": 53, "name": "단정 명령형", "fit_categories": ["홈템"],
               "beat_roles": ["hook"], "templates": {"hook": ["이거 하나면 끝"]}}
FULL = {"original_use": ["가죽 구멍 뚫기"], "hidden_property": ["어떤 재질이든 뚫림"],
        "misuses": ["주방용품 걸이", "지퍼백 구멍 뚫기"], "misuse_genre": True}


def _stub_sul(monkeypatch, facts):
    class _F:
        @staticmethod
        def analyze_sul(raw, **kw):
            return dict(facts)
    import shopping_shorts as pkg
    monkeypatch.setattr(pkg, "sul_facts", _F, raising=False)


def test_슬롯이_다_차면_조립본이_나온다(monkeypatch):
    _stub_sul(monkeypatch, FULL)
    out, left, _why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert len(out) == 1 and not left
    d = out[0]
    assert d["made_by"] == "조립" and d["style_id"] == 56
    # 틀이 글자 그대로 지켜진다 — 생성기는 여기서 어미를 새로 썼다(실측).
    assert d["beats"][0]["text"] == "이게 원래는 가죽 구멍 뚫기로 개발된 제품이었음"
    # twist는 cases와 다른 사례를 쓴다
    assert d["beats"][-1]["text"].endswith("지퍼백 구멍 뚫기")
    # CTA가 붙을 자리가 없다
    assert "남겨주" not in d["script"] and "구독" not in d["script"]
    # 화면·게이트·저장이 다루는 모양과 같다
    for k in ("beats", "script", "hook", "checks", "passed", "style_id", "style_name"):
        assert k in d


def test_슬롯이_모자라면_기존_생성기로_넘긴다(monkeypatch):
    """★반쪽 조립본을 성공인 척 내놓지 않는다."""
    _stub_sul(monkeypatch, {"original_use": ["가죽 구멍 뚫기"], "misuse_genre": True})
    out, left, _why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [SUL_SPINE]


def test_썰_아닌_스타일은_조립하지_않는다(monkeypatch):
    """다른 스타일은 템플릿이 슬롯을 안 쓴다 — 손대면 기존 대본이 망가진다."""
    _stub_sul(monkeypatch, FULL)
    out, left, _why = app._assembled_drafts([OTHER_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [OTHER_SPINE]


def test_재료가_없으면_조립을_시도조차_안_한다():
    out, left, _why = app._assembled_drafts([SUL_SPINE], [], None)
    assert out == [] and left == [SUL_SPINE]


def test_조립_예외가_생성을_막지_않는다(monkeypatch):
    _stub_sul(monkeypatch, FULL)
    def _boom(*a, **k):
        raise RuntimeError("조립 터짐")
    monkeypatch.setattr(spine_fill, "build_draft", _boom)
    out, left, _why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [SUL_SPINE]


def test_생성경로가_조립을_부른다():
    """★안 부르면 배선이 죽은 것이다(모듈만 있는 상태)."""
    import inspect
    src = inspect.getsource(app)
    assert "_assembled_drafts(" in src
    assert '"assembled"' in src, "어느 경로로 만든 대본인지 화면에 안 알려준다"


# ── 재료 자격(2026-08-19 사장님 제보로 추가) ───────────────────────────────
# 슬롯이 차는 것과 **쓸 만한 것**은 다르다. 마커펜 영상으로 조립했더니
# "원래는 필기구로 개발된 마카였음 / 돌맹이에 그림 그리기"가 나왔다 — 틀은 완벽한데
# 재료가 오용형이 아니라 대본이 공허했다.
def test_오용형이_아닌_영상은_조립하지_않는다(monkeypatch):
    """★사장님이 실제로 받은 대본이 이 경우였다(마커펜, 2026-08-19).
    '필기구 ↔ 마카'는 문자열로 못 가른다 — 재료를 뽑은 모델이 직접 답하게 한다."""
    _stub_sul(monkeypatch, {"original_use": ["필기구"], "category_word": "마카펜",
                            "hidden_property": ["잘 지워짐"], "misuse_genre": False,
                            "misuses": ["돌에 그림 그리기", "필통에 넣어주기"]})
    out, left, why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [SUL_SPINE]
    assert why and "오용형이 아닙니다" in why[0]


def test_엉뚱용도가_원래용도와_같으면_거른다(monkeypatch):
    _stub_sul(monkeypatch, {"original_use": ["가죽 구멍 뚫기"], "category_word": "펀칭기",
                            "hidden_property": ["잘 뚫림"], "misuse_genre": True,
                            "misuses": ["가죽 구멍 뚫기", "다른 가죽 구멍 뚫기"]})
    out, left, why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and why and "정상 사용" in why[0]


def test_엉뚱용도가_1개면_거른다(monkeypatch):
    _stub_sul(monkeypatch, {"original_use": ["가죽 구멍 뚫기"], "category_word": "펀칭기",
                            "hidden_property": ["잘 뚫림"], "misuse_genre": True,
                            "misuses": ["지퍼백 구멍"]})
    out, left, why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and why and "1개" in why[0]


def test_화면이_조립못한_이유를_받는다():
    import inspect
    src = inspect.getsource(app)
    assert '"assemble_skipped"' in src
