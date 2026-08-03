"""썸네일 PNG 저장·선택. 파일명은 **서버가 부여**한다 — 클라이언트 이름을 믿지 않는다."""
import base64
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.store import Store

# 유효한 최소 PNG(1x1)
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_DIR", tmp_path / "thumbs")
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j1", ["https://x/1"], 30, "template")
    return TestClient(app_module.app)


@pytest.fixture
def client_no_exception(tmp_path, monkeypatch):
    """서버 예외를 테스트할 때용 — 프레임워크가 기본값으로 예외를 raise한다."""
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(app_module, "_THUMB_DIR", tmp_path / "thumbs")
    s = Store(tmp_path / "t.db")
    s.create_mix_job("j1", ["https://x/1"], 30, "template")
    return TestClient(app_module.app, raise_server_exceptions=False)


_META = json.dumps({"frame_ts": 4.7, "layers": [{"text": "강남언니", "x": 0.5, "y": 0.18}]})


def test_save_writes_png_and_records(client, tmp_path):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    assert r.status_code == 200
    name = r.json()["name"]
    assert (tmp_path / "thumbs" / "j1" / name).read_bytes() == _PNG_1PX
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert thumb["results"] == [name]
    assert thumb["layers"][0]["text"] == "강남언니"   # meta가 함께 보존된다
    assert thumb["frame_ts"] == 4.7


def test_save_accumulates_gallery(client, tmp_path):
    for _ in range(3):
        client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert len(thumb["results"]) == 3
    assert len(set(thumb["results"])) == 3        # 서로 안 덮어쓴다


def test_save_ignores_client_filename(client, tmp_path):
    """'../../evil.png'을 보내도 서버 이름(thumb_N.png)으로만 떨어진다."""
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("../../evil.png", _PNG_1PX, "image/png")})
    assert r.status_code == 200
    assert r.json()["name"].startswith("thumb_")
    assert not (tmp_path / "evil.png").exists()
    assert not (tmp_path / "thumbs" / "evil.png").exists()


def test_save_rejects_non_png(client):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", b"not a png at all", "image/png")})
    assert r.status_code == 400


def test_save_404_unknown_job(client):
    r = client.post("/api/produce/thumb/save",
                    data={"job_id": "nope", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    assert r.status_code == 404


def test_select_sets_selected(client, tmp_path):
    name = client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
                       files={"file": ("x.png", _PNG_1PX, "image/png")}).json()["name"]
    r = client.post("/api/produce/thumb/select", json={"job_id": "j1", "name": name})
    assert r.status_code == 200
    assert Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]["selected"] == name


def test_select_rejects_unknown_name(client):
    """results에 없는 이름은 못 고른다 — 임의 문자열이 selected에 박히면 안 된다."""
    r = client.post("/api/produce/thumb/select", json={"job_id": "j1", "name": "../../etc/passwd"})
    assert r.status_code == 400


def test_save_meta_cannot_clobber_server_fields(client, tmp_path):
    """★frames·results·selected는 서버 소유다. 클라이언트 meta가 못 덮는다.

    meta를 통째로 thumb.update()하면 여기서 뚫린다 — 후보 프레임 목록이 날아가고
    고르지도 않은 썸네일이 selected로 박힌다.
    """
    s = Store(tmp_path / "t.db")
    s.update_mix_job("j1", thumbnail={"frames": [{"url": "/real/0.jpg", "ts": 1.0}],
                                      "results": [], "selected": None})
    evil = json.dumps({"frame_ts": 1.0, "layers": [],
                       "frames": [], "results": ["hacked.png"], "selected": "hacked.png"})
    client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": evil},
                files={"file": ("x.png", _PNG_1PX, "image/png")})
    thumb = Store(tmp_path / "t.db").get_mix_job("j1")["thumbnail"]
    assert thumb["frames"] == [{"url": "/real/0.jpg", "ts": 1.0}]   # 후보목록 보존
    assert thumb["results"] == ["thumb_1.png"]                      # 서버가 매긴 것만
    assert thumb["selected"] is None                                # 고른 적 없다


@pytest.mark.parametrize("meta_json", [
    "42",                           # int — subscript에서 TypeError
    '"frame_ts"',                   # str — subscript에서 TypeError (문자열 in 문자열은 True지만 subscript 불가)
    "null",                         # null — in 연산이 TypeError
    "[1,2,3]",                      # list — in 연산은 True 하지만 dict가 아님
])
def test_save_rejects_non_dict_meta(client_no_exception, meta_json):
    """meta가 유효한 JSON이어도 dict가 아니면 400을 반환한다.

    이전엔 dict가 아닌 유효 JSON은 1790~1792줄 for 루프에서 TypeError를 일으켜
    500이 클라이언트까지 갔다. (실측: meta="42", '"frame_ts"', "null"은 500)
    """
    r = client_no_exception.post("/api/produce/thumb/save",
                                data={"job_id": "j1", "meta": meta_json},
                                files={"file": ("x.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 100, "image/png")})
    assert r.status_code == 400, f"meta={meta_json}에서 {r.status_code} 받음 (400 예상)"
    assert not r.json().get("ok", True), "에러 응답이어야 함"


# ── 배경 서명 기록 + 이전 영상 결과 표시(2026-08-03 사장님: "자막지우기 했는데 남아있다") ──
# 자막제거 전(preview 배경)에 만든 썸네일이 자막제거 후에도 갤러리에 남는다. 지우지 않고
# 결과별 생성 시점 배경 서명(result_sigs)을 남겨, frames API가 지금 배경과 다른 결과를 알린다.

def test_save_records_background_sig_per_result(client, tmp_path):
    st = Store(tmp_path / "t.db")
    st.update_mix_job("j1", thumbnail={"video_sig": "111:1"})
    r = client.post("/api/produce/thumb/save", data={"job_id": "j1", "meta": _META},
                    files={"file": ("x.png", _PNG_1PX, "image/png")})
    name = r.json()["name"]
    thumb = st.get_mix_job("j1")["thumbnail"]
    assert thumb["result_sigs"][name] == "111:1"


def test_frames_reports_stale_results(client, tmp_path, monkeypatch):
    """배경 서명이 다른(또는 서명 없는 옛) 결과는 stale_results로 내려온다."""
    st = Store(tmp_path / "t.db")
    video = tmp_path / "clean.mp4"; video.write_bytes(b"\x00" * 64)
    st.update_mix_job("j1", clean_video_path=str(video),
                      thumbnail={"results": ["thumb_1.png", "thumb_2.png"],
                                 "result_sigs": {"thumb_2.png": "999:9"}})
    # ffmpeg 없이: 프레임 추출을 스텁 — 검사 대상은 stale 판정이지 추출이 아니다.
    out = tmp_path / "thumbs" / "j1"; out.mkdir(parents=True)
    frame = out / "grid_00.jpg"; frame.write_bytes(b"j")
    monkeypatch.setattr(app_module, "extract_grid_frames",
                        lambda *a, **kw: [(frame, 0.0)])
    d = client.post("/api/produce/thumb/frames", json={"job_id": "j1"}).json()
    assert d["ok"] is True
    # thumb_1=서명 없음(옛 결과)·thumb_2=다른 배경 서명 → 둘 다 '이전 영상'
    assert set(d["stale_results"]) == {"thumb_1.png", "thumb_2.png"}
