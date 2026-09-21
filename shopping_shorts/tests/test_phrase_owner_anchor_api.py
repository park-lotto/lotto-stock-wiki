# -*- coding: utf-8 -*-
"""자막 줄 저장 API를 **실제 입구 그대로** 눌러, 맞춰 둔 장면이 안 밀리는지 본다(2026-09-21).

단위 규칙은 test_phrase_owner_anchor.py. 여기는 배선이다:
  · /caplines 가 줄을 바꾸기 **전에** 짝을 얼리는가(자막 단계·장면꾸미기·믹스 타임라인 공용 입구)
  · 응답·GET이 싣는 captions에 owner가 붙는가(화면은 계산 안 하고 이 값을 쓴다)
  · 얼리기만으로는 멀쩡한 완성본이 무효가 되지 않는가 / 유료 청소본 서명이 안 바뀌는가
"""
from fastapi.testclient import TestClient

from shopping_shorts import app as appmod
from shopping_shorts import mix_pipeline, video_assemble as va

NARR = "웬 키친타월인가 했더니, 기름때 낀 프라이팬을 쓱 닦아내는 항균 행주더라고요."
L3 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는 항균 행주더라고요"]
L4 = ["웬 키친타월인가 했더니", "기름때 낀 프라이팬을", "쓱 닦아내는", "항균 행주더라고요"]
OVER = [{"video_id": "s2", "seg_id": "film_s2_30.23_31.63", "start": 30.23, "end": 31.63},
        {"video_id": "s5", "seg_id": "film_s5_3.55_4.85", "start": 3.55, "end": 4.85},
        {"video_id": "s2", "seg_id": "film_s2_33.76_34.80", "start": 33.76, "end": 34.80}]


def _client(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod.video_assemble, "_probe_duration", lambda p: 4.46)
    monkeypatch.setattr(appmod.mix_pipeline, "_probe_duration", lambda p: 4.46)
    monkeypatch.setattr(appmod.mix_pipeline.asr_check, "transcribe_words", lambda p: None)
    return TestClient(appmod.app)


def _job(tmp_path, lines=L3, **beat_kw):
    mp3 = tmp_path / "beat_0.mp3"
    mp3.write_bytes(b"x")
    beat = {"beat_idx": 0, "role": "body", "narration": NARR, "target_seconds": 4.46,
            "tts_path": str(mp3), "cap_durs": None, "cap_lead": 0.0,
            "caption_lines": list(lines), "caption_lines_human": True,
            "phrase_sync": True, "scene_override": [dict(s) for s in OVER]}
    beat.update(beat_kw)
    s = appmod.Store(appmod.DB_PATH)
    s.create_mix_job("j", ["u"], 30, "free")
    s.update_mix_job("j", status="done", video_path="/tmp/final.mp4", edit_plan={"beats": [beat]})
    return s


def _beat():
    return appmod.Store(appmod.DB_PATH).get_mix_job("j")["edit_plan"]["beats"][0]


def test_자막단계에서_마지막줄을_나눠도_둘째줄_장면이_안_밀린다(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/produce/mix/j/caplines", json={"beat_idx": 0, "lines": L4})
    assert r.status_code == 200, r.text
    caps = r.json()["captions"]
    assert [x["owner"] for x in caps] == [0, 1, 2, 2], caps
    assert {x["owner_n"] for x in caps} == {3}
    b = _beat()
    assert b["caption_lines"] == L4 and b.get("clip_anchor"), "짝이 DB에 남아야 렌더가 쓴다"
    plan = va._plan_phrase_clips(b, va._beat_material(b), 4.46)
    assert [x["video_id"] for x in plan] == ["s2", "s5", "s2", "s2"]
    # GET(믹스 화면이 여는 데이터)도 같은 값을 싣는다 — 같은 함수(_lab_captions)
    caps2, _ = appmod._lab_captions(appmod.Store(appmod.DB_PATH).get_mix_job("j")["edit_plan"])
    assert [x["owner"] for x in caps2["0"]] == [0, 1, 2, 2]


def test_자동으로_되돌려도_짝은_남는다(tmp_path, monkeypatch):
    c = _client(tmp_path, monkeypatch)
    _job(tmp_path)
    r = c.post("/api/produce/mix/j/caplines", json={"beat_idx": 0, "reset": True})
    assert r.status_code == 200, r.text
    b = _beat()
    n = len(va._caption_segments(NARR, None))
    own = va.phrase_owners(b, 3)
    assert len(own) == n and own[0] == 0 and own == sorted(own)
    # 「기름때 낀 프라이팬을」로 시작하는 구절은 여전히 닦는 장면(조각 1)이 덮는다
    segs = va._caption_segments(NARR, None)
    k = next(i for i, s in enumerate(segs) if s.startswith("기름때"))
    assert own[k] == 1, (segs, own)


def test_얼리기만으로는_완성본이_무효가_안_된다(tmp_path, monkeypatch):
    _client(tmp_path, monkeypatch)
    s = _job(tmp_path, lines=L4)             # 옛 job: 짝 없음, 완성본 있음
    job = s.get_mix_job("j")
    plan = job["edit_plan"]
    appmod._freeze_clip_anchors(plan)        # 믹스에서 열어 저장만 한 것과 같다
    assert plan["beats"][0].get("clip_anchor")
    changed = appmod._save_render_inputs(s, "j", edit_plan=plan)
    after = s.get_mix_job("j")
    assert changed is False and after["status"] == "done" and after["video_path"] == "/tmp/final.mp4"
    assert after["edit_plan"]["beats"][0].get("clip_anchor"), "그래도 짝은 저장된다"


def test_유료_청소본_서명_옛job은_불변_짝이_다르면_달라진다():
    legacy = {"narration": NARR, "caption_lines": list(L4), "phrase_sync": True,
              "scene_override": [dict(s) for s in OVER], "target_seconds": 4.46}
    sig_legacy = mix_pipeline._plan_signature({"beats": [dict(legacy)]})
    frozen_same = dict(legacy)
    va.ensure_clip_anchor(frozen_same)       # 종전 식 그대로 얼림 → 그림 같음
    assert mix_pipeline._plan_signature({"beats": [frozen_same]}) == sig_legacy
    fixed = dict(legacy, caption_lines=list(L3))
    va.ensure_clip_anchor(fixed)             # 3줄=3장면으로 1:1 얼린 뒤
    fixed["caption_lines"] = list(L4)        # 마지막 줄을 나눔 → 짝 [0,1,2,2]
    assert mix_pipeline._plan_signature({"beats": [fixed]}) != sig_legacy, \
        "짝이 다른데 서명이 같으면 옛 배정의 청소본이 재사용된다"
