"""약한 비트의 **화면 재선택**(_repick_weak_beats) — 2026-08-14 사장님
"조각이 많이 나온다고 좋다는 게 아니고 필요한 걸 못 가져오는 게 문제야 / 좋은 장면을
가져오는 것에 집중해".

실측 근거(job 74d3f7a29620, 인스타 릴스 4소스): "찍히는 즉시 결과 나온다니 바로 저장"
멘트에 s1-13(촬영 모드 전환 버튼)이 fit=2로 붙었는데, 정작 s3-4(촬영 직후 결과 데이터가
뜨는 화면)는 한 번도 안 쓰였다. 미사용 장면 13개(s2 소스는 통째로 0컷).

뿌리: 약한 비트 구제 수단이 _reconcile_weak_beats 하나뿐이고, 그건 **대사를 화면에
맞춰 고친다** — 방향이 반대라 더 맞는 화면을 찾는 경로가 아예 없었다.
"""
from shopping_shorts import edit_plan


def _seg_map():
    def s(sid, desc, text=""):
        return {"video_id": sid.split("-")[0], "seg_id": sid, "start": 0.0, "end": 2.0,
                "text": text, "scene_desc": desc, "change": "", "is_key": False,
                "shot_role": "기타"}
    return {"s1-13": s("s1-13", "촬영 모드 전환 버튼을 누른다"),
            "s3-4": s("s3-4", "촬영 직후 카메라 화면에 결과 데이터가 뜬다"),
            "s2-0": s("s2-0", "제품 상자를 든 손")}


def _beat(idx, narration, sid, fit=5, **kw):
    b = {"beat_idx": idx, "narration": narration, "fit": fit,
         "primary": {"seg_id": sid, "video_id": sid.split("-")[0], "start": 0.0, "end": 2.0,
                     "scene_desc": _seg_map()[sid]["scene_desc"]},
         "alternates": []}
    b.update(kw)
    return b


def test_weak_beat_gets_better_screen():
    """fit<=3이면 인벤토리 전체에서 다시 골라 primary를 갈아끼운다."""
    beats = [_beat(0, "찍히는 즉시 결과 나온다니 바로 저장", "s1-13", fit=2)]
    out = edit_plan._repick_weak_beats(
        beats, _seg_map(),
        call=lambda p, s: {"picks": [{"beat_idx": 0, "seg_id": "s3-4", "fit": 5}]})
    assert out[0]["primary"]["seg_id"] == "s3-4"
    assert out[0]["fit"] == 5
    assert out[0]["repicked"] is True
    assert out[0].get("forced") is False


def test_forced_beat_is_target_even_when_fit_high():
    """모델이 fit=4를 주면서 forced=True로 '억지'라고 인정한 비트도 대상(재작성 규칙과 동일)."""
    seen = {}
    beats = [_beat(0, "결과가 바로 뜬다", "s1-13", fit=4, forced=True)]
    edit_plan._repick_weak_beats(beats, _seg_map(),
                                 call=lambda p, s: seen.setdefault("p", p) and None)
    assert "결과가 바로 뜬다" in seen["p"]


def test_no_weak_beat_means_no_call():
    """대상 0개면 Gemini를 아예 안 부른다(과금 0·회귀 0)."""
    called = []
    beats = [_beat(0, "멀쩡한 비트", "s1-13", fit=5)]
    out = edit_plan._repick_weak_beats(beats, _seg_map(),
                                       call=lambda p, s: called.append(1))
    assert called == [] and out == beats


def test_respined_beat_excluded():
    """시간순 스파인 b-roll(respined)은 의미매칭을 일부러 포기한 배치라 대상 아님."""
    called = []
    beats = [_beat(0, "b롤", "s1-13", fit=2, respined=True)]
    edit_plan._repick_weak_beats(beats, _seg_map(), call=lambda p, s: called.append(1))
    assert called == []


def test_low_fit_pick_rejected():
    """새로 고른 화면의 fit이 낮으면(<4) 갈아끼우지 않는다 — 억지 교체 금지."""
    beats = [_beat(0, "대사", "s1-13", fit=2)]
    out = edit_plan._repick_weak_beats(
        beats, _seg_map(),
        call=lambda p, s: {"picks": [{"beat_idx": 0, "seg_id": "s3-4", "fit": 3}]})
    assert out[0]["primary"]["seg_id"] == "s1-13"


def test_unknown_seg_id_ignored():
    """환각 seg_id는 무시(그라운딩 원칙)."""
    beats = [_beat(0, "대사", "s1-13", fit=2)]
    out = edit_plan._repick_weak_beats(
        beats, _seg_map(),
        call=lambda p, s: {"picks": [{"beat_idx": 0, "seg_id": "없는거", "fit": 5}]})
    assert out[0]["primary"]["seg_id"] == "s1-13"


def test_call_failure_keeps_beats():
    """호출 실패는 원본 유지(fail-open)."""
    beats = [_beat(0, "대사", "s1-13", fit=2)]
    assert edit_plan._repick_weak_beats(beats, _seg_map(), call=lambda p, s: None) == beats


def test_other_beat_primary_not_offered():
    """다른 비트가 쓰는 화면은 후보에서 빠진다(중복 컷 방지)."""
    seen = {}
    beats = [_beat(0, "약한 비트", "s1-13", fit=2), _beat(1, "멀쩡", "s2-0", fit=5)]
    edit_plan._repick_weak_beats(beats, _seg_map(),
                                 call=lambda p, s: seen.setdefault("p", p) and None)
    body = seen["p"].split("[후보 화면]")[1]
    assert "[s3-4]" in body and "[s2-0]" not in body


def test_two_weak_beats_cannot_take_same_seg():
    """서로 다른 약한 비트가 같은 화면을 집으면 뒤엣것은 버린다."""
    beats = [_beat(0, "A", "s1-13", fit=2), _beat(1, "B", "s2-0", fit=2)]
    out = edit_plan._repick_weak_beats(
        beats, _seg_map(),
        call=lambda p, s: {"picks": [{"beat_idx": 0, "seg_id": "s3-4", "fit": 5},
                                     {"beat_idx": 1, "seg_id": "s3-4", "fit": 5}]})
    assert out[0]["primary"]["seg_id"] == "s3-4"
    assert out[1]["primary"]["seg_id"] == "s2-0"


def test_new_primary_removed_from_alternates():
    """새 primary가 여분에 남아 라운드로빈으로 두 번 나오지 않게 뺀다."""
    beats = [_beat(0, "대사", "s1-13", fit=2)]
    beats[0]["alternates"] = [{"seg_id": "s3-4"}, {"seg_id": "s2-0"}]
    out = edit_plan._repick_weak_beats(
        beats, _seg_map(),
        call=lambda p, s: {"picks": [{"beat_idx": 0, "seg_id": "s3-4", "fit": 5}]})
    assert [a["seg_id"] for a in out[0]["alternates"]] == ["s2-0"]
