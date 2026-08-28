"""칸 타임라인 ⑥ — 사용자 구절 경계 편집: caption_lines 저장 + 워드 타임스탬프 재계산.

재TTS 없이, mp3 옆 사이드카(align.json)의 실제 발화 시각으로 구절 초를 다시 계산한다.
어절 재배열(끊기/합치기)만 허용 — 글자가 바뀌면 422(대본 수정은 narration POST의 일).
"""
import json

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod

NARR = "마침 파티플래너인 친구가 추천해 주는데"
# 단어별 실제 발화 시각(초): 마침0.0 파티플래너인0.5 친구가1.5 추천해2.0 주는데2.6~3.2
_WORD_TIMES = [("마침", 0.0, 0.4), ("파티플래너인", 0.5, 1.4), ("친구가", 1.5, 1.9),
               ("추천해", 2.0, 2.5), ("주는데", 2.6, 3.2)]


def _alignment():
    chars, st, en = [], [], []
    for wi, (w, a, b) in enumerate(_WORD_TIMES):
        if wi:
            chars.append(" "); st.append(a); en.append(a)
        for ci, ch in enumerate(w):
            chars.append(ch)
            st.append(a + (b - a) * ci / len(w))
            en.append(a + (b - a) * (ci + 1) / len(w))
    return {"characters": chars, "character_start_times_seconds": st,
            "character_end_times_seconds": en}


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    # mp3 실파일 대신 길이만 고정 — 시각 계산은 사이드카가 진실이라 probe는 총길이만 준다
    monkeypatch.setattr(appmod.video_assemble, "_probe_duration", lambda p: 3.4)
    return TestClient(appmod.app)


def _job(tmp_path, with_align=True):
    mp3 = tmp_path / "beat_0.mp3"
    mp3.write_bytes(b"x")
    if with_align:
        (tmp_path / "beat_0.mp3.align.json").write_text(
            json.dumps(_alignment()), encoding="utf-8")
    s = appmod.Store(appmod.DB_PATH)
    s.create_mix_job("j", ["u"], 30, "free")
    s.update_mix_job("j", status="done")   # 진행 중 가드(409)에 안 걸리게
    s.update_mix_job("j", edit_plan={"beats": [{
        "beat_idx": 0, "role": "hook", "narration": NARR,
        "target_seconds": 3.4, "tts_path": str(mp3),
        "cap_durs": None, "cap_lead": 0.0, "caption_lines": None}]})
    return s


def test_split_recomputes_durs_from_words(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/mix/scene_lab/j/caption_lines/0",
               json={"lines": ["마침 파티플래너인", "친구가 추천해 주는데"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and len(d["captions"]) == 2
    # 경계는 실제 발화 시각: 구절1 = 마침(0.0)~친구가 직전 → 표시시간 ≈ 1.5초
    g1 = d["captions"][0]
    assert abs((g1["end"] - g1["start"]) - 1.5) < 0.35
    # 저장까지 됐나 — 다음 로드·렌더가 같은 경계를 쓴다
    beat = appmod.Store(appmod.DB_PATH).get_mix_job("j")["edit_plan"]["beats"][0]
    assert beat["caption_lines"] == ["마침 파티플래너인", "친구가 추천해 주는데"]
    assert beat["cap_durs"] and len(beat["cap_durs"]) == 2


def test_text_change_rejected(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/mix/scene_lab/j/caption_lines/0",
               json={"lines": ["대본에 없는 문장"]})
    assert r.status_code == 422


def test_no_alignment_409(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path, with_align=False)
    r = c.post("/api/mix/scene_lab/j/caption_lines/0",
               json={"lines": ["마침 파티플래너인", "친구가 추천해 주는데"]})
    assert r.status_code == 409
