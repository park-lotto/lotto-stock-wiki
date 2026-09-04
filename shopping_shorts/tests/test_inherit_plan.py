# -*- coding: utf-8 -*-
"""3단계 '붙어 온 장면 그대로 쓰기'(build_inherit_plan, 2026-09-04) — 사장님 "3단계는 상속만".

2단계가 줄마다 남긴 출처(beat_sources)를 줄=비트로 잇는다. Gemini 0회. 추측 층(respine·verify·repick·reconcile)은
이 경로에서 안 부른다. 못 이으면 None(옛 경로 폴백)."""
from shopping_shorts import edit_plan as EP


def _src(n=8, vid="s0"):
    return [{"video_id": vid, "segments": [
        {"seg_id": f"{vid}-{i}", "start": float(i * 2), "end": float(i * 2 + 2),
         "text": f"말{i}", "scene_desc": f"화면{i}", "shot_role": "사용중"} for i in range(n)]}]


SCRIPT = "카페 쿠키 사 먹지 마세요\n버터를 휘핑하고 가루를 섞었죠\n오븐에서 갓 구운 단면이 이래요\n댓글에 쿠키 남겨주세요"


def test_출처가_있는_줄은_그대로_잇고_없는_줄은_다음_컷으로_채운다():
    srcs = [{"role": "hook", "seg": "", "segs": []},
            {"role": "demo", "seg": "s0-2", "segs": ["s0-2", "s0-3"]},
            {"role": "result", "seg": "s0-5", "segs": ["s0-5"]},
            {"role": "cta", "seg": "", "segs": []}]
    plan = EP.build_inherit_plan(_src(), SCRIPT, srcs)
    assert plan and plan["generator"] == "inherit"
    b = plan["beats"]
    assert [x["narration"] for x in b] == SCRIPT.split("\n")
    assert b[1]["primary"]["seg_id"] == "s0-2" and [a["seg_id"] for a in b[1]["alternates"]][:1] == ["s0-3"]
    assert b[1]["inherited"] and b[1]["fit"] == 5 and b[1]["src_seg_applied"] == "s0-2"
    assert b[2]["primary"]["seg_id"] == "s0-5" and b[2]["inherited"]
    # 훅(출처 없음): 앞 비트가 없으니 미사용 첫 컷. CTA(출처 없음): 앞 비트 s0-5의 다음 미사용 컷 = s0-6
    assert not b[0]["inherited"] and b[0]["fit"] == 3 and b[0]["fit_evidence"] == "broll_fill"
    assert b[3]["primary"]["seg_id"] == "s0-6" and not b[3]["inherited"]
    # 화면 길이 보루가 돌았다(대사보다 짧지 않다)
    assert all(EP._beat_screen_secs(x) >= x["target_seconds"] - 1e-6 for x in b)


def test_지어낸_번호는_버리고_남은_실재_번호로_잇는다():
    srcs = [{"role": "a", "seg": "s0-99", "segs": ["s0-99", "s0-1"]},
            {"role": "b", "seg": "s0-4", "segs": []},
            {"role": "c", "seg": "", "segs": []},
            {"role": "d", "seg": "s0-6", "segs": []}]
    plan = EP.build_inherit_plan(_src(), SCRIPT, srcs)
    assert plan["beats"][0]["primary"]["seg_id"] == "s0-1"
    assert plan["beats"][1]["primary"]["seg_id"] == "s0-4"        # seg만 있고 segs 비어도 된다


def test_줄_수와_출처_수가_다르면_None으로_옛_경로에_넘긴다():
    assert EP.build_inherit_plan(_src(), SCRIPT, [{"role": "a", "seg": "s0-1"}]) is None
    assert EP.build_inherit_plan(_src(), "", [{"role": "a", "seg": "s0-1"}]) is None
    assert EP.build_inherit_plan(_src(), SCRIPT, None) is None
    # 실재 출처가 하나도 없으면(전부 지어냄) 상속할 게 없다
    none = [{"role": "x", "seg": "s0-99"}] * 4
    assert EP.build_inherit_plan(_src(), SCRIPT, none) is None


def test_추측_층을_부르지_않는다(monkeypatch):
    called = []
    for name in ("_chronological_respine", "_verify_fits", "_repick_weak_beats", "_reconcile_weak_beats"):
        monkeypatch.setattr(EP, name, lambda *a, _n=name, **k: called.append(_n) or a[0])
    srcs = [{"role": "a", "seg": "s0-1"}, {"role": "b", "seg": "s0-2"},
            {"role": "c", "seg": "s0-3"}, {"role": "d", "seg": "s0-4"}]
    EP.build_inherit_plan(_src(), SCRIPT, srcs)
    assert called == [], f"상속 경로가 추측 층을 불렀다: {called}"


def test_mix_pipeline은_스위치가_켜진_잡에서만_상속을_시도한다(monkeypatch):
    from shopping_shorts import mix_pipeline as MP, edit_plan as EP2
    seen = []
    monkeypatch.setattr(EP2, "build_inherit_plan", lambda *a, **k: seen.append(1) or None)
    import inspect
    sig = inspect.signature(MP._plan_and_tts)
    assert "script_structure" in sig.parameters, "잡의 script_structure가 계획 함수까지 와야 한다"
    src = inspect.getsource(MP._plan_and_tts)
    assert "inherit_scenes" in src and "build_inherit_plan" in src
    # 호출부 2곳 모두 넘긴다
    body = inspect.getsource(MP)
    assert body.count("script_structure=job.get(\"script_structure\")") == 2
