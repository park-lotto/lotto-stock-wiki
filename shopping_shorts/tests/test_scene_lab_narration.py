# -*- coding: utf-8 -*-
"""3단계 대본 수정(2026-08-17 사장님) — POST /api/mix/scene_lab/{job}/narration/{beat}.

왜 생겼나: 3단계에서 자막을 보다가 몇 글자 고치려면 **2단계를 왕복**해야 했다.
화면엔 편집 장치가 다 있었는데(scene_lab.html NARR/editNarr) 라이브에선 잠겨 있었고,
안내가 가리키는 "① 새 대본 고르기"는 9단계 개편에서 감춰져(produce.html #mixScriptPick
display:none) **앱 어디에서도 대본을 못 고치는 상태**였다.

계약:
  ① 고친 문장을 edit_plan.beats[i].narration 에 저장한다
  ② 옛 문장 기준 자막 타이밍(cap_durs·cap_lead·caption_lines)은 **전부 버린다**
     — 안 버리면 구절 수가 안 맞아 자막이 중간에서 끊긴다
  ③ 음성·자막 재생성은 **이미 있던** resynth_one_beat 을 예약한다(새로 만들지 않는다)
  ④ 생성·렌더 중엔 409 (apply·tts_regen과 같은 가드)
  ⑤ 빈 문장 422 / 없는 비트 404 / 안 바뀌면 unchanged
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

_SEGS = [
    {"seg_id": "s0-0", "start": 0.0, "end": 2.0, "text": "a", "scene_desc": "반죽"},
    {"seg_id": "s0-1", "start": 2.0, "end": 4.5, "text": "b", "scene_desc": "완성"},
]
_OLD = "아침, 풍신, 빵, 나도 중 댓글 남겨주시면"


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", tmp_path / "work")
    return TestClient(app_module.app), Store(db)


def _seed(store, job_id="j1", status="ready_for_review"):
    store.create_mix_job(job_id, ["u0"], 20, "free")
    store.update_mix_job(
        job_id, status=status, voice={"voice_id": "v1", "speed": 1.0},
        extract={"s0": {"video_id": "s0", "full_text": "x", "segments": _SEGS}},
        edit_plan={
            "structure": "free", "plagiarism_flags": [],
            "beats": [{"beat_idx": 0, "role": "cta", "narration": _OLD,
                       "target_seconds": 9.7,
                       # 옛 문장 기준 잔재 — 저장 시 지워져야 한다
                       "cap_durs": [1.0, 2.0, 3.0], "cap_lead": 0.4,
                       "caption_lines": ["아침,", "풍신,", "빵, 나도 중 댓글 남겨주시면"],
                       "primary": {"video_id": "s0", "seg_id": "s0-1",
                                   "start": 2.0, "end": 4.5},
                       "alternates": [], "effect": "cut"}]})
    return job_id


def _url(job="j1", beat=0):
    return f"/api/mix/scene_lab/{job}/narration/{beat}"


def test_대본을_저장한다(monkeypatch, tmp_path):
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    new = "궁금하시면 댓글 남겨주세요, 비법 링크 보내드릴게요."
    r = c.post(_url(), json={"text": new, "regen": False})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
    b = store.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert b["narration"] == new


def test_옛_자막타이밍을_버린다(monkeypatch, tmp_path):
    """cap_durs·caption_lines가 남으면 구절 수가 안 맞아 자막이 끊긴다."""
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    c.post(_url(), json={"text": "짧게 고친 문장이에요.", "regen": False})
    b = store.get_mix_job("j1")["edit_plan"]["beats"][0]
    assert b["cap_durs"] is None, "옛 표시시간이 남았다"
    assert b["cap_lead"] == 0.0
    assert b["caption_lines"] is None, "옛 호흡 줄이 남았다"


def test_regen이_기본이면_재생성을_예약한다(monkeypatch, tmp_path):
    """★음성·자막은 새로 만들지 않고 이미 있는 resynth_one_beat을 쓴다."""
    called = {}

    def fake(job_id, beat_idx, voice, db, work):
        called.update(job=job_id, beat=beat_idx, voice=voice)

    monkeypatch.setattr(app_module, "resynth_one_beat", fake)
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    r = c.post(_url(), json={"text": "고친 문장입니다."})     # regen 생략 = 기본 True
    assert r.status_code == 200, r.text
    assert r.json()["regen"] is True
    assert called.get("beat") == 0 and called.get("job") == "j1"
    # job의 voice 스냅샷을 물려줘야 이 비트만 소리가 달라지지 않는다
    assert called.get("voice", {}).get("voice_id") == "v1"


def test_regen_false면_예약하지_않는다(monkeypatch, tmp_path):
    called = {}
    monkeypatch.setattr(app_module, "resynth_one_beat",
                        lambda *a, **k: called.setdefault("hit", True))
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    r = c.post(_url(), json={"text": "고친 문장입니다.", "regen": False})
    assert r.json()["regen"] is False
    assert "hit" not in called


def test_생성_렌더_중엔_409(monkeypatch, tmp_path):
    c, store = _client(monkeypatch, tmp_path)
    _seed(store, status="rendering")
    r = c.post(_url(), json={"text": "고친 문장입니다."})
    assert r.status_code == 409
    # 대본이 바뀌지 않았어야 한다
    assert store.get_mix_job("j1")["edit_plan"]["beats"][0]["narration"] == _OLD


def test_빈_문장은_422(monkeypatch, tmp_path):
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    assert c.post(_url(), json={"text": "   "}).status_code == 422
    assert store.get_mix_job("j1")["edit_plan"]["beats"][0]["narration"] == _OLD


def test_없는_비트는_404(monkeypatch, tmp_path):
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    assert c.post(_url(beat=9), json={"text": "고친 문장"}).status_code == 404


def test_없는_작업은_404(monkeypatch, tmp_path):
    c, _ = _client(monkeypatch, tmp_path)
    assert c.post(_url(job="nope"), json={"text": "고친 문장"}).status_code == 404


def test_안_바뀌면_unchanged(monkeypatch, tmp_path):
    """같은 문장을 다시 보내면 재생성을 걸지 않는다(헛돈·헛시간 방지)."""
    called = {}
    monkeypatch.setattr(app_module, "resynth_one_beat",
                        lambda *a, **k: called.setdefault("hit", True))
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    r = c.post(_url(), json={"text": _OLD})
    assert r.json().get("unchanged") is True
    assert "hit" not in called


def test_저장한_대본이_새_자막으로_계산된다(monkeypatch, tmp_path):
    """GET이 고친 문장 기준으로 자막을 다시 나눠 준다(옛 preset에 안 묶인다)."""
    c, store = _client(monkeypatch, tmp_path)
    _seed(store)
    c.post(_url(), json={"text": "궁금하시면 댓글 남겨주세요.", "regen": False})
    d = c.get("/api/mix/scene_lab/j1").json()
    assert d["ok"] is True
    caps = d["data"]["captions"]["0"]
    joined = "".join(x["text"] for x in caps).replace(" ", "")
    assert "풍신" not in joined, f"옛 문장 자막이 남았다: {caps}"
    assert "궁금하시면" in joined
