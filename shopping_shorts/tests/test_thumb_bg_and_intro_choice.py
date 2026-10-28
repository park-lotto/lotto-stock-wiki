# -*- coding: utf-8 -*-
"""썸네일 배경 = 지금 편성의 청소 조립본 · 인트로 선택 판단 한 곳 (2026-09-27).

① _thumb_clean_background: 청소본 정본(clean_base.json)이 있으면 clean_video_path(assemble_clean_video 가
   정본+증분 조각으로 렌더와 같은 입력으로 만든 **지금 편성**의 조립본)를 정본 파일(청소 당시 편성)보다 먼저 쓴다.
② _save_render_inputs 의 인트로 선택 비교는 mix_pipeline._intro_choice(완성본 도장과 같은 함수) — 인트로 길이만
   바꿔도 옛 완성본을 끊는다.
"""
from shopping_shorts import app as A
from shopping_shorts import mix_pipeline as mp


def _files(tmp_path):
    work = tmp_path / "j1"; work.mkdir()
    base_file = work / "final_clean_abc.mp4"; base_file.write_bytes(b"b" * 2048)
    assembled = work / "clean_assembled.mp4"; assembled.write_bytes(b"a" * 2048)
    return work, base_file, assembled


def test_thumb_bg_prefers_assembled_when_clean_base_exists(tmp_path, monkeypatch):
    work, base_file, assembled = _files(tmp_path)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(mp, "clean_base_for", lambda job, w: {"path": str(base_file), "extras": {"cb1_0": {}}})
    job = {"clean_status": "ready", "clean_video_path": str(assembled), "subtitle_removal": 1}
    assert A._thumb_clean_background("j1", job) == str(assembled)


def test_thumb_bg_falls_back_to_base_file_without_assembled(tmp_path, monkeypatch):
    work, base_file, assembled = _files(tmp_path)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(mp, "clean_base_for", lambda job, w: {"path": str(base_file)})
    job = {"clean_status": "ready", "clean_video_path": None, "subtitle_removal": 1}
    assert A._thumb_clean_background("j1", job) == str(base_file)


def test_thumb_bg_without_base_keeps_plan_file_first(tmp_path, monkeypatch):
    """정본이 없는 옛 경로는 종전 그대로 — 지금 편성 서명의 청소본 파일이 옛 clean_video_path 보다 먼저."""
    work, base_file, assembled = _files(tmp_path)
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    monkeypatch.setattr(mp, "clean_base_for", lambda job, w: None)
    monkeypatch.setattr(mp, "clean_final_path_for_plan", lambda job, w: base_file)
    job = {"clean_status": "ready", "clean_video_path": str(assembled)}
    assert A._thumb_clean_background("j1", job) == str(base_file)


class _Store:
    def __init__(self, job):
        self.job, self.upd = job, {}

    def get_mix_job(self, j):
        return self.job

    def update_mix_job(self, j, **kw):
        self.upd.update(kw)


def test_intro_length_change_invalidates_final():
    th = {"intro": True, "results": ["a.png"], "selected": "a.png", "intro_sec": 1.0}
    st = _Store({"thumbnail": th, "status": "done", "video_path": "/x/final.mp4"})
    assert A._save_render_inputs(st, "j1", thumbnail=dict(th, intro_sec=2.0)) is True
    assert st.upd.get("video_path") is None and st.upd.get("status") == "ready_for_review"


def test_intro_choice_is_mix_pipeline_one():
    import inspect
    src = inspect.getsource(A._save_render_inputs)
    # 2026-09-27: 비교 값은 intro_signature(= _intro_choice 결과 + 고른 이름 + 파일 크기·시각) — 판단은 여전히 _intro_choice 한 곳
    assert "mix_pipeline.intro_signature(" in src and "def _intro_choice" not in src
