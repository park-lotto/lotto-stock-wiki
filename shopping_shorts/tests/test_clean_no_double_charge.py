# -*- coding: utf-8 -*-
"""자막제거에서 **돈이 나간 뒤** 결과를 잃고 다시 보내는 구멍 4곳 (2026-09-27 사장님 "이런 구멍이 또 없나").

① 진행 조회 끊김(poll_aborted): 업체는 계속 돌고 크레딧은 나갔다 → 장부를 지우면 재클릭이 재과금.
② 결과를 받은 뒤 되붙이기·쪼개기(ffmpeg)에서 죽음 → 받아둔 파일이 있는데 다시 보냄.
③ 큐 대기 10분 뒤 재클릭 → 같은 청소가 큐에 두 번.
④ 옛 소스별 경로엔 이름표가 없어 이어받기 자체가 없음.
"""
import subprocess
import urllib.request
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import vmake_client as vc


class _Client:
    def __init__(self, log):
        self.log = log; self.payload = {"output_urls": ["https://r/a.mp4"], "task_id": "t_1"}

    def fetch_config(self, version=None): pass

    def _consume_permission(self, url, task):
        return {"context": "c"}

    def run_task(self, task_name, image_path, params=None, on_async_submitted=None):
        self.log.append("run")
        if on_async_submitted: on_async_submitted("t_1")
        return self.payload

    def poll_task_status(self, task_id):
        self.log.append("poll"); return {"output_urls": ["https://r/a.mp4"], "task_id": task_id}


@pytest.fixture
def env(tmp_path, monkeypatch):
    log = []; cl = _Client(log)
    monkeypatch.setattr(vc, "_new_api_client", lambda ak, sk: cl)
    monkeypatch.setattr(vc.time, "sleep", lambda s: None)
    monkeypatch.setattr(vc, "_seconds", lambda p: 3.0)
    monkeypatch.setattr(urllib.request, "urlretrieve", lambda url, dst: Path(dst).write_bytes(b"v" * 4096))
    src = tmp_path / "in.mp4"; src.write_bytes(b"i" * 4096)
    return cl, log, src, tmp_path


def test_poll_aborted_keeps_ledger_and_resumes_free(env):
    from shopping_shorts.app import clean_failure_kind
    cl, log, src, tmp = env
    cl.payload = {"error": "poll_aborted", "skill_status": "failed", "task_id": "t_1", "detail": "network"}
    with pytest.raises(RuntimeError) as ei:
        vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    assert clean_failure_kind(str(ei.value)) == "interrupted"
    cl.payload = {"output_urls": ["https://r/a.mp4"], "task_id": "t_1"}; log.clear()
    vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    assert log == ["poll"]                                   # 재업로드·재과금 없이 이어받았다


def test_vendor_task_failed_drops_ledger(env):
    """진짜 실패(task_failed)는 이어받을 게 없다 — 다음엔 새로 맡긴다(종전 동작 유지)."""
    cl, log, src, tmp = env
    cl.payload = {"error": "task_failed", "skill_status": "failed", "task_id": "t_1", "detail": "10101"}
    with pytest.raises(RuntimeError):
        vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    cl.payload = {"output_urls": ["https://r/a.mp4"], "task_id": "t_1"}; log.clear()
    vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    assert log == ["run"]


needs_ffmpeg = pytest.mark.skipif(not __import__("shutil").which("ffmpeg"), reason="ffmpeg 없음")


def _mk(path, n):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=64x128:r=30:d=%.2f" % (n / 30 + 1),
                    "-f", "lavfi", "-i", "sine=r=48000:d=%.2f" % (n / 30 + 1), "-frames:v", str(n),
                    "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)


@needs_ffmpeg
def test_partial_splice_failure_then_retry_reuses_downloaded_piece(tmp_path, monkeypatch):
    raw = tmp_path / "mix_raw.mp4"; _mk(raw, 90)
    calls = []

    def _fake_vmake(src, keys, out, tier=None, **k):
        calls.append(Path(src).name); _mk(out, mp._probe_fps_frames(src)[2]); return str(out)
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vmake)
    cuts = [{"video_id": "s0", "beat_idx": 0, "src": 0.0, "fin": 0.0, "dur": 1.0},
            {"video_id": "s1", "beat_idx": 1, "src": 4.0, "fin": 1.0, "dur": 1.0},
            {"video_id": "s0", "beat_idx": 2, "src": 8.0, "fin": 2.0, "dur": 1.0}]
    out = tmp_path / "final_clean_abcp.mp4"
    # 1차: 업체 결과는 받았는데 되붙이기(ffmpeg)가 죽는다
    real_run = subprocess.run

    def _boom(cmd, *a, **k):
        if "concat=" in " ".join(map(str, cmd)):
            raise subprocess.CalledProcessError(1, cmd)
        return real_run(cmd, *a, **k)
    monkeypatch.setattr(subprocess, "run", _boom)
    with pytest.raises(subprocess.CalledProcessError):
        mp._clean_partial(str(raw), cuts, ["1|s1|4.00"], ["k"], str(out), "pro", tmp_path)
    monkeypatch.setattr(subprocess, "run", real_run)
    # 2차(다시 누름): 받아둔 조각을 쓴다 — 업체 호출 0
    mp._clean_partial(str(raw), cuts, ["1|s1|4.00"], ["k"], str(out), "pro", tmp_path)
    assert calls == ["partial_in.mp4"] and out.exists()
    # 다른 선택이면 받아둔 조각을 빌려 쓰지 않는다
    mp._clean_partial(str(raw), cuts, ["0|s0|0.00"], ["k"], str(tmp_path / "final_clean_abcpZZ.mp4"), "pro", tmp_path)
    assert len(calls) == 2


@needs_ffmpeg
def test_joined_split_failure_then_retry_reuses_downloaded_join(tmp_path, monkeypatch):
    a = tmp_path / "a.mp4"; b = tmp_path / "b.mp4"; _mk(a, 30); _mk(b, 30)
    calls = []

    def _fake_vmake(src, keys, out, tier=None, **k):
        calls.append(1); Path(out).write_bytes(Path(src).read_bytes()); return str(out)
    monkeypatch.setattr(mp, "_vmake_clean", _fake_vmake)
    monkeypatch.setattr(mp.time, "sleep", lambda s: None)
    items = [("cb0_0", str(a)), ("cb1_0", str(b))]
    monkeypatch.setattr(mp, "_split_cleaned", lambda *x, **k: (_ for _ in ()).throw(RuntimeError("쪼개기 실패")))
    with pytest.raises(RuntimeError):
        mp._clean_joined(items, ["k"], str(tmp_path), tag="cb", tier="basic", resume_key="inc:abc")
    monkeypatch.setattr(mp, "_split_cleaned", lambda cleaned, spans, work: {v: cleaned for v, _ in items})
    monkeypatch.setattr(mp.sub_region, "detect_erased_region", lambda *x, **k: None)
    mp._clean_joined(items, ["k"], str(tmp_path), tag="cb", tier="basic", resume_key="inc:abc")
    assert calls == [1]                                      # 두 번째는 받아둔 합본 — 업체 호출 0
    mp._clean_joined(items, ["k"], str(tmp_path), tag="cb", tier="basic", resume_key="inc:other")
    assert calls == [1, 1]                                   # 다른 묶음은 새로


def test_clean_api_does_not_enqueue_twice_when_pending(monkeypatch):
    from shopping_shorts import app as A
    job = {"job_id": "j", "edit_plan": {"beats": [{"beat_idx": 0}]}, "customer_id": 7,
           "clean_status": "cleaning", "updated_at": "2000-01-01T00:00:00"}   # 오래돼 stale → 가드가 열린다
    enq = []

    class _S:
        def __init__(self, *a): pass
        def get_mix_job(self, j): return job
        def update_mix_job(self, *a, **k): pass
        def queue_has_pending(self, task, key, value): return (task, key, value) == ("clean", "job_id", "j")
        def task_is_alive(self, *a): return False
        def queue_status(self, *a): return None
        def enqueue(self, *a, **k): enq.append(a)
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A, "_need_own_key_or_402", lambda *a, **k: None)
    r = A.api_produce_mix_clean(None, {"job_id": "j"})
    assert r.get("status") == "cleaning" and enq == []


def test_charge_without_task_id_alerts_admin_then_resubmits(env, monkeypatch):
    """⑤ 업체 SDK 틈: 과금(consume) 직후·작업번호 전에 죽음 → 다음 클릭이 '번호 없는 과금'을 알아채고 경보한다."""
    cl, log, src, tmp = env
    alerts = []
    from shopping_shorts import ops_alert
    monkeypatch.setattr(ops_alert, "raise_alert", lambda kind, title, detail="", **k: alerts.append((kind, k.get("signature"))))

    class _Boom(Exception):
        pass

    def run_crash(task_name, image_path, params=None, on_async_submitted=None):
        cl._consume_permission("u", task_name)                     # 과금은 됐다
        raise _Boom("제출 직전 워커 사망")                            # 번호를 못 받았다
    cl._consume_permission = lambda url, task: {"context": "c"}
    cl.run_task = run_crash
    with pytest.raises(_Boom):
        vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    ent = vc._pending_get(tmp / "o.mp4", "final:x|basic|SKM0003")
    assert ent and ent.get("task_id") is None and ent.get("consumed")
    # 다시 누름 — 새로 보내되(결과는 받아야 하니) 관리자 경보 1건
    def run_ok(task_name, image_path, params=None, on_async_submitted=None):
        log.append("run"); return {"output_urls": ["https://r/a.mp4"], "task_id": "t_2"}
    cl.run_task = run_ok
    vc.remove_subtitles(str(src), "ak:sk", str(tmp / "o.mp4"), resume_key="final:x")
    assert alerts == [("vmake_orphan_charge", "final:x|basic|SKM0003")] and "run" in log
    assert vc._pending_get(tmp / "o.mp4", "final:x|basic|SKM0003") is None


def test_failure_kind_maps_reaper_and_worker_messages_to_interrupted():
    from shopping_shorts.app import clean_failure_kind
    assert clean_failure_kind("작업 도중 중단됐습니다 — 다시 시도해 주세요") == "interrupted"
    assert clean_failure_kind("워커가 중단됐습니다") == "interrupted"


def test_dead_worker_is_detected_immediately_by_queue_not_10min(monkeypatch):
    """⑥ 워커 죽음: 큐 기록이 있고 하트비트가 없으면 10분 안 기다리고 바로 '중단'(재클릭 가능)."""
    from shopping_shorts import app as A
    from datetime import datetime, timezone
    fresh = datetime.now(timezone.utc).isoformat()

    class _S:
        def __init__(self, alive, qs): self.alive, self.qs = alive, qs
        def task_is_alive(self, task, args): return self.alive
        def queue_status(self, task, args): return self.qs
    job = {"job_id": "j", "clean_status": "cleaning", "updated_at": fresh}      # 방금 갱신 = 10분 안 지남
    assert A._clean_interrupted(_S(True, {"state": "running"}), job) is False   # 하트비트 뛴다 → 진행 중
    assert A._clean_interrupted(_S(False, {"state": "failed"}), job) is True    # 큐가 죽었다 → 즉시 중단
    assert A._clean_interrupted(_S(False, {"state": "running"}), job) is True   # 죽은 running(하트비트 끊김)
    assert A._clean_interrupted(_S(False, None), job) is False                 # 큐 기록 없음 → 종전 10분 규칙
    assert A._clean_interrupted(_S(False, None), dict(job, clean_status="ready")) is False


def test_clean_api_allows_reclick_when_worker_dead(monkeypatch):
    from shopping_shorts import app as A
    from datetime import datetime, timezone
    job = {"job_id": "j", "edit_plan": {"beats": [{"beat_idx": 0}]}, "customer_id": 7,
           "clean_status": "cleaning", "updated_at": datetime.now(timezone.utc).isoformat()}
    enq = []

    class _S:
        def __init__(self, *a): pass
        def get_mix_job(self, j): return job
        def update_mix_job(self, *a, **k): pass
        def queue_has_pending(self, *a): return False
        def task_is_alive(self, *a): return False
        def queue_status(self, *a): return {"state": "failed"}
        def enqueue(self, *a, **k): enq.append(a); return 1
    monkeypatch.setattr(A, "Store", _S)
    monkeypatch.setattr(A, "_need_own_key_or_402", lambda *a, **k: None)
    r = A.api_produce_mix_clean(None, {"job_id": "j"})
    assert r.get("ok") and enq                                     # 10분 안 지났어도 다시 넣는다


def test_legacy_source_clean_passes_resume_key(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(mp, "_vmake_clean", lambda src, keys, out, tier=None, resume_key=None: (seen.append(resume_key), Path(out).write_bytes(b"x" * 2048), out)[2])
    monkeypatch.setattr(mp.sub_region, "detect_erased_region", lambda *x, **k: None)
    src = tmp_path / "v.mp4"; src.write_bytes(b"s" * 2048)
    mp._clean_one(("s0", str(src)), ["k"], tmp_path)
    assert seen == ["src:s0:v.mp4"]
