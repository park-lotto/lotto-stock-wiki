"""503(모델 혼잡)일 때 대체 모델로 갈아타는지 — 2026-07-16 실사고 대응.

사고: 사장님 뽑기가 통째로 실패. 서버 로그 = script_extract가 Gemini 503 UNAVAILABLE
("This model is currently experiencing high demand")로 빈 결과 반환 → 프론트가 재료 없이
생성 요청 → 404 "먼저 S급으로 저장하세요"라는 정반대 안내까지 뜸.

★핵심 사실(추측 아님, 서버 실측 2026-07-16 23:5x):
  - 전용 키풀 16개 전부 살아있음. 그중 5개를 각각 호출 → gemini-3.5-flash는 **5/5 전부 503**.
    → **503은 키 문제가 아니다. 키 로테이션으로는 절대 안 풀린다.**
  - 같은 키·같은 영상·같은 순간에 gemini-3.1-flash-lite는 정상 — 실제 extract_script를
    이 모델로 태워 구간 6개·full_text 208자 확보(response_schema까지 지켜짐).
  → 그래서 '키를 더 넣자'가 아니라 '모델을 갈아타자'가 맞는 대응이다.

설계(2026-07-24 갱신):
  - primary(_MODEL)로 503을 **1번** 겪으면 바로 _FALLBACK_MODEL로 내려간다. 예전엔 spike 회복을
    기대해 2번 겪은 뒤 내려갔으나, 검열 실측 성공률 29%(100/350)로 3.5-flash가 spike가 아니라
    지속적으로 막힌 게 드러나 죽은 모델 재시도를 낭비하지 않게 첫 503에서 바로 폴백한다.
  - 폴백 후엔 sleep 없이 바로 간다 — 다른 모델이라 앞 모델의 혼잡과 무관.
  - _MODEL 자체는 안 건드린다(video_analysis·similarity가 공유).

네트워크·실키 없이 검증하려고 comment_gen의 클라이언트 팩토리만 가짜로 바꾼다.
"""
import sys
import types as pytypes

import pytest

from shopping_shorts import comment_gen, script_extract


class _FakeFiles:
    def upload(self, **kw):
        return pytypes.SimpleNamespace(name="files/fake", state=pytypes.SimpleNamespace(name="ACTIVE"))

    def delete(self, **kw):
        pass


class _FakeModels:
    """overloaded에 든 모델명은 503을 던진다. raise_all이 있으면 모델과 무관하게 그 오류를 던진다."""

    def __init__(self, overloaded, calls, raise_all=None):
        self._overloaded = overloaded
        self._calls = calls
        self._raise_all = raise_all

    def generate_content(self, model=None, contents=None, config=None):
        self._calls.append(model)
        if self._raise_all:
            raise RuntimeError(self._raise_all)
        if model in self._overloaded:
            raise RuntimeError(
                "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
                "'This model is currently experiencing high demand.', 'status': 'UNAVAILABLE'}}"
            )
        return pytypes.SimpleNamespace(
            text='{"segments": [{"start": 0.0, "end": 2.0, "text": "가짜 대본", "scene_desc": "x"}],'
                 ' "full_text": "가짜 대본"}'
        )


class _FakeClient:
    def __init__(self, overloaded, calls, box):
        self.files = _FakeFiles()
        self.models = _FakeModels(overloaded, calls, box.get("raise_all"))


@pytest.fixture
def harness(monkeypatch, tmp_path):
    """(calls 리스트, overloaded 집합, 영상경로, box)를 주고 extract_script를 실제로 돌린다.

    box["raise_all"]에 오류 문자열을 넣으면 모든 호출이 그 오류를 던진다(429 등 재현용)."""
    vid = tmp_path / "v.mp4"
    vid.write_bytes(b"\x00" * 16)
    calls = []
    overloaded = set()
    box = {}

    monkeypatch.setattr(script_extract, "SHORTS_GEMINI_KEYS", ["k1", "k2"], raising=False)
    monkeypatch.setattr(comment_gen, "_current_key_and_idx", lambda: ("k1", 0))
    monkeypatch.setattr(comment_gen, "_client_for_key", lambda k: _FakeClient(overloaded, calls, box))
    monkeypatch.setattr(script_extract, "_wait_until_active", lambda c, f: f)
    monkeypatch.setattr(script_extract.time, "sleep", lambda s: None)  # 테스트는 안 기다린다
    # ★_MODEL을 매 테스트마다 원복한다. 안 하면 '폴백이 전역을 오염시키는' 결함이 앞 테스트에서
    # 먼저 터져, 뒤 테스트의 before가 이미 오염된 값이라 비교가 무의미해진다 —
    # test_fallback_does_not_mutate_shared_model이 통과하는데 결함은 살아있는 죽은 테스트가 된다
    # (실측: 뮤턴트를 심고 전체 실행하면 통과, 단독 실행하면 실패했다).
    monkeypatch.setattr(script_extract, "_MODEL", script_extract._MODEL)
    return calls, overloaded, str(vid), box


def test_primary_used_when_healthy(harness):
    """평소엔 폴백까지 안 내려간다 — 품질이 그대로여야 한다."""
    calls, overloaded, vid, box = harness
    r = script_extract.extract_script(vid, "vid1")
    assert r["full_text"] == "가짜 대본"
    assert calls == [script_extract._MODEL], f"평소에 폴백 모델이 불렸다: {calls}"
    assert script_extract._FALLBACK_MODEL not in calls


def test_falls_back_to_lite_when_primary_overloaded(harness):
    """★사고 재현: primary가 503이면 대체 모델로 갈아타 대본을 확보한다."""
    calls, overloaded, vid, box = harness
    overloaded.add(script_extract._MODEL)          # 3.5-flash만 혼잡(= 실측 상황)
    r = script_extract.extract_script(vid, "vid1")
    assert r["full_text"] == "가짜 대본", f"503에 폴백 못 하고 빈 결과 — calls={calls}"
    assert script_extract._FALLBACK_MODEL in calls, f"대체 모델을 안 불렀다: {calls}"
    assert r["segments"] and r["segments"][0]["seg_id"] == "vid1-0"


def test_falls_back_on_first_503(harness):
    """503은 지속적이므로 첫 503에서 바로 폴백한다 — 죽은 모델 재시도 낭비 제거(2026-07-24)."""
    calls, overloaded, vid, box = harness
    overloaded.add(script_extract._MODEL)
    script_extract.extract_script(vid, "vid1")
    primary_tries = [c for c in calls if c == script_extract._MODEL]
    assert len(primary_tries) == 1, f"첫 503에서 바로 폴백해야 한다 — calls={calls}"
    assert calls.index(script_extract._FALLBACK_MODEL) == 1, \
        f"폴백이 첫 503 직후가 아니다 — calls={calls}"


def test_gives_up_when_both_models_overloaded(harness):
    """둘 다 막히면 무한루프 돌지 말고 빈 결과로 끝낸다."""
    calls, overloaded, vid, box = harness
    overloaded.update({script_extract._MODEL, script_extract._FALLBACK_MODEL})
    r = script_extract.extract_script(vid, "vid1")
    assert r["full_text"] == "" and r["segments"] == []
    assert len(calls) <= 4, f"max_retries를 넘겨 호출했다 — {calls}"


def test_fallback_does_not_mutate_shared_model(harness):
    """_MODEL은 video_analysis·similarity가 공유한다 — 폴백이 전역을 오염시키면 안 된다."""
    calls, overloaded, vid, box = harness
    before = script_extract._MODEL
    overloaded.add(script_extract._MODEL)
    script_extract.extract_script(vid, "vid1")
    assert script_extract._MODEL == before, "폴백이 공유 _MODEL을 바꿨다 — 다른 기능까지 lite로 끌려간다"


def test_quota_error_still_rotates_keys_not_model(harness, monkeypatch):
    """429(키 소진)는 모델이 아니라 키 문제 — 폴백으로 새지 않아야 한다.

    원인과 대응이 어긋나면 안 된다: 503=모델 갈아타기 / 429=키 갈아타기."""
    calls, overloaded, vid, box = harness
    box["raise_all"] = ("429 RESOURCE_EXHAUSTED. {'error': {'code': 429, "
                        "'message': 'Quota exceeded', 'status': 'RESOURCE_EXHAUSTED'}}")
    marked = []
    monkeypatch.setattr(comment_gen, "_mark_key_exhausted", lambda i: marked.append(i))
    monkeypatch.setattr(script_extract.key_vault, "is_daily_exhausted_error", lambda e: True)
    script_extract.extract_script(vid, "vid1")
    assert marked, "429인데 키를 소진 처리하지 않았다"
    assert script_extract._FALLBACK_MODEL not in calls,         f"429(키 문제)인데 모델을 갈아탔다 — 원인과 대응이 어긋남: {calls}"
