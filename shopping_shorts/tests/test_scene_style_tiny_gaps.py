"""장면꾸미기 컨텍스트: 자막 없는 아주 짧은 틈(cap_lead 등)이 빈 장면으로 세지지 않는다 (2026-09-22 사장님 "본문 첫 자막이 없음").

실측 job d29a2bd26032: 본문 첫 비트 3.58~3.74(0.16초)가 caption '' 장면 → 편집기 '5/35'가 빈 띠, 렌더에 5프레임 빈 띠.
"""
from shopping_shorts import scene_style


def _timeline():
    # 훅(2.9초, cap_lead 0.21) + 본문(3.55초, cap_lead 0.16) — 실제 job 모양
    return [
        {"beat_idx": 0, "t0": 0.0, "dur": 3.58, "narration": "시간 없는 직장인들 사이에서 입소문 터진 두피 관리 치트키",
         "cap_durs": [1.53, 0.81, 1.03], "cap_lead": 0.21, "caption_lines": ["시간 없는 직장인들 사이에서", "입소문 터진", "두피 관리 치트키"]},
        {"beat_idx": 1, "t0": 3.58, "dur": 3.55, "narration": "아침마다 머리 감고 앰플 바르느라 진 빠지던 사람들이",
         "cap_durs": [1.02, 0.68, 1.02], "cap_lead": 0.16, "caption_lines": ["아침마다 머리 감고", "앰플 바르느라", "진 빠지던 사람들이"]},
    ]


def test_leading_tiny_gap_is_absorbed_into_first_caption():
    ctx = scene_style.context_for(_timeline(), {"text": "두피 관리\n치트키"}, None, "qa")
    scenes = ctx["scenes"]
    empties = [s for s in scenes if not s["caption"] and (s["end"] - s["start"]) < scene_style._TINY_GAP]
    assert empties == [], f"0.35초 미만 빈 장면이 남았다: {empties}"
    first_body = next(s for s in scenes if s["kind"] == "body")
    assert first_body["caption"] == "아침마다 머리 감고"
    assert abs(first_body["start"] - 3.58) < 1e-6, "본문 첫 자막이 비트 시작(3.58)부터 보여야 한다"
    assert abs(scenes[0]["start"]) < 1e-6 and scenes[0]["caption"] == "시간 없는 직장인들 사이에서"


def test_real_silent_gap_is_kept():
    scenes = [{"start": 0, "end": 1, "caption": "a", "beat_idx": 0, "kind": "hook", "caption_visible": True},
              {"start": 1, "end": 1.9, "caption": "", "beat_idx": 0, "kind": "hook", "caption_visible": True},
              {"start": 1.9, "end": 3, "caption": "b", "beat_idx": 0, "kind": "hook", "caption_visible": True}]
    out = scene_style._absorb_tiny_gaps(scenes)
    assert [s["caption"] for s in out] == ["a", "", "b"], "0.35초 이상 무자막 구간은 그대로 둔다"


def test_gap_does_not_cross_beat_boundary():
    scenes = [{"start": 0, "end": 1, "caption": "a", "beat_idx": 0, "kind": "hook", "caption_visible": True},
              {"start": 1, "end": 1.2, "caption": "", "beat_idx": 1, "kind": "body", "caption_visible": True},
              {"start": 1.2, "end": 2, "caption": "b", "beat_idx": 1, "kind": "body", "caption_visible": True}]
    out = scene_style._absorb_tiny_gaps(scenes)
    assert [(s["caption"], s["start"], s["end"]) for s in out] == [("a", 0, 1), ("b", 1, 2)]
