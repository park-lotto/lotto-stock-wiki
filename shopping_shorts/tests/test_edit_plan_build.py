import json
from shopping_shorts import edit_plan


def _scripts():
    return [
        {"video_id": "A", "full_text": "가방이 흥건",
         "segments": [{"seg_id": "A-0", "start": 0.0, "end": 2.0, "text": "훅", "scene_desc": "컵"}]},
        {"video_id": "B", "full_text": "안 흘러요",
         "segments": [{"seg_id": "B-0", "start": 0.0, "end": 3.0, "text": "반전", "scene_desc": "뒤집기"}]},
    ]


def _fake_gemini(monkeypatch, payload_text):
    class FakeResp:
        text = payload_text

    class FakeModels:
        def generate_content(self, **k): return FakeResp()

    class FakeClient:
        models = FakeModels()

    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: ("k", 0))
    monkeypatch.setattr(edit_plan.comment_gen, "_client_for_key", lambda key: FakeClient())
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    # ★build_edit_plan은 comment_gen 전용키가 아니라 **key_vault 캐스케이드 예비키풀**을
    #   쓴다(_vault_call, 2026-07-13 전환 — 전용키 1개가 쉽게 소진돼서). 위 comment_gen
    #   stub만으로는 그 경로를 못 막아 실제 키를 찾다 못 찾고 None을 반환 → beats가 []가 되어
    #   이 테스트가 실패했다. 여기서 검증하려는 건 '응답을 어떻게 그라운딩·표절판정하느냐'이므로
    #   모델 호출 자체를 payload로 갈음한다.
    monkeypatch.setattr(edit_plan, "_vault_call",
                        lambda prompt, schema, **kw: json.loads(payload_text))


def test_build_edit_plan_grounds_and_flags(monkeypatch):
    payload = json.dumps({"structure": "free", "affiliate_target": "소금", "beats": [
        {"role": "훅", "narration": "완전 새로운 훅", "target_seconds": 2,
         "primary": {"seg_id": "A-0", "start": 999}, "alternates": [{"seg_id": "B-0"}], "effect": "cut"},
        {"role": "반전", "narration": "안 흘러요", "target_seconds": 3,
         "primary": {"seg_id": "B-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="free",
                                     video_type="product_reveal")
    assert len(out["beats"]) == 2
    # 그라운딩: 모델의 start=999 무시하고 실제값
    assert out["beats"][0]["primary"]["start"] == 0.0
    assert out["beats"][0]["primary"]["end"] == 2.0
    # 표절: beat1 narration "안 흘러요"가 소스 full_text와 동일 → flag
    assert any(f["beat_idx"] == 1 for f in out["plagiarism_flags"])
    # 장면스파인 재설계(2026-07-29): 옛 key product_reveal은 generic으로 흡수된다.
    assert out["detected_type"] == "generic"
    assert out["affiliate_target"] == "소금"


def test_build_edit_plan_structure_locked_to_input(monkeypatch):
    """모델이 raw structure에 지어낸 라벨(예: template_mode)을 줘도 입력 structure로 고정된다."""
    payload = json.dumps({"structure": "template_mode", "beats": [
        {"role": "훅", "narration": "훅 문장", "target_seconds": 2,
         "primary": {"seg_id": "A-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template",
                                     video_type="recipe_secret")
    assert out["structure"] == "template"
    assert out["detected_type"] == "recipe"   # 옛 key recipe_secret → recipe 흡수


def test_build_edit_plan_exhausted_returns_empty(monkeypatch):
    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: (None, None))
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template",
                                     video_type="product_reveal")
    assert out == {"structure": "template", "beats": [], "plagiarism_flags": [],
                    "detected_type": "generic", "affiliate_target": ""}


def test_build_edit_plan_auto_detects_when_type_not_given(monkeypatch):
    """video_type을 안 주면 detect_video_type()을 호출해 결과에 반영한다."""
    payload = json.dumps({"structure": "template", "beats": [
        {"role": "훅", "narration": "훅 문장", "target_seconds": 2,
         "primary": {"seg_id": "A-0"}, "alternates": []},
    ]})
    _fake_gemini(monkeypatch, payload)
    monkeypatch.setattr(edit_plan, "detect_video_type", lambda scripts: "recipe_secret")
    out = edit_plan.build_edit_plan(_scripts(), target_seconds=5, structure="template")
    assert out["detected_type"] == "recipe"   # 감지값(옛 key)도 새 key로 흡수


def test_detect_video_type_returns_valid_key(monkeypatch):
    payload = json.dumps({"video_type": "recipe_secret"})
    _fake_gemini(monkeypatch, payload)
    result = edit_plan.detect_video_type(_scripts())
    assert result == "recipe"   # 옛 key → 새 key 정규화 반환


def test_detect_video_type_invalid_key_falls_back_to_default(monkeypatch):
    payload = json.dumps({"video_type": "존재하지않는유형"})
    _fake_gemini(monkeypatch, payload)
    result = edit_plan.detect_video_type(_scripts())
    assert result == edit_plan._DEFAULT_TYPE


def test_detect_video_type_key_exhausted_falls_back_to_default(monkeypatch):
    monkeypatch.setattr(edit_plan.comment_gen, "_current_key_and_idx", lambda: (None, None))
    monkeypatch.setattr(edit_plan, "SHORTS_GEMINI_KEYS", ["fake_key"])
    result = edit_plan.detect_video_type(_scripts())
    assert result == edit_plan._DEFAULT_TYPE


def test_확정대본_경로도_화면이_대사보다_짧지_않다(monkeypatch):
    """★전수감사 1순위(2026-08-18): 화면 길이 보장이 이 경로엔 없었다.

    모델이 긴 대사에 1.5초 컷 하나만 붙여도 프롬프트는 통과한다(개수만 요구).
    그러면 렌더가 모자란 화면을 다음 클립으로 메워 밀림이 누적된다.
    이제 build_edit_plan도 _fill_beat_screen_time을 태워 남는 컷을 더 붙인다.
    """
    scripts = [{"video_id": "A", "full_text": "원문", "segments": [
        {"seg_id": f"A-{i}", "start": float(i * 2), "end": float(i * 2 + 2),
         "text": f"t{i}", "scene_desc": f"장면{i}"} for i in range(8)]}]
    long_narr = "가" * 60          # ≈ 60/_SYLLABLES_PER_SEC 초 — 2초 컷 하나론 턱없다
    payload = json.dumps({"structure": "free", "affiliate_target": "", "beats": [
        {"role": "훅", "narration": long_narr, "target_seconds": 2,
         "primary": {"seg_id": "A-1"}, "alternates": [], "effect": "cut"},
    ]})
    _fake_gemini(monkeypatch, payload)
    out = edit_plan.build_edit_plan(scripts, target_seconds=20, structure="free",
                                    video_type="generic", given_script=long_narr)
    b = out["beats"][0]
    assert edit_plan._beat_screen_secs(b) >= b["target_seconds"], \
        "화면 길이가 대사 읽는 시간보다 짧다 — 렌더에서 밀림이 누적된다"
