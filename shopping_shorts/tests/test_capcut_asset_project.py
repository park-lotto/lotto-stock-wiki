"""관제 195 — 캡컷 재료는 그 내보내기(project) 폴더의 파일이어야 한다.

옛 내보내기 폴더에 같은 이름 파일이 남아 있으면, 이름만으로 찾던 서버가 옛 그림을 보냈다."""
import os, time
from shopping_shorts import app as A


def test_asset_served_from_requested_project(tmp_path, monkeypatch):
    monkeypatch.setattr(A, "_MIX_WORK_DIR", tmp_path)
    cap = tmp_path / "job1" / "capcut"
    for proj, body in (("old 1337", b"OLD"), ("new 1941", b"NEW")):
        (cap / proj).mkdir(parents=True)
        (cap / proj / "scene-style-0007.png").write_bytes(body)
    r = A.api_mix_capcut_asset("job1", "scene-style-0007.png", p="new 1941")
    assert open(r.path, "rb").read() == b"NEW"
    assert r.headers["cache-control"] == "no-store"
    r = A.api_mix_capcut_asset("job1", "scene-style-0007.png", p="old 1337")
    assert open(r.path, "rb").read() == b"OLD"
    # 주소에 폴더가 없는 옛 요청은 가장 최근 폴더
    t = time.time()
    os.utime(cap / "old 1337", (t - 100, t - 100)); os.utime(cap / "new 1941", (t, t))
    r = A.api_mix_capcut_asset("job1", "scene-style-0007.png")
    assert open(r.path, "rb").read() == b"NEW"
    assert A.api_mix_capcut_asset("job1", "x.png", p="../etc").status_code == 400
