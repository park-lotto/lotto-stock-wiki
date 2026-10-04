# -*- coding: utf-8 -*-
"""관제 117 — AI 장면은 프롬프트(한글·영어)를 보여 주고 확인한 뒤에만 만든다. 출발 화면은 그 칸에 담은 조각.

사장님 2026-10-04: "어떤 프롬프트로 하는지 한글과 영어를 같이 보여주고 / 기존 영상 조각을 활용 / 출발 장면·초 선택 /
대본 흐름에 맞게 초안, 방향을 바꿀 수 있게 / 영어는 수정 못 하게 / 사물·환경·카메라 각도·효과 등 아주 구체적으로"."""
import importlib.util
import json
from pathlib import Path

import pytest

from shopping_shorts import ai_scene as ai
from shopping_shorts import app as A

_P = Path(__file__).resolve().parent / "test_ai_scene.py"
_sp = importlib.util.spec_from_file_location("_ais_base", str(_P))
B = importlib.util.module_from_spec(_sp)
_sp.loader.exec_module(B)

RICH = {"subject_desc_en": "A grey finger-chopstick clip worn on two fingers, holding one chip.",
        "environment_en": "A desk with an RGB keyboard, lit from the left by a window.",
        "camera_en": "Close-up, slightly high angle, slow push-in.",
        "effects_en": "A soft focus pull from the chip to the clip.",
        "motion_steps_en": ["The fingers lift the chip.", "The chip moves toward the camera.", "The hand holds still."],
        "subject_desc_ko": "두 손가락에 낀 회색 손가락 젓가락이 과자 한 개를 집고 있다.",
        "environment_ko": "RGB 키보드가 있는 책상, 왼쪽 창에서 빛이 든다.",
        "camera_ko": "클로즈업, 살짝 높은 각도, 천천히 다가간다.",
        "effects_ko": "과자에서 집게로 초점이 부드럽게 옮겨 간다.",
        "motion_steps_ko": ["손가락이 과자를 들어 올린다.", "과자가 카메라 쪽으로 온다.", "손이 그대로 멈춘다."]}
SRCS = {"s0": "S0.mp4", "s2": "S2.mp4"}


def _setup(tmp_path, monkeypatch):
    work = tmp_path / "j"
    job = B._job(work)
    store = B._Store(job)
    B._patch_common(monkeypatch, tmp_path, store)
    return work, job, store


def _shot(monkeypatch):
    seen = {}

    def fake(src, t, out):
        seen.update(src=src, t=t)
        Path(out).write_bytes(b"p")
        return str(out)
    monkeypatch.setattr(ai, "extract_frame", fake)
    return seen


def test_초안은_그_칸_조각에서_출발하고_한글_영어를_같이_준다(tmp_path, monkeypatch):
    work, job, _ = _setup(tmp_path, monkeypatch)
    beat = job["edit_plan"]["beats"][1]
    seen = _shot(monkeypatch)
    got = {}

    def call(p, s):
        got["p"] = p
        return dict(RICH)
    d = ai.draft_scene(job, work, beat, "natural", call=call, resolve_sources=lambda j, w: SRCS,
                       direction="손가락에 끼운 모습을 천천히")
    # 출발 화면 = 이 칸 첫 장면(작업 전체의 '제품만 가장 긴 조각'이 아니다)
    m = (beat.get("scene_override") or [beat["primary"]])[0]
    assert d["base"]["video_id"] == m["video_id"] and abs(d["base"]["t"] - (float(m["start"]) + 0.2)) < 1e-6
    assert abs(seen["t"] - d["base"]["t"]) < 1e-6
    # 대본 흐름·사장님 방향이 지시문에 들어간다
    assert "Script flow (Korean)" in got["p"] and "DIRECTOR'S NOTE" in got["p"] and "손가락에 끼운 모습을 천천히" in got["p"]
    # 영어: 사물·환경·카메라·효과 / 한글: 같은 항목의 번역
    en, ko = d["prompt_en"], d["prompt_ko"]
    assert en.startswith("INPUT IMAGE = FRAME 0: A grey finger-chopstick clip")
    assert "SCENE AND ENVIRONMENT: A desk with an RGB keyboard" in en
    assert "CAMERA AND LIGHT: Close-up, slightly high angle" in en and "IN-CAMERA EFFECTS: A soft focus pull" in en
    assert "두 손가락에 낀 회색 손가락 젓가락" in ko and "[환경] RGB 키보드" in ko
    assert "[카메라·빛] 클로즈업" in ko and "[효과] 과자에서 집게로" in ko and "손가락이 과자를 들어 올린다." in ko


def test_출발_화면과_초를_고를_수_있다(tmp_path, monkeypatch):
    work, job, _ = _setup(tmp_path, monkeypatch)
    beat = job["edit_plan"]["beats"][0]
    seen = _shot(monkeypatch)
    d = ai.draft_scene(job, work, beat, "natural", base={"video_id": "s2", "t": 7.3}, sec=8, only_frame=True,
                       call=lambda p, s: pytest.fail("출발 화면만 뜰 땐 프롬프트를 쓰지 않는다"),
                       resolve_sources=lambda j, w: SRCS)
    assert seen == {"src": "S2.mp4", "t": 7.3} and d["sec"] == 8 and d["base"] == {"video_id": "s2", "t": 7.3}
    assert "prompt_en" not in d
    assert ai.draft_scene(job, work, beat, sec=5, only_frame=True, resolve_sources=lambda j, w: SRCS)["sec"] in (4, 6, 8)


def test_한글_번역이_없으면_영어_원문을_보여준다():
    m = {"subject_desc_en": "A plush toy.", "motion_steps_en": ["one", "two", "three"]}
    ko = ai.build_prompt_ko(m, 4, "natural")
    assert "A plush toy." in ko and "0.0~1.3초  one" in ko and "[환경]" not in ko and "[금지]" in ko


class _Req:
    class state:
        customer_id = 0


class _ApiStore:
    def __init__(self, job):
        self.job = job
        self.queued = []

    def get_mix_job(self, j):
        return self.job

    def get_setting(self, k, d=None):
        return "admin" if k == "ai_scene_enabled" else d

    def task_is_alive(self, task, args, stale_minutes=3):
        return False

    def enqueue(self, task, args, owner=None, prio=None):
        self.queued.append((task, args))
        return 7

    def update_mix_job(self, j, **kw):
        self.job.update(kw)


def _api(tmp_path, monkeypatch):
    job = {"job_id": "j", "status": "ready_for_review", "customer_id": 0,
           "edit_plan": {"beats": [{"beat_idx": 0, "narration": "a"}, {"beat_idx": 1, "narration": "b"}]}}
    st = _ApiStore(job)
    monkeypatch.setattr(A, "Store", lambda db: st)
    monkeypatch.setattr(A, "_is_admin", lambda cid: cid == 0)
    monkeypatch.setattr(A, "_save_render_inputs", lambda s, j, **kw: st.update_mix_job(j, **kw))
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    return st


def _body(r):
    return r if isinstance(r, dict) else json.loads(bytes(r.body).decode())


def test_초안_없이는_못_만든다_문장은_서버_것만_쓴다(tmp_path, monkeypatch):
    st = _api(tmp_path, monkeypatch)
    evil = "EVIL prompt " * 5
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1, "style": "natural", "prompt": evil})
    assert getattr(r, "status_code", 200) == 422 and _body(r)["need"] == "draft" and st.queued == []
    monkeypatch.setattr(ai, "draft_scene", lambda job, work, beat, style, **kw: {
        "png": "x.png", "sec": 6, "visible": 4.8, "style": style, "base": {"video_id": "s0", "t": 1.2},
        "prompt_en": "INPUT IMAGE = FRAME 0: server prompt, long enough.", "prompt_ko": "한글 번역본"})
    d = _body(A.api_produce_mix_ai_scene_draft("j", _Req(), {"beat_idx": 1, "style": "natural", "direction": "천천히"}))
    assert d["ok"] and d["draft"] and d["prompt_ko"] == "한글 번역본" and d["sec"] == 6
    assert st.job["edit_plan"]["beats"][1].get("ai_scene") is None          # 초안은 편성표를 안 고친다
    # 틀린 번호·화면이 보낸 문장은 안 받는다
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1, "draft": "wrong", "prompt": evil})
    assert getattr(r, "status_code", 200) == 422 and st.queued == []
    r = A.api_produce_mix_ai_scene("j", _Req(), {"beat_idx": 1, "draft": d["draft"], "prompt": evil})
    assert _body(r)["ok"] is True and st.queued == [("ai_scene", {"job_id": "j", "beat_idx": 1, "style": "natural"})]
    s = st.job["edit_plan"]["beats"][1]["ai_scene"]
    assert s["confirmed"] is True and s["prompt_en"] == "INPUT IMAGE = FRAME 0: server prompt, long enough."
    assert s["sec_pick"] == 6 and s["base"] == {"video_id": "s0", "t": 1.2} and s["direction"] == "천천히"


def test_고객은_초안도_못_만든다(tmp_path, monkeypatch):
    _api(tmp_path, monkeypatch)

    class _Cust:
        class state:
            customer_id = 42
    assert getattr(A.api_produce_mix_ai_scene_draft("j", _Cust(), {"beat_idx": 0}), "status_code", 200) == 403


def test_워커는_확인한_문장_출발_화면_초_그대로_만든다(tmp_path, monkeypatch):
    work, job, store = _setup(tmp_path, monkeypatch)
    job["edit_plan"]["beats"][1]["ai_scene"] = {"state": "queued", "style": "natural", "confirmed": True,
                                                "prompt_en": "CONFIRMED PROMPT exactly as shown.", "sec_pick": 8,
                                                "base": {"video_id": "s2", "t": 3.4}}
    shot = _shot(monkeypatch)
    seen = {}

    def fake_gen(png, prompt, sec, out):
        seen.update(prompt=prompt, sec=sec)
        Path(out).write_bytes(b"m" * 20000)
        return str(out)
    aid = ai.run_ai_scene("j", 1, "natural", "db", tmp_path, gen=fake_gen,
                          call=lambda p, s: pytest.fail("확인한 프롬프트가 있으면 다시 쓰지 않는다"))
    assert aid == 77 and seen == {"prompt": "CONFIRMED PROMPT exactly as shown.", "sec": 8}
    assert shot["t"] == 3.4 and shot["src"].replace("\\", "/").endswith("s2/v.mp4")
    assert (work / "ai_scene_prompt_1.txt").read_text(encoding="utf-8") == "CONFIRMED PROMPT exactly as shown."
