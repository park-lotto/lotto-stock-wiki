# -*- coding: utf-8 -*-
"""번역·브리프도 429면 **다른 키로** 재시도한다(2026-09-05 실측 수리).

사고: 힌디어 태깅건 영상(즐겨찾기)에서 text_ko가 12구간 전부 비었다. 원인은 코드가
_current_key_and_idx를 **한 번만** 부르고 429가 나도 같은 키로 모델만 바꿔 또 죽은 것.
태깅(_gemini_tag_frames)에만 키 회전이 있었다 — 같은 판단이 세 군데에 따로 적힌 자리.
"""
from shopping_shorts import frame_script as F


class _Boom(Exception):
    pass


def test_일시오류_판정은_한곳에서():
    assert F._is_transient("429 RESOURCE_EXHAUSTED")
    assert F._is_transient("503 UNAVAILABLE")
    assert F._is_transient("model is overloaded")
    assert not F._is_transient("400 INVALID_ARGUMENT")


def test_429면_다른_키로_한번_더(monkeypatch):
    keys = iter([("k1", 0), ("k2", 1), ("k3", 2), ("k4", 3)])
    used = []
    monkeypatch.setattr(F, "TAG_MODELS", ("m1", "m2"))

    class _CG:
        @staticmethod
        def _current_key_and_idx():
            return next(keys)

        @staticmethod
        def _client_for_key(k):
            return k

    import shopping_shorts
    monkeypatch.setattr(shopping_shorts, "comment_gen", _CG)

    def _call(client, model):
        used.append((client, model))
        if len(used) == 1:
            raise _Boom("429 RESOURCE_EXHAUSTED")   # 첫 키 소진
        return ["결과"]

    out = F._call_with_key_rotation(_call, what="테스트")
    assert out == ["결과"]
    assert used[0][0] == "k1" and used[1][0] == "k2", "두 번째 시도는 **다른 키**여야 한다"
    assert used[0][1] == used[1][1] == "m1", "같은 모델을 다른 키로 먼저 재시도한다"


def test_영구오류면_키를_안_바꾸고_다음_모델로(monkeypatch):
    keys = iter([("k1", 0), ("k2", 1), ("k3", 2)])
    used = []
    monkeypatch.setattr(F, "TAG_MODELS", ("m1", "m2"))

    class _CG:
        @staticmethod
        def _current_key_and_idx():
            return next(keys)

        @staticmethod
        def _client_for_key(k):
            return k

    import shopping_shorts
    monkeypatch.setattr(shopping_shorts, "comment_gen", _CG)

    def _call(client, model):
        used.append((client, model))
        if model == "m1":
            raise _Boom("400 INVALID_ARGUMENT")     # 키를 바꿔도 소용없는 오류
        return ["ok"]

    assert F._call_with_key_rotation(_call, what="테스트") == ["ok"]
    assert [m for _, m in used] == ["m1", "m2"], "영구 오류는 재시도 없이 다음 모델"


def test_키가_없으면_None(monkeypatch):
    class _CG:
        @staticmethod
        def _current_key_and_idx():
            return (None, 0)

        @staticmethod
        def _client_for_key(k):
            raise AssertionError("키가 없으면 호출하면 안 된다")

    import shopping_shorts
    monkeypatch.setattr(shopping_shorts, "comment_gen", _CG)
    assert F._call_with_key_rotation(lambda c, m: ["x"], what="테스트") is None
