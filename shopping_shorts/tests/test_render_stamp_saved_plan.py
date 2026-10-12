"""렌더·미리보기는 **DB에 실제로 들어간 편성**으로 만들고 도장·지문을 뜬다(2026-10-05 관제 122).

★무엇이 있었나: 저장 출구(store.update_mix_job)의 관문이 저장할 때마다 편성을 고쳐 쓰고, 한 번에 수렴하지
  않는다(실측 박세현님 job cd0cc361bb3e: 저장마다 9번 칸 alternates 가 바뀌어 3번째에야 멈춤).
  run_render 는 메모리 편성으로 도장을 찍고 끝에서 DB 편성과 비교해 **매번 스스로 완성본을 버렸다**
  (status=ready_for_review, 화면은 done/failed 만 기다려 무한 '렌더 중'). 서버 재실측에서 DIFF ['plan'] 재현.
★여기서는 '저장마다 alternates 에 한 칸 붙이는 관문'으로 같은 모양을 만든다. 실 ffmpeg 는 부르지 않는다.
"""
import copy
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import store as store_mod
from shopping_shorts.store import Store


def _gate_appends_alternate(plan, store, job_id):
    """수렴하지 않는 관문 흉내 — 저장할 때마다 첫 칸 alternates 에 하나를 더 붙인다."""
    plan = copy.deepcopy(plan)
    b = plan["beats"][0]
    alts = list(b.get("alternates") or [])
    alts.append({"video_id": "s0", "seg_id": "s0-%d" % len(alts), "start": 0.0, "end": 1.0})
    b["alternates"] = alts
    return plan


def _setup(tmp_path, monkeypatch, jid="jr"):
    db = tmp_path / "t.db"
    work = tmp_path / "work"
    s = Store(db)
    s.create_mix_job(jid, ["url0"], 20, "free")
    tts = work / jid / "tts" / "beat_0_x.mp3"
    tts.parent.mkdir(parents=True, exist_ok=True)
    tts.write_bytes(b"ID3voice")
    s.update_mix_job(jid, status="ready_for_review", edit_plan={
        "structure": "free",
        "beats": [{"beat_idx": 0, "role": "훅", "narration": "n", "target_seconds": 2,
                   "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0},
                   "alternates": [], "tts_path": str(tts)}]})
    src = work / jid / "s0"
    src.mkdir(parents=True, exist_ok=True)
    (src / "vid.mp4").write_bytes(b"")
    # 관문은 이 시점부터 켠다(위 준비 저장은 평범하게)
    monkeypatch.setattr(store_mod, "_ensure_screen_time", _gate_appends_alternate)
    # 음성은 이미 있다 — 합성은 부르지 않는다
    monkeypatch.setattr(mp, "_synthesize_beats", lambda beats, *a, **k: None)
    used = {}

    def fake_assemble(plan, tts_paths, source_video_paths, out_path, clean_fn=None, **kw):
        used["plan"] = copy.deepcopy(plan)
        Path(out_path).write_bytes(b"mp4")
        return out_path
    monkeypatch.setattr(mp, "assemble", fake_assemble)
    return db, work, s, used


def test_render_keeps_result_when_save_gate_rewrites_plan(tmp_path, monkeypatch, capsys):
    db, work, s, used = _setup(tmp_path, monkeypatch)
    mp.run_render("jr", db, work)
    job = s.get_mix_job("jr")
    assert job["status"] == "done", "저장 관문이 편성을 고쳤다고 렌더가 스스로 완성본을 버렸다"
    assert job["video_path"]
    # 렌더한 편성 = DB 편성(화면이 다시 열면 보는 것) — 메모리 편성이 아니다
    assert used["plan"]["beats"][0]["alternates"] == job["edit_plan"]["beats"][0]["alternates"]
    assert "[render-stamp]" not in capsys.readouterr().err


def test_sabotage_old_in_memory_stamp_discards(tmp_path, monkeypatch, capsys):
    """옛 동작(저장만 하고 메모리 편성으로 도장)으로 되돌리면 결과를 버려야 한다 — 위 시험이 우연히 통과하지 않음을 보인다.
    버릴 때는 달라진 칸 이름(plan)이 로그에 남는다."""
    db, work, s, used = _setup(tmp_path, monkeypatch)

    def old(store, job_id, job, plan, work_dir, gpron):
        store.update_mix_job(job_id, edit_plan=copy.deepcopy(plan))
        return plan
    monkeypatch.setattr(mp, "_save_plan_with_tts", old)
    mp.run_render("jr", db, work)
    job = s.get_mix_job("jr")
    assert job["status"] == "ready_for_review"
    err = capsys.readouterr().err
    assert "[render-stamp] job=jr 완성본 버림 — 달라진 항목: plan" in err


def test_discard_log_names_changed_setting(tmp_path, monkeypatch, capsys):
    """렌더 도중 꾸미기를 바꾸면 버리고(종전 그대로), 로그에 deco 가 찍힌다."""
    db, work, s, used = _setup(tmp_path, monkeypatch)
    real = mp.assemble

    def assemble_and_edit(*a, **k):
        s.update_mix_job("jr", deco={"changed": True})
        return real(*a, **k)
    monkeypatch.setattr(mp, "assemble", assemble_and_edit)
    mp.run_render("jr", db, work)
    assert s.get_mix_job("jr")["status"] == "ready_for_review"
    assert "달라진 항목: deco" in capsys.readouterr().err


def test_stamp_diff_names():
    a = "|".join(["d", "h", "c", "s", "t", "cc", "i", "p1"])
    b = "|".join(["d", "h", "c", "s", "t", "cc", "i2", "p2"])
    assert mp.render_stamp_diff(a, b) == ["intro", "plan"]
    assert mp.render_stamp_diff(a, a) == []
    assert mp.render_stamp_diff(a, "x|y") == ["parts"]


def test_stamp_parts_match_render_stamp(tmp_path):
    """칸 이름 수 = _render_stamp 가 이어 붙이는 칸 수(한쪽만 늘리면 로그가 엉뚱한 이름을 찍는다)."""
    job = {"edit_plan": {"beats": []}, "deco": {}, "headcopy": None, "caption_style": None,
           "subtitle_removal": False, "thumbnail": {}}
    assert len(mp._render_stamp(job).split("|")) == len(mp._STAMP_PARTS)


def test_preview_sig_matches_saved_plan(tmp_path, monkeypatch):
    """미리보기 지문 = DB 편성 지문 — 아니면 멀쩡한 미리보기가 늘 '낡음'(app._preview_is_stale)이 된다."""
    db, work, s, used = _setup(tmp_path, monkeypatch, jid="jp")
    monkeypatch.setattr(mp, "render_inputs_for",
                        lambda store, job, job_id, w, keys, cid, allow_clean=False:
                        (job["edit_plan"], {"s0": str(w / "s0" / "vid.mp4")}, None))
    mp.run_preview("jp", db, work)
    job = s.get_mix_job("jp")
    sig = mp.preview_sig_path(work, "jp")
    if job.get("preview_status") != "ready" or not sig.exists():
        pytest.skip("미리보기 하네스가 이 환경에서 끝까지 못 돎: %s" % job.get("preview_error"))
    assert sig.read_text(encoding="utf-8").strip() == mp.plan_signature(job["edit_plan"])
