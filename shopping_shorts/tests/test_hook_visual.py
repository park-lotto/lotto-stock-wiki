"""P1 훅 비주얼(2026-07-29): 인벤토리가 shot_role/is_key를 프롬프트에 노출하되 scene_desc는 불변.
훅 규칙이 완성/실증 장면을 첫 화면으로 당기고 준비동작을 금지하는지."""
import inspect
from shopping_shorts import edit_plan as ep


def _script():
    return [{"video_id": "v1", "segments": [
        {"seg_id": "v1-0", "start": 0, "end": 2, "text": "훅", "scene_desc": "인트로"},
        {"seg_id": "v1-1", "start": 2, "end": 4, "text": "재료 붓기", "scene_desc": "우유를 붓는다",
         "shot_role": "조리", "is_key": False},
        {"seg_id": "v1-2", "start": 4, "end": 6, "text": "완성", "scene_desc": "완성된 모찌",
         "shot_role": "완성", "is_key": True},
        {"seg_id": "v1-3", "start": 6, "end": 8, "text": "끝", "scene_desc": "인사"},
    ]}]


def test_inventory_exposes_shot_role_and_is_key():
    seg_map, block = ep._build_inventory(_script())
    assert "역할:조리" in block and "역할:완성" in block
    assert "실증:Y" in block            # v1-2 is_key=True
    assert "실증:N" in block            # v1-1 is_key=False
    # scene_desc 문자열엔 역할/실증이 안 섞였다(_claim_key 오염 방지)
    assert seg_map["v1-2"]["scene_desc"] == "완성된 모찌"
    assert "역할" not in seg_map["v1-2"]["scene_desc"]


def test_prompt_has_hook_visual_rule():
    src = inspect.getsource(ep._scene_first_candidates)
    assert "역할:완성" in src
    assert "준비동작" in src
    assert "시간순" in src


def test_reconcile_catches_forced_beats_even_if_fit_high():
    """★2026-07-29 억지매칭: forced=True면 fit이 높아도 화면에 맞게 재작성 대상이어야 한다."""
    calls = {"n": 0}
    def fake_call(prompt, schema):
        calls["n"] += 1
        # 프롬프트에 forced 비트가 들어왔는지로 대상 선정을 검증
        assert "억지대사" in prompt
        return {"rewrites": [{"beat_idx": 1, "narration": "고친대사"}]}
    beats = [
        {"beat_idx": 0, "narration": "정상", "fit": 5, "forced": False,
         "primary": {"scene_desc": "완성"}},
        {"beat_idx": 1, "narration": "억지대사", "fit": 4, "forced": True,   # fit 높지만 forced
         "primary": {"scene_desc": "우유붓기"}},
    ]
    out = ep._reconcile_weak_beats(beats, call=fake_call)
    assert calls["n"] == 1                       # forced 비트 때문에 호출됨(예전엔 fit>3라 스킵)
    assert out[1]["narration"] == "고친대사"     # 재작성 반영


def test_reconcile_skips_when_all_good():
    """fit 높고 forced 아니면 호출 없이 원문 유지(불필요한 Gemini 호출 방지)."""
    called = {"n": 0}
    def fake_call(p, s):
        called["n"] += 1
        return {"rewrites": []}
    beats = [{"beat_idx": 0, "narration": "정상", "fit": 5, "forced": False,
              "primary": {"scene_desc": "완성"}}]
    out = ep._reconcile_weak_beats(beats, call=fake_call)
    assert called["n"] == 0 and out[0]["narration"] == "정상"
