"""#4901(11-04 김효준): 판 frame.segments 훅 구간 틀이 bg·제목·watermark 등을 판 원래 값으로 덮어, 회원이 정한 바탕색·채널명이 첫 장면에서 빠졌다
(실측: 썰템쇼판·맛템썰템판·이븐쇼핑판). 회원이 바꾼 칸만 구간 틀에도 같은 규칙으로(styles.member_frame) — 안 바꾼 칸은 구간 판 값 그대로."""
import json

import pytest

from tools.calcopy.hybrid import render_bench as RB, styles as STY

S = {"lines": [{"id": "L1", "kind": "tts", "tts": "a", "caps": [{"text": "a"}]}]}
T = {"lines": {"L1": [0.0, 1.0]}, "end": 10.0}


def _hook(tmp_path, monkeypatch, v, member):
    p = tmp_path / "p.json"
    p.write_text(json.dumps({"member": member}), encoding="utf-8")
    monkeypatch.setenv("SHORTEM_MEMBER_PACK", str(p))
    return RB.frame_segments(S, T, STY.load(v))[0]["frame"]


@pytest.mark.parametrize("v", ["썰템쇼판", "맛템썰템판", "이븐쇼핑판"])
def test_회원이_바꾼_칸은_훅_구간에도(tmp_path, monkeypatch, v):
    Fi = _hook(tmp_path, monkeypatch, v, {"brand": {"channel_name": "테스트채널", "colors": {"bg": [10, 10, 10]},
                                                  "watermark": {"cx": 540, "cy": 1500, "px": 50, "alpha": 200}}})
    assert Fi["bg"] == [10, 10, 10]
    assert (Fi.get("watermark") or {}).get("text") == "테스트채널" and Fi["watermark"]["cy"] == 1500


@pytest.mark.parametrize("v", ["썰템쇼판"])
def test_안_바꾼_칸은_구간_판_값(tmp_path, monkeypatch, v):
    monkeypatch.delenv("SHORTEM_MEMBER_PACK", raising=False)
    base = RB.frame_segments(S, T, STY.load(v))[0]["frame"]
    Fi = _hook(tmp_path, monkeypatch, v, {"brand": {"channel_name": "테스트채널"}})
    assert Fi["bg"] == base["bg"]                       # 바탕색은 안 바꿨다 = 훅 카드 판 색
    assert Fi.get("watermark") == base.get("watermark")  # 워터마크 칸을 안 정했다 = 구간 판 값(없음) 그대로


def test_hook_card_gets_channel_name_when_only_head_bar_has_it(tmp_path, monkeypatch):
    # 11-05 김효준 #7230: 썰템쇼판은 본 틀 머리띠에만 채널명 자리 — 훅 카드 머리띠가 비어 첫 구간에 채널명이 안 나왔다(렌더 길 frame_segments 로 잰다)
    Fi = _hook(tmp_path, monkeypatch, "썰템쇼판", {"brand": {"channel_name": "살까말까잡화점"}})
    icons = ((Fi.get("post") or {}).get("head_bar") or {}).get("icons") or []
    assert any(ic.get("text") == "살까말까잡화점" for ic in icons), "훅 카드에 채널명이 없다"
