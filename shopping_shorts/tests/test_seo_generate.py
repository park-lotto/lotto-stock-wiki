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


def test_prompt_keyword_stats_note_differs_by_verdict(monkeypatch):
    """되먹임 — verdict별로 지시 문구가 실제로 달라야 Pass 3가 의미 있다.
    raw verdict 값("red")만 찍고 note 분기가 통째로 지워져도 안 잡히던 가짜 신호를 대체한다."""
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))

    def _prompt_for(verdict):
        log.clear()
        seo_generate.generate(_JOB, only="title", keyword_stats=[
            {"keyword": "빨대텀블러", "verdict": verdict, "views_median": 1_800_000, "small_ratio": 0.05}])
        return log[0]

    assert "밀어라" in _prompt_for("blue")
    assert "메인으로 쓰지 마라" in _prompt_for("red")
    assert "빼라" in _prompt_for("dead")
    assert "미측정" in _prompt_for("unknown")


def test_prompt_locked_fields_reflect_dict_contents(monkeypatch):
    """locked dict 내용이 실제로 필드명 단위로 반영되는지 — 헤더 문구("확정"/"잠")만
    확인하면 locked 내용을 통째로 무시해도 통과하던 가짜 신호를 대체한다.
    field는 comment_bait/cta로 골랐다 — "title"은 _BASE_PROMPT의 "title_candidates"
    문구에, "hook_line"은 _JOB.script_structure의 키에 항상 부분일치돼 위양성이 난다."""
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB, locked={"comment_bait": True, "cta": False}, only="description")
    p = log[0]
    assert "comment_bait" in p
    assert "cta" not in p


def test_seed_keywords_dedups_preserving_order():
    got = seo_generate.seed_keywords(_OUT)
    assert got == ["빨대텀블러", "보냉텀블러", "홈템"]


def test_seed_keywords_empty_on_missing():
    assert seo_generate.seed_keywords({}) == []


def test_schema_forces_exactly_20_tags():
    """response_schema로 개수를 강제 — 프롬프트 텍스트("정확히 20개")에만 의존하지 않는다.
    video_analysis.py:37의 minItems/maxItems 패턴과 동일."""
    tags_schema = seo_generate._SCHEMA["properties"]["tags"]
    assert tags_schema["minItems"] == 20
    assert tags_schema["maxItems"] == 20


# ── T8 실측이 드러낸 것(2026-07-17) ──────────────────────────────


def test_prompt_orders_tone_to_follow_script(monkeypatch):
    """실측: 대본 tone이 '친근한 반말'인데 제목·CTA가 전부 존댓말로 나왔다.
    tone은 structure JSON에 실려 프롬프트에 '있긴' 했으나 따르라는 지시가 없었다.
    영상은 반말인데 제목이 존댓말이면 같은 영상으로 안 보인다."""
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB)
    p = log[0]
    assert "친근한 반말" in p          # 값은 전부터 있었다
    assert "말투" in p                 # 지시가 새로 생겼다


def test_stats_prompt_uses_views_top_not_tail_median(monkeypatch):
    """되먹임에 넣는 숫자는 수요(views_top)여야 한다. 20편 중앙값을 '상위 조회수'라고
    넘기면 AI가 틀린 근거 위에서 다시 쓴다."""
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(_JOB, only="title", keyword_stats=[
        {"keyword": "빨대텀블러", "verdict": "blue", "views_top": 150_651,
         "views_median": 10_230, "small_ratio": 0.3}])
    p = log[0]
    assert "150,651" in p or "150651" in p     # 수요가 들어간다
    assert "10,230" not in p and "10230" not in p   # 꼬리 중앙값은 근거로 안 쓴다


# ── 리뷰가 잡은 Major: 잠금이 이름뿐이었다(2026-07-17) ──────────────


def test_prompt_includes_locked_values_not_just_field_names(monkeypatch):
    """★잠긴 항목의 '내용'이 프롬프트에 들어간다.

    기존엔 'title, cta' 같은 **영문 필드명만** 실려서, AI는 잠긴 제목을 볼 수 없는 채로
    "그대로 두고 나머지를 여기에 어울리게 써라"는 지시를 받았다 — 볼 수 없는 것에
    맞출 수는 없으므로 지시가 물리적으로 수행 불가능했다. 잠금의 광고된 동작이
    전혀 일어나지 않고 있었다."""
    job = {**_JOB, "seo": {"title": "다이슨 에어랩 3개월 실사용",
                           "tags": ["기존태그"], "cta": {"youtube": "구독 눌러"}}}
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(job, locked={"title": True}, only="tags")
    locked_block = log[0].split("[잠긴 항목")[1]
    assert "다이슨 에어랩 3개월 실사용" in locked_block   # ★잠근 제목의 내용이 실린다
    assert "title" not in locked_block                   # 영문 필드명이 새지 않는다


def test_prompt_locked_shows_only_locked_fields(monkeypatch):
    """안 잠근 항목까지 '확정'이라고 넣으면 재생성이 아무것도 못 바꾼다."""
    job = {**_JOB, "seo": {"title": "잠긴제목", "description": "안잠근설명"}}
    log = []
    _patch(monkeypatch, ["k1"], _FakeClient(_OUT, log=log))
    seo_generate.generate(job, locked={"title": True, "description": False}, only="tags")
    p = log[0]
    locked_block = p.split("[잠긴 항목")[1]
    assert "잠긴제목" in locked_block
    assert "안잠근설명" not in locked_block
