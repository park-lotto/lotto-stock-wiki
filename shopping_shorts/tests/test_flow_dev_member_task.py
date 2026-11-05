# -*- coding: utf-8 -*-
"""개발 시험기 flow_dev 의 회원 과제(bm_trial, meta.kind=member_task) 길 — 회원 PC shortem_make 대신 엔진 길(make.py start→choose→approve)로 1편,
결과 폴더를 W/trial/t<try>_<sid> 로 옮겨 {work_dir, ok} 로 답한다(관제 319). 엔진 호출은 가짜(run)로 — 꼴만 본다."""
import json
import threading
from pathlib import Path

from tools.calcopy.hybrid import flow_dev as FD


def _job(tmp: Path) -> Path:
    job = tmp / "W" / "job"
    pd = job / "channel/my_t/preset/틀"
    pd.mkdir(parents=True)
    (pd / "frame.json").write_text("{}", encoding="utf-8")
    (pd / "manifest.json").write_text("{}", encoding="utf-8")
    return job


RV = {"id": "bm_trial", "ask": "…", "need": ["work_dir", "ok"],
      "meta": {"kind": "member_task", "tool": "shortem_make", "preset": {"slug": "my_t", "style": "틀", "dir": "channel/my_t/preset/틀"},
               "source": {"channel": "https://www.youtube.com/@abc"}, "try": 1, "purpose": "calcopy"}}


def test_member_task_runs_engine_path_and_moves_trial(tmp_path):
    job = _job(tmp_path)
    data = job.parent / "trial_data"
    calls, envs = [], []
    work = data / "make" / "s1" / "work" / "7" / "제작"

    def run(args, env):
        calls.append(args[0])
        envs.append(env)
        if args[0] == "start":
            return {"sid": "abcdef123456", "state": "candidates", "candidates": [{"n": 1, "id": 7}]}
        if args[0] == "choose":
            assert args[1:] == ["abcdef123456", "1"]
            work.mkdir(parents=True)
            (work / "대본.json").write_text(json.dumps({"lines": []}), encoding="utf-8")
            return {"sid": "abcdef123456", "state": "plan_review", "topic_id": 7, "merged_preset": str(data / "make" / "s1" / "preset")}
        if args[0] == "approve":
            assert args[1:] == ["abcdef123456", "--by", "고객"]
            assert json.loads((work / "대본.json").read_text(encoding="utf-8"))["purpose"] == "calcopy"   # 피쉬 목소리 = 렌더 전에 purpose
            (work / "final.mp4").write_bytes(b"x")
            return {"sid": "abcdef123456", "state": "final_review"}
        raise AssertionError(args)

    started = []
    a = FD.member_task(job, RV, lambda o: None, {"X": "1"}, run=run, answerer=lambda q, stop, log: started.append(q))
    assert a == {"work_dir": "trial/t1_abcdef123456", "ok": True}
    assert calls == ["start", "choose", "approve"]
    assert (job / "trial" / "t1_abcdef123456" / "final.mp4").exists() and not work.exists()
    e = envs[0]
    assert e["CALCOPY_GEMINI_BACKEND"] == "client" and e["SHORTEM_LLM_QUEUE"] == str(data / "_q") and e["CALCOPY_DATA_DIR"] == str(data)
    assert json.loads(Path(e["CALCOPY_ORIGINALS_FILE"]).read_text(encoding="utf-8"))["channels"][0]["url"] == "https://www.youtube.com/@abc"
    assert started == [data / "_q"]


def test_member_task_fail_is_ok_false_with_why(tmp_path):
    job = _job(tmp_path)
    a = FD.member_task(job, RV, lambda o: None, {}, run=lambda args, env: {"sid": "abcdef123456", "state": "candidates", "candidates": []},
                       answerer=lambda q, stop, log: None)
    assert a["ok"] is False and a["work_dir"] == "" and "후보 0개" in a["why"]
    bad = {**RV, "meta": {**RV["meta"], "preset": {"slug": "my_t", "style": "틀", "dir": "../x"}}}
    assert FD.member_task(job, bad, lambda o: None, {}, run=None, answerer=lambda q, s, l: None)["ok"] is False


def test_queue_answerer_answers_request_with_claude_shape(tmp_path):
    q = tmp_path / "q"
    d = q / "r1"
    d.mkdir(parents=True)
    (d / "p00.jpg").write_bytes(b"j")
    (d / "request.json").write_text(json.dumps({"id": "r1", "tag": "draft", "tier": "haiku", "prompt": "대본 써",
                                                "parts": [{"kind": "image", "file": "p00.jpg"}, {"kind": "text", "text": "글"}]}), encoding="utf-8")
    seen = []

    def ask(prompt, cwd, add_dir, model, need):
        seen.append((prompt, model))
        return {"ok": 1}, ""
    stop = threading.Event()
    th = threading.Thread(target=FD._queue_answerer, args=(q, stop, lambda o: None), kwargs={"ask": ask}, daemon=True)
    th.start()
    for _ in range(50):
        if (d / "answer.json").exists():
            break
        stop.wait(0.1)
    stop.set()
    th.join(5)
    assert json.loads((d / "answer.json").read_text(encoding="utf-8")) == {"ok": 1}
    assert seen[0][1] == "opus"                       # 하이쿠 금지 — 모르는/하이쿠 등급은 opus
    assert "p00.jpg" in seen[0][0] and "글" in seen[0][0]
