"""3단계에서 **사람이 고친 대본**이 저장 직후 되돌려지던 것 — 2026-08-25 고객 오류신고.

## 신고
cid 110 이준연 님: "3번 영상대본믹스에서 자막수정이 안되요 대본수정 누르고 대본 변경하고
저장+음성자막 다시 뽑기도하고 채우기도 해봤는데 다 수정이 안되요"

## 실측으로 확정한 원인 (재현 완료)
`store.update_mix_job(edit_plan=...)` 저장 출구의 `_ensure_screen_time`이
`enforce_scripted_narration(beats, given_script)`을 부른다. 이 검사는 비트 나레이션이
**1단계 확정 대본(given_script)에 없으면 "EDL이 지어낸 것"으로 보고 원본 문장으로 되돌린다**.

3단계에서 사람이 대본을 고치면 당연히 given_script와 달라진다 → **매번 되돌려졌다.**

재현(사장님 작업 ac7c7c0f6742 beat0, 라이브):
    보낸 것: {"text": "재현테스트 문장입니다 지워주세요", "regen": true}
    응답    : {"ok": true, "saved": true}          ← 저장했다고 답한다
    DB 실제 : "아니, 요즘 믹스커피 타 마시는 게 난리라는 거 아셨어요?"   ← 원본 그대로
고객 작업(253042206536 beat5)의 흔적도 정확히 같았다 — tts_ver만 1로 오르고
파일명 해시(=나레이션 md5)는 그대로였다. 즉 **글자는 안 바뀐 채 음성만 다시 뽑혔다.**

## 고치는 방향 (사장님 결정: "사람이 고친 건 표식을 달아 지킨다")
AI 창작 방어(2026-08-18 "영상이랑 대본이랑 다르다")는 **그대로 살린다**. 대신 사람이
직접 고친 비트에 `narration_manual` 표식을 달고, 되돌림 검사가 그 비트만 건너뛴다.
표식은 **사람이 고치는 그 자리**(3단계 저장 API)에서만 달린다 — AI 경로는 못 단다.
"""
from shopping_shorts.edit_plan import enforce_script_order, enforce_scripted_narration


GIVEN = "첫 문장입니다. 둘째 문장입니다. 셋째 문장입니다."


def _beats(*narrs):
    return [{"beat_idx": i, "narration": n, "target_seconds": 3.0}
            for i, n in enumerate(narrs)]


def test_사람이_고친_문장은_되돌려지지_않는다():
    """★신고의 핵심. 표식이 있으면 given_script에 없어도 그대로 살아남는다."""
    beats = _beats("첫 문장입니다.", "제가 직접 고친 새 문장이에요", "셋째 문장입니다.")
    beats[1]["narration_manual"] = True
    out, fixed = enforce_scripted_narration(beats, GIVEN)
    assert out[1]["narration"] == "제가 직접 고친 새 문장이에요", "사람이 고친 문장이 되돌려졌다"
    assert fixed == 0
    assert not out[1].get("narration_restored")


def test_AI_창작은_여전히_되돌린다():
    """★회귀 방지. 2026-08-18 방어 장치는 그대로 살아 있어야 한다.

    표식 없는 비트가 대본에 없는 문장을 들고 있으면 = EDL이 지어낸 것 → 되돌린다."""
    beats = _beats("첫 문장입니다.", "둥근 글씨를 정성스럽게 써 내려갑니다", "셋째 문장입니다.")
    out, fixed = enforce_scripted_narration(beats, GIVEN)
    assert fixed == 1
    assert out[1]["narration"] == "둘째 문장입니다."
    assert out[1].get("narration_restored") is True


def test_표식과_창작이_섞여도_각자_처리된다():
    """사람이 고친 칸은 지키고, 같은 계획 안의 AI 창작 칸은 되돌린다."""
    beats = _beats("첫 문장입니다.", "사람이 고친 문장", "AI가 지어낸 장면 설명 말투입니다")
    beats[1]["narration_manual"] = True
    out, fixed = enforce_scripted_narration(beats, GIVEN)
    assert out[1]["narration"] == "사람이 고친 문장"          # 지켜짐
    assert out[2]["narration"] in ("둘째 문장입니다.", "셋째 문장입니다.")  # 되돌려짐
    assert fixed == 1


def test_표식이_있어도_대본과_같으면_평소대로():
    """표식은 '되돌리지 마라'는 뜻일 뿐, 다른 동작을 바꾸지 않는다."""
    beats = _beats("첫 문장입니다.", "둘째 문장입니다.", "셋째 문장입니다.")
    beats[1]["narration_manual"] = True
    out, fixed = enforce_scripted_narration(beats, GIVEN)
    assert fixed == 0
    assert [b["narration"] for b in out] == ["첫 문장입니다.", "둘째 문장입니다.", "셋째 문장입니다."]


def test_표식_비트는_되돌릴_재료로도_소비되지_않는다():
    """★조용한 버그 방지.

    되돌림은 '아직 안 쓰인 대본 문장'을 골라 꽂는다. 표식 비트의 문장은 대본에 없으므로
    `used` 집계에서 빠지는데, 그러면 그 자리에 해당하는 대본 문장이 '안 쓰였다'고 판정돼
    **다른 창작 칸에 엉뚱하게 꽂힌다**. 표식 비트가 있어도 재료 계산이 어긋나면 안 된다."""
    beats = _beats("첫 문장입니다.", "사람이 고친 문장", "지어낸 문장")
    beats[1]["narration_manual"] = True
    out, _ = enforce_scripted_narration(beats, GIVEN)
    # 2번 칸은 되돌려지되, 1번(사람) 칸은 절대 안 건드린다
    assert out[1]["narration"] == "사람이 고친 문장"
    assert out[2]["narration"] != "사람이 고친 문장"


# ── 저장 출구의 **두 번째** 관문 (실측으로 뒤늦게 발견, 2026-08-25) ─────────────
# ★되돌림만 막았더니 여전히 안 됐다. `_ensure_screen_time`은 되돌림 **뒤에**
#   `enforce_script_order`(2026-08-24 순서 재배분)를 부르는데, 이건 given_script 문장만으로
#   **모든 칸을 다시 채운다** — 사람이 고친 문장은 대본에 없으니 통째로 덮여 사라진다.
#   실측: 되돌림 통과 후 순서배분에서 '제가 직접 고친 새 문장이에요' → '둘째 문장입니다.'
#   관문이 둘이므로 **양쪽 다** 표식을 존중해야 한다(한 곳만 고치면 증상이 그대로다).


def test_순서배분도_사람이_고친_칸을_덮지_않는다():
    """★한 곳만 고치면 증상이 그대로다 — 이 테스트가 그걸 못박는다."""
    beats = _beats("첫 문장입니다.", "제가 직접 고친 새 문장이에요", "셋째 문장입니다.")
    beats[1]["narration_manual"] = True
    out, _ = enforce_script_order(beats, GIVEN)
    assert out[1]["narration"] == "제가 직접 고친 새 문장이에요", "순서배분이 사람 수정을 덮었다"


def test_순서배분_회귀_사람표식이_없으면_평소대로():
    """2026-08-24 순서 보장은 그대로 살아 있어야 한다(표식 없는 계획은 재배분된다)."""
    beats = _beats("셋째 문장입니다.", "첫 문장입니다.", "둘째 문장입니다.")
    out, fixed = enforce_script_order(beats, GIVEN)
    assert fixed > 0
    assert out[0]["narration"] == "첫 문장입니다."


def test_두_관문을_연달아_지나도_살아남는다():
    """★신고 재현 경로 그대로 — 저장 출구는 되돌림 → 순서배분 순으로 돈다."""
    beats = _beats("첫 문장입니다.", "제가 직접 고친 새 문장이에요", "셋째 문장입니다.")
    beats[1]["narration_manual"] = True
    b1, _ = enforce_scripted_narration(beats, GIVEN)
    b2, _ = enforce_script_order(b1, GIVEN)
    assert any("직접 고친" in (b.get("narration") or "") for b in b2), \
        "두 관문을 지나며 사람이 고친 문장이 사라졌다"


def test_사람이_고친_칸_때문에_대본_문장이_사라지지_않는다():
    """★조용한 누락 방지 (실측으로 발견).

    사람이 고친 칸을 재배분에서 그냥 건너뛰면, 그 칸에 배정됐던 **대본 문장이 버려진다**.
    실측: 3칸 중 가운데를 사람이 고치니 '둘째 문장입니다.'가 통째로 사라졌다.
    enforce_script_order의 규약은 '칸보다 문장이 많아도 버리지 않는다'이므로
    사람 칸을 빼되 그 몫의 문장은 **남은 칸들이 나눠 가져야** 한다."""
    beats = _beats("셋째 문장입니다.", "사람이 고친 문장", "첫 문장입니다.")
    beats[1]["narration_manual"] = True
    out, _ = enforce_script_order(beats, GIVEN)
    joined = "".join(b.get("narration") or "" for b in out)
    for s in ("첫 문장", "둘째 문장", "셋째 문장"):
        assert s in joined, f"'{s}'이(가) 재배분에서 사라졌다"
    assert "사람이 고친 문장" in joined


def test_표식_비트의_음성은_버리지_않는다():
    """되돌리지 않으므로 _drop_stale_tts도 안 돈다 — 음성이 살아 있어야 한다.

    (저장 API가 대본을 바꿀 때 이미 cap_durs를 지우고 재합성을 예약한다. 여기서 또
     지우면 두 벌이 된다 — 0순위-B.)"""
    beats = _beats("첫 문장입니다.", "사람이 고친 문장", "셋째 문장입니다.")
    beats[1]["narration_manual"] = True
    beats[1]["tts_path"] = "/tmp/beat_1_abcdef0123.mp3"
    out, _ = enforce_scripted_narration(beats, GIVEN)
    assert out[1]["tts_path"] == "/tmp/beat_1_abcdef0123.mp3"
