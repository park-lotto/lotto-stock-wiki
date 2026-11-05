# -*- coding: utf-8 -*-
"""G10 원본 추적(관제 319) — 클립 채널 소재 편은 원 출처를 찾은 것만 후보, 벤치 편은 소재·재료가 아니다.
실측 근거(11-06): 스냅봤니 h3RPb5yZ9Ew 설명란 '원본 출처: ＠glitter_esther' · 벤치 3편 설명란엔 출처 없음."""
import json

from tools.calcopy.hybrid import origin_trace as OT
from tools.calcopy.hybrid import rules as RU
from tools.calcopy.engine import topic_find as TF

DESC_H = "글리터댄스 크리에이터님께 감사드리며\n 원본 출처: ＠glitter_esther\n 이 영상의 모든 저작권은 원작자님께 있습니다."


def test_refs_of_handle_and_url():
    assert OT.refs_of(DESC_H) == [{"kind": "handle", "handle": "glitter_esther"}]
    r = OT.refs_of("출처 https://www.tiktok.com/@abc/video/7703498440872856884 감사")
    assert r[0] == {"kind": "url", "url": "https://www.tiktok.com/@abc/video/7703498440872856884"}
    assert OT.refs_of("스냅봤니: 귀여운 아기들 일상") == []


def test_trace_rejects_bench_and_no_source():
    d = {"desc": lambda u: {"description": "출처 없음 설명"}}
    assert OT.trace({"id": "Z956odeOZvM"}, ["Z956odeOZvM"], deps=d)["why"].startswith("벤치 편 자체")
    r = OT.trace({"id": "gMKpXMWssTo"}, ["Z956odeOZvM"], deps=d)
    assert not r["ok"] and "원 출처" in r["why"]


def test_trace_handle_finds_same_video(tmp_path):
    cands = [{"key": "1", "url": "https://www.tiktok.com/@glitter_esther/video/1", "duration": 30},
             {"key": "2", "url": "https://www.tiktok.com/@glitter_esther/video/2", "duration": 58}]
    tried = []
    d = {"desc": lambda u: {"description": DESC_H, "duration": 28},
         "list": lambda u: (tried.append(u), cands if "tiktok" in u else [])[1],
         "seed": lambda u, wd: ["s1.jpg"],
         "judge": lambda seed, cs, wd, log: {"1": False, "2": True}}
    r = OT.trace({"id": "h3RPb5yZ9Ew", "url": "https://www.youtube.com/shorts/h3RPb5yZ9Ew"}, ["Z956odeOZvM"], work=tmp_path, deps=d)
    assert r["ok"] and r["origin_url"].endswith("/video/2") and tried[0] == "https://www.tiktok.com/@glitter_esther"


def test_channel_candidates_clip_channel_keeps_only_traced(tmp_path):
    f = tmp_path / "o.json"
    f.write_text(json.dumps({"bench_ids": ["Z956odeOZvM"], "channels": [{"platform": "youtube", "url": "https://www.youtube.com/@x", "role": "bench"}]}), encoding="utf-8")
    vids = [{"id": "Z956odeOZvM", "title": "유치원 학예회 리허설", "views": 900}, {"id": "h3RPb5yZ9Ew", "title": "동대문 시장 아침 줌바", "views": 800},
            {"id": "gMKpXMWssTo", "title": "할머니 식당 반전", "views": 700}, {"id": "aaaaaaaaaaa", "title": "보통", "views": 10}]
    st = lambda ref, n: {"median_views": 100, "name": "스냅", "videos": vids}

    def tr(v, bench_ids, log=print):
        if v["id"] in bench_ids:
            return {"ok": False, "why": "벤치 편 자체"}
        return {"ok": True, "origin_url": "https://www.tiktok.com/@g/video/2", "how": "t"} if v["id"] == "h3RPb5yZ9Ew" else {"ok": False, "why": "출처 없음"}
    cands, failed = TF.channel_candidates(f, 5, set(), log=lambda m: None, stats=st, trace=tr)
    assert [c["source"]["id"] for c in cands] == ["h3RPb5yZ9Ew"]
    assert cands[0]["source"]["kind"] == "원본추적" and cands[0]["source"]["origin_url"].endswith("/video/2")
    assert {x["where"] for x in failed} >= {"원본 추적 Z956odeOZvM", "원본 추적 gMKpXMWssTo"}


def test_source_rule_static_rejects_bench_ids():
    M = {"cuts": {"L1": [{"src": "src_Z956odeOZvM.mp4", "face": "없음"}], "L2": [{"src": "origin_2.mp4", "face": "없음"}]}}
    bad = RU.source_rule_static(M, {"origin_2.mp4"}, "", {}, bench_ids=["Z956odeOZvM"])
    assert len(bad) == 1 and bad[0].startswith("L1") and "벤치" in bad[0]


def test_list_and_desc_survive_ytdlp_null(monkeypatch):
    """yt-dlp 가 추출 실패 때 stdout 'null' 을 찍는다(11-06 실측 틱톡 @glitter_esther) — trace 가 터지지 않고 이유를 남긴다."""
    import subprocess as SP

    class R:
        stdout, stderr, returncode = "null", "ERROR: Unable to extract secondary user ID", 1
    monkeypatch.setattr(SP, "run", lambda *a, **k: R())
    assert OT._list("https://www.tiktok.com/@x") == []
    assert "secondary user ID" in OT._desc("https://www.youtube.com/shorts/aaaaaaaaaaa")["error"]


# ── 같은 영상 판정 = 프레임 대조(관제 319 11-06 감시 적발) ──────────────────────────
# 실사고: judge_same 눈(썸네일 한 장)이 벤치 h3RPb5yZ9Ew 의 원본을 같은 가게 다른 편(@glitter_esther DeaeUEbzy6E '2탄')으로 골랐다.
#   실측: 벤치→그 릴스 0.8 넘는 프레임 0/28 · 우리 1차(그 릴스 재편집)→릴스 0.52 · 같은 가게 다른 편 CZdHXV0nfGw→릴스 0.00
import io
from pathlib import Path

import pytest

from tools.calcopy import origin_find as OF

SNAP = Path("C:/t/kal_snap")
_B = SNAP / "origin/work_ig/h3RPb5yZ9Ew/seed/v.mp4"
_O = SNAP / "material/origin_DeaeUEbzy6E.mp4"
_U = SNAP / "out/숏템스냅_남대문스카프_1차.mp4"
_C = SNAP / "data/snapbwatni/src/CZdHXV0nfGw.mp4"


@pytest.mark.skipif(not (_B.exists() and _O.exists() and _U.exists() and _C.exists()), reason="스냅봤니 실측 영상 없음(CH PC 전용)")
def test_frame_match_three_way_on_snap_samples():
    """11-06 재조정(장부 표본 같음 21·다름 37 — C:/t/fm_jev/fm_table_seedpairs.json): 확정은 '같음'만, 못 잡으면 '미확정'(다름 아님)."""
    assert OF.frame_match(_B, _O)["verdict"] == "unconfirmed"    # 같은 가게 다른 편(오판 사례) — 프레임으로는 '다름'을 증명 못 한다
    assert OF.frame_match(_C, _O)["verdict"] == "unconfirmed"
    r = OF.frame_match(_U, _O)                                  # 같은 촬영분 재편집
    assert r["verdict"] == "same" and r["hits"] >= OF.FRAME_MIN_HITS


def test_frame_verdict_rule():
    """판정식 한 곳: 0.8 넘는 씨앗 프레임 5개 이상 = 같음 확정, 그 밖 = 미확정(다른 편 37짝 최대 4프레임 · 같음 쪽 0~4프레임 11짝이 겹친다)."""
    import numpy as np
    assert OF.frame_verdict(np.array([0.81] * 5 + [0.1] * 50))["verdict"] == "same"
    v = OF.frame_verdict(np.array([0.81] * 4 + [0.1] * 50))
    assert v["verdict"] == "unconfirmed" and v["hits"] == 4 and v["share"] == round(4 / 54, 3)


def _jpeg():
    from PIL import Image
    b = io.BytesIO(); Image.new("RGB", (40, 70), "gray").save(b, "JPEG"); return b.getvalue()


def _judge_env(tmp_path, monkeypatch, eye_same):
    import urllib.request
    from PIL import Image
    from tools.calcopy.engine import claude_cli as CC
    s = tmp_path / "seed"; s.mkdir(); Image.new("RGB", (40, 70), "white").save(s / "f15.jpg")

    class Resp:
        def read(self):
            return _jpeg()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Resp())
    monkeypatch.setattr(CC, "ask", lambda parts, prompt, tag="", model=None: ({"same": eye_same, "why": "같은 가게"}, None))
    return s / "f15.jpg"


def test_judge_same_frame_unconfirmed_keeps_eye_with_alarm(tmp_path, monkeypatch):
    """프레임이 못 잡으면 '다름'이 아니라 미확정 — 눈 판정(같음)을 유지하고 경보 + 후보에 verdict 기록(11-06 사장님 지시 · Jev q1c fix_0)."""
    img = _judge_env(tmp_path, monkeypatch, [1, 2])
    cands = [{"key": "a", "url": "u/a", "thumb": "http://t/a"}, {"key": "b", "url": "u/b", "thumb": "http://t/b"}, {"key": "c", "url": "u/c", "thumb": "http://t/c"}]
    seen, logs = [], []

    def confirm(seed, v, d):
        seen.append(v["key"])
        return {"verdict": "same" if v["key"] == "b" else "unconfirmed", "hits": 6 if v["key"] == "b" else 0, "share": 0.0}
    out = OF.judge_same([img], cands, tmp_path, log=logs.append, confirm=confirm)
    assert out == {"a": True, "b": True, "c": False}
    assert seen == ["a", "b"]                                    # 눈이 '다름'이라 한 c 는 받지 않는다(비용)
    assert cands[0]["frame_match"]["verdict"] == "unconfirmed" and cands[1]["frame_match"]["verdict"] == "same"
    assert any("경보" in x and "a" in x for x in logs)


def test_judge_same_frames_unavailable_keeps_eye_with_alarm(tmp_path, monkeypatch):
    """후보 영상을 못 받아도(confirm None) 미확정 — 눈 판정 유지 + 경보(인스타 받기 고장으로 원본을 통째로 버리지 않는다)."""
    img = _judge_env(tmp_path, monkeypatch, [1])
    logs = []
    c = [{"key": "a", "url": "u/a", "thumb": "http://t/a"}]
    out = OF.judge_same([img], c, tmp_path, log=logs.append, confirm=lambda *a: None)
    assert out == {"a": True} and c[0]["frame_match"]["verdict"] == "unconfirmed"
    assert any("경보" in x for x in logs)
