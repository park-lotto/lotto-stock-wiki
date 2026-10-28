# -*- coding: utf-8 -*-
"""영상 관문 전후 비교(2026-10-02 사장님 "쓸데없는 것까지 하는 거 아닌가 → 얼른 해", 카드 071).

종전: 병합본 영상이 **완벽한가**(잔상 0·다른 장면 0 …)로 판정 → main 에도 있는 차이(옛 완성본·기존 결함)로 무관한 병합이 막혔다
      (10-01 062·063·064 · 2기모집 1차 · 관문선정 11차).
지금: 같은 작업을 **main 코드로 먼저** 재고, 기준 = max(설정값, main 실측) 으로 병합본을 판정 → 병합본이 **더 나빠졌을 때만** 막는다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import video_gate as vg  # noqa: E402

G = {"compare_main": True, "jobs": 6, "timeout_sec": 60, "poll_sec": 0, "min_free_gb": 20, "min_jobs_compared": 3, "max_scene": 0,
     "max_error_skips": 0, "max_shift_center": None, "max_shift_boundary": None, "max_shift_hold": None,
     "max_capcut_mismatch": 0, "max_export_mismatch": 0, "max_ghost": 0, "max_ghost_screen_only": 0,
     "max_audio_narr": 0, "max_audio_surplus": 0, "max_audio_delay": 0, "max_audio_lost": 0, "max_clean_left": 0}
JOBS = ["aaaaaaaaaaa1", "aaaaaaaaaaa2", "aaaaaaaaaaa3"]


def evf_report(scene=0, ghost=0, ghost_so=0, jobs=JOBS):
    lines = ["판정: …"]
    lines += ["%s 칸10(청소본 0) 화면20.00s 완성본20.00s 음성20.00s | 다른장면 %s | 밀림0.15+ [] | 경계밀림 [] | 정지컷밀림 [] | 최대거리 0.03"
              % (j, "[(1, 0.9)]" if (scene and i == 0) else "[]") for i, j in enumerate(jobs)]
    lines.append("== 칸 30 · 다른 장면 %d · 0.15초 이상 밀림(가운데) 0 · 경계 밀림 0 · 정지컷만 밀림 0" % scene)
    lines.append("== 잔상 %d프레임(컷 %d · 화면에만 %d프레임) · 짧은컷(3프레임 이하) 0" % (ghost, 1 if ghost else 0, ghost_so))
    return "\n".join(lines) + "\n"


CC = "== 컷 60 · 캡컷 불일치 %d · 내보내기 불일치 0 · 청소 미생성 0 job\n"
AU = ("== 칸 30 · 나레이션 0.15초+ 오차 %d · 효과음 누락 0 · BGM 이상 0 · 음성-자막 0.15초+ 0 · 나레이션 못찾음 0 · 효과음 타점0.10+ 0"
      " · 길이 이상 0 · 렌더뒤음성바뀜 0 · 건너뜀 0 · 패킷 잉여 0.05초+ 0편 · 일정 지연 0편 · 검출불일치 0칸\n")
CL = "== 작업 3 · 자막 남음 %d칸 · 증분 대기 0칸 · 원인 미상 0칸 · 대상 아님 0작업\n"


class FakeServer:
    """경로(gate_main_… / gate_<sha>)별로 다른 report 를 돌려주는 가짜 ssh."""
    def __init__(self, main, merged, cache=None):
        self.side = {"main": main, "merged": merged}
        self.cache = dict(cache or {})
        self.cmds = []

    def _which(self, cmd):
        return "main" if "gate_main_" in cmd else "merged"

    def __call__(self, cmd, stdin=None, timeout=120):
        self.cmds.append(cmd)
        s = self.side[self._which(cmd)]
        if cmd.startswith("df "):
            return 0, "  100G\n"
        if "UP_OK" in cmd:
            return 0, "UP_OK"
        if "gate_main_cache" in cmd:
            path = cmd.split()[-1] if cmd.startswith("cat ") else None
            if cmd.startswith("cat "):
                return (0, self.cache[path]) if path in self.cache else (1, "")
            if stdin is not None:
                self.cache[cmd.rsplit(" ", 1)[-1]] = stdin.decode("utf-8")
                return 0, ""
            return 0, ""
        if "evf_run.py" in cmd:
            s["evf_args"] = cmd
            return 0, "PID=11"
        for tool, key in (("capcut_export_audit", "cc"), ("final_audio_audit", "au"), ("clean_left_audit", "cl")):
            if tool in cmd and "PID" in cmd:
                return 0, "PID=12"
        if "done.txt" in cmd:
            return 0, "EVF_DONE rc=0 AUDIO_DONE CC_DONE CL_DONE\n---\n3\nGONE"
        if cmd.startswith("cat ") and "/out/report.txt" in cmd:
            return 0, s["evf"]
        if cmd.startswith("cat ") and "/cc/report.txt" in cmd:
            return 0, s["cc"]
        if cmd.startswith("cat ") and "/audio/report.txt" in cmd:
            return 0, s["au"]
        if cmd.startswith("cat ") and "/cl/report.txt" in cmd:
            return 0, s["cl"]
        return 0, ""


def side(ghost=0, scene=0, cc=0, narr=0, left=0):
    return {"evf": evf_report(scene=scene, ghost=ghost), "cc": CC % cc, "au": AU % narr, "cl": CL % left}


def _run(monkeypatch, srv):
    monkeypatch.setattr(vg, "_bundle", lambda stage, side="merged": ("bundle-" + side).encode())
    monkeypatch.setattr(vg, "_git", lambda stage, *a: (0, "abcdef1234") if a[0] == "rev-parse" else (0, ""))
    return vg._measure_and_judge(srv, "stage", "track/x", {"gate": G, "benign_skips": ["음성 없음"]}, G,
                                 say=lambda s: None, sleep=lambda s: None, remote_tmp="/tmp")


def test_main에도_있는_결함은_병합을_막지_않는다(monkeypatch):
    srv = FakeServer(main=side(ghost=3, scene=2, cc=1, narr=2, left=1), merged=side(ghost=3, scene=2, cc=1, narr=2, left=1))
    ok, fails, notes = _run(monkeypatch, srv)
    assert ok, fails
    assert any("main 실측" in n for n in notes)


def test_병합본이_더_나빠지면_막는다(monkeypatch):
    srv = FakeServer(main=side(ghost=3), merged=side(ghost=5))
    ok, fails, _ = _run(monkeypatch, srv)
    assert not ok and any("잔상 5프레임" in f for f in fails)
    srv = FakeServer(main=side(narr=0), merged=side(narr=2))
    ok, fails, _ = _run(monkeypatch, srv)
    assert not ok and any("나레이션" in f for f in fails)


def test_병합본은_main이_본_그_작업들로_잰다(monkeypatch):
    srv = FakeServer(main=side(), merged=side())
    _run(monkeypatch, srv)
    assert all(j in srv.side["merged"]["evf_args"] for j in JOBS), "병합본은 main 이 비교한 작업 id 를 그대로 받는다"
    assert " 6 " in srv.side["main"]["evf_args"] or "evf_run.py 6" in srv.side["main"]["evf_args"]


def test_기준은_설정값보다_낮아지지_않는다():
    g2, raised = vg.baseline_limits(G, vg.parse_report(evf_report()), {"cc": CC % 0, "au": AU % 0, "cl": CL % 0})
    assert g2["max_ghost"] == 0 and g2["max_scene"] == 0 and not raised
    g2, raised = vg.baseline_limits(G, vg.parse_report(evf_report(ghost=3)), {"cc": CC % 2, "au": AU % 1, "cl": CL % 0})
    assert g2["max_ghost"] == 3 and g2["max_capcut_mismatch"] == 2 and g2["max_audio_narr"] == 1 and raised


def test_main_결과는_캐시해서_두번째엔_main을_다시_안_돌린다(monkeypatch):
    srv = FakeServer(main=side(ghost=3), merged=side(ghost=3))
    _run(monkeypatch, srv)
    n_main = sum(1 for c in srv.cmds if "evf_run.py" in c and "gate_main_" in c)
    srv2 = FakeServer(main=side(ghost=3), merged=side(ghost=3), cache=srv.cache)
    ok, fails, notes = _run(monkeypatch, srv2)
    assert n_main == 1 and ok
    assert not any("evf_run.py" in c and "gate_main_" in c for c in srv2.cmds), "캐시가 있으면 main 비교를 안 띄운다"
    assert any("캐시" in n for n in notes)


def test_main을_못_재면_종전_절대기준으로_판정한다(monkeypatch):
    bad = side(); bad["evf"] = "깨진 출력\n"
    srv = FakeServer(main=bad, merged=side(ghost=3))
    ok, fails, notes = _run(monkeypatch, srv)
    assert not ok and any("잔상 3프레임" in f for f in fails)
    assert any("main 을 못 재" in n for n in notes)
