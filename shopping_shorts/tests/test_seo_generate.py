import json
from shopping_shorts import seo_generate


_JOB = {
    "given_script": "이 텀블러는 뒤집어도 안 새요. 얼음이 하루 종일 유지됩니다.",
    "script_structure": {"product_category": "홈템", "hook_line": "가방에 내용물 샐까",
                         "appeal": "완벽 밀폐", "one_line_why": "새지 않는 텀블러",
                         "tone": "친근한 반말"},
    "headcopy": {"text": "샐 걱정 ZERO"},
    "edit_plan": {"beats": [{"narration": "뒤집어도 안 새요", "role": "본문"}]},
}

_OUT = {
    "title": "샐 걱정 ZERO 텀블러",
    "title_candidates": [{"text": "A", "why": "훅을 앞으로", "keywords": ["빨대텀블러", "보냉텀블러"]},
                         {"text": "B", "why": "카테고리", "keywords": ["빨대텀블러", "홈템"]}],
    "description": "설명",
    "tags": ["t1", "t2"],
    "hashtags": {"youtube": ["#a"], "tiktok": ["#b"], "threads": ["#c"]},
    "hook_line": "훅", "comment_bait": "힙해",
    "cta": {"youtube": "y", "tiktok": "t", "threads": "th"},
}


class _FakeResp:
    def __init__(self, payload):
        self.text = json.dumps(payload, ensure_ascii=False)


class _FakeModels:
    def __init__(self, payload, exc=None, log=None):
        self._p, self._exc, self._log = payload, exc, log

    def generate_content(self, model=None, contents=None, config=None):
        if self._log is not None:
            self._log.append(contents)
        if self._exc:
            raise self._exc
        return _FakeResp(self._p)


class _FakeClient:
    def __init__(self, payload, exc=None, log=None):
        self.models = _FakeModels(payload, exc, log)


def _patch(monkeypatch, keys, client):
    monkeypatch.setattr(seo_generate.key_vault, "get_live_keys_cascade", lambda g: keys)
    monkeypatch.setattr(seo_generate.key_vault, "get_client_for_key", lambda k: client)


def test_generate_returns_seo(monkeypatch):
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT))
    got = seo_generate.generate(_JOB)
    assert got["title"] == "샐 걱정 ZERO 텀블러"
    assert got["cta"]["tiktok"] == "t"


def test_generate_no_keys_returns_none(monkeypatch):
    monkeypatch.setattr(seo_generate.key_vault, "get_live_keys_cascade", lambda g: [])
    assert seo_generate.generate(_JOB) is None


def test_generate_cascades_on_exhausted_key(monkeypatch):
    """소진키는 마킹하고 다음 키로 — 공유풀 캐스케이드."""
    marked = []
    bad, good = _FakeClient(None, exc=RuntimeError("quota")), _FakeClient(_OUT)
    clients = iter([bad, good])
    monkeypatch.setattr(seo_generate.key_vault, "get_live_keys_cascade", lambda g: ["k1", "k2"])
    monkeypatch.setattr(seo_generate.key_vault, "get_client_for_key", lambda k: next(clients))
    monkeypatch.setattr(seo_generate.key_vault, "is_daily_exhausted_error", lambda e: True)
    monkeypatch.setattr(seo_generate.key_vault, "is_account_disabled_error", lambda e: False)
    monkeypatch.setattr(seo_generate.key_vault, "_owner_group", lambda k: "general")
    monkeypatch.setattr(seo_generate.key_vault, "mark_exhausted", lambda g, k: marked.append(k))
    got = seo_generate.generate(_JOB)
    assert got["title"] == "샐 걱정 ZERO 텀블러"
    assert marked == ["k1"]


def test_generate_bad_json_returns_none(monkeypatch):
    class _Bad:
        text = "not json"

    class _M:
        def generate_content(self, **k):
            return _Bad()

    class _C:
        models = _M()

    _patch(monkeypatch, ["k1"], _C())
    assert seo_generate.generate(_JOB) is None


def test_prompt_includes_script_and_structure(monkeypatch):
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB)
    p = log[0]
    assert "뒤집어도 안 새요" in p        # 대본
    assert "가방에 내용물 샐까" in p       # hook_line
    assert "샐 걱정 ZERO" in p           # headcopy


def test_prompt_includes_captions(monkeypatch):
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB, captions=["#텀블러 이거 대박 #홈템"])
    assert "#텀블러 이거 대박" in log[0]


def test_prompt_includes_keyword_stats_when_given(monkeypatch):
    """되먹임 — 실측치가 프롬프트에 들어가야 Pass 3가 의미 있다."""
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB, only="title", keyword_stats=[
        {"keyword": "빨대텀블러", "verdict": "red", "views_median": 1_800_000, "small_ratio": 0.05}])
    p = log[0]
    assert "빨대텀블러" in p
    assert "red" in p or "레드" in p


def test_prompt_marks_locked_fields(monkeypatch):
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB, locked={"title": True}, only="tags")
    assert "잠" in log[0] or "확정" in log[0]


def test_seed_keywords_dedups_preserving_order():
    got = seo_generate.seed_keywords(_OUT)
    assert got == ["빨대텀블러", "보냉텀블러", "홈템"]


def test_seed_keywords_empty_on_missing():
    assert seo_generate.seed_keywords({}) == []
