"""🖼 '이 장면을 썸네일로' — 6단계 장면 → 7단계 후보 (2026-08-30 사장님 요청).

여기서 반드시 지켜야 하는 것 둘:
  ① [다른 장면 더 뽑기](재추출)로 **핀이 사라지면 안 된다** — 사장님이 고른 장면이
     조용히 없어지는 게 이 기능의 유일한 치명상이다.
  ② 핀 그림은 미리보기와 **같은 함수**(_beatframe_file)에서 나와야 한다 — 두 벌이 되면
     화면에서 본 장면과 썸네일로 간 장면이 달라진다(0순위-B).
"""
import json
import pytest

from shopping_shorts import app as A
from shopping_shorts.store import Store


@pytest.fixture()
def job(tmp_path, monkeypatch):
    """빈 DB + 썸네일 폴더를 tmp로 돌린 mix_job 하나."""
    db = tmp_path / "t.db"
    monkeypatch.setattr(A, "DB_PATH", str(db))
    monkeypatch.setattr(A, "_THUMB_DIR", tmp_path / "thumb")
    st = Store(str(db))
    jid = "job_pin_test"
    st.create_mix_job(jid, ["u"], 30, "template")
    st.update_mix_job(jid, edit_plan={"beats": [{"start": 0.0}, {"start": 3.5}, {"start": 7.0}]})
    return jid, tmp_path


def _fake_frame(tmp_path, name="2_vid@3.5.jpg"):
    """_beatframe_file이 돌려줄 가짜 프레임 파일(내용은 아무거나 — 복사만 검증한다)."""
    p = tmp_path / "beatframes"
    p.mkdir(exist_ok=True)
    f = p / name
    f.write_bytes(b"\xff\xd8\xff" + b"jpegbytes")
    return f


def test_pin_creates_candidate_at_front(job, monkeypatch):
    jid, tmp = job
    src = _fake_frame(tmp)
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: src)

    r = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})
    assert r["ok"] is True
    assert r["label"] == "장면 2"                     # 사람이 세는 번호 = idx+1
    assert r["name"].startswith("pin_")

    # 파일이 실제로 썸네일 폴더에 복사됐고 내용이 원본과 같다
    copied = (tmp / "thumb" / jid / r["name"])
    assert copied.is_file()
    assert copied.read_bytes() == src.read_bytes()

    # DB에 pins로 남는다 — frames(서버 소유 자동추출 목록)를 건드리지 않는다
    thumb = Store(A.DB_PATH).get_mix_job(jid)["thumbnail"]
    assert [p["name"] for p in thumb["pins"]] == [r["name"]]
    assert thumb.get("frames") in (None, [])


def test_pin_survives_regrid(job, monkeypatch):
    """★재추출(더 뽑기)이 자동 프레임을 갈아엎어도 핀은 후보 맨 앞에 남는다."""
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    pin = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})["name"]

    st = Store(A.DB_PATH)
    thumb = st.get_mix_job(jid)["thumbnail"]
    # 자동 추출이 새 16장을 채운 상황을 그대로 흉내낸다(frames를 통째 교체)
    thumb["frames"] = [{"url": f"/g/{i}", "ts": i} for i in range(16)]
    st.update_mix_job(jid, thumbnail=thumb)

    merged = A._with_pins(jid, st.get_mix_job(jid)["thumbnail"], thumb["frames"])
    assert len(merged) == 17
    assert merged[0]["pin"] == pin                    # 핀이 맨 앞
    assert merged[0]["label"] == "장면 2"
    assert [f["url"] for f in merged[1:]] == [f"/g/{i}" for i in range(16)]


def test_pin_same_beat_twice_is_one(job, monkeypatch):
    """같은 장면을 두 번 보내도 후보가 두 개로 늘지 않는다(같은 파일로 덮어씀)."""
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    A.api_thumb_pin({"job_id": jid, "beat_idx": 1})
    r2 = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})
    assert len(r2["pins"]) == 1


def test_unpin_removes_file_and_entry(job, monkeypatch):
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    name = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})["name"]
    path = tmp / "thumb" / jid / name

    r = A.api_thumb_pin({"job_id": jid, "name": name, "remove": True})
    assert r["ok"] is True and r["pins"] == []
    assert not path.exists()


def test_unpin_refuses_unknown_name(job, monkeypatch):
    """★임의 파일 삭제 통로가 되면 안 된다 — 목록에 없는 이름은 거절."""
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    A.api_thumb_pin({"job_id": jid, "beat_idx": 1})
    victim = tmp / "thumb" / jid / "thumb_1.png"       # 사장님이 저장한 결과물
    victim.write_bytes(b"\x89PNG\r\n\x1a\n")

    r = A.api_thumb_pin({"job_id": jid, "name": "thumb_1.png", "remove": True})
    assert getattr(r, "status_code", None) == 400
    assert victim.exists()                             # 안 지워졌다


def test_missing_frame_returns_error_not_crash(job, monkeypatch):
    """프레임을 못 뜨면 404 + 사람 말 — 조용한 성공은 안 된다."""
    jid, _ = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: None)
    r = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})
    assert getattr(r, "status_code", None) == 404


def test_pin_with_missing_file_is_skipped(job, monkeypatch):
    """파일이 사라진 핀은 목록에서 조용히 빠진다(깨진 이미지 대신)."""
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    name = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})["name"]
    (tmp / "thumb" / jid / name).unlink()

    thumb = Store(A.DB_PATH).get_mix_job(jid)["thumbnail"]
    assert A._with_pins(jid, thumb, [{"url": "/g/0", "ts": 0}]) == [{"url": "/g/0", "ts": 0}]


def test_pins_visible_before_mix_video_exists(job, monkeypatch, tmp_path):
    """★영상이 아직 없어도 보낸 장면은 후보에 보인다(2026-08-30 실브라우저 관찰로 발견).

    핀은 비트 프레임에서 오므로 믹스 영상과 무관한데, 종전엔 '믹스 영상 없음' 404가
    먼저 나가 사장님이 6단계에서 보낸 장면이 7단계에서 통째로 사라져 보였다.
    """
    jid, tmp = job
    monkeypatch.setattr(A, "_beatframe_file", lambda job, job_id, i: _fake_frame(tmp))
    name = A.api_thumb_pin({"job_id": jid, "beat_idx": 1})["name"]

    r = A.api_thumb_frames({"job_id": jid})           # 이 job엔 preview/final mp4가 없다
    assert getattr(r, "status_code", None) is None, "영상 없다고 404를 내면 핀이 사라진다"
    assert [f["pin"] for f in r["frames"]] == [name]


def test_no_video_and_no_pin_still_404(job):
    """핀도 없고 영상도 없으면 종전대로 404 — 안내문이 그대로 돌아야 한다."""
    jid, _ = job
    r = A.api_thumb_frames({"job_id": jid})
    assert getattr(r, "status_code", None) == 404
