"""11-05 회원 3명(박은숙 #6604·한정수 #6675·김효준 #6079): 장면 검수 답에 재료_더찾기와 재료를 같이 보내면 재료 수정이 버려져
다음 검수에 옛 재료가 다시 보였다. + 줄 캐시 글자 시각 어긋남(render_bench StageError)이 목소리 결함으로 안 잡혀 재료 고리로 가 '3번 연속'."""
from tools.calcopy.hybrid import flow as F


def _st():
    return {"version": "v1", "tries": {}, "log": [], "research": {}, "bench": {"id": "b"}, "origin": {"id": "o", "files": [{"name": "o.mp4"}]},
            "script": {"S": {"lines": []}, "M": {"cuts": {"L3": [{"src": "o.mp4", "ss": 11.0}]}}}, "material": {"files": []}, "_plan_over": []}


def test_more_material_keeps_same_answer_material(monkeypatch):
    st = _st()
    newM = {"cuts": {"L3": [{"src": "o.mp4", "ss": 42.0}]}}
    monkeypatch.setattr(F, "_reply", lambda rp, k, need: {"재료": newM, "재료_더찾기": ["삼립 호빵 리뷰"]})
    monkeypatch.setattr(F, "_take_fix", lambda st, r: st["script"].__setitem__("M", r["재료"]) or r["재료"])
    monkeypatch.setattr(F, "_material_n", lambda st: (1, 3))
    r = F.ph_plan_look(st, {}, {}, {})
    assert st["script"]["M"]["cuts"]["L3"][0]["ss"] == 42.0, "같은 답의 재료 수정이 버려졌다"
    assert r["do"][0]["cmd"] == "write_doc" and any(d.get("cmd") == "screen" for d in r["do"]) and r["then"] == "more_got"


def test_line_cache_timing_is_voice_defect():
    assert F.VOICE_RX.search("줄 캐시 a332.mp3 글자 시각이 줄 글(18자)과 안 맞는다 — 줄 캐시를 지우고 다시")
    assert F.VOICE_RX.search("줄 캐시로 이은 글자 시각이 전체 글과 다르다")
