"""미리보기 지문(plan_signature)·완성본 도장(_render_stamp)이 칸 내용 전체를 본다(2026-09-27).

★무엇이 있었나: plan_signature 가 narration·seg_ids·cutaway·seconds 만 넣었는데 seg_ids·seconds 를
  채우는 코드가 없어(실측 3,032칸 전부 0) 사실상 대사·cutaway 만 봤다 → 장면·손 컷·확대·자막 줄·음성을
  바꿔도 _preview_is_stale 이 "낡음"을 못 잡았다. _render_stamp 는 등급·고른 장면·썸네일 인트로·편성을
  안 봐서, 렌더 도중 그걸 바꿔도 옛 결과물이 완성본으로 박혔다.
★과금 서명(_plan_signature/_clean_sig)은 건드리지 않는다 — 여기 테스트 대상이 아니다.

실 ffmpeg 는 부르지 않는다(assemble 가짜화 — test_mix_preview_pipeline 과 같은 방식).
"""
import copy
import os
import pathlib

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import screen_clips
from shopping_shorts.store import Store


def _plan(tmp_path):
    tts = tmp_path / "beat_0_abc.mp3"
    tts.write_bytes(b"voice-1")
    return {"beats": [
        {"beat_idx": 0, "narration": "첫 줄", "role": "훅",
         "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
         "manual_cuts": [{"video_id": "s0", "start": 0.0, "end": 1.0}],
         "scene_zoom": None, "caption_lines": ["첫 줄"], "cutaway": "",
         "tts_path": str(tts), "fit": 0.8},
        {"beat_idx": 1, "narration": "둘째 줄", "role": "본문",
         "primary": {"video_id": "s1", "seg_id": "s1-0", "start": 3.0, "end": 5.0},
         "caption_lines": ["둘째 줄"], "cutaway": ""},
    ]}


# ── (a) 미리보기 지문 ─────────────────────────────────────────────────────────────

def test_same_plan_same_sig(tmp_path):
    p = _plan(tmp_path)
    assert mp.plan_signature(p) == mp.plan_signature(copy.deepcopy(p))


@pytest.mark.parametrize("label,edit", [
    ("장면(primary)", lambda b: b[0]["primary"].update(seg_id="s0-3", start=7.0, end=9.0)),
    ("손 컷(manual_cuts)", lambda b: b[0].update(manual_cuts=[{"video_id": "s0", "start": 0.5, "end": 1.5}])),
    ("확대(scene_zoom)", lambda b: b[0].update(scene_zoom={"x": 0.5, "y": 0.5, "z": 1.4})),
    ("자막 줄(caption_lines)", lambda b: b[0].update(caption_lines=["첫", "줄"])),
    ("cutaway", lambda b: b[1].update(cutaway="c1")),
    ("칸 순서", lambda b: b.reverse()),
])
def test_scene_level_edit_changes_sig(tmp_path, label, edit):
    p = _plan(tmp_path)
    before = mp.plan_signature(p)
    q = copy.deepcopy(p)
    edit(q["beats"])
    assert mp.plan_signature(q) != before, f"{label}만 바꿨는데 지문이 같다 — 미리보기가 낡음을 못 잡는다"


def test_voice_file_resynth_changes_sig(tmp_path):
    """같은 이름으로 음성을 다시 합성해도(내용·크기·수정시각 변화) 지문이 바뀐다."""
    p = _plan(tmp_path)
    before = mp.plan_signature(p)
    tts = pathlib.Path(p["beats"][0]["tts_path"])
    tts.write_bytes(b"voice-2-longer")
    st = tts.stat()
    os.utime(tts, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert mp.plan_signature(p) != before


def test_voice_mtime_only_changes_sig(tmp_path):
    p = _plan(tmp_path)
    before = mp.plan_signature(p)
    tts = pathlib.Path(p["beats"][0]["tts_path"])
    st = tts.stat()
    os.utime(tts, ns=(st.st_atime_ns, st.st_mtime_ns + 5_000_000_000))
    assert mp.plan_signature(p) != before


def test_volatile_fields_do_not_change_sig(tmp_path):
    """휘발 필드(fit·scene_desc·screen_clips·`_` 접두)는 그림과 무관 — 지문 그대로(멀쩡한 미리보기 보존)."""
    p = _plan(tmp_path)
    before = mp.plan_signature(p)
    q = copy.deepcopy(p)
    q["beats"][0].update(fit=0.1, scene_desc="x", screen_clips=[{"a": 1}], _tmp=3)
    assert mp.plan_signature(q) == before


def test_empty_and_none(tmp_path):
    assert mp.plan_signature(None) == mp.plan_signature({}) == mp.plan_signature({"beats": []})


# ── (c) 사보타주: 지문이 정말 beat_key 에 기대는가 ─────────────────────────────────

def test_sabotage_without_beat_key_scene_change_is_missed(tmp_path, monkeypatch):
    """beat_key 를 대사만 보는 옛 방식으로 바꾸면 장면 변경을 못 잡아야 한다 — 이 테스트가 없으면
    위 파라미터 테스트가 beat_key 가 아닌 우연한 이유로 통과하는지 알 수 없다."""
    p = _plan(tmp_path)
    monkeypatch.setattr(screen_clips, "beat_key", lambda b: (b or {}).get("narration"))
    before = mp.plan_signature(p)
    q = copy.deepcopy(p)
    q["beats"][0]["primary"].update(seg_id="s0-3", start=7.0, end=9.0)
    assert mp.plan_signature(q) == before, "beat_key 를 빼도 장면 변경이 잡힌다 — 지문이 beat_key 를 안 쓴다"


# ── (b) 완성본 도장 ─────────────────────────────────────────────────────────────

def _job(tmp_path):
    return {"edit_plan": _plan(tmp_path), "deco": {"t": 1}, "headcopy": {"text": "h"},
            "caption_style": {"c": 1}, "subtitle_removal": True,
            "clean_tier": "basic", "clean_cuts": None,
            "thumbnail": {"intro": False, "results": ["a.png", "b.png"], "selected": "a.png"},
            "seo": {"title": "s"}}


def test_stamp_same_when_nothing_changes(tmp_path):
    j = _job(tmp_path)
    assert mp._render_stamp(j) == mp._render_stamp(copy.deepcopy(j))


@pytest.mark.parametrize("label,patch", [
    ("등급", {"clean_tier": "pro"}),
    ("고른 장면", {"clean_cuts": ["0|s0|0.00"]}),
    ("인트로 켬", {"thumbnail": {"intro": True, "results": ["a.png", "b.png"], "selected": "a.png"}}),
])
def test_stamp_catches(tmp_path, label, patch):
    j = _job(tmp_path)
    assert mp._render_stamp(dict(j, **patch)) != mp._render_stamp(j), f"{label} 변경을 도장이 못 잡는다"


def test_stamp_intro_selection_and_length(tmp_path):
    on = dict(_job(tmp_path), thumbnail={"intro": True, "results": ["a.png", "b.png"], "selected": "a.png"})
    other = dict(on, thumbnail={"intro": True, "results": ["a.png", "b.png"], "selected": "b.png"})
    longer = dict(on, thumbnail={"intro": True, "results": ["a.png", "b.png"], "selected": "a.png",
                                 "intro_sec": 2.0})
    assert mp._render_stamp(other) != mp._render_stamp(on)
    assert mp._render_stamp(longer) != mp._render_stamp(on)


def test_stamp_catches_plan_change(tmp_path):
    j = _job(tmp_path)
    q = copy.deepcopy(j)
    q["edit_plan"]["beats"][0]["primary"]["seg_id"] = "s0-9"
    assert mp._render_stamp(q) != mp._render_stamp(j)


def test_stamp_ignores_non_video_changes(tmp_path):
    """영상이 안 바뀌는 것 — SEO·인트로 꺼진 채 고른 썸네일·등급 None↔basic·고른 장면 None↔[] — 은 그대로."""
    j = _job(tmp_path)
    base = mp._render_stamp(j)
    assert mp._render_stamp(dict(j, seo={"title": "다른"})) == base
    assert mp._render_stamp(dict(j, thumbnail={"intro": False, "results": ["b.png"], "selected": "b.png"})) == base
    assert mp._render_stamp(dict(j, clean_tier=None)) == base
    assert mp._render_stamp(dict(j, clean_cuts=[])) == base


# ── 흐름: 렌더·미리보기가 스스로 도장/지문을 깨지 않는다 + 렌더 중 편성 변경은 버린다 ──────────

@pytest.fixture
def rjob(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.create_mix_job("J1", ["https://x/1"], 20, "template")
    work = tmp_path / "work"
    tts_dir = work / "J1" / "tts"
    tts_dir.mkdir(parents=True, exist_ok=True)
    beat = {"beat_idx": 0, "narration": "비트", "primary": {"video_id": "v1", "start": 0, "end": 2}}
    beat["tts_path"] = mp._beat_tts_path(tts_dir, beat)
    open(beat["tts_path"], "w").write("m")
    store.update_mix_job("J1", edit_plan={"beats": [beat]}, status="ready_for_review")
    monkeypatch.setattr(mp, "_resolve_sources", lambda job, w: {"v1": str(tmp_path / "v1.mp4")})
    return db, str(work), store


def _fake_assemble(on_call=None):
    def f(plan, tts, srcs, out, clean_fn=None, **kw):
        if on_call:
            on_call()
        pathlib.Path(out).write_bytes(b"x")
        return out
    return f


def test_render_untouched_stays_done(rjob, monkeypatch):
    db, work, store = rjob
    monkeypatch.setattr(mp, "assemble", _fake_assemble())
    mp.run_render("J1", db, work)
    j = store.get_mix_job("J1")
    assert j["status"] == "done" and j["video_path"], j.get("error")


@pytest.mark.parametrize("label,mutate", [
    ("편성(장면)", lambda s: s.update_mix_job(
        "J1", edit_plan={"beats": [dict(s.get_mix_job("J1")["edit_plan"]["beats"][0],
                                        primary={"video_id": "v1", "start": 4, "end": 6})]})),
    ("등급", lambda s: s.update_mix_job("J1", clean_tier="pro")),
    ("썸네일 인트로", lambda s: s.update_mix_job("J1", thumbnail={"intro": True, "results": ["a.png"]})),
])
def test_render_discards_when_changed_mid_render(rjob, monkeypatch, label, mutate):
    db, work, store = rjob
    monkeypatch.setattr(mp, "assemble", _fake_assemble(lambda: mutate(store)))
    monkeypatch.setattr(mp, "prepend_still", lambda *a, **k: False)
    mp.run_render("J1", db, work)
    j = store.get_mix_job("J1")
    assert j["status"] == "ready_for_review" and not j["video_path"], \
        f"렌더 중 {label}을 바꿨는데 옛 결과물이 완성본으로 박혔다: {j['status']}"


def test_preview_sig_matches_db_then_goes_stale_on_scene_change(rjob, monkeypatch):
    db, work, store = rjob
    monkeypatch.setattr(mp, "assemble", _fake_assemble())
    mp.run_preview("J1", db, work)
    j = store.get_mix_job("J1")
    assert j["preview_status"] == "ready", j.get("preview_error")
    sig = mp.preview_sig_path(work, "J1").read_text(encoding="utf-8").strip()
    assert sig == mp.plan_signature(j["edit_plan"]), "막 구운 미리보기가 스스로 낡음으로 보인다"
    plan = j["edit_plan"]
    plan["beats"][0]["primary"] = {"video_id": "v1", "start": 4, "end": 6}
    store.update_mix_job("J1", edit_plan=plan)
    assert sig != mp.plan_signature(store.get_mix_job("J1")["edit_plan"]), "장면을 바꿨는데 미리보기가 낡음이 아니다"


def test_int_float_same_value_same_sig(tmp_path):
    """화면(JS)이 3.0 을 3 으로 돌려 저장해도 같은 편성이다 — 멀쩡한 미리보기를 낡음으로 만들지 않는다."""
    p = _plan(tmp_path)
    q = copy.deepcopy(p)
    q["beats"][1]["primary"].update(start=3, end=5)
    assert mp.plan_signature(q) == mp.plan_signature(p)
    q["beats"][1]["primary"].update(start=3.5)
    assert mp.plan_signature(q) != mp.plan_signature(p)
