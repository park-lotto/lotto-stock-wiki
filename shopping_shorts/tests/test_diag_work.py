# -*- coding: utf-8 -*-
"""작업 진단(diag_work, 2026-09-05) — 오류 신고의 작업번호로 서버 상태 한 장을 SSH 없이 본다."""
import json
import os
import tempfile
from pathlib import Path


def test_work_번호로_잡_상태_계획_폴더_신고까지_한_장():
    from shopping_shorts.store import Store
    from shopping_shorts.app import diag_work
    d = tempfile.mkdtemp()
    st = Store(os.path.join(d, "t.db"))
    plan = {"generator": "inherit", "beats": [{"beat_idx": 0, "inherited": True, "tts_path": "x"}, {"beat_idx": 1}],
            "gate": {"skipped": "inherit"}}
    with st._conn() as c:
        c.execute("INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, status, error, extract_json, edit_plan_json, "
                  "given_script, script_structure_json, customer_id, created_at, updated_at) "
                  "VALUES('job1','[]',25,'template','failed','TTS 합성 실패: 키 없음',?,?,?,?,260,'t','t')",
                  (json.dumps({"s0": {"segments": [{"seg_id": "s0-0"}, {"seg_id": "s0-1"}]}}), json.dumps(plan),
                   "줄1\n줄2", json.dumps({"inherit_scenes": True, "beat_sources": [{"seg": "s0-0"}, {"seg": ""}]})))
        c.execute("INSERT INTO produce_works(work_id, customer_id, title, state_json, job_id, step, created_at, updated_at) "
                  "VALUES('w1',260,'테스트','{\"given_script\":\"줄1\\n줄2\"}','job1',3,'t','t')")
    st.add_bug_report(260, "3단계에서 계속 실패합니다", work_id="w1", step="3", console=["TypeError: x is null"])
    work = Path(d) / "work" / "job1" / "tts"
    work.mkdir(parents=True)
    (work / "beat_0.mp3").write_bytes(b"x")
    out = diag_work(st, "w1", Path(d) / "work")
    assert out["found"] and out["kind"] == "work" and out["job_id"] == "job1" and out["customer_id"] == 260
    j = out["job"]
    assert j["status"] == "failed" and "TTS 합성 실패" in j["error"]
    assert j["extract_sources"] == 1 and j["extract_segments"] == 2 and j["given_script_chars"] == 5
    assert j["script_structure"]["inherit_scenes"] is True and j["script_structure"]["beat_sources"] == 2
    assert j["plan"] == {"generator": "inherit", "beats": 2, "inherited": 1, "tts_files": 1, "gate": {"skipped": "inherit"}}
    assert out["work_dir"]["exists"] and out["work_dir"]["files_by_dir"] == {"tts": 1}
    assert out["bug_reports"] and "TypeError" in out["bug_reports"][0]["console"]
    # job 번호로 바로 넣어도 된다 / 없는 번호는 found False
    assert diag_work(st, "job1", Path(d) / "work")["found"] and diag_work(st, "nope", Path(d) / "work")["found"] is False
