"""칸 타임라인 ⑥⑦a — 구절 경계 편집은 **기존** caplines API 한 벌로(0순위-B).

2026-08-29: 처음엔 별도 라우트를 만들었다가 `/api/produce/mix/{job}/caplines`(08-25)가
같은 일(경계 검증→저장→타이밍 재계산)을 이미 하는 걸 발견하고 그쪽을 확장했다.
여기서 검증하는 확장분: ①응답에 새 시간표(captions — GET과 같은 _lab_captions)
②cap_src(정밀/받아쓰기/추정) 기록.
"""
import json

from fastapi.testclient import TestClient

from shopping_shorts import app as appmod

NARR = "마침 파티플래너인 친구가 추천해 주는데"
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
    monkeypatch.setattr(appmod.video_assemble, "_probe_duration", lambda p: 3.4)
    monkeypatch.setattr(appmod.mix_pipeline, "_probe_duration", lambda p: 3.4)
    # ASR 폴백이 외부 호출로 새지 않게 — 사이드카 없으면 estimate로 떨어져야 한다
    monkeypatch.setattr(appmod.mix_pipeline.asr_check, "transcribe_words", lambda p: None)
    return TestClient(appmod.app)


def _job(tmp_path, with_align=True):
    mp3 = tmp_path / "beat_0.mp3"
    mp3.write_bytes(b"x")
    if with_align:
        (tmp_path / "beat_0.mp3.align.json").write_text(
            json.dumps(_alignment()), encoding="utf-8")
    s = appmod.Store(appmod.DB_PATH)
    s.create_mix_job("j", ["u"], 30, "free")
    s.update_mix_job("j", status="done")
    s.update_mix_job("j", edit_plan={"beats": [{
        "beat_idx": 0, "role": "hook", "narration": NARR,
        "target_seconds": 3.4, "tts_path": str(mp3),
        "cap_durs": None, "cap_lead": 0.0, "caption_lines": None}]})
    return s


def test_split_recomputes_and_returns_timetable(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/produce/mix/j/caplines",
               json={"beat_idx": 0, "lines": ["마침 파티플래너인", "친구가 추천해 주는데"]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["ok"] and d["timed"] and d["cap_src"] == "precise"
    assert len(d["captions"]) == 2
    g1 = d["captions"][0]
    # 경계 = 친구가의 실제 시작(1.5초) 언저리
    assert abs((g1["end"] - g1["start"]) - 1.5) < 0.35
    beat = appmod.Store(appmod.DB_PATH).get_mix_job("j")["edit_plan"]["beats"][0]
    assert beat["caption_lines"] == ["마침 파티플래너인", "친구가 추천해 주는데"]
    assert beat["cap_src"] == "precise" and len(beat["cap_durs"]) == 2


def test_text_change_rejected(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/produce/mix/j/caplines",
               json={"beat_idx": 0, "lines": ["대본에 없는 문장"]})
    assert r.status_code == 422


def test_no_alignment_falls_to_estimate(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path, with_align=False)
    r = c.post("/api/produce/mix/j/caplines",
               json={"beat_idx": 0, "lines": ["마침 파티플래너인", "친구가 추천해 주는데"]})
    assert r.status_code == 200
    d = r.json()
    # 조용히 실패하던 자리 — 이제 단계가 보인다: 추정 폴백 + timed False
    assert d["ok"] and d["timed"] is False and d["cap_src"] == "estimate"
    # 시간표는 글자수 폴백으로라도 나온다(화면이 비지 않게)
    assert len(d["captions"]) == 2


def test_asr_fallback_marks_cap_src(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path, with_align=False)
    words = [{"word": w, "start": a, "end": b} for w, a, b in _WORD_TIMES]
    monkeypatch.setattr(appmod.mix_pipeline.asr_check, "transcribe_words", lambda p: words)
    r = c.post("/api/produce/mix/j/caplines",
               json={"beat_idx": 0, "lines": ["마침 파티플래너인", "친구가 추천해 주는데"]})
    d = r.json()
    assert r.status_code == 200 and d["ok"] and d["timed"] and d["cap_src"] == "asr"
