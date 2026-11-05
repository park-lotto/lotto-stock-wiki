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
