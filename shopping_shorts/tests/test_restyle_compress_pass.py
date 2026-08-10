"""restyle 마지막 압축 패스 — 재시도가 전부 길이 밖이어도 스타일을 버리지 않는다.

2026-08-07 실사고: maison·chae 리라이트가 매번 1.45배를 넘어 재시도 소진 →
원본 복귀 → trio 3안이 같은 결로 수렴("매칭이 안 됨"). 이제 최근접 스타일본을
"문체 유지·길이만 축소"로 한 번 더 눌러 스타일과 길이를 둘 다 지킨다.
"""
from shopping_shorts import single_source


def _beats(texts):
    return [{"n": i + 1, "narration": t, "covers": [i + 1]}
            for i, t in enumerate(texts)]


def _resp(texts):
    return {"beats": [{"n": i + 1, "narration": t} for i, t in enumerate(texts)]}


def test_compress_pass_rescues_overlong_style(monkeypatch):
    monkeypatch.setattr(single_source.style_profiles if hasattr(single_source, "style_profiles") else
                        __import__("shopping_shorts.style_profiles", fromlist=["x"]),
                        "active_style", lambda: "maison", raising=False)
    orig = _beats(["원본 문장 하나입니다 열심히", "원본 문장 둘입니다 열심히"])
    long_texts = ["스타일이 입혀졌지만 아주 아주 아주 길게 불어난 문장입니다 정말로 길어요 계속 길어요",
                  "두 번째도 마찬가지로 크게 불어난 스타일 문장입니다 정말로 길어요 계속 길어요"]
    short_texts = ["스타일 결 유지한 문장요", "둘째도 결 유지한 문장요"]
    calls = {"n": 0}

    def call(prompt, schema):
        calls["n"] += 1
        # 처음 3회(재시도)는 전부 과길이, 4번째(압축 패스)는 목표 길이 안.
        return _resp(long_texts if calls["n"] <= 3 else short_texts)

    rep = {}
    out = single_source.apply_restyle(orig, call, style_name="maison", report=rep)
    assert rep["ok"] is True
    assert "압축패스" in rep["why"]
    assert out[0]["narration"] == short_texts[0]
    assert out[0]["covers"] == [1]          # 컷 매핑 보존


def test_exhaustion_without_any_valid_style_keeps_original(monkeypatch):
    monkeypatch.setattr(__import__("shopping_shorts.style_profiles", fromlist=["x"]),
                        "active_style", lambda: "maison", raising=False)
    orig = _beats(["원본 하나입니다 열심히 사는", "원본 둘입니다 열심히 사는"])

    def call(prompt, schema):
        return {"beats": []}                 # 구조 실패만 반복

    rep = {}
    out = single_source.apply_restyle(orig, call, style_name="maison", report=rep)
    assert rep["ok"] is False
    assert out[0]["narration"] == orig[0]["narration"]
