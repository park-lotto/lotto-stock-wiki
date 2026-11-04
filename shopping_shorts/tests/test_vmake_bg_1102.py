"""관제 304 — VMake 를 뒤에서 돌린다: 기다리지 않고 임시 흐림으로 렌더, 결과가 오면 그 구간만 교체, 늦거나 실패하면 흐림 판으로 완성.

주인: 뒤로 보내도 되나 = vmake_clean.bg_start · 받기 = vmake_clean.bg_take · 언제 받나 = flow._bg_take · 컷 지문 = render_bench.cut_src_id.
VMake 는 전부 가짜(돈 0). 실제 ffmpeg 로 조각을 자르고 끼운다. 프레임·소리 대조는 hybrid/patch_render_check.py --change vmake.
"""
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from tools.calcopy import vmake_clean as VC
from tools.calcopy.engine import final_splice as FS
from tools.calcopy.hybrid import flow as F, render_bench as RB, runner_ops as RO
from tools.calcopy.hybrid.common import md5


def _sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True, stdin=subprocess.DEVNULL, capture_output=True)


@pytest.fixture
def src(tmp_path):
    d = tmp_path / "src"
    d.mkdir()
    _sh("ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=160x120:r=30:d=6", "-f", "lavfi", "-i", "sine=f=500:d=6", "-map", "0:v", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", "-c:a", "aac", d / "a.mp4")
    return d


@pytest.fixture
def fake(monkeypatch):
    """가짜 VMake — 칸을 칠해 돌려준다. delay = 걸리는 초 · fail = 실패로 칠 조각 · error = 통째로 터짐. calls = 돈 드는 호출 수. 뒤 프로세스는 스레드로."""
    st = {"delay": 0.0, "fail": (), "error": None, "calls": 0, "threads": []}

    def member_clean(files, key, log=print, tier=VC.TIER):
        st["calls"] += 1
        time.sleep(st["delay"])
        if st["error"]:
            raise st["error"]
        out = {"cleaned": [], "calls": 1, "fail": {}}
        for f in map(Path, files):
            if any(x in f.name for x in st["fail"]):
                out["fail"][f.name] = "크레딧 부족"
                continue
            t = f.with_name(f.stem + "_v" + f.suffix)
            _sh("ffmpeg", "-y", "-v", "error", "-i", f, "-vf", "drawbox=x=0:y=0:w=80:h=60:c=red:t=fill", "-c:v", "libx264", "-preset", "ultrafast", "-threads", "1", "-pix_fmt", "yuv420p", t)
            VC.swap_in(f, t)
            VC.log_entry(f.parent, {"file": f.name, "mode": "member", "ok": True, "calls": 1, **VC._sent(f)})
            out["cleaned"].append(f.name)
        return out

    def spawn(d):
        t = threading.Thread(target=VC.bg_run, args=(d,), daemon=True)
        st["threads"].append(t)
        t.start()
        return 1

    monkeypatch.setattr(VC, "member_clean", member_clean)
    monkeypatch.setattr(VC, "_spawn_bg", spawn)
    monkeypatch.setattr(VC, "member_key", lambda: "k:s")
    monkeypatch.setattr(VC, "key_source", lambda: "member")
    monkeypatch.setattr(VC, "free_ok", lambda: False)
    monkeypatch.delenv("SHORTEM_NO_PAID", raising=False)
    monkeypatch.delenv("SHORTEM_ERASE_ENGINE", raising=False)
    return st


def _frames(f):
    return FS.keyframes(f)[1]


def test_start_does_not_wait_and_source_stays_until_taken(src, fake):
    fake["delay"] = 1.0
    f = src / "a.mp4"
    before = md5(f)
    t0 = time.time()
    j = VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    assert j["mode"] == "bg" and time.time() - t0 < 0.8                # VMake 1초를 기다리지 않는다
    assert VC.bg_take(src, 0)["state"] == "running" and md5(f) == before  # 도는 동안 원본 그대로(렌더가 읽는 중일 수 있다)
    r = VC.bg_take(src, 20)
    assert r["state"] == "done" and r["done"] == {"a.mp4": [[1.0, 2.0]]} and r["calls"] == 1
    assert md5(f) != before and (src / "a_orig.mp4").exists()
    assert _frames(f) == 180 and abs(VC._dur(f) - 6.0) < 0.05          # 같은 이름·같은 길이
    assert not (src / VC.BG_DIR).exists()


def test_ledger_counts_the_call_in_source_folder(src, fake):
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    assert VC.bg_take(src, 20)["state"] == "done"
    assert VC.sent_from_ledger(src) == {"a.mp4": pytest.approx(1.0, abs=0.1)}


def test_failure_keeps_source_untouched(src, fake):
    fake["error"] = RuntimeError("서버 오류")
    f = src / "a.mp4"
    before = md5(f)
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    r = VC.bg_take(src, 20)
    assert r["state"] == "done" and r["error"] and r["done"] == {} and md5(f) == before and not (src / "a_orig.mp4").exists()
    assert fake["calls"] == 1                    # 다시 보내지 않는다


def test_partial_failure_splices_only_cleaned_span(src, fake, monkeypatch):
    monkeypatch.setattr(VC, "send_joined", lambda files, send, log=print: send(files))      # 조각마다 보내는 길(크기가 다른 원본) — 합본 길은 묶음째 성공·실패다
    fake["fail"] = ("4.00_5.00",)
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0], [4.0, 5.0]]}, "vmake")
    r = VC.bg_take(src, 20)
    assert r["done"]["a.mp4"] == [[1.0, 2.0]] and "크레딧" in r["why"]
    assert fake["calls"] == 1


def test_late_is_late(src, fake):
    fake["delay"] = 30
    d = src / VC.BG_DIR
    d.mkdir()
    (d / "job.json").write_text(json.dumps({"src": str(src), "spans": {}, "rd": {}, "at": time.time() - VC.BG_MAX - 1}), encoding="utf-8")
    assert VC.bg_take(src, 0)["state"] == "late"


def test_second_start_refused_while_running(src, fake):
    fake["delay"] = 1.0
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    with pytest.raises(RuntimeError, match="이미"):
        VC.bg_start(src, {"a.mp4": [[3.0, 4.0]]})
    assert fake["calls"] <= 1
    VC.bg_take(src, 20)


@pytest.mark.parametrize("case", ["no_spans", "no_key", "blur", "free"])
def test_blocking_way_when_background_does_not_apply(src, fake, monkeypatch, case):
    spans = {"a.mp4": [[1.0, 2.0]]}
    if case == "no_spans":
        spans = {}
    elif case == "no_key":
        monkeypatch.setattr(VC, "member_key", lambda: "")
    elif case == "free":
        monkeypatch.setattr(VC, "erase_engine", lambda: "free")
    assert VC.bg_start(src, spans, "blur" if case == "blur" else "vmake") is None
    assert fake["calls"] == 0


def _a(ss, n=30):
    return {"ss": ss, "crop": [0, 0, 160, 120], "win": (160, 120), "push": 0.0, "move": None, "blur": None, "pic": None, "pic_bg": None, "speed": 1.0, "n": n}


def test_fingerprint_changes_only_inside_spliced_span(src, fake, monkeypatch):
    monkeypatch.setattr(RB, "_code_sig", lambda kind: "c")
    f = src / "a.mp4"
    a_in, a_out = RB.cut_fp(f, _a(1.2), 30), RB.cut_fp(f, _a(4.0), 30)
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    VC.bg_take(src, 20)
    assert RB.cut_fp(f, _a(1.2), 30) != a_in      # 지운 구간의 컷 = 다시 굽는다
    assert RB.cut_fp(f, _a(4.0), 30) == a_out     # 구간 밖 컷 = 그대로 — 옛 코드는 파일 mtime 이 바뀌어 이 파일의 컷이 전부 다시 구워졌다


def test_fingerprint_distrusts_stale_tag(src, fake, monkeypatch):
    monkeypatch.setattr(RB, "_code_sig", lambda kind: "c")
    f = src / "a.mp4"
    VC.bg_start(src, {"a.mp4": [[1.0, 2.0]]})
    VC.bg_take(src, 20)
    a = RB.cut_fp(f, _a(4.0), 30)
    f.write_bytes(f.read_bytes() + b"x")          # 다른 파일로 바뀌면 표식을 믿지 않는다
    assert RB.cut_fp(f, _a(4.0), 30) != a


def test_second_splice_keeps_base(src, fake, monkeypatch):
    monkeypatch.setattr(RB, "_code_sig", lambda kind: "c")
    f = src / "a.mp4"
    a_out = RB.cut_fp(f, _a(4.5), 15)
    for span in ([1.0, 2.0], [2.5, 3.5]):
        VC.bg_start(src, {"a.mp4": [span]})
        VC.bg_take(src, 20)
    assert RB.cut_fp(f, _a(4.5), 15) == a_out


def test_runner_starts_background_and_takes(src, fake, monkeypatch, tmp_path):
    W = tmp_path
    (W / "doc" / "v").mkdir(parents=True)
    (W / "doc" / "v" / "재료.json").write_text(json.dumps({"cand_dir": str(src)}), encoding="utf-8")
    fake["delay"] = 0.5
    monkeypatch.setattr(VC, "plan_spans", lambda doc, shots=None, done=None, style_name=None: (src, {"a.mp4": [[1.0, 2.0]]}, {"a.mp4": [[0.0, 3.0]]}))
    monkeypatch.setattr(VC, "style_mode", lambda v: "vmake")
    monkeypatch.setattr(RO, "PAID_OFF", False)
    monkeypatch.setattr(RO, "progress", lambda *a, **k: None)
    r = RO.c_clean_text(W, {"version": "v", "bg": True})
    assert r["mode"] == "bg" and r["send_sec"] == 1.0
    assert RO.c_clean_take(W, {"version": "v", "wait": 0})["state"] == "running"
    r = RO.c_clean_take(W, {"version": "v", "wait": 20})
    assert r["state"] == "done" and r["done"] == {"a.mp4": [[1.0, 2.0]]} and r["sent_bad"] == []


def test_runner_without_bg_flag_waits_as_before(src, fake, monkeypatch, tmp_path):
    (tmp_path / "doc" / "v").mkdir(parents=True)
    monkeypatch.setattr(VC, "plan_spans", lambda doc, shots=None, done=None, style_name=None: (src, {"a.mp4": [[1.0, 2.0]]}, {"a.mp4": [[0.0, 3.0]]}))
    monkeypatch.setattr(VC, "style_mode", lambda v: "vmake")
    monkeypatch.setattr(RO, "PAID_OFF", False)
    monkeypatch.setattr(RO, "progress", lambda *a, **k: None)
    r = RO.c_clean_text(tmp_path, {"version": "v"})
    assert r["mode"] == "vmake" and r["done"] == {"a.mp4": [[1.0, 2.0]]} and (src / "a_orig.mp4").exists()


# ── 지시서 순서 ─────────────────────────────────────────────────────────────
def _st(**tf):
    return {"version": "v", "log": [], "tries": {}, "script": {"S": {"lines": []}, "M": {"cuts": {"L1": []}, "blur": {"a.mp4": [[1, 2, 3, 4, 0.0, 9.0]]}}},
            "text_fix": {"mode": "vmake", "done": {}, "calls": 0, "sec": 0.0, **tf}}


def test_render_asks_background_and_old_answer_still_works():
    st = _st()
    d = F.f_render(st, {}, {}, {})["do"][0]
    assert d["cmd"] == "clean_text" and d["bg"] is True
    r = F.f_render_clean_got(st, {"clean": {"mode": "bg", "send_sec": 3.0}}, {}, {})
    assert r == {"goto": "render"} and st["text_fix"]["bg"] and st["text_fix"]["key"] == F._cuts_key(st)
    st2 = _st()              # 옛 실행기 = bg 를 몰라 끝까지 기다린 답 → 옛 길 그대로
    r2 = F.f_render_clean_got(st2, {"clean": {"mode": "vmake", "done": {"a.mp4": [[1.0, 2.0]]}, "calls": 2, "send_sec": 1.0}}, {}, {})
    assert r2["do"][0]["cmd"] == "write_doc" and not st2["text_fix"].get("bg")


def test_after_render_takes_without_waiting(monkeypatch):
    monkeypatch.setattr(F, "_redo_done", lambda st: None)
    monkeypatch.setattr(F, "_style", lambda v: {"voice": {}})
    st = _st(bg=True)
    r = F.ph_render_got(st, {"render": {"ok": True}}, {}, {})
    assert r["do"][0]["cmd"] == "clean_take" and r["do"][0]["wait"] == 0 and r["then"] == "f_bg_got"


def test_not_finished_goes_on_to_check():
    st = _st(bg=True)
    F._bg_take(st, 0, "check")
    assert F.f_bg_got(st, {"bg": {"state": "running"}}, {}, {}) == {"goto": "check"}
    assert st["text_fix"]["bg"]                  # 끝난 게 아니다 — 완성 직전에 다시 본다


def test_arrived_goes_to_render_with_blur_removed():
    st = _st(bg=True)
    F._bg_take(st, 0, "check")
    r = F.f_bg_got(st, {"bg": {"state": "done", "done": {"a.mp4": [[0.0, 9.0]]}, "calls": 1, "sec": 9.0, "sent": {}}}, {}, {})
    assert r["do"][0]["cmd"] == "write_doc" and r["then"] == "render"
    assert not st["text_fix"].get("bg") and st["script"]["M"]["blur"]["a.mp4"] == [] and st["text_fix"]["calls"] == 1 and st["text_fix"]["done"] == {"a.mp4": [[0.0, 9.0]]}


def test_before_delivery_waits_for_paid_job_then_finishes_with_blur():
    # 11-04 강병주 #5656: 완성 직전 120초만 기다려 이미 과금된 VMake 15조각(조각당 수 분)을 버리고 흐림 판으로 완성했다
    #   → 완성 직전에도 BG_WAIT(실행기 예산 안)까지 기다린다. 그래도 안 오면 흐림 판(아래 단언 그대로)
    st = _st(bg=True)
    r = F.ph_deliver(st, {}, {}, {})
    assert r["do"][0]["cmd"] == "clean_take" and r["do"][0]["wait"] == F.BG_WAIT >= 1200
    r = F.f_bg_got(st, {"bg": {"state": "running"}}, {}, {})
    assert r == {"goto": "deliver"} and not st["text_fix"].get("bg") and "흐림" in st["notice"]
    assert st["script"]["M"]["blur"]["a.mp4"]    # 흐림 칸 그대로


@pytest.mark.parametrize("c", [{"state": "done", "error": "x", "done": {}}, {"state": "late", "done": {}}, {"state": "none", "done": {}}])
def test_failure_keeps_blur_and_never_resends(c, monkeypatch):
    monkeypatch.setattr(F, "ph_render", lambda st, m, rp, u: {"do": [{"cmd": "render"}]})
    st = _st(bg=True, key="k")
    F._bg_take(st, 0, "check")
    r = F.f_bg_got(st, {"bg": c}, {}, {})
    assert r == {"goto": "check"} and "흐림" in st["notice"] and st["text_fix"]["key"] == "k"
    d = st["text_fix"]
    d["key"] = F._cuts_key(st)                   # 컷이 그대로면 render 는 다시 보내지 않는다
    assert F.f_render(st, {}, {}, {})["do"][0]["cmd"] == "render"


def test_new_cuts_wait_for_running_job_first():
    st = _st(bg=True, key="옛 컷")
    r = F.f_render(st, {}, {}, {})
    assert r["do"][0]["cmd"] == "clean_take" and r["do"][0]["wait"] == F.BG_WAIT
    st2 = _st(bg=True, key="옛 컷")
    F._bg_take(st2, F.BG_WAIT, "render")
    F.f_bg_got(st2, {"bg": {"state": "done", "done": {"a.mp4": [[0.0, 1.0]]}, "calls": 1, "sec": 1.0}}, {}, {})
    d = F.f_render(st2, {}, {}, {})["do"][0]     # 받은 뒤 남은 구간만 — 지운 구간은 done 으로 빠진다
    assert d["cmd"] == "clean_text" and d["done"] == {"a.mp4": [[0.0, 1.0]]}


def test_gate_stuck_on_blur_waits_instead_of_asking_to_fix(monkeypatch):
    monkeypatch.setattr(F, "_redo_done", lambda st: None)
    st = _st(bg=True, key="k")
    r = F.ph_render_got(st, {"render": {"ok": False, "error": "흐림이 화면의 40%", "gate": [["흐림 면적", "x"]]}}, {}, {})
    assert r["do"][0]["cmd"] == "clean_take" and r["do"][0]["wait"] == F.BG_WAIT
