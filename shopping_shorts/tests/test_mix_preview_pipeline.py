"""run_preview — 유료 VMake·꾸미기 없이 렌더한다(스펙 §3·§6.2).

★이 파일의 존재이유: clean_fn=None으로 부르는 것이 이 설계의 전부다.
  여기가 틀리면 미리보기가 유료 API를 불러 '0원'이라는 전제가 무너진다.

실 ffmpeg를 부르지 않는다 — 이 저장소는 pytest 기본 캡처가 fd 0을 무효화해
subprocess.run이 죽는다(장면라이브러리 트랙 실측). assemble을 가짜화한다.
mix_pipeline이 `from shopping_shorts.video_assemble import assemble`로 **이름 import**
하므로 monkeypatch.setattr(mix_pipeline, "assemble", ...)가 먹는다.
"""
import pytest

from shopping_shorts import mix_pipeline
from shopping_shorts.store import Store


@pytest.fixture
def job(tmp_path, monkeypatch):
    db = str(tmp_path / "t.db")
    store = Store(db)
    store.create_mix_job("J1", ["https://x/1"], 20, "template")
    plan = {"beats": [{"beat_idx": 0, "tts_path": str(tmp_path / "a.mp3"),
                       "primary": {"video_id": "v1", "start": 0, "end": 2}}]}
    store.update_mix_job("J1", edit_plan=plan, status="ready_for_review")
    monkeypatch.setattr(mix_pipeline, "_resolve_sources",
                        lambda job, work: {"v1": str(tmp_path / "v1.mp4")})
    return db, str(tmp_path / "work"), store


def test_preview_never_calls_clean_fn(job, monkeypatch):
    """★설계의 존재이유 — subtitle_removal이 켜져 있어도 VMake를 부르면 안 된다.

    다음 단계(자막제거)가 유료라, 컷·대본이 틀린 채 넘어가면 그 돈이 날아간다.
    미리보기는 0원이어야 그 판단을 공짜로 할 수 있다."""
    db, work, store = job
    store.update_mix_job("J1", subtitle_removal=True)   # 유료 옵션 ON인 job
    seen = {}

    def fake_assemble(plan, tts, srcs, out, clean_fn=None, headcopy=None,
                      caption_style=None, deco=None):
        seen["clean_fn"] = clean_fn
        seen["deco"] = deco
        open(out, "w").write("x")
        return out

    monkeypatch.setattr(mix_pipeline, "assemble", fake_assemble)
    mix_pipeline.run_preview("J1", db, work)

    assert seen["clean_fn"] is None, "미리보기가 유료 VMake를 붙였다 — 0원 전제가 깨진다"
    assert not seen["deco"], f"미리보기에 꾸미기가 붙었다(4단계 소관): {seen['deco']}"


def test_preview_sets_ready_and_path(job, monkeypatch):
    db, work, store = job
    monkeypatch.setattr(mix_pipeline, "assemble",
                        lambda *a, **k: (open(a[3], "w").write("x"), a[3])[1])
    mix_pipeline.run_preview("J1", db, work)
    j = store.get_mix_job("J1")
    assert j["preview_status"] == "ready"
    assert j["preview_path"] and j["preview_path"].endswith("preview.mp4")


def test_preview_does_not_touch_status(job, monkeypatch):
    """★기존 status 한 줄기 보호(스펙 §6.1)."""
    db, work, store = job
    monkeypatch.setattr(mix_pipeline, "assemble",
                        lambda *a, **k: (open(a[3], "w").write("x"), a[3])[1])
    mix_pipeline.run_preview("J1", db, work)
    assert store.get_mix_job("J1")["status"] == "ready_for_review", \
        "미리보기가 최종렌더용 status를 덮었다"


def test_preview_failure_records_error_not_crash(job, monkeypatch):
    """렌더가 죽어도 예외를 밖으로 던지지 않는다 — BackgroundTasks라 아무도 안 받는다."""
    db, work, store = job

    def boom(*a, **k):
        raise RuntimeError("ffmpeg 죽음")

    monkeypatch.setattr(mix_pipeline, "assemble", boom)
    mix_pipeline.run_preview("J1", db, work)      # 여기서 터지면 실패
    j = store.get_mix_job("J1")
    assert j["preview_status"] == "failed"
    assert "ffmpeg" in (j["preview_error"] or "")


def test_preview_without_edit_plan_is_noop(tmp_path):
    """매칭 전 job — 조용히 아무것도 안 한다(run_render와 같은 계약)."""
    db = str(tmp_path / "t2.db")
    store = Store(db)
    store.create_mix_job("J2", ["https://x/1"], 20, "template")
    mix_pipeline.run_preview("J2", db, str(tmp_path / "w"))
    assert store.get_mix_job("J2")["preview_status"] is None
