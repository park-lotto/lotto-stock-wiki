# -*- coding: utf-8 -*-
"""topic_find — 고객이 준 틱톡·인스타 영상이 첫 벤치(관제 234) · 검색은 넉넉히 받아 60초로 거른다(10-20 실측 0편 결함)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import topic_find as T  # noqa: E402


def _llm(prompt, tag):
    return {"points": [{"text": "귀찮음 공감", "from": "v_ref", "kind": "pain"}], "best_angle": "귀찮음"}, None


def test_ref_video_is_first_bench_even_when_search_is_empty(tmp_path):
    calls = []
    net = {"yt_search": lambda q, n, m: [{"id": None, "fallback": "0편"}],
           "yt_detail": lambda vid, n, url=None: calls.append((vid, url)) or {"id": vid, "url": url, "title": "파스타 쿠커 후기", "description": "", "comments": []}}
    c = {"id": "c1", "topic": "🍝직접 써본 전자레인지 파스타 쿠커 후기! 요리하기 귀찮은데...", "query": "x", "key": "",
         "source": {"kind": "참고영상", "url": "https://www.tiktok.com/@a/video/1"}}
    b = T.bench(c, tmp_path, net, _llm, 4, limits=T.Limits())
    assert calls == [("ref", "https://www.tiktok.com/@a/video/1")]
    assert [v["id"] for v in b["videos"]] == ["ref"] and b["points"], b["failed"]
    assert b["videos"][0]["relevance"] == "고객이 준 영상"


def test_youtube_topic_without_ref_still_needs_search(tmp_path):
    net = {"yt_search": lambda q, n, m: [], "yt_detail": lambda vid, n, url=None: {"id": vid}}
    b = T.bench({"id": "c1", "topic": "t", "query": "q", "key": "", "source": {}}, tmp_path, net, _llm, 4, limits=T.Limits())
    assert b["videos"] == [] and not b["points"]


def test_search_overfetches_then_keeps_short_ones(monkeypatch):
    got = {}

    def fake_flat(cmd, timeout):
        got.setdefault("cmd", cmd)
        rows = [178, 213, 103, 167, 75, 26, 71, 175, 53, 43]           # 10-20 실측 '전자레인지 파스타 쿠커' 앞 10편 길이
        return [{"id": f"v{i}", "duration": float(d), "views": 1, "title": "t", "channel": None, "url": ""} for i, d in enumerate(rows)], None
    monkeypatch.setattr(T, "_flat", fake_flat)
    out = T.yt_search("전자레인지 파스타 쿠커", 4, None)
    assert got["cmd"][got["cmd"].index("-I") + 1] == "1:16"
    assert [v["duration"] for v in out] == [26.0, 53.0, 43.0]
