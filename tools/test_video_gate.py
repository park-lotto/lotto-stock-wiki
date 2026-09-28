"""영상 관문(video_gate.py) + finish 연결 테스트.

핵심: ① '다른 장면'이 있으면 **반드시** 실패 ② 요약을 못 읽으면 통과가 아니라 실패
③ 서버에 못 붙거나 디스크가 모자라면 조용히 넘기지 않고 실패 ④ 영상 관문이 실패하면 main 에 아무것도 안 나간다.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import track
import video_gate as vg
from test_track import repo, _Gate, _git, _head, _make_track_commit, _origin_head  # noqa: F401 (fixture)

CFG = vg.load_config()

# 서버 실측 report(2026-09-27 /tmp/evf/report.txt) 모양 그대로
_HEAD = ("판정: 가운데 띠(10~70%) 5x5 z거리 >= 0.55 = 다른 장면 / 밀림 >= 0.15s (찾는 범위 ±0.6s)\n"
         "표기: 칸번호(*=청소본 칸) · ...\n")
_JOB_OK = ("62ed6bf66eb9 칸10(청소본 10) 화면40.03s 완성본40.02s 음성40.01s | 다른장면 [] | 밀림0.15+ "
           "[('0*', 0.2, [('0', 0.01, 0.0)])] | 경계밀림 [] | 정지컷밀림 [] | 최대거리 0.33 | 54s(굽기12 렌더38 비교4)\n")
_JOB_BAD = ("7bbb00000001 칸8(청소본 0) 화면30.00s 완성본30.00s 음성30.00s | 다른장면 [('3', 0.91, [('0', 0.91, 0.0)])] "
            "| 밀림0.15+ [] | 경계밀림 [] | 정지컷밀림 [] | 최대거리 0.91 | 40s(굽기10 렌더26 비교4)\n")


def _report(jobs, summary):
    return _HEAD + "".join(jobs) + summary + "\n"


def _sum(cells, scene, sc=0, sb=0, sh=0, ghost=0, ghost_only=0):
    """요약 줄 + 잔상 줄(도구가 늘 함께 낸다 — 2026-09-27). ghost=None 이면 잔상 줄을 안 넣는다(옛 도구 흉내)."""
    line = "== 칸 %d · 다른 장면 %d · 0.15초 이상 밀림(가운데) %d · 경계 밀림 %d · 정지컷만 밀림 %d" % (cells, scene, sc, sb, sh)
    if ghost is None:
        return line
    return line + chr(10) + _ghost_line(ghost, ghost_only)


def _ghost_line(frames, only=0, cuts=None, short=0):
    return "== 잔상 %d프레임(컷 %d · 화면에만 %d프레임) · 짧은컷(3프레임 이하) %d" % (
        frames, frames if cuts is None else cuts, only, short)


GATE = dict(CFG["gate"], min_jobs_compared=1)


# ── 요약 판정 ────────────────────────────────────────────────────

def test_clean_report_passes():
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, 2, 3, 2)))
    assert p["summary"] == {"cells": 10, "scene": 0, "shift_center": 2, "shift_boundary": 3, "shift_hold": 2}
    ok, fails, notes = vg.judge(p, GATE)
    assert ok, fails
    assert any("보고만" in n for n in notes), "밀림은 기준 null 이면 보고만 해야 한다"


def test_scene_mismatch_fails():
    """★사보타주 기준: '다른 장면 3'인데 통과하면 관문은 존재 이유가 없다."""
    p = vg.parse_report(_report([_JOB_OK, _JOB_BAD], _sum(18, 3)))
    ok, fails, _ = vg.judge(p, GATE)
    assert not ok
    assert any("다른 장면 3칸" in f for f in fails), fails


def test_summary_zero_but_job_line_has_scene_fails():
    """요약만 믿지 않는다 — 작업 줄에 다른 장면이 있으면 요약이 0이어도 실패."""
    p = vg.parse_report(_report([_JOB_BAD], _sum(8, 0)))
    ok, fails, _ = vg.judge(p, GATE)
    assert not ok and any("작업 줄" in f for f in fails), fails


@pytest.mark.parametrize("text", [
    "",                                                       # 도구가 아무것도 못 썼다
    _HEAD + _JOB_OK,                                          # 요약 줄 없이 죽었다
    _HEAD + _JOB_OK + "== 칸 10 · 다른장면 3 · 모양이 바뀜\n",   # 요약 형식이 바뀌었다
])
def test_unreadable_summary_fails(text):
    ok, fails, _ = vg.judge(vg.parse_report(text), GATE)
    assert not ok and fails


def test_nothing_compared_fails():
    rep = _HEAD + "aaaa11112222 건너뜀 TypeError: boom\nbbbb11112222 건너뜀 TypeError: boom\n" + _sum(0, 0) + "\n"
    ok, fails, _ = vg.judge(vg.parse_report(rep), CFG["gate"])
    assert not ok
    assert any("0 —" in f for f in fails) and any("오류로 건너뛴" in f for f in fails)


def test_benign_skip_does_not_fail_but_error_skip_does():
    ok, _, _ = vg.judge(vg.parse_report(_report([_JOB_OK, "cccc11112222 건너뜀 음성 없음\n"], _sum(10, 0))), GATE)
    assert ok
    ok, fails, _ = vg.judge(vg.parse_report(_report([_JOB_OK, "cccc11112222 건너뜀 완성본 렌더 실패\n"], _sum(10, 0))), GATE)
    assert not ok and "완성본 렌더 실패" in fails[0]


def test_min_jobs_compared():
    ok, fails, _ = vg.judge(vg.parse_report(_report([_JOB_OK], _sum(10, 0))), dict(GATE, min_jobs_compared=3))
    assert not ok and "최소 3개" in fails[0]


def test_shift_threshold_tightens_when_set():
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, 2, 3, 2)))
    ok, fails, _ = vg.judge(p, dict(GATE, max_shift_center=0))
    assert not ok and "밀림(가운데) 2칸" in fails[0]


def test_audit_shift_ratio():
    audit = dict(CFG["audit"])
    ok, _, _ = vg.judge(vg.parse_report(_report([_JOB_OK], _sum(10, 0, 2))), audit)
    assert ok
    ok, fails, _ = vg.judge(vg.parse_report(_report([_JOB_OK], _sum(10, 0, 5))), audit)
    assert not ok and "비율" in fails[0]


# ── 실행 여부 ────────────────────────────────────────────────────

def test_needs_gate_for_watched_files():
    run, reasons, unmeasured = vg.needs_video_gate(["shopping_shorts/video_assemble.py", "README.md"], CFG)
    assert run and "video_assemble" in reasons[0] and not unmeasured
    run, _, unmeasured = vg.needs_video_gate(["shopping_shorts/capcut_draft.py"], CFG)
    assert run and unmeasured == [], "캡컷은 이제 캡컷·내보내기 대조가 잰다(2026-09-27)"
    # not_measured 가 있으면(설정) 여전히 경고 목록으로 돌려준다 — 판정 함수는 그대로
    run, _, unmeasured = vg.needs_video_gate(["shopping_shorts/capcut_draft.py"],
                                             dict(CFG, not_measured=["shopping_shorts/capcut_draft.py"]))
    assert run and unmeasured == ["shopping_shorts/capcut_draft.py"]


def test_no_gate_for_unrelated_files():
    run, _, _ = vg.needs_video_gate(["tools/track.py", "shopping_shorts/static/produce.html", "wiki/x.md"], CFG)
    assert not run


def test_app_without_decider_runs():
    run, reasons, _ = vg.needs_video_gate(["shopping_shorts/app.py"], CFG)
    assert run and "판정 함수 없음" in reasons[0]


_APP_OLD = '''import os

X = 1


def _pvproxy_build(job_id):
    return 1


@app.post("/api/mix/render")
def api_render(body):
    return 2


@app.get("/api/admin/customers")
def api_customers():
    return 3
'''


def _udiff(tmp_path, old, new):
    a, b = tmp_path / "a.py", tmp_path / "b.py"
    a.write_bytes(old.encode("utf-8"))
    b.write_bytes(new.encode("utf-8"))
    p = subprocess.run(["git", "diff", "--no-index", "-U0", str(a), str(b)], capture_output=True)
    return p.stdout.decode("utf-8")


@pytest.mark.parametrize("old,new,expect,why", [
    ("    return 1", "    return 11", True, "_pvproxy_build"),
    ("    return 2", "    return 22", True, "api_render"),                 # 이름엔 render 가 있고 라우트도 /api/mix/render
    ("    return 3", "    return 33", False, "api_customers"),             # 제작 라인 밖
    ("X = 1", "X = 2", True, "모듈 수준"),                                   # 못 정함 → 실행
    ("    return 3", "    return 3  # 주석만", False, None),                 # 주석이 붙어도 코드 줄이 바뀌면…
])
def test_app_function_level_decision(tmp_path, old, new, expect, why):
    new_src = _APP_OLD.replace(old, new, 1)
    run, reason = vg.app_touches_video(_APP_OLD, new_src, _udiff(tmp_path, _APP_OLD, new_src), CFG)
    if why == "api_customers" or why is None:
        assert run is False, reason
    else:
        assert run is expect and why in reason, reason


def test_app_comment_only_change_is_ignored(tmp_path):
    new_src = _APP_OLD.replace("X = 1\n", "X = 1\n# 설명 주석\n", 1)
    run, reason = vg.app_touches_video(_APP_OLD, new_src, _udiff(tmp_path, _APP_OLD, new_src), CFG)
    assert run is False and "주석" in reason


def test_app_route_path_counts_even_if_name_is_plain(tmp_path):
    old = _APP_OLD + '\n\n@app.get("/api/mix/capcut/{job_id}")\ndef download_it(job_id):\n    return 4\n'
    new = old.replace("return 4", "return 44")
    run, reason = vg.app_touches_video(old, new, _udiff(tmp_path, old, new), CFG)
    assert run and "download_it" in reason


def test_app_deleted_video_function_runs(tmp_path):
    new = _APP_OLD.replace("def _pvproxy_build(job_id):\n    return 1\n\n\n", "", 1)
    run, reason = vg.app_touches_video(_APP_OLD, new, _udiff(tmp_path, _APP_OLD, new), CFG)
    assert run and "_pvproxy_build" in reason


# ── 서버 실행(가짜 ssh) ──────────────────────────────────────────

def _stage(tmp_path, changed_rel="shopping_shorts/video_assemble.py"):
    """origin/main 에 detached + track/x 를 --no-commit 병합한 '병합 임시 폴더'와 같은 상태."""
    r = tmp_path / "stage"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "t@t.t")
    _git(r, "config", "user.name", "t")
    files = {"shopping_shorts/video_assemble.py": "A = 1\n", "shopping_shorts/app.py": "B = 1\n",
             "tools/editor_vs_final_video.py": "# tool\n", "tools/evf_run.py": "# run\n",
             "tools/capcut_export_audit.py": "# cc\n", "tools/final_audio_audit.py": "# au\n",
             "tools/clean_left_audit.py": "# cl\n", "README.md": "r\n"}
    for rel, body in files.items():
        (r / rel).parent.mkdir(parents=True, exist_ok=True)
        (r / rel).write_bytes(body.encode("utf-8"))
    _git(r, "add", "-A")
    _git(r, "commit", "-m", "base")
    _git(r, "checkout", "-b", "track/x")
    (r / changed_rel).write_bytes(b"CHANGED = 2\n")
    _git(r, "commit", "-am", "work")
    _git(r, "checkout", "--detach", "main")
    _git(r, "merge", "--no-ff", "--no-commit", "track/x")
    return r


_CC_OK = "abc 칸3 컷R10/C10/E10 | 캡컷 불일치 0 {} | 내보내기 불일치 0 {}\n== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 0\n"
_AU_LINE = '== 칸 %d · 나레이션 0.15초+ 오차 %d · 효과음 누락 0 · BGM 이상 0 · 음성-자막 0.15초+ 0 · 나레이션 못찾음 0 · 효과음 타점0.10+ 0 · 길이 이상 0 · 렌더뒤음성바뀜 0 · 건너뜀 0 · 패킷 잉여 0.05초+ %d편 · 일정 지연 %d편 · 검출불일치 0칸   (…)'


def _au(cells=10, narr=0, surplus=0, delay=0):
    return "62ed6bf66eb9 칸10 패킷잉여0.026 …\n" + _AU_LINE % (cells, narr, surplus, delay) + "\n"


_AU_OK = _au()
_CL_OK = ("62ed6bf66eb9 | 자막 남음 [] | 증분 대기 [] | 원인 미상 [] | 고른 원본 [] | 3s\n"
          "== 작업 1 · 자막 남음 0칸 · 증분 대기 0칸 · 원인 미상 0칸 · 대상 아님 0작업\n")
_CL_BAD = ("52a1ef1723a8 | 자막 남음 [1, 2, 4, 6, 7, 8, 9] | 증분 대기 [] | 원인 미상 [] | 고른 원본 [] | 3s\n"
           "== 작업 1 · 자막 남음 7칸 · 증분 대기 0칸 · 원인 미상 0칸 · 대상 아님 0작업\n")
_CL_PENDING = ("3c885b9e3643 | 자막 남음 [] | 증분 대기 [5, 7] | 원인 미상 [] | 고른 원본 [] | 3s\n"
               "== 작업 1 · 자막 남음 0칸 · 증분 대기 2칸 · 원인 미상 0칸 · 대상 아님 0작업\n")


class _FakeSSH:
    def __init__(self, report="", free=57, reachable=True, crash="", poll="EVF_DONE rc=0\n---\n5\nGONE\n",
                 cc_report=_CC_OK, cc_crash="", cc_poll="CEA_DONE rc=0\n---\nGONE\n",
                 au_report=_AU_OK, au_crash="", au_poll="AUDIO_DONE rc=0\n---\nGONE\n",
                 cl_report=_CL_OK, cl_crash="", cl_poll="CLA_DONE rc=0\n---\nGONE\n"):
        self.report, self.free, self.reachable, self.crash, self.poll = report, free, reachable, crash, poll
        self.cc_report, self.cc_crash, self.cc_poll = cc_report, cc_crash, cc_poll
        self.au_report, self.au_crash, self.au_poll = au_report, au_crash, au_poll
        self.cl_report, self.cl_crash, self.cl_poll = cl_report, cl_crash, cl_poll
        self.cmds = []

    def __call__(self, cmd, stdin=None, timeout=120):
        self.cmds.append(cmd)
        if not self.reachable:
            return 255, "ssh: connect to host timed out"
        if "capcut_export_audit.py" in cmd:
            return 0, "PID=4343\n"
        if "final_audio_audit.py" in cmd:
            return 0, "PID=4444\n"
        if "clean_left_audit.py" in cmd:
            return 0, "PID=4545\n"
        if cmd.startswith("cat ") and "/cl/done.txt" in cmd:
            return 0, self.cl_poll
        if cmd.startswith("cat ") and "/cl/report.txt" in cmd:
            return 0, self.cl_report
        if cmd.startswith("cat ") and "/cl/crash.txt" in cmd:
            return 0, self.cl_crash
        if cmd.startswith("cat ") and "/audio/done.txt" in cmd:
            return 0, self.au_poll
        if cmd.startswith("cat ") and "/audio/report.txt" in cmd:
            return 0, self.au_report
        if cmd.startswith("cat ") and "/audio/crash.txt" in cmd:
            return 0, self.au_crash
        if cmd.startswith("cat ") and "/cc/done.txt" in cmd:
            return 0, self.cc_poll
        if cmd.startswith("cat ") and "/cc/report.txt" in cmd:
            return 0, self.cc_report
        if cmd.startswith("cat ") and "/cc/crash.txt" in cmd:
            return 0, self.cc_crash
        if cmd.startswith("df "):
            return 0, " %dG\n" % self.free
        if "tar xzf" in cmd:
            return 0, "UP_OK\n"
        if "evf_run.py" in cmd:
            return 0, "PID=4242\n"
        if cmd.startswith("cat ") and "done.txt" in cmd:
            return 0, self.poll
        if "report.txt" in cmd and cmd.startswith("cat "):
            return 0, self.report
        if "crash.txt" in cmd and cmd.startswith("cat "):
            return 0, self.crash
        return 0, ""


def _run(stage, ssh, **kw):
    out = []
    res = vg.run_video_gate(stage, "track/x", printer=out.append, sh=ssh, cfg=kw.pop("cfg", dict(CFG, gate=GATE)),
                            env=kw.pop("env", {}), sleep=lambda s: None)
    return res, "\n".join(out)


def test_gate_skips_without_touching_server(tmp_path):
    ssh = _FakeSSH()
    res, out = _run(_stage(tmp_path, "README.md"), ssh)
    assert res.ok and not res.ran and "건너뜀" in out
    assert ssh.cmds == [], "해당 변경이 없으면 서버에 붙지도 않는다"


def test_gate_passes_clean_report_and_cleans_up(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0, 2)))
    res, out = _run(_stage(tmp_path), ssh)
    assert res.ok and res.ran, out
    assert "판정 근거: == 칸 10" in out and "62ed6bf66eb9" in out, "report 전문과 근거 줄이 출력에 남아야 한다"
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_"), "성공해도 서버 폴더를 지운다"


def test_gate_fails_on_scene_mismatch_and_cleans_up(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK, _JOB_BAD], _sum(18, 3)))
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "다른 장면 3칸" in out
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_")


def test_gate_fails_when_server_unreachable(tmp_path):
    res, out = _run(_stage(tmp_path), _FakeSSH(reachable=False))
    assert not res.ok and "못 붙었다" in out


def test_gate_fails_on_low_disk(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), free=12)
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "12GB" in out
    assert not any("evf_run.py" in c for c in ssh.cmds), "디스크 모자라면 비교를 띄우지 않는다"


def test_gate_fails_on_tool_crash(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), crash="Traceback ... ImportError")
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "crash" in out


def test_gate_skip_switch_is_loud(tmp_path):
    ssh = _FakeSSH()
    res, out = _run(_stage(tmp_path), ssh, env={"VIDEO_GATE_SKIP": "사장님 지시 09-27 긴급"})
    assert res.ok and not res.ran
    assert "영상 관문 건너뜀 (사유: 사장님 지시 09-27 긴급)" in out and "!!!!" in out
    assert ssh.cmds == []


def test_gate_uploads_merged_modules_and_main_tool(tmp_path):
    stage = _stage(tmp_path)
    blobs = []

    class _Cap(_FakeSSH):
        def __call__(self, cmd, stdin=None, timeout=120):
            if stdin:
                blobs.append(stdin)
            return super().__call__(cmd, stdin, timeout)

    _run(stage, _Cap(report=_report([_JOB_OK], _sum(10, 0))))
    import io
    import tarfile
    with tarfile.open(fileobj=io.BytesIO(blobs[0])) as tf:
        names = set(tf.getnames())
        assert tf.extractfile("video_assemble.py").read() == b"CHANGED = 2\n", "병합본 모듈을 올려야 한다"
    assert {"app.py", "_tool/editor_vs_final_video.py", "_tool/evf_run.py", "_tool/capcut_export_audit.py"} <= names


# ── finish 연결 ─────────────────────────────────────────────────

def test_finish_pushes_nothing_when_video_gate_fails(repo):
    _make_track_commit(repo, "영상")
    before_origin = _origin_head(repo)
    fail = lambda stage, br: vg.GateResult(False, True, "x")          # noqa: E731
    with pytest.raises(track.TrackError, match="영상 관문 실패"):
        track.finish("영상", repo=repo, gate=_Gate(), video_gate=fail)
    assert _origin_head(repo) == before_origin, "★영상 관문 실패인데 main 으로 나갔다"
    assert not (track.tracks_dir(repo) / "_merge-영상").exists()


def test_finish_calls_video_gate_before_commit(repo):
    _make_track_commit(repo, "영상")
    seen = []

    def spy(stage, br):
        rc, _ = track.run(["git", "rev-parse", "--verify", "--quiet", "MERGE_HEAD"], stage)
        seen.append((rc, br))
        return vg.GateResult(True, False, "")

    assert track.finish("영상", repo=repo, gate=_Gate(), video_gate=spy) == 0
    assert seen == [(0, "track/영상")], "영상 관문은 병합 중(커밋 전) 상태에서 불려야 한다"


def test_gate_fails_when_compare_dies_without_done_mark(tmp_path):
    """비교 프로세스가 끝 표식(done.txt) 없이 사라지면 — report 가 멀쩡해 보여도 — 실패."""
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), poll="---\n3\nGONE\n")
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "끝 표식 없이 죽었다" in out
    assert any(c.startswith("kill -- -4242") for c in ssh.cmds)


def test_gate_fails_on_timeout(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), poll="---\n3\nALIVE\n")
    cfg = dict(CFG, gate=dict(GATE, timeout_sec=1))
    res, out = _run(_stage(tmp_path), ssh, cfg=cfg)
    assert not res.ok and "시간 초과" in out


def test_gate_warns_loudly_when_merge_changes_the_gate_tool(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)))
    res, out = _run(_stage(tmp_path, "tools/editor_vs_final_video.py"), ssh)
    assert "영상 관문 자체를 바꾼다" in out and "tools/editor_vs_final_video.py" in out


def test_patch_rels_cover_tool_loader():
    """도구가 PATCH_DIR 에서 얹는 모듈(for _n in (...))은 전부 관문이 서버에 올리는 목록(PATCH_RELS)에 있어야 한다.
    2026-09-27: frame_match.py 가 도구 목록엔 있고 업로드 목록엔 없어 첫 finish 가 ImportError 로 막혔다."""
    import re
    src = (Path(__file__).resolve().parent / "editor_vs_final_video.py").read_text(encoding="utf-8")
    m = re.search(r"for _n in \(([^)]*)\):", src)
    assert m, "도구의 PATCH_DIR 모듈 목록(for _n in (...))을 못 찾았다"
    names = re.findall(r'"([A-Za-z_]+)"', m.group(1))
    assert names, m.group(1)
    missing = [n for n in names if ("%s.py" % n) not in vg.PATCH_RELS]
    assert not missing, "도구는 얹는데 관문이 안 올리는 모듈: %s" % missing
    for n in names:
        rel = vg.PATCH_RELS["%s.py" % n]
        assert (Path(__file__).resolve().parents[1] / rel).exists(), rel
        assert rel in vg.load_config().get("watch_files", []), "감시 목록(gate_video.json)에도 있어야 한다: %s" % rel


# ── ⑤ 캡컷·내보내기 대조(2026-09-27) ─────────────────────────────────

def test_gate_runs_capcut_audit_on_compared_jobs(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)))
    res, out = _run(_stage(tmp_path), ssh)
    assert res.ok, out
    launch = [c for c in ssh.cmds if "capcut_export_audit.py" in c]
    assert launch and "62ed6bf66eb9" in launch[0] and "PATCH_DIR=" in launch[0], "영상 비교가 본 작업으로 병합본 모듈을 재야 한다"
    assert "캡컷·내보내기 대조: 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 0" in out


@pytest.mark.parametrize("cc,why", [
    ("== 컷 10 · 캡컷 불일치 3 · 내보내기 불일치 0\n", "캡컷 불일치 3컷"),
    ("== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 27\n", "내보내기 불일치 27컷"),
    ("x\n", "요약 줄"),
    ("== 컷 0 · 캡컷 불일치 0 · 내보내기 불일치 0\n", "비교한 컷이 0"),
    ("j1 건너뜀 KeyError: x\n== 컷 10 · 캡컷 불일치 0 · 내보내기 불일치 0\n", "오류로 건너뛴"),
])
def test_gate_fails_on_capcut_mismatch(tmp_path, cc, why):
    """★사보타주 기준: 캡컷·ZIP 이 완성본과 다른데 통과하면 관문은 존재 이유가 없다."""
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), cc_report=cc)
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and why in out, out
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_")


def test_gate_fails_when_capcut_audit_crashes_or_dies(tmp_path):
    res, out = _run(_stage(tmp_path), _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), cc_crash="Traceback x"))
    assert not res.ok and "예외로 끝났다" in out
    (tmp_path / "b").mkdir()
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), cc_poll="---\nGONE\n")
    res, out = _run(_stage(tmp_path / "b"), ssh)
    assert not res.ok and "끝 표식 없이 죽었다" in out and any(c.startswith("kill -- -4343") for c in ssh.cmds)


def test_capcut_files_are_measured_now():
    """캡컷·내보내기 파일은 이제 재는 대상이다(not_measured 에서 빠짐) — 대조 도구도 감시 목록에."""
    assert not set(CFG.get("not_measured") or []) & {"shopping_shorts/capcut_draft.py", "shopping_shorts/export_bundle.py"}
    assert "tools/capcut_export_audit.py" in CFG["watch_files"]
    assert CFG["gate"]["max_capcut_mismatch"] == 0 and CFG["gate"]["max_export_mismatch"] == 0


# ── 잔상(컷 가장자리 딴 장면 1~3프레임, 2026-09-27) ─────────────────────────────
def test_ghost_line_parsed():
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=5, ghost_only=2)))
    assert p["ghost"] == {"frames": 5, "cuts": 5, "screen_only": 2, "short": 0}


@pytest.mark.parametrize("frames,only", [(3, 3), (1, 1), (5, 2)])
def test_screen_only_ghost_fails_gate(frames, only):
    """★사보타주 기준: 미리보기에만 있는 잔상(미리보기≠완성본)이 1프레임이라도 있으면 관문 실패 — 기준 0."""
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=frames, ghost_only=only)))
    ok, fails, _ = vg.judge(p, GATE)
    assert not ok and any("화면에만 있는 잔상 %d프레임" % only in f for f in fails), fails
    ok, fails, _ = vg.judge(p, dict(CFG["audit"], min_jobs_compared=1))
    assert not ok, "매일 점검 기준도 화면에만 잔상 0"


def test_ghost_in_both_fails_gate():
    """화면·완성본 둘 다에 있는 잔상도 실패(max_ghost 0, 2026-09-28) — 도구가 원본 장면 전환이 있을 때만 세므로
    빠른 움직임 오탐은 이 수에 안 들어온다('== 움직임 의심' 줄은 판정 밖)."""
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=4, ghost_only=0)))
    ok, fails, notes = vg.judge(p, GATE)
    assert not ok and any("잔상 4프레임" in f for f in fails), fails


def test_ghost_threshold_null_still_report_only():
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=4, ghost_only=0)))
    ok, fails, notes = vg.judge(p, dict(GATE, max_ghost=None))
    assert ok, fails
    assert any("잔상 4프레임" in n and "보고만" in n for n in notes), notes


def test_motion_line_does_not_affect_judge():
    text = _report([_JOB_OK], _sum(10, 0)) + "== 움직임 의심 5프레임(컷 2)" + chr(10)
    p = vg.parse_report(text)
    ok, fails, _ = vg.judge(p, GATE)
    assert ok, fails


def test_missing_ghost_line_fails_when_threshold_set():
    """잔상 줄이 없으면(옛 도구·형식 바뀜) 조용히 통과하지 않는다."""
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=None)))
    ok, fails, _ = vg.judge(p, GATE)
    assert not ok and any("잔상 줄" in f for f in fails), fails
    p2 = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=None) + "\n== 잔상 모양이 바뀜"))
    assert not vg.judge(p2, GATE)[0]


def test_ghost_threshold_null_reports_only():
    p = vg.parse_report(_report([_JOB_OK], _sum(10, 0, ghost=4)))
    ok, fails, notes = vg.judge(p, dict(GATE, max_ghost=None, max_ghost_screen_only=None))
    assert ok, fails
    assert any("잔상 4프레임" in n and "보고만" in n for n in notes), notes


def test_gate_config_ghost_thresholds():
    assert CFG["gate"]["max_ghost_screen_only"] == 0 and CFG["audit"]["max_ghost_screen_only"] == 0
    assert CFG["gate"]["max_ghost"] == 0 and CFG["audit"]["max_ghost"] == 0       # 전환 있는 잔상만 세므로 0


def test_gate_reports_clean_missing_jobs_not_as_failure(tmp_path):
    """청소 미생성 job 은 실패가 아니라 **따로 보고**된다(숨기지 않음) — 요약 파서가 새 항목을 읽는다."""
    cc = "== 컷 12 · 캡컷 불일치 0 · 내보내기 불일치 0 · 청소 미생성 2 job" + chr(10)
    res, out = _run(_stage(tmp_path), _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), cc_report=cc))
    assert res.ok, out
    assert "청소 미생성 2 job" in out
    assert vg.capcut_summary(cc)["clean_missing"] == 2


def test_gate_tools_write_scene_cache_to_gate_dir(tmp_path):
    """관문의 영상 비교·캡컷 대조 명령은 장면 전환 캐시를 관문 임시 폴더에 둔다 — 소재 옆(고객 폴더)에 쓰지 않는다(9차 관문 실측)."""
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)))
    res, out = _run(_stage(tmp_path), ssh)
    evf = [c for c in ssh.cmds if "evf_run.py" in c]
    cc = [c for c in ssh.cmds if "capcut_export_audit.py" in c]
    assert evf and cc, ssh.cmds
    for c in evf + cc:
        m = re.search(r"SEG_SNAP_CACHE_DIR=(\S+)", c)
        assert m and m.group(1).startswith("/tmp/gate_"), c


def test_tools_default_scene_cache_under_own_out():
    """비교 도구를 따로 돌려도(관문·점검 밖) 캐시는 자기 결과 폴더 아래 — 기본값이 코드에 있다."""
    src_evf = (Path(__file__).resolve().parent / "evf_run.py").read_text(encoding="utf-8")
    src_cc = (Path(__file__).resolve().parent / "capcut_export_audit.py").read_text(encoding="utf-8")
    src_tool = (Path(__file__).resolve().parent / "editor_vs_final_video.py").read_text(encoding="utf-8")
    assert 'setdefault("SEG_SNAP_CACHE_DIR", str(out / "snapcache"))' in src_evf
    assert 'setdefault("SEG_SNAP_CACHE_DIR", str(OUT / "snapcache"))' in src_cc
    assert 'setdefault("SEG_SNAP_CACHE_DIR"' in src_tool



# ── ⑥ 소리 대조(2026-09-27) — 영상 비교가 구운 임시 완성본을 재사용(렌더 2번 금지) ─────────────────

def test_gate_runs_audio_audit_on_compared_jobs_reusing_finals(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)))
    res, out = _run(_stage(tmp_path), ssh)
    assert res.ok, out
    evf = [c for c in ssh.cmds if "evf_run.py" in c]
    assert evf and "EVF_KEEP_FINAL=/tmp/gate_" in evf[0], "영상 비교가 구운 완성본을 남겨야 소리 대조가 재사용한다"
    au = [c for c in ssh.cmds if "final_audio_audit.py" in c]
    assert au and "62ed6bf66eb9" in au[0] and "AUDIO_FINAL_DIR=/tmp/gate_" in au[0] and "PATCH_DIR=" in au[0], au
    assert "소리 대조: 칸 10 · 나레이션 0.15초+ 0 · 패킷 잉여 0.05초+ 0편 · 일정 지연 0편" in out
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_"), "임시 완성본(finals)도 폴더째 지운다"


@pytest.mark.parametrize("au,why", [
    (_au(narr=2), "나레이션 0.15초+ 오차 2"),
    (_au(surplus=1), "패킷 잉여 0.05초+ 1"),
    (_au(delay=3), "일정 지연 3"),
    (_au(cells=0), "잰 칸이 0"),
    (_AU_LINE.split(" · 일정 지연")[0] % (10, 0, 0) + "\n", "요약 줄"),        # 옛 판본(일정 지연 항목 없음)
    ("j1 건너뜀 KeyError: x\n" + _AU_OK, "오류로 건너뛴"),
])
def test_gate_fails_on_audio_mismatch(tmp_path, au, why):
    """★사보타주 기준: 목소리가 화면과 어긋났는데(또는 못 쟀는데) 통과하면 소리 관문은 존재 이유가 없다."""
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), au_report=au)
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and why in out, out
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_")


def test_gate_fails_when_audio_audit_crashes_or_dies(tmp_path):
    res, out = _run(_stage(tmp_path), _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), au_crash="Traceback x"))
    assert not res.ok and "소리 대조 도구가 예외로 끝났다" in out
    (tmp_path / "b").mkdir()
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), au_poll="---\nGONE\n")
    res, out = _run(_stage(tmp_path / "b"), ssh)
    assert not res.ok and "소리 대조가 끝 표식 없이 죽었다" in out and any(c.startswith("kill -- -4444") for c in ssh.cmds)


def test_audio_tool_is_uploaded_and_watched():
    assert "tools/final_audio_audit.py" in vg.TOOL_RELS
    assert "tools/final_audio_audit.py" in CFG["watch_files"]
    for k in ("max_audio_narr", "max_audio_surplus", "max_audio_delay"):
        assert CFG["gate"][k] == 0 and CFG["audit"][k] == 0, k


def test_gate_passes_vcut_mismatch_as_report_only(tmp_path):
    """영상 컷 검출이 계획 프레임과 갈리는 칸(칸 안 장면 전환 오검출 — finish 12차 6c1a 칸2)은 판정이 아니라 보고만."""
    au = _AU_OK.replace("검출불일치 0칸", "검출불일치 3칸")
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), au_report=au)
    res, out = _run(_stage(tmp_path), ssh)
    assert res.ok, out
    assert "검출불일치 3칸(보고만" in out


def test_gate_fails_when_audio_summary_lacks_vcut_item(tmp_path):
    au = _AU_OK.replace(" · 검출불일치 0칸", "")
    res, out = _run(_stage(tmp_path), _FakeSSH(report=_report([_JOB_OK], _sum(10, 0)), au_report=au))
    assert not res.ok and "요약 줄" in out


# ── ⑦ 자막 남음(2026-09-28) — 영상 비교는 원본을 틀어 장면이 같게 나와 "청소본이 있어야 할 칸인데 원본"을 못 본다 ──

def test_clean_left_summary_parses_both_modes():
    assert vg.clean_left_summary(_CL_BAD) == {"jobs": 1, "left": 7, "pending": 0, "unknown": 0, "na": 0, "stale": 0}
    s = vg.clean_left_summary("== 작업 9 · 자막 남음 2칸 · 증분 대기 0칸 · 원인 미상 1칸 · 대상 아님 3작업 · 재구성 불가 4작업\n")
    assert s == {"jobs": 9, "left": 2, "pending": 0, "unknown": 1, "na": 3, "stale": 4}
    assert vg.clean_left_summary("== 칸 10 · 다른 장면 0\n") is None


def test_judge_clean_left_fails_on_left_passes_on_pending():
    ok, fails, notes = vg.judge_clean_left(_CL_BAD, {})
    assert not ok and "자막 남음 7칸" in fails[0] and "52a1ef1723a8" in fails[0]
    ok, fails, notes = vg.judge_clean_left(_CL_PENDING, {})
    assert ok and not fails and "증분 대기 2칸" in notes[0], "편성 변경으로 대기 중인 칸은 결함이 아니다(렌더 때 동의창)"
    ok, fails, _ = vg.judge_clean_left("x\n", {})
    assert not ok and "요약 줄" in fails[0]
    ok, fails, _ = vg.judge_clean_left(_CL_OK, {}, crash="Traceback")
    assert not ok and "crash" in fails[-1]
    ok, fails, _ = vg.judge_clean_left("abc 건너뜀 KeyError: x\n" + _CL_OK, {})
    assert not ok and "건너뛴 작업 1개" in fails[0]


def test_gate_fails_on_clean_left_even_when_scene_matches(tmp_path):
    """★사보타주 기준(52a1): 영상 비교는 다른 장면 0인데 자막 남음 7칸 → 관문 실패."""
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0, 2)), cl_report=_CL_BAD)
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "자막 남음 7칸" in out, out
    assert any("clean_left_audit.py 62ed6bf66eb9" in c for c in ssh.cmds), "영상 비교와 같은 작업으로 돈다"
    assert ssh.cmds[-1].startswith("rm -rf /tmp/gate_")


def test_gate_passes_with_pending_only(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0, 2)), cl_report=_CL_PENDING)
    res, out = _run(_stage(tmp_path), ssh)
    assert res.ok, out
    assert "증분 대기 2칸" in out


def test_gate_fails_when_clean_left_tool_dies(tmp_path):
    ssh = _FakeSSH(report=_report([_JOB_OK], _sum(10, 0, 2)), cl_poll="---\nGONE\n")
    res, out = _run(_stage(tmp_path), ssh)
    assert not res.ok and "자막 남음 대조가 끝 표식 없이 죽었다" in out


def test_clean_left_tool_is_bundled_and_patch_modules_uploaded():
    import clean_left_audit as cla
    assert "tools/clean_left_audit.py" in vg.TOOL_RELS
    assert set("%s.py" % n for n in cla.PATCH_MODULES) <= set(vg.PATCH_RELS), "도구가 얹는 모듈은 관문이 올려야 한다"
