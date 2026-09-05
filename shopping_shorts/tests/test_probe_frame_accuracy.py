# -*- coding: utf-8 -*-
"""1단계 정확도 서버 실측 프로브(SSH 없이 관리자 API) — 순수 부분과 배선."""
import json
import os
import tempfile
from pathlib import Path

from shopping_shorts import probe_frame_accuracy as P


def test_summarize():
    s = P.summarize([{"classic_score": 0.8, "b1_score": 1.0, "b1_secs": 10},
                     {"classic_score": 0.9, "b1_score": 0.7, "b1_secs": 20},
                     {"classic_score": 0.5, "b1_score": 0.5, "b1_secs": 30},
                     {"classic_score": 0.6, "b1_error": "x"}])
    assert s["videos"] == 4 and s["b1_better"] == 1 and s["classic_better"] == 1 and s["tie"] == 1
    # 평균은 둘 다 판정된 3편에서만(리뷰 M2) — 4번째(b1 없음)는 unjudged
    assert s["compared"] == 3 and s["classic_avg"] == 0.733 and s["b1_avg"] == 0.733 and s["b1_fail"] == 1


def test_pick_sources_는_영상이_남아_있는_소스만_고른다():
    from shopping_shorts.store import Store
    d = tempfile.mkdtemp()
    st = Store(os.path.join(d, "t.db"))
    work = Path(d) / "work"
    ex = {"s0": {"segments": [{"start": 0, "end": 1, "scene_desc": "a"}]},
          "s1": {"segments": [{"start": 0, "end": 1, "scene_desc": "b"}]}}
    with st._conn() as c:
        c.execute("INSERT INTO mix_jobs(job_id, urls_json, target_seconds, structure, status, extract_json, created_at, updated_at) "
                  "VALUES('j1','[]',25,'template','done',?,'2026-09-05T00:00:00','2026-09-05T00:00:00')",
                  (json.dumps(ex),))
    (work / "j1" / "s0").mkdir(parents=True)
    (work / "j1" / "s0" / "s0.mp4").write_bytes(b"x")          # s0만 영상이 남아 있다
    got = P.pick_sources(st, work, n=10)
    assert [(g["job_id"], g["vid"]) for g in got] == [("j1", "s0")]
    assert got[0]["classic"] and got[0]["path"].endswith("s0.mp4")


def test_start_는_동시_1건(monkeypatch):
    import threading
    started = []
    monkeypatch.setattr(P, "_run", lambda *a: started.append(a) or threading.Event().wait(0.2))
    P._STATE.update(status="idle")
    assert P.start(None, "w", "o", n=5) is True
    assert P.start(None, "w", "o", n=5) is False      # 도는 중엔 거절
    assert P.state()["status"] == "running"
    import time; time.sleep(0.4)
    P._STATE.update(status="idle")


def test_api_배선(monkeypatch):
    import inspect
    from shopping_shorts import app as A
    src = inspect.getsource(A)
    assert '@app.post("/api/admin/probe/frame_accuracy")' in src and '@app.get("/api/admin/probe/frame_accuracy")' in src
    assert "_require_admin(request)" in inspect.getsource(A.api_admin_probe_frame_accuracy_start)


def test_summarize_는_둘_다_판정된_영상만_평균한다():
    s = P.summarize([{"classic_score": 0.8, "b1_score": 1.0}, {"classic_score": 1.0, "b1_score": None},
                     {"classic_score": None, "b1_score": 1.0}])
    assert s["compared"] == 1 and s["unjudged"] == 2 and s["classic_avg"] == 0.8 and s["b1_avg"] == 1.0


def test_판정_커버리지가_낮으면_점수를_안_믿는다(monkeypatch, tmp_path):
    from shopping_shorts import tag_qa_frames as T
    segs = [{"start": i, "end": i + 2, "scene_desc": f"d{i}"} for i in range(10)]
    monkeypatch.setattr(T, "_extract_frames", lambda v, picked, d: ([f"f{i}" for i, _ in picked], picked))
    monkeypatch.setattr(T, "_judge", lambda paths, kept: [{"image_no": 1, "verdict": "맞음"}, {"image_no": 2, "verdict": "맞음"}])
    score, n, counts = P._judge_all(segs, "v.mp4", str(tmp_path))
    assert score is None and n == 10 and counts["_judged"] == 2
    monkeypatch.setattr(T, "_judge", lambda paths, kept: [{"image_no": k + 1, "verdict": "맞음"} for k in range(9)])
    score2, _, counts2 = P._judge_all(segs, "v.mp4", str(tmp_path))
    assert score2 == 1.0 and counts2["_judged"] == 9


def test_라벨_일치_판정은_빈_묘사를_분모에서_빼고_키값을_돌려준다():
    from shopping_shorts import probe_frame_accuracy as P
    segs = [{"scene_desc": "손이 병뚜껑을 연다", "shot_role": "사용", "label": "뚜껑 열기"},
            {"scene_desc": "", "shot_role": "기타", "label": ""},
            {"scene_desc": "제품 정면", "shot_role": "제품", "label": "제품 소개"}]
    seen = {}

    def fake(prompt):
        seen["prompt"] = prompt
        return '{"items":[{"no":1,"role_ok":true,"label_ok":false},{"no":3,"role_ok":true,"label_ok":true}]}'
    assert P.judge_labels(segs, _call=fake) == (2, 1, 2)
    assert '"no": 2' not in seen["prompt"] and "판정 규칙" in seen["prompt"]
    assert P.judge_labels([], _call=fake) == (0, 0, 0)
    assert P.judge_labels(segs, _call=lambda p: "not json") == (0, 0, 2)


def test_summarize_에_라벨_백분율이_실린다():
    from shopping_shorts.probe_frame_accuracy import summarize
    rs = [{"classic_role_ok": 3, "classic_label_ok": 1, "classic_label_n": 4, "b1_role_ok": 4, "b1_label_ok": 4, "b1_label_n": 4},
          {"classic_role_ok": 1, "classic_label_ok": 1, "classic_label_n": 2, "b1_role_ok": 1, "b1_label_ok": 2, "b1_label_n": 2}]
    sm = summarize(rs)
    assert (sm["classic_role_pct"], sm["classic_label_pct"], sm["b1_role_pct"], sm["b1_label_pct"]) == (66, 33, 83, 100)
    assert summarize([{}])["b1_role_pct"] is None
