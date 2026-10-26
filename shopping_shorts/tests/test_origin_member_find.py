# -*- coding: utf-8 -*-
"""관제263 10-26 잇템로그 회원 실측 — 해외 원본 찾기(98 #161·#164).
#161: 렌즈가 못 찾으면 회원 Claude 가 목표+가이드+도구로 직접 찾는다(f_of_find → 실행기 origin_foreign find → 같은 영상 판정 of_judge).
#164(10-26 사장님 "계속 찾을 수 있게 · 소재를 두 개 골라서 각각 원본을 찾는다 · 5분에 한 번씩 안내"):
  ① 원본이 틱톡·인스타여도 원본(옛: f_of_pick 이 유튜브 밖을 버림 · 과제 문구 '유튜브만')
  ② 찾기 한도 = 바퀴 3 → 시간 예산(F_FIND_SEC, 새 후보가 나오면 F_FIND_HARD 까지)
  ③ 소재 2편 함께(회원이 준 소재 + 벤치 상위 조회순 중 만든 편 아닌 것) → 먼저 원본을 확보한 소재로 제작, 진 소재는 기록만
  ④ 진행 줄 '소재 2편의 원본을 함께 찾고 있어요 · N분째 · 1편 후보 X개 / 2편 후보 Y개'(5분 단위)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from tools.calcopy.hybrid import flow as F  # noqa: E402
import test_flow_formats as TF  # noqa: E402

BENCH = {"id": "BENCH1", "title": "치아 미백 테이프 이거 맞아??!", "channel": "잇템로그", "date": "20250801", "dur": 28, "sheet": "bench/sheet.jpg", "lines": []}
ALT = "ro1l3u734v4"            # 벤치상위.json 조회 1위(둘째 소재)
YT_CAND = {"n": 1, "platform": "yt", "id": "ORIGX123456", "url": "https://www.youtube.com/shorts/ORIGX123456", "title": "Purple whitening strips?!",
           "channel": "Joe", "channel_id": "UCJOE", "date": "20250301", "dur": 20, "korean": False}
TT_CAND = {"n": 1, "platform": "tt", "id": "7540826607364197640", "url": "https://www.tiktok.com/@hismile/video/7540826607364197640",
           "title": "purple serum", "channel": "hismile", "channel_id": "hismile", "date": "20250220", "dur": 15, "korean": False}


def _slot(d_or_rv) -> int:
    """칸 번호 — do 는 sub(alt1 = 2), 질문은 id 앞 's2:'."""
    if d_or_rv.get("sub"):
        return 2
    m = re.match(r"s([0-9]+):", str(d_or_rv.get("id") or ""))
    return int(m.group(1)) if m else 1


def _ctx(judge_ok_after=None, cand=YT_CAND, bench_fail=(), judge_slots=(1, 2), clock=None):
    """judge_ok_after = 회원 찾기 몇 바퀴째부터 '같음'(None = 끝까지 아님) · bench_fail = 받기 실패할 칸 · judge_slots = '같음'이 나오는 칸."""
    return {"ref_kind": "korean_reedit", "dims": {"ORIGX123456": (1080, 1920), TT_CAND["id"]: (1080, 1920)}, "span_src": cand["id"] + ".mp4",
            "cut_src": cand["id"] + ".mp4", "bench": BENCH, "judge_ok_after": judge_ok_after, "cand": cand, "bench_fail": set(bench_fail),
            "judge_slots": set(judge_slots), "find_round": {1: 0, 2: 0}, "clock": clock}


def _measure(d, ctx):
    k = _slot(d)
    if d["cmd"] == "bench" and k in ctx["bench_fail"]:
        return {"error": "벤치 영상을 받지 못했다 — ERROR: Video unavailable"}
    if d["cmd"] == "origin_foreign":
        ctx.setdefault("of_calls", []).append((k, d.get("mode"), tuple(d.get("urls") or ()), tuple(d.get("queries") or ())))
        if d.get("mode") == "lens":
            return {"mode": "lens", "cands": [{"n": 1, "platform": "ig", "id": "IGX", "title": "Video by someone", "korean": True}], "sheets": ["origin_foreign/judge_0.jpg"]}
        return {"mode": d.get("mode"), "cands": [dict(ctx["cand"])], "sheets": ["origin_foreign/judge_0.jpg"]}
    if d["cmd"] == "origin_get":
        ctx.setdefault("gets", []).append(d)
    return TF._measure(d, ctx)


def _reply(rv, ctx):
    i, k = re.sub(r"^s[0-9]+:", "", rv["id"]), _slot(rv)
    if i == "of_find":
        ctx["find_round"][k] += 1
        ctx.setdefault("find_asks", []).append((k, rv["ask"]))
        if ctx.get("clock") is not None:
            ctx["clock"][0] += 150                    # 한 바퀴 2.5분(run3 실측 바퀴당 2~3분)
        return {"cuts": [{"cut": "S1", "seen": "보라색 테이프 남성", "urls": [ctx["cand"]["url"]], "queries": ["purple teeth whitening strips reaction"]}],
                "why": "보라색 테이프 남성 컷"}
    if i == "of_judge":
        a = ctx.get("judge_ok_after")
        ok = a is not None and k in ctx["judge_slots"] and ctx["find_round"][k] >= a
        return {"same": [1] if ok else [], "why": "같은 촬영분" if ok else "다른 사람·다른 촬영"}
    return TF._reply(rv, ctx)


def walk(mod, st, ctx, limit=400):
    trace, measure, replies, user, res, msgs = [], {}, {}, {}, {}, []
    for _ in range(limit):
        res = mod.step(st, measure, replies, user)
        st = json.loads(json.dumps(res.pop("state"), ensure_ascii=False))
        trace.append((res["status"], st.get("phase"), tuple(d["cmd"] for d in res.get("do") or []), tuple(r["id"] for r in res.get("review") or [])))
        msgs.append(res.get("message"))
        measure, replies, user = {}, {}, {}
        if res["status"] in ("done", "stop"):
            break
        if res["status"] == "execute":
            measure = {d["id"]: _measure(d, ctx) for d in res["do"]}
        elif res["status"] in ("review", "reject"):
            replies = {r["id"]: _reply(r, ctx) for r in res["review"]}
        elif res["status"] == "wait_user":
            user = {"approve": True}
    ctx["msgs"] = msgs
    return trace, res, st


@pytest.fixture(autouse=True)
def _no_heavy(monkeypatch):
    monkeypatch.setattr(F, "audit_script", lambda st, S, M: {"ok": True})
    yield


def _clocked(monkeypatch, ctx):
    ctx["clock"] = [1_000_000.0]
    monkeypatch.setattr(F, "_now", lambda: ctx["clock"][0])
    return ctx


def test_lens_miss_member_finds_and_result_check_passes():
    ctx = _ctx(judge_ok_after=1)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-4:]
    s1 = [c for c in ctx["of_calls"] if c[0] == 1]
    assert [c[1] for c in s1[:2]] == ["lens", "find"]                           # 렌즈 먼저 1번, 그다음 회원 Claude 가 찾은 것
    assert s1[1][2] == ("https://www.youtube.com/shorts/ORIGX123456",)
    assert st["origins"][0]["id"] == "ORIGX123456"
    assert not any(t[0] == "stop" for t in tr)                                  # 회원에게 '다시 시도'를 묻지 않았다
    ask = ctx["find_asks"][0][1]
    assert "해외 원본 영상의 주소" in ask and "## 5." in ask                     # 목표 + 가이드(브리프 §5)
    assert "틱톡" in ask and "인스타" in ask and "유튜브만" not in ask and "컷마다" in ask   # 3플랫폼 · 컷별 표


def test_failed_check_carries_reason_to_next_round():
    ctx = _ctx(judge_ok_after=2)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-4:]
    assert ctx["find_round"][1] == 2
    asks1 = [a for k, a in ctx["find_asks"] if k == 1]
    assert "다른 사람·다른 촬영" in asks1[1]                                     # 불합격 이유를 들고 다음 바퀴


def test_tiktok_origin_is_kept_and_fetched_by_url():
    """사장님 10-26 실측: 이 소재의 원본은 틱톡 @hismile 에만 있었다 — 옛 f_of_pick 은 유튜브 밖을 '받기 길 없음'으로 버렸다."""
    ctx = _ctx(judge_ok_after=1, cand=TT_CAND)
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-4:]
    o = st["origins"][0]
    assert o["platform"] == "tt" and o["id"] == TT_CAND["id"]
    g = next(d for d in ctx["gets"] if d["vid"] == TT_CAND["id"])
    assert g["url"] == TT_CAND["url"]                                           # 받기 = 주소로(runner c_origin_get → media_download)
    assert st["origin"]["url"] == TT_CAND["url"]


def test_time_budget_keeps_searching_past_three_rounds_then_asks(monkeypatch):
    """옛 한도 = 3바퀴. 지금은 시간(20분, 새 후보가 계속 나오면 60분까지) — 같은 후보만 되풀이하면 20분에 마치고 그때만 회원에게."""
    ctx = _clocked(monkeypatch, _ctx(judge_ok_after=None))
    st0 = F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    monkeypatch.setattr(F, "FILL_SAME_KIND", False)   # 같은 종류 해외 반응 채우기(사장님 10-26)를 끈 옛 멈춤을 본다 — 채우기는 아래 시험
    tr, res, st = walk(F, st0, ctx)
    assert res["status"] == "stop"
    assert ctx["find_round"][1] > 3                                             # 3바퀴 넘어 계속
    assert ctx["clock"][0] - 1_000_000.0 >= F.F_FIND_SEC                        # 예산(20분)을 다 쓴 뒤에(두 칸이 한 시계)
    assert "한 번 더 찾아볼게요" in json.dumps(res, ensure_ascii=False)
    assert not re.search(r"주소|다른 영상", str(res.get("message")))               # 회원에게 주소·다른 영상 요구 금지(test_redo_words)
    n = len(ctx["of_calls"])
    res2 = F.step(st, {}, {}, {"retry": True})                                  # 다시 시도 = 찾기 예산을 새로 받아 실제로 찾는다
    assert any(re.sub(r"^s[0-9]+:", "", r["id"]) == "of_find" for r in res2.get("review") or []), res2.get("status")
    assert n == len(ctx["of_calls"])


def test_new_candidates_extend_past_soft_budget(monkeypatch):
    """예산(20분)을 넘어도 바로 앞 바퀴에 새 후보가 있었으면 계속 — 진행 신호(runner 감시 장치와 같은 꼴), 60분이면 무조건 마침."""
    ctx = _clocked(monkeypatch, _ctx(judge_ok_after=None))
    seq = iter(range(10_000))
    base = _measure

    def fresh(d, c):
        r = base(d, c)
        if d["cmd"] == "origin_foreign" and d.get("mode") == "find":
            r["cands"] = [{**r["cands"][0], "id": f"NEW{next(seq):08d}"}]
        return r
    monkeypatch.setattr(sys.modules[__name__], "_measure", fresh)
    st0 = F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    monkeypatch.setattr(F, "FILL_SAME_KIND", False)
    tr, res, st = walk(F, st0, ctx, limit=800)
    assert res["status"] == "stop"
    assert ctx["clock"][0] - 1_000_000.0 >= F.F_FIND_HARD                       # 새 후보가 계속 나와 60분까지


def test_first_source_blocked_second_source_finishes():
    """소재 2편 함께 — 회원이 준 소재(1편)를 못 받아도 벤치 상위 둘째 소재(2편)로 끝까지 간다(사보타주: 옛 flow 는 1편에서 멈춘다)."""
    ctx = _ctx(judge_ok_after=1, bench_fail={1})
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-6:]
    assert st["ref"] == f"https://www.youtube.com/shorts/{ALT}" and st["ref_asked"] == "https://youtu.be/BENCH1"
    assert st["of_times"]["won_slot"] == 2
    settle = next(d for d in ctx["settle"])
    assert settle["win_sub"] == "alt1" and settle["left"][0]["url"] == "https://youtu.be/BENCH1"   # 진 소재 = 기록만(다음에 다시 씀)
    assert any(F.ALT_NOTICE_WON in str(x) for x in ctx["msgs"])                  # 회원에게 한 번 알림


def test_first_found_source_wins_other_recorded():
    """2편만 원본 확보 → 그 소재로 넘어가고, 1편은 찾던 중이어도 그만(기록만)."""
    ctx = _ctx(judge_ok_after=1, judge_slots={2})
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "done", tr[-6:]
    assert st["of_times"]["won_slot"] == 2 and st["origins"][0]["id"] == "ORIGX123456"
    assert ctx["settle"][0]["left"][0]["cands"] >= 1


def test_pick_alt_source_skips_own_and_made():
    st = F.start("https://www.youtube.com/shorts/ro1l3u734v4", "잇템로그판_v2", "sid")
    st["env"] = {"done_refs": ["aUicTeDoW04"]}
    a = F.pick_alt_source(st)
    assert a["id"] == "J7GxfaVdwSU"                                              # 1위 = 회원이 준 것 · 2위 = 이미 만든 편 → 3위
    st["slug"] = "없는판"
    assert F.pick_alt_source(st) is None


def test_progress_line_every_five_minutes(monkeypatch):
    """진행 줄: 첫 5분은 분 없이, 5분마다 'N분째' — 후보 수는 칸마다."""
    ctx = _clocked(monkeypatch, _ctx(judge_ok_after=None))
    walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx, limit=14)
    ms = [m for m in ctx["msgs"] if m and "원본을 함께 찾고 있어요" in m]
    assert ms and "분째" not in ms[0] and "1편 후보" in ms[0] and "2편 후보" in ms[0]
    later = [m for m in ctx["msgs"] if m and "5분째" in m]
    assert later, ctx["msgs"]
    fs = {"sec": 299, "step": 300, "say": "A · {m}분째 · B", "say0": "A · B"}
    assert F.finding_line(fs) == "A · B" and F.finding_line({**fs, "sec": 300}) == "A · 5분째 · B" and F.finding_line({**fs, "sec": 901}) == "A · 15분째 · B"
    for m in ms + later:
        assert F.member_ok(m), m


def _head_flow():
    r = subprocess.run(["git", "-C", str(ROOT), "show", "HEAD:tools/calcopy/hybrid/flow.py"], capture_output=True, text=True, encoding="utf-8")
    if r.returncode != 0 or "f_of_dual" in r.stdout:
        return None
    mod = types.ModuleType("flow_head")
    mod.__file__ = str(ROOT / "tools/calcopy/hybrid/flow.py")
    exec(compile(r.stdout, "flow_head.py", "exec"), mod.__dict__)
    mod.audit_script = lambda st, S, M: {"ok": True}
    return mod


_NEW_REPLY = _reply


def _old_reply(rv, ctx):
    if rv["id"] == "of_find":                                                   # 옛 꼴 답(urls·queries)
        ctx["find_round"][1] += 1
        return {"urls": [ctx["cand"]["url"]], "queries": ["purple teeth whitening strips reaction"], "why": "x"}
    return _NEW_REPLY(rv, ctx)


def test_old_flow_fails_the_new_cases(monkeypatch):
    """사보타주 기준 — 고치기 전 flow 는 ①틱톡 원본을 버리고 ②1편 받기 실패에서 멈춘다(이 시험 묶음이 그 결함을 잡는지)."""
    old = _head_flow()
    if old is None:
        pytest.skip("HEAD 가 이미 새 길")
    monkeypatch.setattr(sys.modules[__name__], "_reply", _old_reply)
    ctx = _ctx(judge_ok_after=1, cand=TT_CAND)
    tr, res, st = walk(old, old.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "stop" or not any((o.get("platform") == "tt") for o in st.get("origins") or [])
    ctx = _ctx(judge_ok_after=1, bench_fail={1})
    tr, res, st = walk(old, old.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx)
    assert res["status"] == "stop"


def test_task_give_url_goes_to_first_source_slot():
    """제작자 과제가 원본 주소를 주면(ph_task_got give) 소재 칸 1편이 그 주소로 바로 판정 — 소재 칸 밖 옛 길(of_find_got 편 상태)로 새지 않는다."""
    st = F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid")
    st.update({"phase": "task_got", "_task": {"id": "task_1", "why": "영상을 받지 못했어요", "fix": "", "retry": "of_dual_retry", "stage": "origin"},
               "slots": [{"ref": "https://youtu.be/BENCH1", "sub": "", "phase": "bench_got", "st": {"bench": BENCH, "read": {}, "origins": []},
                          "dead": {"why": "x", "retry": "of_find", "final": False}}], "finding": {"t0": 1.0}})
    res = F.step(st, {}, {"task_1": {"action": "give", "origin_url": TT_CAND["url"], "note": "틱톡"}}, {})
    do = res.get("do") or []
    assert [d["cmd"] for d in do] == ["origin_foreign"] and do[0]["id"] == "s1:of" and do[0]["urls"] == [TT_CAND["url"]], res.get("status")


def test_runner_makes_alt_dir(tmp_path):
    """실행기 — 둘째 소재 칸 일(sub=alt1)은 작업 폴더를 만들어 그 안에서 돈다(10-26 run4: 폴더가 없어 bench 가 즉시 FileNotFoundError)."""
    from tools.calcopy.hybrid import runner_ops as R
    seen = {}
    R.CMDS["_t_probe"] = lambda W, d: seen.setdefault("w", str(W)) and {"ok": (W / "x").parent.is_dir()}
    try:
        out = R.run_do(tmp_path, [{"id": "s2:p", "cmd": "_t_probe", "sub": "alt1"}], log=lambda s: None)
    finally:
        R.CMDS.pop("_t_probe", None)
    assert out["s2:p"] == {"ok": True} and seen["w"].endswith("alt1")


def test_progress_line_when_one_source_stopped():
    """한 편이 멈추면 '확인 마침'(찾기가 끝난 걸로 읽힘, 10-26 run4) 대신 찾는 편만 앞에 · 멈춘 편은 '잠시 쉬는 중'."""
    fs = F.finding_say({"finding": {"t0": 1, "n": [49, 0], "done": [False, True]}}, sec=620)
    line = F.finding_line(fs)
    assert line == "1편 영상의 원본을 계속 찾고 있어요 · 10분째 · 1편 후보 49개 (2편은 잠시 쉬는 중)" and F.member_ok(line)
    assert "마침" not in line


def test_budget_end_without_origin_fills_with_same_kind_reactions(monkeypatch):
    """사장님 10-26: 같은 촬영분을 끝내 못 찾으면 멈추지 말고 같은 종류(색·브랜드 달라도) 조회수 높은 해외 영상으로 원본을 채운다 — 예산 끝 → peers 검색."""
    ctx = _clocked(monkeypatch, _ctx(judge_ok_after=None))
    tr, res, st = walk(F, F.start("https://youtu.be/BENCH1", "잇템로그판_v2", "sid"), ctx, limit=800)
    assert any("같은 종류 해외 반응" in str(x) for x in st.get("log") or []), st.get("log", [])[-5:]
    assert st.get("_peers_done") is True
