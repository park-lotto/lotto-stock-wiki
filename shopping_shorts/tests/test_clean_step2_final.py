# -*- coding: utf-8 -*-
"""2단계 자막제거를 **완성본 1편**으로 바꾼다 (2026-08-27 사장님 지시).

★무엇이 문제였나 (실측)
    08-26에 완성본 1편만 청소하는 경로(_final_clean_fn)를 만들었는데, 3단계(run_render)에만
    달았다. 2단계 버튼(run_clean_sources)은 _FINAL_CLEAN을 보지도 않고 늘 소스별/합본을 청소했다.
      → 2단계를 누르면 clean_sources가 채워지고, 3단계는 already=True가 돼
        **완성본 경로를 영영 안 탄다.** 2단계를 쓰는 사람에겐 08-26 개선이 없던 것과 같다.
    서버 워커 로그 실측(08-27): join_all.mp4 569MB를 보내 10분(595초)이 걸린 건이 있었다.

★고친 것
    2단계도 _FINAL_CLEAN이면 소스를 안 건드리고, 조립한 완성본 1편만 청소한다.
    clean_sources를 **일부러 비워 둔다** — 그래야 3단계가 같은 완성본 경로를 타고,
    편성이 그대로면 final_clean_{sig}.mp4를 재사용해 재과금이 0이다.

    사장님: "3단계 완성본 30초만 짤라서 돌리는건데 소스별로 안하고"
"""
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp


class _FakeStore:
    def __init__(self, job):
        self._job = job
        self.updates = []
    def get_mix_job(self, _):
        return self._job
    def update_mix_job(self, _, **f):
        self.updates.append(f); self._job.update(f)
    def get_setting(self, *_a, **_k):
        return "appkey:secret"


def _plan():
    return {"beats": [{"beat_idx": 0, "target_seconds": 2.0,
                       "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 1.0, "end": 3.0},
                       "alternates": [], "tts_path": None}]}


@pytest.fixture
def env(monkeypatch, tmp_path):
    """2단계 호출부를 실제 형태 그대로 세운다 — VMake와 ffmpeg만 가짜."""
    job = {"job_id": "j", "urls": ["u"], "customer_id": 7, "edit_plan": _plan()}
    store = _FakeStore(job)
    monkeypatch.setattr(mp, "Store", lambda p: store)
    monkeypatch.setattr(mp, "_resolve_sources", lambda j, w: {"s0": "/orig/s0.mp4"})
    monkeypatch.setattr(mp, "_vmake_key", lambda *a, **k: "appkey:secret")
    monkeypatch.setattr(mp, "_charge_clean", lambda *a, **k: 5)
    monkeypatch.setattr(mp, "_refund_clean", lambda *a, **k: None)
    monkeypatch.setattr(mp, "_resolve_cutaway_paths", lambda *a, **k: {})
    monkeypatch.setattr(mp, "_resolve_sfx_paths", lambda *a, **k: {})
    sent = []
    def fake_remove(video, key, out_path, **kw):
        sent.append(video); Path(out_path).write_text("cleaned" * 500); return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)
    seen = {}
    def fake_assemble(plan, tts_paths, source_video_paths, out_path, **kw):
        seen["sources"] = source_video_paths
        seen["clean_fn"] = kw.get("clean_fn")
        mix_raw = Path(out_path).parent / "mix_raw.mp4"
        mix_raw.parent.mkdir(parents=True, exist_ok=True)
        mix_raw.write_text("mix")
        fn = kw.get("clean_fn")
        if fn is not None:
            seen["cleaned_out"] = fn(str(mix_raw))     # assemble이 하는 그대로 호출한다
        Path(out_path).write_text("preview")
        return out_path
    monkeypatch.setattr(mp, "assemble", fake_assemble)
    return job, store, sent, seen, tmp_path


def test_완성본_1편만_VMake에_보낸다(monkeypatch, env):
    """★핵심: 소스(/orig/s0.mp4)가 아니라 조립된 완성본(mix_raw.mp4)이 보내진다."""
    job, store, sent, seen, tmp = env
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert len(sent) == 1, "VMake 콜은 1회여야 한다"
    assert sent[0].endswith("mix_raw.mp4"), f"완성본이 아니라 {sent[0]}를 보냈다"
    assert "/orig/" not in sent[0], "소스 원본을 보내면 안 된다"


def test_소스별_청소를_아예_안_한다(monkeypatch, env):
    job, store, sent, seen, tmp = env
    called = []
    monkeypatch.setattr(mp, "_ensure_clean_sources",
                        lambda *a, **k: called.append(1) or {})
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert called == [], "_ensure_clean_sources(소스별/합본)를 부르면 안 된다"


def test_clean_sources를_비워둬야_3단계가_완성본경로를_탄다(monkeypatch, env):
    """★run_render는 already=bool(clean_sources)로 갈린다 — 채우면 옛 경로로 떨어진다."""
    job, store, sent, seen, tmp = env
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert not job.get("clean_sources"), "clean_sources를 채우면 3단계가 소스별로 되돌아간다"


def test_조립은_원본소스로_하고_clean_fn이_꽂힌다(monkeypatch, env):
    job, store, sent, seen, tmp = env
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert seen["sources"] == {"s0": "/orig/s0.mp4"}
    assert seen["clean_fn"] is not None


def test_성공하면_ready와_조립본경로가_남는다(monkeypatch, env):
    job, store, sent, seen, tmp = env
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert job["clean_status"] == "ready"
    assert job["clean_video_path"] == str(Path(tmp) / "j" / "clean_preview.mp4")
    assert Path(job["clean_video_path"]).exists()


def test_같은_편성이면_두번째는_과금0(monkeypatch, env):
    """편성 서명이 같으면 final_clean_{sig}.mp4를 재사용한다 — VMake를 다시 안 탄다."""
    job, store, sent, seen, tmp = env
    charges = []
    monkeypatch.setattr(mp, "_charge_clean", lambda s, c, n: charges.append(n) or 5)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    job["clean_sources"] = None          # 2단계를 다시 눌렀다(편성은 그대로)
    mp.run_clean_sources("j", "db", str(tmp))
    assert len(sent) == 1, "같은 편성인데 VMake를 두 번 탔다"
    assert charges == [1], f"재과금이 있었다: {charges}"


def test_청소_실패는_ready로_두지_않는다(monkeypatch, env):
    """★유료 청소가 조립 안에서 돈다 — 삼키면 '완료'인데 자막이 남은 결과가 나간다."""
    job, store, sent, seen, tmp = env
    def boom(video, key, out_path, **kw):
        raise RuntimeError("AI 자막 제거 실패: 60002")
    monkeypatch.setattr(mp, "remove_subtitles", boom)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert job["clean_status"] == "failed"
    assert "60002" in (job.get("clean_error") or "")


def test_포인트부족은_그대로_전달된다(monkeypatch, env):
    job, store, sent, seen, tmp = env
    def nope(*a, **k):
        raise mp.NotEnoughPoints("포인트가 부족합니다")
    monkeypatch.setattr(mp, "_charge_clean", nope)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
    mp.run_clean_sources("j", "db", str(tmp))
    assert job["clean_status"] == "failed"
    assert "포인트" in (job.get("clean_error") or "")


def test_플래그가_꺼지면_옛경로_그대로(monkeypatch, env):
    """되돌릴 스위치가 살아 있어야 한다 — SHORTS_CLEAN_FINAL=0이면 소스별로 돈다."""
    job, store, sent, seen, tmp = env
    called = []
    def fake_ensure(st, jb, jid, work, key, cid=0):
        called.append(1)
        st.update_mix_job(jid, clean_sources={"s0": "/clean/s0.mp4"})
        return {"s0": "/clean/s0.mp4"}
    monkeypatch.setattr(mp, "_ensure_clean_sources", fake_ensure)
    monkeypatch.setattr(mp, "_FINAL_CLEAN", False)
    mp.run_clean_sources("j", "db", str(tmp))
    assert called == [1], "옛 경로(소스별)가 돌아야 한다"
    assert seen["clean_fn"] is None, "옛 경로에서 완성본을 또 청소하면 이중과금이다"


class Test판단은한곳:
    """★0순위-B: 같은 판단이 두 군데 적히면 반드시 어긋난다.

    이번 사고가 그 실례였다 — 08-26에 완성본 경로를 run_render에만 달고
    run_clean_sources를 빠뜨려, 2단계를 쓰는 사람에겐 개선이 통째로 없었다.
    두 호출부가 _clean_strategy 하나만 보게 묶었고, 여기서 그 계약을 고정한다.
    """

    def test_기본은_완성본(self, monkeypatch):
        monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
        assert mp._clean_strategy({}) == "final"

    def test_되돌림스위치가_내려가면_소스별(self, monkeypatch):
        monkeypatch.setattr(mp, "_FINAL_CLEAN", False)
        assert mp._clean_strategy({}) == "sources"

    def test_이미_청소된_소스가_있으면_그걸_쓴다(self, monkeypatch):
        """두 번 과금하지 않는다 — 옛 경로로 청소해 둔 job이 그대로 살아 있어야 한다."""
        monkeypatch.setattr(mp, "_FINAL_CLEAN", True)
        assert mp._clean_strategy({"clean_sources": {"s0": "/clean/s0.mp4"}}) == "sources"

    def test_두_호출부가_같은_함수를_쓴다(self):
        """★grep 계약 — 새 진입 경로가 생겨도 _FINAL_CLEAN을 직접 읽으면 안 된다.

        판단이 흩어지는 순간 이번 사고가 재발한다. _FINAL_CLEAN을 읽는 곳은
        정의 한 줄과 _clean_strategy 안뿐이어야 한다.
        """
        import inspect
        src = inspect.getsource(mp)
        hits = [ln.strip() for ln in src.splitlines()
                if "_FINAL_CLEAN" in ln and not ln.strip().startswith("#")]
        assert len(hits) == 2, f"_FINAL_CLEAN을 직접 읽는 곳이 늘었다: {hits}"

    def test_호출부는_전략함수로만_갈린다(self):
        for fn in (mp.run_clean_sources, mp.run_render):
            import inspect
            body = inspect.getsource(fn)
            assert "_FINAL_CLEAN" not in body, f"{fn.__name__}이 판단을 또 적고 있다"
