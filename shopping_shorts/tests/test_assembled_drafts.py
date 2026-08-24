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


# ── 은폐형은 쿠팡 재료가 있어야 채워진다(2026-08-19) ────────────────────────
CONCEAL_SPINE = {
    "id": 55, "name": "유튜브 은폐형", "fit_categories": ["제품정체형"],
    "beat_roles": ["bait", "authority", "reveal", "benefit"],
    "templates": {
        "bait": ["최근 딱 봤을 때는 평범한 이 {제품군}이"],
        "authority": ["이걸 개발한 {나라}의 천재가 돈방석에 앉았다는데"],
        "reveal": ["이건 바로 {제품}"],
        "benefit": ["이게 말도 안 되는 게 {효능}"],
    },
}


def test_쿠팡재료가_있어야_은폐형이_조립된다(monkeypatch):
    """★전에는 조립이 이 재료를 아예 못 봤다 — 블록 만드는 코드 안에만 있었다.
    그래서 은폐형이 슬롯을 못 채우고 영영 폴백했다."""
    _stub_sul(monkeypatch, {"category_word": "주방템", "misuse_genre": True,
                            "misuses": ["A하기", "B하기"], "original_use": ["원래용도"],
                            "hidden_property": ["숨은성질"]})
    # 쿠팡 재료 없음 → 못 채운다
    monkeypatch.setattr(app, "_facts_for_job", lambda *a, **k: {})
    out, left, _why = app._assembled_drafts([CONCEAL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [CONCEAL_SPINE]

    # 쿠팡 재료 있음 → 채운다
    monkeypatch.setattr(app, "_facts_for_job", lambda *a, **k: {
        "title": "무소음 젤펜", "origin": "미국", "why": ["딸깍 소리가 안 난다", "필기감이 좋다"]})
    out2, left2, _ = app._assembled_drafts([CONCEAL_SPINE], [{"full_text": "자막"}], None,
                                           job_id="j1")
    assert len(out2) == 1 and not left2
    txt = {b["role"]: b["text"] for b in out2[0]["beats"]}
    assert txt["reveal"] == "이건 바로 무소음 젤펜"
    assert txt["authority"] == "이걸 개발한 미국의 천재가 돈방석에 앉았다는데"
    assert txt["benefit"] == "이게 말도 안 되는 게 딸깍 소리가 안 난다"


def test_생성경로가_job_id를_넘긴다():
    """안 넘기면 쿠팡 재료가 조립에 영영 안 닿는다."""
    import inspect
    assert "job_id=_jid" in inspect.getsource(app)


def test_facts_for_job이_한_곳에서_정한다():
    """프롬프트 블록과 조립이 같은 재료를 봐야 한다(0순위-B)."""
    import inspect
    assert "_facts_for_job(" in inspect.getsource(app._facts_block_for_job)


def test_어느_칸이_왜_안됐는지_말한다(monkeypatch):
    """★사장님 질문(2026-08-19): "영상에 없는 내용이면 어떻게 하나".
    답은 '되는 틀을 고른다'인데, 그러려면 어느 틀이 몇 칸 되는지 먼저 보여야 한다."""
    _stub_sul(monkeypatch, {"category_word": "주방템", "misuse_genre": True,
                            "misuses": ["A하기", "B하기"], "original_use": ["원래용도"],
                            "hidden_property": ["숨은성질"]})
    monkeypatch.setattr(app, "_facts_for_job", lambda *a, **k: {})   # 쿠팡 재료 없음
    out, left, why = app._assembled_drafts([CONCEAL_SPINE], [{"full_text": "자막"}], None)
    assert out == [] and left == [CONCEAL_SPINE]
    msg = " ".join(why)
    assert "유튜브 은폐형" in msg and "칸" in msg
    assert "reveal" in msg or "benefit" in msg, "어느 칸이 빈지 말해야 한다"


class _OffStore:
    """assemble_off 설정만 답하는 최소 store(테스트용)."""

    def __init__(self, off):
        self._off = off
        self._d = {}

    def get_setting(self, key, default=""):
        return self._off if key == "assemble_off" else self._d.get(key, default)

    def set_setting(self, key, value):
        self._d[key] = value


def test_조립을_꺼도_재료_사유는_화면까지_간다(monkeypatch):
    """★2026-08-24 회귀 방지 — 조립을 끄는 것과 진단을 끄는 것은 다른 판단이다.

    예전엔 `assemble_off=1`이면 함수 맨 앞에서 즉시 return 해서, 그 아래에 있던
    재료 자격 판정(`sul_material_problem`)·소재 분리·칸 커버리지가 **통째로 안 돌았다**.
    화면엔 "설정에서 껐습니다" 한 줄만 떠서, 재료가 그 틀에 안 맞는다는 사실을
    사장님이 대본을 다 뽑고 나서야 알 수 있었다(실측: 크림치즈 job a31d8f7625e4 —
    재료 4편이 전부 레시피라 오용형이 성립 안 되는데 아무도 안 알려줘 맹탕 B안이 나왔다).
    """
    # 크림치즈 실측 재료 — 오용형이 아니다(misuse_genre=False)
    _stub_sul(monkeypatch, {"category_word": "크림치즈", "misuse_genre": False,
                            "misuses": [], "original_use": [], "hidden_property": []})
    out, left, why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}],
                                           _OffStore("1"))
    # 조립은 여전히 안 한다(비문 회피 그대로) — 전부 생성기로 넘어간다
    assert out == [] and left == [SUL_SPINE]
    # ★그래도 "왜 이 틀이 안 되는지"는 말해준다
    assert any("오용형이 아닙니다" in w for w in why), why
    assert any("틀 조립을 꺼두었습니다" in w for w in why), why


def test_조립을_꺼도_슬롯이_다_차면_조립은_안_한다(monkeypatch):
    """재료가 멀쩡해도 assemble_off=1이면 조립본을 만들지 않는다(끄기의 본뜻)."""
    _stub_sul(monkeypatch, FULL)
    out, left, _why = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}],
                                            _OffStore("1"))
    assert out == [] and left == [SUL_SPINE]
    # 끄지 않으면 종전대로 조립된다(대조군)
    out2, left2, _ = app._assembled_drafts([SUL_SPINE], [{"full_text": "자막"}],
                                           _OffStore("0"))
    assert len(out2) == 1 and not left2
