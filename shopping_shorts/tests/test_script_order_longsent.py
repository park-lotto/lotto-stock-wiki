# -*- coding: utf-8 -*-
"""음슴체(마침표 없는) 대본이 훅 한 칸에 통째로 들어가던 사고의 회귀 테스트.

2026-08-29 실사고(job fdf6ece94471·86d60b915742): 유튜브 오용형 대본은 설계상
마침표가 없는 ~음체라 script_sentences()가 **통짜 1문장**을 돌려주고,
enforce_script_order의 "문장은 쪼개지 않는다" 규칙이 그 덩어리를 첫 칸(hook)에
통째로 넣었다(288자·29.9초). 수리: 칸이 감당 못 할 초장문만 호흡 분할기
(_caption_segments — 렌더 자막과 같은 분할기)로 갈라 칸 크기 덩이로 묶는다.
"""
from shopping_shorts.edit_plan import enforce_script_order, _narr_key

# 실사고 대본과 같은 음슴체 — 마침표·물음표가 하나도 없다(207자, 문장분리 1개가 나온다)
UMCHE = ("개발자도 예상 못 한 이 제품의 정체 딱 봤을 때는 용도를 알기 힘든 이 제품이 "
         "이걸 만든 천재가 떼돈을 벌었다는데 도대체 뭘까 했는데 무봉제 스티치 건이었음 "
         "솔직히 처음엔 스테이플러인 줄 알았는데 원래는 옷감 수선용으로 나온 기기임 "
         "사람들이 실 없이도 직물을 단단하게 고정하는 걸 알아채고 예상 밖의 방식으로 쓰기 시작한 거임 "
         "바늘 없이도 1초 만에 커튼 단까지 정리하는 거 보면 이게 왜 대박인지 알게 됨")

PUNCT = ("첫 문장입니다. 두 번째 문장이 이어집니다. 세 번째 문장은 조금 더 깁니다. "
         "네 번째 문장도 있습니다. 다섯 번째 문장으로 끝납니다.")


def _beats(targets, roles=None):
    roles = roles or (["hook"] + ["solution"] * (len(targets) - 2) + ["cta"])
    return [{"beat_idx": i, "role": roles[i], "narration": f"엉뚱한 옛말 {i}",
             "target_seconds": t} for i, t in enumerate(targets)]


def test_umche_script_spreads_across_beats():
    beats = _beats([3.0, 4.0, 5.0, 6.0, 4.0])
    out, fixed = enforce_script_order(beats, UMCHE)
    narrs = [(b.get("narration") or "") for b in out]
    # ①누락·창작 없음: 이어붙이면 대본 그대로
    assert _narr_key("".join(narrs)) == _narr_key(UMCHE)
    # ②훅 독식 금지: 첫 칸이 전체의 45%를 넘지 않는다(칸 비례 배분이 살아있다)
    total = sum(len(n) for n in narrs)
    assert len(narrs[0]) < total * 0.45, f"hook {len(narrs[0])}/{total}자 독식"
    # ③빈 칸 없음
    assert all(n.strip() for n in narrs)


def test_punctuated_script_behavior_unchanged():
    beats = _beats([3.0, 3.0, 3.0, 3.0, 3.0])
    out, fixed = enforce_script_order(beats, PUNCT)
    narrs = [(b.get("narration") or "") for b in out]
    assert _narr_key("".join(narrs)) == _narr_key(PUNCT)
    # 문장 5개·칸 5개 — 문장 중간이 잘리지 않고 한 문장씩 들어간다(종전 동작)
    assert narrs[0].startswith("첫 문장") and narrs[-1].startswith("다섯 번째")


def test_short_umche_single_beat_untouched():
    # 칸 하나·짧은 음슴체 — 자를 이유가 없다: 통째로 그 칸에
    beats = _beats([5.0], roles=["hook"])
    out, fixed = enforce_script_order(beats, "이 제품 하나로 정리 끝남")
    assert _narr_key(out[0]["narration"]) == _narr_key("이 제품 하나로 정리 끝남")
