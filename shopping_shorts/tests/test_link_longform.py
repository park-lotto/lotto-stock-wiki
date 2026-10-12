"""구매링크용 롱폼(가로) 판 — 실제로 구워서 결과 파일을 검사한다(관제 132).

계산 대조가 아니라 **나온 영상**을 tools/link_longform_check.py 로 원본과 대조한다.
경로(HTTP) 배선도 실제 job 을 심어 끝까지 돌린다: 시작 → 상태 → 받기 → 완성본이 바뀌면 옛 파일은 안 준다.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import link_longform as LL
from shopping_shorts.store import Store

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import link_longform_check as chk  # noqa: E402


def _mk_short(path, dur=3):
    """세로 쇼츠 흉내: 움직이는 그림 + 소리."""
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc2=s=540x960:r=30:d={dur}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _all_ok(res):
    return [name for name, ok, _ in res if not ok]


def test_render_passes_output_check(tmp_path):
    src = tmp_path / "final.mp4"
    _mk_short(src)
    assert LL.state(tmp_path, src, "comment")["state"] == "none"
    out = LL.render_link_longform(str(src), tmp_path, "comment")
    assert out.name == LL.OUT_NAME and out.exists()
    assert _all_ok(chk.check(str(src), str(out))) == []
    # 표식: 같은 완성본·같은 문구일 때만 최신
    assert LL.state(tmp_path, src, "comment")["state"] == "ready"
    assert LL.state(tmp_path, src, "desc")["state"] == "none"
    # 임시 파일을 남기지 않는다
    assert not LL.paths(tmp_path)["tmp"].exists()
    assert not (tmp_path / "link_longform_overlay.png").exists()


def test_check_catches_plain_pad(tmp_path):
    """검사가 진짜로 재는지 — 문구·흐린 배경 없이 검정 여백만 붙인 영상은 떨어져야 한다."""
    src = tmp_path / "final.mp4"
    _mk_short(src)
    fake = tmp_path / "fake.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src),
                    "-vf", "scale=608:1080,pad=1920:1080:(ow-iw)/2:0", "-c:a", "copy", str(fake)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)
    bad = _all_ok(chk.check(str(src), str(fake)))
    assert any("문구" in b for b in bad) and any("흐린" in b for b in bad)


def test_rerendered_final_makes_it_stale(tmp_path):
    src = tmp_path / "final.mp4"
    _mk_short(src)
    LL.render_link_longform(str(src), tmp_path, "comment")
    _mk_short(src, dur=2)                                # 완성본을 다시 만들었다
    os.utime(src, (time.time() + 5, time.time() + 5))
    assert LL.is_fresh(tmp_path, src, "comment") is False


def test_failure_leaves_reason(tmp_path):
    src = tmp_path / "final.mp4"
    src.write_bytes(b"not a video")
    try:
        LL.render_link_longform(str(src), tmp_path, "comment")
    except Exception:
        pass
    else:
        raise AssertionError("깨진 파일인데 예외가 안 났다")
    assert not LL.paths(tmp_path)["out"].exists()


def _seed(monkeypatch, tmp_path, status="done"):
    db = tmp_path / "t.db"
    root = tmp_path / "mix_jobs"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", root)
    work = root / "j1"
    work.mkdir(parents=True)
    final = work / "final.mp4"
    _mk_short(final)
    store = Store(db)
    store.create_mix_job("j1", ["https://www.instagram.com/reel/AAA111/"], 20, "free")
    store.update_mix_job("j1", status=status, video_path=str(final))
    return TestClient(app_module.app), final


def _wait_ready(client, where="comment", sec=60):
    t0 = time.time()
    while time.time() - t0 < sec:
        d = client.get(f"/api/mix/longform_link/j1?where={where}").json()
        if d.get("state") != "running":
            return d
        time.sleep(0.3)
    raise AssertionError("시간 안에 안 끝났다")


def test_route_end_to_end(monkeypatch, tmp_path):
    client, final = _seed(monkeypatch, tmp_path)
    assert client.get("/api/mix/longform_link/j1").json()["state"] == "none"
    assert client.get("/api/mix/video_longform/j1").status_code == 404      # 아직 없다
    d = client.post("/api/mix/longform_link/j1", json={"where": "comment"}).json()
    assert d["state"] in ("running", "ready") and d["text"] == LL.TEXTS["comment"]
    d = _wait_ready(client)
    assert d["state"] == "ready" and d["url"] == "/api/mix/video_longform/j1"
    r = client.get(d["url"] + "?dl=1")
    assert r.status_code == 200 and "attachment" in r.headers.get("content-disposition", "")
    got = tmp_path / "got.mp4"
    got.write_bytes(r.content)
    assert _all_ok(chk.check(str(final), str(got))) == []
    # 다른 문구는 아직 안 만들었다 → 그 문구로는 주지 않는다
    assert client.get("/api/mix/video_longform/j1?where=desc").status_code == 404
    # 완성본을 다시 만들면 옛 롱폼은 주지 않는다
    _mk_short(final, dur=2)
    os.utime(final, (time.time() + 5, time.time() + 5))
    assert client.get("/api/mix/longform_link/j1").json()["state"] == "none"
    assert client.get("/api/mix/video_longform/j1").status_code == 404


def test_route_blocks_without_final(monkeypatch, tmp_path):
    client, _ = _seed(monkeypatch, tmp_path, status="rendering")
    assert client.post("/api/mix/longform_link/j1", json={}).status_code == 409
    assert client.get("/api/mix/longform_link/nope").status_code == 404


def test_cleanup_knows_longform_file():
    """완성본 정리가 롱폼 파일도 같이 지운다(안 넣으면 지우는 규칙 없이 쌓인다)."""
    from shopping_shorts import disk_cleanup
    assert LL.OUT_NAME in disk_cleanup._FINAL_VIDEO_FILES
