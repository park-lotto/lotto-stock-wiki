# -*- coding: utf-8 -*-
"""화면 검증(verify_beat_screens) — 고른 화면이 그 대사에 맞는지 되묻는 단계 (2026-09-09).

■ 왜 이 모양인지가 여기 박혀 있다 (라이브 실측으로 세 번 갈아엎었다)
  ① 바로 고르기    억지 선택을 **0%** 잡았다. 모델은 재료가 없어도 고른다.
  ② 요구 먼저 적기  그 문장에 갇혀 **67%가 가짜 '없음'**("물에 슥 씻기만"에 '식재료 씻는
                   모습'이라 적고, 정작 있는 '롤러 헹구는 장면'을 기각).
  ③ 고르기 → 검증  탈락 17%가 전부 진짜였고 오탐 0. ← 이 파일이 지키는 것.

■ 이 테스트가 못박는 계약
  · 아무것도 **교체하지 않는다**(표시만) — 자동 교체는 84%가 바뀌어 회귀 위험이 크다
  · 스위치가 꺼져 있으면 **호출조차 안 한다**(과금 0)
  · visual_verb=false(이야기 문장)는 대상이 아니다
  · 모델·키가 죽어도 원본 그대로(fail-open)
"""
import pytest

from shopping_shorts import edit_plan


class _Store:
    def __init__(self, on): self._on = on
    def get_setting(self, k, d=""): return "1" if self._on else ""


def _beat(fit=5, narr="옆으로 누워도 안 아픔", sid="s1", **kw):
    b = {"beat_idx": 0, "role": "info", "narration": narr, "fit": fit,
         "primary": {"video_id": "s0", "seg_id": sid}}
    b.update(kw)
    return b


SEGS = {"s1": {"seg_id": "s1", "scene_desc": "물그릇에서 건져낸 이어플러그를 천으로 닦는다"}}


def _frame(_sid, _seg):
    return "frame.jpg"


def test_스위치가_꺼져있으면_호출조차_안한다():
    """검증 안 된 걸 라이브에 켜두면 조용히 비용이 나간다(B1 실사고 계보)."""
    called = []
    out = edit_plan.verify_beat_screens(
        [_beat()], SEGS, call=lambda *a, **k: called.append(1) or {"ok": False},
        store=_Store(False), frame_resolver=_frame)
    assert called == [], "스위치가 꺼졌는데 모델을 불렀다"
    assert out[0]["fit"] == 5


def test_탈락하면_fit을_깎고_근거를_남긴다():
    out = edit_plan.verify_beat_screens(
        [_beat()], SEGS,
        call=lambda *a, **k: {"ok": False, "why": "세척 장면이라 무관"},
        store=_Store(True), frame_resolver=_frame)
    b = out[0]
    assert b["fit"] == 2, "탈락인데 fit이 안 깎였다"
    assert b["fit_evidence"] == "verify_failed"
    assert "세척" in b["verify_why"]


def test_통과하면_아무것도_안_바꾼다():
    out = edit_plan.verify_beat_screens(
        [_beat()], SEGS, call=lambda *a, **k: {"ok": True}, store=_Store(True),
        frame_resolver=_frame)
    assert out[0]["fit"] == 5
    assert "fit_evidence" not in out[0] or out[0]["fit_evidence"] != "verify_failed"


def test_화면을_교체하지_않는다():
    """★표시만 한다 — primary를 바꾸면 84%가 바뀌어 회귀 위험이 크다(2026-09-09 실측)."""
    out = edit_plan.verify_beat_screens(
        [_beat()], SEGS, call=lambda *a, **k: {"ok": False, "why": "무관"},
        store=_Store(True), frame_resolver=_frame)
    assert out[0]["primary"]["seg_id"] == "s1", "검증이 화면을 갈아치웠다"


def test_이야기_문장은_대상이_아니다():
    """감정·설명·CTA는 화면이 안 맞는 게 정상이다(2026-09-08 실측: fit<=2의 49%)."""
    called = []
    out = edit_plan.verify_beat_screens(
        [_beat(visual_verb=False)], SEGS,
        call=lambda *a, **k: called.append(1) or {"ok": False}, store=_Store(True),
        frame_resolver=_frame)
    assert called == [], "이야기 문장에 모델을 불렀다"
    assert out[0]["fit"] == 5


def test_모델이_죽어도_원본_그대로():
    out = edit_plan.verify_beat_screens(
        [_beat()], SEGS, call=lambda *a, **k: None, store=_Store(True),
        frame_resolver=_frame)
    assert out[0]["fit"] == 5 and "fit_evidence" not in out[0]


def test_화면묘사가_없으면_건너뛴다():
    called = []
    out = edit_plan.verify_beat_screens(
        [_beat(sid="없는칸")], SEGS,
        call=lambda *a, **k: called.append(1) or {"ok": False}, store=_Store(True),
        frame_resolver=_frame)
    assert called == []


def test_프롬프트가_맥락_허용을_담고_있다():
    """이 문구가 빠지면 문자 그대로 따져 멀쩡한 것까지 떨군다(요구먼저 방식의 67% 과잉기각)."""
    assert "맥락으로" in edit_plan._SCREEN_VERIFY_PROMPT
    assert "실제로 보이거나" in edit_plan._SCREEN_VERIFY_PROMPT


def test_장면설명_대신_대표프레임을_넘긴다():
    seen = {}

    def call(prompt, schema, frame_path):
        seen.update(prompt=prompt, schema=schema, frame_path=frame_path)
        return {"ok": True}

    edit_plan.verify_beat_screens(
        [_beat()], SEGS, call=call, store=_Store(True), frame_resolver=_frame)
    assert seen["frame_path"] == "frame.jpg"
    assert "첨부 이미지" in seen["prompt"]
    assert SEGS["s1"]["scene_desc"] not in seen["prompt"], "텍스트 화면묘사가 아직 모델에 전달됐다"


def test_장면설명이_비어도_프레임이_있으면_검증한다():
    called = []
    segs = {"s1": {"seg_id": "s1", "scene_desc": ""}}
    edit_plan.verify_beat_screens(
        [_beat()], segs,
        call=lambda *a: called.append(a) or {"ok": True},
        store=_Store(True), frame_resolver=_frame)
    assert len(called) == 1


def test_이미지호출이_jpeg_bytes를_기존_키회전에_싣는다(tmp_path, monkeypatch):
    frame = tmp_path / "s1.jpg"
    frame.write_bytes(b"\xff\xd8\xfffake-jpeg")
    seen = {}

    def fake_vault(contents, schema):
        seen.update(contents=contents, schema=schema)
        return {"ok": True}

    monkeypatch.setattr(edit_plan, "_vault_call", fake_vault)
    assert edit_plan._vault_call_image("prompt", edit_plan._SCREEN_VERIFY_SCHEMA, frame) == {"ok": True}
    assert seen["contents"][0] == "prompt"
    image = seen["contents"][1]
    assert image.inline_data.mime_type == "image/jpeg"
    assert image.inline_data.data == b"\xff\xd8\xfffake-jpeg"
