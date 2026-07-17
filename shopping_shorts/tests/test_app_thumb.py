"""썸네일 라우트 — 프레임 추출·파일 서빙.

경로순회 차단은 협상 대상이 아니다: 모션효과 트랙 Task5에서 클라이언트가 준 경로를
그대로 쓰다가 '임의파일 덮어쓰기'가 잡혔다. 같은 구멍을 만들지 않는다.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_DIR", tmp_path / "thumbs")
    return TestClient(app_module.app)


def _job_with_video(tmp_path, job_id="j1"):
    s = Store(tmp_path / "t.db")
    s.create_mix_job(job_id, ["https://x/1"], 30, "template")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"fake")
    s.update_mix_job(job_id, video_path=str(video))
    return s


def test_frames_extracts_and_returns_ts(client, tmp_path, monkeypatch):
    _job_with_video(tmp_path)

    def fake_grid(video_path, dest_dir, n=10):
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(n):
            p = dest / f"grid_{i:02d}.jpg"
            p.write_bytes(b"img")
            # 소수점 3자리 이상 섞어서 round(ts, 2)가 실제로 값을 바꾸게 한다.
            # round를 지워도 frames[0]만 보면(1.17→반올림해도 그대로) 안 죽는다는
            # 뮤테이션 실측(픽스3) 때문에 전체 프레임을 검사한다.
            out.append((p, i * 2.3456789 + 1.1734567))
        return out

    monkeypatch.setattr(app_module, "extract_grid_frames", fake_grid)
    r = client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    assert r.status_code == 200
    frames = r.json()["frames"]
    assert len(frames) == 10
    for i, f in enumerate(frames):
        expected = round(i * 2.3456789 + 1.1734567, 2)
        assert f["ts"] == pytest.approx(expected)
        # round(ts, 2)가 없으면 원본 소수점 자리(예: 1.1734567)가 그대로 나와
        # expected(반올림된 값)와 달라 이 단언이 죽는다.
        assert len(str(f["ts"]).split(".")[-1]) <= 2
    assert frames[0]["url"].startswith("/api/produce/thumb/file/j1/")


def test_frames_reuses_existing(client, tmp_path, monkeypatch):
    """이미 뽑아뒀으면 재추출하지 않는다(설계: '이미 있으면 재사용')."""
    _job_with_video(tmp_path)
    calls = {"n": 0}

    def counting(video_path, dest_dir, n=10):
        calls["n"] += 1
        dest = Path(dest_dir); dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(n):
            p = dest / f"grid_{i:02d}.jpg"; p.write_bytes(b"img")
            out.append((p, float(i)))
        return out

    monkeypatch.setattr(app_module, "extract_grid_frames", counting)
    client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    assert calls["n"] == 1


def test_frames_re_extracts_after_rerender(client, tmp_path, monkeypatch):
    """재렌더(=같은 job_id, 같은 final.mp4 경로, 내용만 교체)면 옛 프레임을 버리고 재추출한다.

    픽스1: mix_pipeline이 job_id로 결정적인 경로(work/job_id/final.mp4)에 렌더하므로
    재렌더는 파일을 덮어쓴다. len(meta)==len(existing)만 보던 낡은 재사용 검사는
    n=10 고정이라 이 경우를 절대 못 잡는다 — 영상 서명(mtime_ns+size)을 같이 저장해
    비교해야 한다.
    """
    _job_with_video(tmp_path)
    calls = {"n": 0}

    def counting(video_path, dest_dir, n=10):
        calls["n"] += 1
        dest = Path(dest_dir); dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(n):
            p = dest / f"grid_{i:02d}.jpg"; p.write_bytes(f"img{calls['n']}".encode())
            out.append((p, float(i) + calls["n"]))  # 회차마다 ts가 달라짐 = 새 영상 흔적
        return out

    monkeypatch.setattr(app_module, "extract_grid_frames", counting)
    r1 = client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    assert r1.json()["frames"][0]["ts"] == pytest.approx(1.0)

    # 재렌더: 같은 경로(v.mp4)를 다른 내용으로 덮어쓴다 -> mtime/size가 바뀐다.
    video = tmp_path / "v.mp4"
    import time
    time.sleep(0.01)
    video.write_bytes(b"fake-but-longer-content-after-rerender")

    r2 = client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    assert calls["n"] == 2, "영상이 바뀌었으면 재추출이 실제로 돌아야 한다"
    assert r2.json()["frames"][0]["ts"] == pytest.approx(2.0)


def test_frames_no_reextract_when_video_unchanged(client, tmp_path, monkeypatch):
    """영상이 그대로면(서명 동일) 여전히 재사용한다 -- 기존 회귀 방지의 연장."""
    _job_with_video(tmp_path)
    calls = {"n": 0}

    def counting(video_path, dest_dir, n=10):
        calls["n"] += 1
        dest = Path(dest_dir); dest.mkdir(parents=True, exist_ok=True)
        out = []
        for i in range(n):
            p = dest / f"grid_{i:02d}.jpg"; p.write_bytes(b"img")
            out.append((p, float(i)))
        return out

    monkeypatch.setattr(app_module, "extract_grid_frames", counting)
    client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    client.post("/api/produce/thumb/frames", json={"job_id": "j1"})
    assert calls["n"] == 1


def test_frames_404_when_no_video(client, tmp_path):
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j2", ["https://x/1"], 30, "template")  # video_path 없음
    r = client.post("/api/produce/thumb/frames", json={"job_id": "j2"})
    assert r.status_code == 404


def test_frames_404_unknown_job(client):
    assert client.post("/api/produce/thumb/frames", json={"job_id": "nope"}).status_code == 404


def test_file_serves_frame(client, tmp_path, monkeypatch):
    _job_with_video(tmp_path)
    d = tmp_path / "thumbs" / "j1"
    d.mkdir(parents=True)
    (d / "grid_00.jpg").write_bytes(b"imgdata")
    r = client.get("/api/produce/thumb/file/j1/grid_00.jpg")
    assert r.status_code == 200
    assert r.content == b"imgdata"


def test_file_blocks_path_traversal(client, tmp_path):
    """../../ 로 남의 파일을 못 읽는다.

    ⚠️ **이 테스트는 우리 가드의 자물쇠가 아니다**(2026-07-17 실측). 우리 가드를 통째로
    지워도 초록으로 남는다 — Starlette 라우팅이 경로 세그먼트의 %2F를 먼저 거부하고,
    httpx가 보내기도 전에 RFC 3986 정규화로 `..`를 지워버리기 때문이다
    (`httpx.Request('GET', '…/file/j1/../../secret.txt').url.path` == `/api/produce/thumb/secret.txt`).
    즉 여기서 초록인 것은 **프레임워크가 막아준다**는 뜻이지 우리 코드가 막는다는 뜻이 아니다.
    우리 가드의 진짜 자물쇠는 아래 `test_guard_functions_direct_traversal`이다(뮤테이션으로 확인됨).
    이 테스트는 그래도 남긴다 — 스택 전체(프레임워크+우리 코드)가 이 요청에 비밀을 안 흘린다는
    회귀 방어로는 유효하다. 다만 **이게 초록이라고 순회가 막혔다고 믿지 마라.**
    """
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"TOPSECRET")
    (tmp_path / "thumbs" / "j1").mkdir(parents=True)
    r = client.get("/api/produce/thumb/file/j1/..%2F..%2Fsecret.txt")
    assert r.status_code in (400, 404)
    assert b"TOPSECRET" not in r.content


def test_file_blocks_traversal_in_job_id(client, tmp_path):
    """job_id 자리로 순회 시도. ⚠️ 위와 같은 이유로 **우리 가드의 자물쇠가 아니다** — 참고만."""
    secret = tmp_path / "secret.txt"
    secret.write_bytes(b"TOPSECRET")
    r = client.get("/api/produce/thumb/file/..%2F..%2F/secret.txt")
    assert r.status_code in (400, 404)
    assert b"TOPSECRET" not in r.content


def test_file_404_missing(client, tmp_path):
    (tmp_path / "thumbs" / "j1").mkdir(parents=True)
    assert client.get("/api/produce/thumb/file/j1/nope.jpg").status_code == 404


def test_file_blank_name_not_500(client, tmp_path):
    """픽스2: name=" "(URL %20)은 윈도우에서 path.exists()가 True를 낸다
    (경로 끝 공백을 잘라내 디렉터리 자신과 같아짐) -- 하지만 is_file()은 False다.
    .exists()만 보면 FileResponse가 '경로가 파일이 아니다' RuntimeError를 던져
    아무도 안 잡는 500이 나간다(실측). 400/404여야 한다."""
    d = tmp_path / "thumbs" / "j1"
    d.mkdir(parents=True)
    r = client.get("/api/produce/thumb/file/j1/%20")
    assert r.status_code in (400, 404)


def test_guard_file_blank_name_direct_not_500(tmp_path):
    """HTTP 레벨은 서버·클라이언트 정규화가 섞여 신뢰 못하므로 함수를 직접 불러
    실제로 우리 가드(is_file 체크)가 막는지 확인한다."""
    d = tmp_path / "thumbs" / "j1"
    d.mkdir(parents=True)
    import shopping_shorts.app as app_module
    orig = app_module._THUMB_DIR
    app_module._THUMB_DIR = tmp_path / "thumbs"
    try:
        r = app_module.api_thumb_file("j1", " ")
        assert r.status_code in (400, 404)
    finally:
        app_module._THUMB_DIR = orig


def test_guard_functions_direct_traversal(client, tmp_path):
    """가드 로직을 HTTP 클라이언트를 거치지 않고 직접 호출해 검증한다.

    실측(2026-07-17): httpx(TestClient가 쓰는 라이브러리)는 URL의 리터럴 `..`
    세그먼트를 RFC3986 정규화로 전송 전에 스스로 지워버리고(`/file/j1/..` →
    `/file`), `%2F` 인코딩은 FastAPI/Starlette 라우팅 자체가 세그먼트에 `/`를
    허용하지 않아 우리 함수에 도달하기 전에 404가 난다. 즉 위 HTTP 레벨
    traversal 테스트 2건은 실제로 통과하지만 우리 `_thumb_dir`/`api_thumb_file`
    가드를 통과시켜서가 아니라 프레임워크가 먼저 막아서다(뮤테이션해도 안 죽음,
    실측 확인함). 이 테스트는 그 우회를 걷어내고 가드 함수 자체를 직접 불러
    실제로 우리 코드가 막는지 검증한다."""
    _job_with_video(tmp_path)
    assert app_module._thumb_dir("../x") is None
    assert app_module._thumb_dir("..") is None
    assert app_module._thumb_dir(".") is None
    r = app_module.api_thumb_file("j1", "..")
    assert r.status_code == 400
    r2 = app_module.api_thumb_file("j1", "sub/../../secret.txt")
    assert r2.status_code == 400
