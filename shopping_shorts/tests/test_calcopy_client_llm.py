"""고객 PC 모드 AI 창구(관제 234) — gemini_free.ask(BACKEND=client) → client_llm 줄 폴더 → 답.

2026-10-19 실측 결함을 시험으로 박는다:
  - 답을 쓰는 중(빈 파일)에 읽어 '틀린 답'으로 셌다 → 다 써진 뒤에만 읽는다
  - 틀린 모양의 답은 error.json 에 이유를 적고 다시 기다린다(RETRIES 넘으면 실패 이유를 돌려준다)
  - 고객 모드에서만 '고객'이 승인할 수 있다
"""
import json
import threading
import time

import pytest

from tools.calcopy.engine import client_llm as C


def _answer_when_ready(q, payload, delay=0.2, empty_first=False):
    def run():
        t0 = time.time()
        while time.time() - t0 < 10:
            for d in q.iterdir():
                if (d / "request.json").exists() and not (d / "answer.json").exists():
                    if empty_first:
                        (d / "answer.json").write_text("", encoding="utf-8")
                        time.sleep(0.3)
                    time.sleep(delay)
                    (d / "answer.json").write_text(payload, encoding="utf-8")
                    return
            time.sleep(0.05)
    th = threading.Thread(target=run, daemon=True)
    th.start()
    return th


def test_client_answer_roundtrip_and_image_part(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    _answer_when_ready(tmp_path, json.dumps({"items": [{"label": "자막 0", "lines": ["안녕"]}]}))
    d, err = C.ask([b"\xff\xd8fakejpeg", "라벨"], "읽어라", tag="ocr0")
    assert err is None and d["items"][0]["lines"] == ["안녕"] and d["_via"] == "client"
    req = json.loads(next(tmp_path.iterdir()).joinpath("request.json").read_text(encoding="utf-8"))
    assert [p["kind"] for p in req["parts"]] == ["image", "text"] and req["tier"] == "sonnet"


def test_empty_file_while_writing_is_not_counted_as_bad(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    _answer_when_ready(tmp_path, '{"ok": 1}', empty_first=True)
    d, err = C.ask([], "x", tag="t")
    assert err is None and d["ok"] == 1
    assert not list(next(tmp_path.iterdir()).glob("answer.bad*.json"))


def test_bad_answer_retries_then_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTEM_LLM_QUEUE", str(tmp_path))
    monkeypatch.setattr(C, "RETRIES", 0)

    def bad():
        t0 = time.time()
        while time.time() - t0 < 10:
            for d in tmp_path.iterdir():
                if (d / "request.json").exists() and not (d / "answer.json").exists() and not (d / "done").exists():
                    (d / "answer.json").write_text('"문자열"', encoding="utf-8")
                    return
            time.sleep(0.05)
    threading.Thread(target=bad, daemon=True).start()
    d, err = C.ask([], "x", tag="t")
    assert d is None and err.startswith("client_bad_answer")


def test_tier_of():
    assert C.tier_of("draft") == "opus" and C.tier_of("asr") == "haiku" and C.tier_of("mat0") == "sonnet"


def test_customer_mode_approve_gate(monkeypatch):
    import importlib
    from shopping_shorts import calcopy_make as MK
    monkeypatch.setenv("CALCOPY_CUSTOMER_MODE", "1")
    MK2 = importlib.reload(MK)
    assert MK2.CUSTOMER_MODE and MK2.CUSTOMER == "고객"
    monkeypatch.delenv("CALCOPY_CUSTOMER_MODE")
    MK3 = importlib.reload(MK)
    assert not MK3.CUSTOMER_MODE
    with pytest.raises(MK3.MakeError):
        MK3.approve("없는세션", by="고객")


def test_channel_candidates_picks_breakouts_only(tmp_path):
    """채널 기준 찾기: 확정 채널만, 조회 중앙값 1.5배 이상만, 배수 순, 이미 본 id 는 뺀다."""
    from tools.calcopy.engine import topic_find as TF
    f = tmp_path / "ch.json"
    f.write_text(json.dumps({"channels": [{"name": "가", "channel_id": "UCa", "verdict": "확정"},
                                          {"name": "나", "channel_id": "UCb", "verdict": "후보"}]}, ensure_ascii=False), encoding="utf-8")
    calls = []

    def stats(ref, n):
        calls.append(ref)
        return {"name": "가", "median_views": 1000, "videos": [
            {"id": "v1", "title": "평범한 편", "views": 1000}, {"id": "v2", "title": "터진 주걱 영상", "views": 9000},
            {"id": "v3", "title": "조금 터진 의자 영상", "views": 2000}, {"id": "v4", "title": "이미 만든 편", "views": 50000}]}
    c, failed = TF.channel_candidates(f, 5, {"v4"}, log=lambda m: None, stats=stats)
    assert calls == ["UCa"] and not failed
    assert [x["source"]["id"] for x in c] == ["v2", "v3"] and c[0]["source"]["kind"] == "채널"


def test_bench_seeds_channel_source_video(tmp_path):
    """채널 기준 후보의 벤치는 그 채널에서 터진 원본 편부터(검색 0건이어도 벤치 1편) — 10-19 실측 5후보 모두 벤치 0 결함."""
    from tools.calcopy.engine import topic_find as TF
    seen = []
    net = {"yt_search": lambda q, n, m: [], "yt_detail": lambda vid, n: (seen.append(vid) or {"id": vid, "url": f"https://www.youtube.com/shorts/{vid}", "title": "주걱", "views": 9, "comments": []})}
    llm = TF.LLM(lambda p, t: ({"points": [{"kind": "hook", "text": "주걱", "from": "v_SRC"}], "best_angle": "a"}, None), budget=5)
    c = {"id": "c1", "topic": "미국에서 터진 주걱 영상", "query": "주걱", "key": "채널:가", "source": {"kind": "채널", "id": "SRC"}}
    b = TF.bench(c, tmp_path, net, llm, 4)
    assert seen == ["SRC"] and b["points"]


def test_sfx_list_end_relative_and_missing_file(tmp_path, monkeypatch):
    """효과음 시각·파일 판단 한 곳(remake_video.sfx_list): 'end-0.2' 는 끝 기준, 빈 파일·없는 파일은 빼고 렌더는 계속."""
    from tools.calcopy import remake_video as RV
    f = tmp_path / "a.mp3"
    f.write_bytes(b"x")
    monkeypatch.setattr(RV, "ROOT", tmp_path)
    got = RV.sfx_list({"sfx": [{"file": "a.mp3", "t": "end-0.2", "db": -3}, {"file": None, "t": 0.0}, {"file": "없음.mp3", "t": 1}]}, 10.0)
    assert got == [(f, 9.8, -3.0)]


def test_title_text_fills_per_video_from_script():
    """제목 판단 한 곳: 틀 제목이 $per_video 면 대본 제목, 틀에 진짜 글이 있으면 그 글."""
    from tools.calcopy import remake_video as RV
    spec = {"layers": [{"kind": "text", "role": "title", "text": "$per_video"}]}
    assert RV.title_text(spec, {"title": "외국인이 역겹다는 한국 코팩\n범인은 따로"}) == "외국인이 역겹다는 한국 코팩\n범인은 따로"
    assert RV.title_text({"layers": [{"kind": "text", "role": "title", "text": "고정 제목"}]}, {"title": "x"}) == "고정 제목"
    assert RV.title_text(spec, {}) == ""


def test_merge_keeps_ad_disclosure():
    """채널명을 넣어도 '[광고]' 자리는 그대로(썰풀다 틀). 10-19 렌더 눈 확인 결함."""
    from shopping_shorts import calcopy_make as MK
    cfg = MK.merge_preset_pack("channel/sseolpulda/preset/A_흰바탕창/창아래_검정", {"brand": {"channel_name": "내 채널"}})
    texts = [L.get("text") for fr in MK._frames(cfg["frame"]) for L in fr.get("layers", []) if L.get("kind") == "text" and L.get("role") == "brand"]
    assert "[광고]" in texts and "내 채널" not in texts
