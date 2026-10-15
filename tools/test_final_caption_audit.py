# -*- coding: utf-8 -*-
"""final_caption_audit 시험 — 가짜 편성표·가짜 자막 필터 파일로 도구가 **실제로 잡는지** 본다.

  ① 순수 대조: 같은 구절 → 불일치 0 / 한 글자 다름 → 글자 1 / 시작 0.3초 밀림 → 시각 1 / NBSP·공백은 같은 글자
  ② 가짜 자막 필터(렌더가 만드는 drawtext 문자열 + txt 파일) 파싱 → 글자·시각을 그대로 읽는다
  ③ 통합: 가짜 편성표(칸 2개, 음성 길이 고정)로 **진짜** app._lab_captions 와 **진짜** _caption_drawtexts 를 불러
     대조 → 일치 / 칸 하나에 cap_offset 0.3 → 렌더만 밀려 시각차가 잡힌다 / 렌더 글자 한 자 바꾸면 잡힌다
  ④ 장면꾸미기 손자막: 장면 목록 밖 키(고아)·남의 칸 문구(밀림 의심)를 잡는다
사보타주: CAP_SABOTAGE=1 이면 compare_beat 가 항상 "일치"를 돌려주게 바꾼다 → ①③의 잡기 시험이 빨강이어야 한다.
돌리기: py -m pytest tools/test_final_caption_audit.py -q      (사보타주: CAP_SABOTAGE=1 py -m pytest ...)
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import final_caption_audit as fa      # noqa: E402


@pytest.fixture(autouse=True)
def _sabotage(monkeypatch):
    if os.getenv("CAP_SABOTAGE") == "1":
        real = fa.compare_beat

        def always_same(editor, render, tol=fa.TOL):
            r = real(editor, render, tol)
            r.update(text_bad=[], time_bad=[], count_bad=False, worst=0.0)
            return r
        monkeypatch.setattr(fa, "compare_beat", always_same)
    yield


def _rows(*spec):
    return [{"text": t, "start": a, "end": b} for t, a, b in spec]


# ① 순수 대조 ───────────────────────────────────────────

def test_same_is_clean():
    e = _rows(("이거 진짜", 0.1, 1.0), ("대박이에요", 1.0, 2.2))
    c = fa.compare_beat(e, [dict(x) for x in e])
    assert not c["text_bad"] and not c["time_bad"] and not c["count_bad"]


def test_one_char_diff_caught():
    e = _rows(("이거 진짜", 0.1, 1.0), ("대박이에요", 1.0, 2.2))
    r = _rows(("이거 진짜", 0.1, 1.0), ("대박이네요", 1.0, 2.2))
    c = fa.compare_beat(e, r)
    assert len(c["text_bad"]) == 1 and c["text_bad"][0]["i"] == 1


def test_shift_03_caught():
    e = _rows(("이거 진짜", 0.1, 1.0), ("대박이에요", 1.0, 2.2))
    r = _rows(("이거 진짜", 0.4, 1.3), ("대박이에요", 1.3, 2.5))
    c = fa.compare_beat(e, r)
    assert len(c["time_bad"]) == 2
    assert c["time_bad"][0]["d_start"] == pytest.approx(0.3)


def test_small_shift_under_tol_ok_and_last_end_is_tail():
    e = _rows(("가", 0.0, 1.0), ("나", 1.0, 2.0))
    r = _rows(("가", 0.05, 1.05), ("나", 1.05, 2.9))     # 마지막 끝 +0.9 = 렌더 여운(설계) → 시각차 아님
    c = fa.compare_beat(e, r)
    assert not c["time_bad"] and c["tail_diff"] == pytest.approx(0.9)


def test_count_diff_caught():
    c = fa.compare_beat(_rows(("가", 0, 1), ("나", 1, 2)), _rows(("가나", 0, 2)))
    assert c["count_bad"]


def test_nbsp_and_space_equal():
    assert fa.norm_text("가나 다 ") == fa.norm_text("가나 다") == fa.norm_text("가나다")


# ② 가짜 자막 필터 파일 ─────────────────────────────────

def test_parse_fake_drawtext_files(tmp_path):
    (tmp_path / "txt_cap_3_0_0_0.txt").write_text("첫 구절", encoding="utf-8")
    (tmp_path / "txt_cap_3_1_0_0.txt").write_text("둘째", encoding="utf-8")
    (tmp_path / "txt_cap_3_1_0_1.txt").write_text("구절", encoding="utf-8")      # 강조로 조각난 같은 구절
    parts = [
        "drawbox=x=0:y=ih-450:w=iw:h=450:color=black@0.82:t=fill:enable='between(t,5.00,8.00)'",
        "drawtext=fontfile=font_cap_3_0.ttf:textfile=txt_cap_3_0_0_0.txt:expansion=none:fontsize=78:enable='between(t,5.10,6.00)'",
        "drawtext=fontfile=font.ttf:textfile=txt_cap_3_1_0_0.txt:expansion=none:enable='between(t,6.00,8.00)'",
        "drawtext=fontfile=font.ttf:textfile=txt_cap_3_1_0_1.txt:expansion=none:enable='between(t,6.00,8.00)'",
    ]
    got = fa.parse_drawtexts(parts, tmp_path)
    assert list(got) == [3]
    assert [r["text"] for r in got[3]] == ["첫 구절", "둘째구절"]
    assert got[3][0]["start"] == pytest.approx(5.10) and got[3][1]["end"] == pytest.approx(8.0)
    assert got[3][0]["font"] == "font_cap_3_0.ttf" and got[3][1]["font"] == "font.ttf"


# ③ 통합 — 진짜 서버 함수 ────────────────────────────────

@pytest.fixture
def fake_plan(tmp_path, monkeypatch):
    V = fa.va()
    durs = {}
    beats = []
    for i, (narr, lines, cd, dur) in enumerate([
        ("이거 진짜 대박이에요", ["이거 진짜", "대박이에요"], [0.9, 1.1], 2.3),
        ("여러분도 한번 써보세요", ["여러분도", "한번 써보세요"], [0.8, 1.3], 2.4),
    ]):
        p = tmp_path / ("beat_%d.mp3" % i)
        p.write_bytes(b"\0")
        durs[str(p)] = dur
        beats.append({"beat_idx": i, "narration": narr, "caption_lines": lines, "cap_durs": cd,
                      "cap_lead": 0.12, "tts_path": str(p), "role": "body"})
    monkeypatch.setattr(V, "_probe_duration", lambda path: durs.get(str(path), 0.0))
    return {"beats": beats}


def _audit(plan, tmp_path, tamper=None):
    job = {"job_id": "t", "edit_plan": plan, "caption_style": {}, "deco": {}, "headcopy": None}
    tl = fa.timeline_of(plan)
    ed, _ = fa.editor_captions(plan, job.get("deco"))
    ren = fa.render_captions_drawtext(job, tl, tmp_path / "w")
    if tamper:
        tamper(ren)
    out = []
    for b in tl:
        out.append(fa.compare_beat(ed.get(b["beat_idx"]) or [], fa.to_rel(ren.get(b["beat_idx"]) or [], b["t0"])))
    return out


def test_integration_real_functions_match(fake_plan, tmp_path):
    res = _audit(fake_plan, tmp_path)
    assert all(not c["text_bad"] and not c["time_bad"] and not c["count_bad"] for c in res), res
    assert [c["n_render"] for c in res] == [2, 2]


def test_integration_cap_offset_same_on_screen(fake_plan, tmp_path):
    """4단계 '자막 +0.3초'(cap_offset) — 2026-09-27부터 3단계 화면도 같은 값을 더해 보여 준다(_lab_captions 행의 off)."""
    fake_plan["beats"][1]["cap_offset"] = 0.3
    res = _audit(fake_plan, tmp_path)
    assert all(not c["time_bad"] for c in res), res


def test_editor_ignoring_offset_is_caught(fake_plan, tmp_path, monkeypatch):
    """화면이 off 를 안 더하면(2026-09-27 이전) 잡힌다 — 대조가 살아 있는지."""
    fake_plan["beats"][1]["cap_offset"] = 0.3
    real = fa.editor_captions

    def no_off(plan, deco):
        caps, td = real(plan, deco)
        return {k: [dict(r, start=r["start"] - float(r.get("off") or 0), end=r["end"] - float(r.get("off") or 0))
                    for r in rows] for k, rows in caps.items()}, td
    monkeypatch.setattr(fa, "editor_captions", no_off)
    res = _audit(fake_plan, tmp_path)
    assert len(res[1]["time_bad"]) >= 1 and res[1]["time_bad"][0]["d_start"] == pytest.approx(0.3, abs=0.01)


def test_integration_render_text_tamper_caught(fake_plan, tmp_path):
    def tamper(ren):
        ren[0][1]["text"] = "대박이네요"
    res = _audit(fake_plan, tmp_path, tamper)
    assert len(res[0]["text_bad"]) == 1


def test_capcut_schedule_equals_drawtext(fake_plan, tmp_path):
    """캡컷 시간표(caption_schedule)와 렌더 필터(_caption_drawtexts)는 같은 규칙이어야 한다."""
    job = {"job_id": "t", "edit_plan": fake_plan, "caption_style": {}, "deco": {}, "headcopy": None}
    tl = fa.timeline_of(fake_plan)
    ren = fa.render_captions_drawtext(job, tl, tmp_path / "w")
    cap = fa.capcut_schedule(tl)
    for b in tl:
        c = fa.compare_beat(fa.to_rel(cap[b["beat_idx"]], b["t0"]), fa.to_rel(ren[b["beat_idx"]], b["t0"]), tol=0.02)
        assert not c["text_bad"] and not c["time_bad"] and abs(c["tail_diff"]) <= 0.02


# ④ 장면꾸미기 손자막 ───────────────────────────────────

def test_scene_caption_override_lookup():
    snap = {"presetId": "t11", "mode": "story", "captionTexts": {"t11:story:1:caption": "고친 자막"}}
    assert fa.scene_caption_text(snap, 1, {"caption": "원래"})[:2] == ("고친 자막", True)
    assert fa.scene_caption_text(snap, 0, {"caption": "원래"})[:2] == ("원래", False)


def test_override_orphan_and_moved():
    scenes = [{"beat_idx": 0}, {"beat_idx": 1}]
    narr = {0: "이거 진짜 대박이에요", 1: "여러분도 한번 써보세요"}
    snap = {"presetId": "t11", "mode": "story", "captionTexts": {
        "t11:story:0:caption": "여러분도",        # 0번 장면(칸0)에 칸1 문구 → 밀림 의심
        "t11:story:5:caption": "아무거나",        # 장면 2개뿐 → 고아
        "t11:story:1:caption": "써보세요!!",      # 손으로 고친 글 — 어느 칸 대본에도 그대로는 없음 → 밀림 아님(고객 편집)
        "t9:story:0:caption": "다른 틀"}}         # 다른 틀 기억 — 무시
    got = fa.caption_text_overrides(snap, scenes, narr)
    assert got["n"] == 3
    assert got["orphan"] == ["t11:story:5:caption"]
    assert [m["key"] for m in got["moved"]] == ["t11:story:0:caption"]


# ⑤ 인트로 — 켰는데 붙일 그림이 없으면 잡는다 / 고른 그림이 있고 끈 경우는 조용
def test_intro_on_without_png_caught(tmp_path, monkeypatch):
    monkeypatch.setattr(fa.app_funcs(), "_THUMB_DIR", tmp_path / "thumbs")
    job = {"job_id": "j1", "video_path": str(tmp_path / "none.mp4"), "thumbnail": {"intro": True, "results": []}}
    intro, thumb = fa.intro_and_thumb(job, 10.0, tmp_path)
    assert intro["on"] and intro["png"] is None and intro["bad"]
    job["thumbnail"] = {"intro": False, "selected": "thumb_1.png", "results": ["thumb_1.png"]}
    (tmp_path / "thumbs" / "j1").mkdir(parents=True)
    (tmp_path / "thumbs" / "j1" / "thumb_1.png").write_bytes(b"x" * 2048)
    intro, thumb = fa.intro_and_thumb(job, 10.0, tmp_path)
    assert not intro["bad"] and thumb["exists"] and not thumb["bad"]
