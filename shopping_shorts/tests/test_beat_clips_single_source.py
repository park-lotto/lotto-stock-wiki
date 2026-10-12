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


class _Spied(Exception):
    pass


def _spy_render_cut_plan(monkeypatch):
    """render_cut_plan 을 호출 기록기로 바꾼다 — 불리면 인자를 남기고 멈춘다(영상은 안 만든다)."""
    calls = []

    def spy(edit_plan, tts_paths, source_video_paths, **kw):
        calls.append((edit_plan, tts_paths, source_video_paths, kw))
        raise _Spied()
    monkeypatch.setattr(va, "render_cut_plan", spy)
    return calls


def test_렌더·캡컷·ZIP이_완성본_컷_계획_하나를_부른다(monkeypatch, tmp_path):
    """★단일 출처 못박기(0순위-B) — **호출로** 확인한다(소스 글자 검사는 호출이 옮겨가면 거짓으로 깨지고,
    글자만 남긴 채 호출을 빼도 통과한다 — 메모리 '마크업테스트 문자열검색은 무용지물').

    컷 계획(소스 길이 표·여운·컷 프레임·전환 여유·느리게+정지·시작 당기기 + plan_beat_clips_for)은
    video_assemble.render_cut_plan 하나. 렌더(_render_mix)·캡컷(capcut_draft)·ZIP(export_bundle)이 그 함수를 부른다(2026-09-27)."""
    import pytest
    from shopping_shorts import capcut_draft as cd, export_bundle as eb
    plan = {"beats": [_beat(0, _seg("v1", 0.0, 2.0))]}
    tts, src = {0: "/x/b0.mp3"}, {"v1": "/x/v1.mp4"}
    tl = [{"beat_idx": 0, "t0": 0.0, "dur": 2.0, "role": "훅"}]

    calls = _spy_render_cut_plan(monkeypatch)
    with pytest.raises(_Spied):
        va._render_mix(plan, tts, src, tmp_path)
    assert calls and calls[-1][0] is plan, "렌더가 완성본 컷 계획(render_cut_plan)을 안 부른다 — 두 벌이 된다"

    calls.clear()
    assert cd.capcut_segments(plan, tl, src, tts, {"/x/v1.mp4": 10.0}) is None   # 계획 실패 = 경보 후 종전 조각 계획
    assert calls and calls[-1][0] is plan and calls[-1][3]["beat_durs"] == {0: 2.0}, "캡컷이 완성본 컷 계획을 안 부른다"

    calls.clear()
    monkeypatch.setattr(eb, "_cut_clip", lambda *a: False)
    eb._beat_source_clips(plan, tl, src, tmp_path / "s", src_durs={"v1": 10.0})
    assert calls and calls[-1][0] is plan, "ZIP 이 완성본 컷 계획을 안 부른다"


def test_렌더_본문은_저수준_계획을_직접_안_부른다():
    """렌더가 plan_beat_clips_for·_plan_beat_clips 를 직접 다시 부르면 render_cut_plan 과 두 벌이 된다."""
    src = inspect.getsource(va._render_mix)
    assert "plan_beat_clips_for(" not in src and "_plan_beat_clips(" not in src


def test_저수준_함수를_직접_부르는_곳은_공용함수_하나뿐이다():
    """★`_plan_beat_clips(`를 부르는 곳이 늘어나면 또 두 벌이 된다.

    파일 전체에서 호출부를 세어 **1곳**(plan_beat_clips_for 안)인지 못박는다.
    새 경로가 저수준 함수를 몰래 부르기 시작하면 여기서 걸린다.
    """
    src = inspect.getsource(va)
    calls = src.count("_plan_beat_clips(") - src.count("def _plan_beat_clips(")
    assert calls == 1, f"저수준 클립 계산 호출부가 {calls}곳 — 1곳이어야 한다"
