"""쓸 수 없는 제미니 키(선불 소진·월 한도·할당량 0)는 모든 풀에서 빠진다 — 2026-09-25 실사고.

실측(서버 api_events): 402 선불 소진 키(…3L0lEA)·월 지출 한도 키(…HLpLEE)·할당량 0 키 10개가
잠금 0번인 채 계속 불렸다(할당량 0 키만 24시간 1,013번 헛호출). 전부 429/402라 '잠깐 기다리면
풀리는 한도'로 취급됐고, 대부분의 호출부는 PerDay일 때만 잠가서 아무도 안 잠갔다.

이 테스트가 지키는 계약:
  ① 판정은 좁다 — 503·일반 429·분당/일일 한도는 '쓸 수 없음'이 아니다(멀쩡한 키를 하루 빼지 않는다)
  ② 쓸 수 없는 키는 두 풀(key_vault·쇼츠 comment_gen) 모두에서 빠진다
  ③ 영구가 아니다 — 24시간 뒤 다시 시험받고, 성공하면 표시가 지워진다
  ④ 모든 호출이 지나가는 usage_meter 깔때기가 판정을 부른다(호출부를 안 고쳐도 잡힌다)
"""
import time

import pytest

from pipeline.atoms import key_vault as kv

# 서버 api_events detail에 남은 원문과 같은 모양(키는 가림)
PREPAY = ("402 Payment Required. {'error': {'code': 402, 'message': 'Your prepayment credits are "
          "depleted. Please go to AI Studio at https://ai.studio/projects to manage your project "
          "and billing.', 'status': 'RESOURCE_EXHAUSTED'}}")
SPEND_CAP = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Your project has exceeded "
             "its monthly spending cap. Please go to AI Studio at https://ai.studio/spend to manage "
             "your project spend cap.', 'status': 'RESOURCE_EXHAUSTED'}}")
# ★서버 api_events 실제 원문(2026-09-25, 프로젝트 번호만 가림). 문장엔 'limit: 0'이 없고
#   세부 항목에만 quota_limit_value '0'이 있다 — 처음에 지어낸 문자열로 테스트해 통과했는데
#   실제 9,097건은 하나도 못 잡았다(서버 원문 재생에서 드러남). 테스트 문자열은 원문으로 쓴다.
LIMIT_ZERO = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': \"Quota exceeded for quota "
              "metric 'Generate Content API requests per minute' and limit 'GenerateContent request "
              "limit per minute for a region' of service 'generativelanguage.googleapis.com' for "
              "consumer 'project_number:000000000000'.\", 'status': 'RESOURCE_EXHAUSTED', 'details': "
              "[{'@type': 'type.googleapis.com/google.rpc.ErrorInfo', 'reason': 'RATE_LIMIT_EXCEEDED', "
              "'domain': 'googleapis.com', 'metadata': {'quota_limit_value': '0', 'service': "
              "'generativelanguage.googleapis.com', 'consumer': 'projects/000000000000', "
              "'quota_location': 'asia-east1', 'quota_unit': '1/min/{project}/{region}', 'quota_limit': "
              "'GenerateContentRequestsPerMinutePerProjectPerRegion', 'quota_metric': "
              "'generativelanguage.googleapis.com/generate_content_requests'}}]}}")
LIMIT_ZERO_SENTENCE = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generativelanguage.googleapis.com/"
                       "generate_content_free_tier_requests, limit: 0, model: gemini-3.1-flash-lite")
DAILY_20 = ("429 RESOURCE_EXHAUSTED. Quota exceeded for metric: generativelanguage.googleapis.com/"
            "generate_content_free_tier_requests, limit: 20, model: gemini-3.5-flash "
            "quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier. Please retry in 41.2s.")
GENERIC_429 = "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, 'message': 'Resource has been exhausted (e.g. check quota).'}}"
OVERLOAD_503 = ("503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently "
                "experiencing high demand. Spikes in demand are usually temporary.'}}")


@pytest.fixture
def vault(tmp_path, monkeypatch):
    monkeypatch.setattr(kv, "_STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(kv, "_LOCK_PATH", tmp_path / "state.lock")
    monkeypatch.setattr(kv, "get_keys", lambda g: ["K0", "K1", "K2"])
    sent = []
    monkeypatch.setattr(kv, "_tg_alert", lambda text: sent.append(text))   # 실제 텔레그램 금지
    kv._SUS_CACHE["t"] = 0.0
    kv.sent = sent
    return kv


# ── ① 판정 ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("msg,want", [
    (PREPAY, kv.UNUSABLE_PREPAY),
    (SPEND_CAP, kv.UNUSABLE_SPEND_CAP),
    (LIMIT_ZERO, kv.UNUSABLE_NO_QUOTA),
    ("403 PERMISSION_DENIED. Your project has been denied access.", kv.UNUSABLE_AUTH),
    ("400 INVALID_ARGUMENT. API key not valid. API_KEY_INVALID", kv.UNUSABLE_AUTH),
])
def test_기다려도_안_풀리는_실패는_이유를_낸다(msg, want):
    assert kv.unusable_reason(Exception(msg)) == want


@pytest.mark.parametrize("msg", [OVERLOAD_503, GENERIC_429, DAILY_20,
                                 "429 Quota exceeded ... limit: 05 per minute",
                                 LIMIT_ZERO.replace("'quota_limit_value': '0'", "'quota_limit_value': '15'"),
                                 # ★문장형 'limit: 0, model: X'는 모델 하나의 한도 — 키 전체를 빼면 풀이 빈다
                                 LIMIT_ZERO_SENTENCE,
                                 "504 DEADLINE_EXCEEDED", ""])
def test_시간이_풀어주는_실패는_건드리지_않는다(msg):
    """★여기서 참을 내면 멀쩡한 키를 하루 뺀다. 503(구글 과부하)·일반 429·일일 한도(limit: 20)는 아니다."""
    assert kv.unusable_reason(Exception(msg)) is None


# ── ② 두 풀에서 빠진다 ─────────────────────────────────────────────────────
def test_선불소진_키는_vault_풀에서_빠진다(vault):
    assert vault.note_failure("K1", Exception(PREPAY)) == vault.UNUSABLE_PREPAY
    assert vault.get_live_keys("general") == ["K0", "K2"]
    assert vault.without_dead(["K0", "K1", "K2"]) == ["K0", "K2"]    # 최후 폴백에서도


def test_503은_아무_표시도_안_남긴다(vault):
    assert vault.note_failure("K1", Exception(OVERLOAD_503)) is None
    assert vault.get_live_keys("general") == ["K0", "K1", "K2"]
    assert vault.suspension_info() == {}


def test_쇼츠_풀도_같은_표시를_본다(vault, tmp_path, monkeypatch):
    """쇼츠 풀(comment_gen)은 상태파일이 따로라 종전엔 key_vault 표시를 몰랐다."""
    from shopping_shorts import comment_gen as cg
    monkeypatch.setattr(cg, "_STATE_PATH", tmp_path / "shorts_state.json")
    monkeypatch.setattr(cg, "SHORTS_GEMINI_KEYS", ["S0", "S1", "S2", "S3", "S4"])
    assert cg._live_key_indices() == [0, 1, 2, 3, 4]
    vault.note_failure("S2", Exception(SPEND_CAP))
    assert 2 not in cg._live_key_indices()
    assert cg._live_key_indices() == [0, 1, 3, 4]


def test_쇼츠_풀의_사망표시가_날짜가_바뀌어도_남는다(vault, tmp_path, monkeypatch):
    """★comment_gen 상태파일은 UTC 날짜가 바뀌면 통째로 새로 시작해 dead_keys가 사라졌다.
    깔때기가 key_vault(날짜로 안 버림)에 남기므로 다음 날에도 빠져 있어야 한다."""
    from shopping_shorts import comment_gen as cg
    monkeypatch.setattr(cg, "_STATE_PATH", tmp_path / "shorts_state.json")
    monkeypatch.setattr(cg, "SHORTS_GEMINI_KEYS", ["S0", "S1"])
    vault.note_failure("S1", Exception("403 PERMISSION_DENIED"))
    monkeypatch.setattr(cg, "_today_str", lambda: "2099-01-01")       # 다음 날
    assert cg._live_key_indices() == [0]


# ── ③ 영구가 아니다 ───────────────────────────────────────────────────────
def test_하루_뒤_다시_시험받고_성공하면_표시가_지워진다(vault, monkeypatch):
    vault.note_failure("K1", Exception(PREPAY))
    assert "K1" not in vault.get_live_keys("general")
    later = time.time() + 25 * 3600
    monkeypatch.setattr(time, "time", lambda: later)
    assert "K1" in vault.get_live_keys("general")                      # 다시 시험받는다
    fp = vault._key_fingerprint("K1")
    assert fp in vault.suspension_info()                                # 살아난 건 아직 모른다
    vault._SUS_CACHE["t"] = 0.0
    vault.note_success("K1")                                            # 충전해서 성공
    assert fp not in vault.suspension_info()


def test_재실패는_연장이고_경보는_처음_한_번만(vault):
    assert vault.suspend("K2", vault.UNUSABLE_NO_QUOTA) is True
    assert vault.suspend("K2", vault.UNUSABLE_NO_QUOTA) is False
    assert len(vault.sent) == 1


def test_회원_화면용_정보(vault):
    vault.note_failure("K0", Exception(PREPAY))
    vault.note_failure("K1", Exception("401 UNAUTHENTICATED"))
    fps = {vault._key_fingerprint(k): k for k in ("K0", "K1", "K2")}
    info = vault.unusable_info_for(fps)
    assert {fps[f]: v["reason"] for f, v in info.items()} == {
        "K0": vault.UNUSABLE_PREPAY, "K1": vault.UNUSABLE_AUTH}


# ── ④ 깔때기 ─────────────────────────────────────────────────────────────
class _FakeModels:
    def __init__(self, exc=None):
        self.exc = exc

    def generate_content(self, *a, **kw):
        if self.exc:
            raise self.exc
        return type("R", (), {"usage_metadata": None, "text": "{}"})()


class _FakeClient:
    def __init__(self, exc=None):
        self.models = _FakeModels(exc)


def test_usage_meter_깔때기가_정지와_해제를_부른다(vault, monkeypatch):
    from shopping_shorts import usage_meter
    monkeypatch.delenv("USAGE_METER", raising=False)   # 0이면 깔때기 자체가 꺼진다
    bad = usage_meter.wrap(_FakeClient(Exception(PREPAY)), pool="shorts", key="K1")
    with pytest.raises(Exception):
        bad.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
    assert "K1" not in vault.get_live_keys("general")                  # 호출부를 안 고쳐도 빠진다
    vault._SUS_CACHE["t"] = 0.0
    good = usage_meter.wrap(_FakeClient(), pool="shorts", key="K1")
    good.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
    assert vault._key_fingerprint("K1") not in vault.suspension_info()


def test_usage_meter_깔때기는_503에_손대지_않는다(vault, monkeypatch):
    from shopping_shorts import usage_meter
    monkeypatch.delenv("USAGE_METER", raising=False)   # 0이면 깔때기 자체가 꺼진다
    c = usage_meter.wrap(_FakeClient(Exception(OVERLOAD_503)), pool="shorts", key="K0")
    with pytest.raises(Exception):
        c.models.generate_content(model="gemini-3.1-flash-lite", contents="hi")
    assert vault.get_live_keys("general") == ["K0", "K1", "K2"]


def test_쇼츠_풀_자체_사망처리도_다음날까지_남는다(vault, tmp_path, monkeypatch):
    """깔때기를 안 거치고 comment_gen이 직접 사망 처리한 키도(되살림 프로브 등) 다음 날 빠져 있어야 한다.
    원래 코드에서 재현됨(2026-09-25): 날짜가 바뀌면 403 키가 다시 살아났다."""
    from shopping_shorts import comment_gen as cg
    monkeypatch.setattr(cg, "_STATE_PATH", tmp_path / "shorts_state.json")
    monkeypatch.setattr(cg, "SHORTS_GEMINI_KEYS", ["S0", "S1"])
    cg._mark_key_dead(1, detail="403")
    assert cg._live_key_indices() == [0]
    monkeypatch.setattr(cg, "_today_str", lambda: "2099-01-01")
    assert cg._live_key_indices() == [0]


# ── ⑤ 사망도 영구가 아니다 (2026-09-25 반박 검토: 회원 57 …nIWJaw는 403 엿새 뒤 되살아났다) ──
def test_사망표시는_3일_뒤_다시_시험받는다(vault, monkeypatch):
    vault.note_failure("K1", Exception("403 PERMISSION_DENIED. Your project has been denied access."))
    assert "K1" not in vault.get_live_keys("general")
    later = time.time() + vault._DEAD_RETEST_S + 60
    monkeypatch.setattr(time, "time", lambda: later)
    assert "K1" in vault.get_live_keys("general")            # 재시험 기간이 지나면 한 번 불린다
    vault.note_failure("K1", Exception("403 PERMISSION_DENIED"))   # 또 죽으면
    assert "K1" not in vault.get_live_keys("general")        # 시각을 새로 박아 다시 3일


def test_옛_사망기록은_키를_빼지_않는다(vault):
    """서버 상태파일엔 09-03 '영구 사망'이 남아 있다 — 그 키는 09-08부터 매일 성공 중이다."""
    import json
    old = time.time() - 22 * 24 * 3600
    vault._STATE_PATH.write_text(json.dumps({"exhausted": {}, "dead_keys": {
        vault._key_fingerprint("K1"): old, vault._key_fingerprint("K2"): 0}}), encoding="utf-8")
    assert vault.get_live_keys("general") == ["K0", "K1", "K2"]
    assert vault.unusable_info_for({vault._key_fingerprint("K1")}) == {}


def test_성공하면_사망표시도_지운다(vault):
    vault.note_failure("K2", Exception("401 UNAUTHENTICATED"))
    assert "K2" not in vault.get_live_keys("general")
    vault._SUS_CACHE["t"] = 0.0
    vault.note_success("K2")                                  # 확인 버튼·재시험에서 살아 있음이 드러남
    assert "K2" in vault.get_live_keys("general")
    assert vault._key_fingerprint("K2") not in vault._dead_map(vault._load_state())


def test_같은_실패가_두_번_들어와도_한_번만_쓴다(vault):
    assert vault.suspend("K0", vault.UNUSABLE_PREPAY) is True
    before = vault._STATE_PATH.stat().st_mtime_ns
    assert vault.suspend("K0", vault.UNUSABLE_PREPAY) is False   # 깔때기+호출부 이중 호출
    assert vault._STATE_PATH.stat().st_mtime_ns == before
