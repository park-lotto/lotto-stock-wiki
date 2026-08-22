"""화면 조각(클립) 계획의 **단일 출처** 검증.

## 왜 이 파일이 있나 (2026-08-23 실사고)

캡컷 내보내기와 ZIP 내보내기가 `beat["primary"]` **하나만** 보고 있었다. 그런데 비트
하나에는 화면이 여러 개 붙는다(`primary` + `alternates`, 장면실험실이 편성하면
`scene_override`). 실제 렌더는 `_beat_material()`로 그 전부를 쓴다.

라이브 실측(2026-08-23 `reference.db`): 화면 조각 19개인 job이 캡컷엔 **7개**만 갔다.
→ "캡컷에서 연 것"과 "완성본"이 다른 영상이었다.

여기서 검사하는 것은 두 가지다:
  ① `plan_beat_clips_for`가 **화면 재료 전부**를 쓴다(primary만 보지 않는다)
  ② 렌더·캡컷·ZIP이 **같은 함수**를 부른다 = 결과가 어긋날 수 없다 (CLAUDE.md 0순위-B)
"""
import inspect

from shopping_shorts import video_assemble as va


def _beat(idx, prim, alts=None, **kw):
    b = {"beat_idx": idx, "primary": prim}
    if alts:
        b["alternates"] = alts
    b.update(kw)
    return b


def _seg(vid, start, end):
    return {"video_id": vid, "start": start, "end": end, "seg_id": f"{vid}:{start}"}


def test_클립계획이_primary만이_아니라_대안까지_전부_쓴다():
    """primary 1개 + alternates 2개 = 화면 재료 3개가 모두 계획에 들어가야 한다."""
    beat = _beat(0, _seg("v1", 0.0, 2.0),
                 [_seg("v2", 0.0, 2.0), _seg("v3", 0.0, 2.0)])
    src_durs = {"v1": 30.0, "v2": 30.0, "v3": 30.0}

    plan = va.plan_beat_clips_for(beat, tts_dur=6.0, src_durs=src_durs)

    used = {c["video_id"] for c in plan}
    assert used == {"v1", "v2", "v3"}, f"대안이 빠졌다: {used}"


def test_장면실험실_편성이_있으면_그것이_재료다():
    """scene_override는 사람이 편성한 결과 — primary/alternates보다 우선한다."""
    beat = _beat(0, _seg("v1", 0.0, 2.0), [_seg("v2", 0.0, 2.0)],
                 scene_override=[_seg("v9", 1.0, 3.0)])
    plan = va.plan_beat_clips_for(beat, tts_dur=2.0, src_durs={"v9": 30.0})

    assert {c["video_id"] for c in plan} == {"v9"}


def test_소스가_없거나_손상되면_그_구간은_빠진다():
    """_src_dur<=0.05(디코드 불가)면 렌더가 죽으므로 계획에서 제외한다."""
    beat = _beat(0, _seg("ok", 0.0, 2.0), [_seg("broken", 0.0, 2.0)])
    plan = va.plan_beat_clips_for(beat, tts_dur=2.0,
                                  src_durs={"ok": 30.0, "broken": 0.0})

    assert {c["video_id"] for c in plan} == {"ok"}


def test_재료가_하나도_없으면_빈_계획():
    beat = _beat(0, None)
    assert va.plan_beat_clips_for(beat, tts_dur=2.0, src_durs={}) == []


def test_클립_길이_합이_나레이션_길이와_맞는다():
    """out_dur 합 == tts_dur. 어긋나면 자막·음성과 싱크가 깨진다."""
    beat = _beat(0, _seg("v1", 0.0, 2.0), [_seg("v2", 0.0, 2.0)])
    plan = va.plan_beat_clips_for(beat, tts_dur=5.0,
                                  src_durs={"v1": 30.0, "v2": 30.0})

    assert abs(sum(c["out_dur"] for c in plan) - 5.0) < 0.05


def test_렌더가_이_함수를_쓴다():
    """★단일 출처 못박기(0순위-B).

    렌더(`_render_mix`)가 자기만의 클립 계산을 다시 하면, 내보내기를 고쳐도 둘이 또
    어긋난다. 렌더 본문이 `plan_beat_clips_for`를 부르는지 소스로 확인한다.
    """
    src = inspect.getsource(va._render_mix)
    assert "plan_beat_clips_for" in src, "렌더가 공용 함수를 안 쓴다 — 두 벌이 된다"
    assert "_plan_beat_clips(" not in src, "렌더가 아직 저수준 함수를 직접 부른다"


def test_저수준_함수를_직접_부르는_곳은_공용함수_하나뿐이다():
    """★`_plan_beat_clips(`를 부르는 곳이 늘어나면 또 두 벌이 된다.

    파일 전체에서 호출부를 세어 **1곳**(plan_beat_clips_for 안)인지 못박는다.
    새 경로가 저수준 함수를 몰래 부르기 시작하면 여기서 걸린다.
    """
    src = inspect.getsource(va)
    calls = src.count("_plan_beat_clips(") - src.count("def _plan_beat_clips(")
    assert calls == 1, f"저수준 클립 계산 호출부가 {calls}곳 — 1곳이어야 한다"
