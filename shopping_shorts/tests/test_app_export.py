"""내보내기 엔드포인트 배선 검증 (job → 경로 → zip → 응답).

유닛(test_export_bundle)은 순수 로직·zip을 보지만, 실 사고는 배선(저장위치≠읽기위치)에서 난다.
여기선 실제 job을 시딩하고 work 폴더에 실 mp4/mp3를 두고 HTTP로 호출해 zip이 나오는지 본다.
"""
import subprocess
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from shopping_shorts import app as app_module
from shopping_shorts.store import Store


def _mk_video(path, dur=6):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"color=c=red:s=320x568:r=30:d={dur}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
                   check=True, capture_output=True, stdin=subprocess.DEVNULL)


def _mk_audio(path, dur=2.0):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={dur}",
                    "-c:a", "libmp3lame", str(path)], check=True, capture_output=True,
                   stdin=subprocess.DEVNULL)


def _seed(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    work_root = tmp_path / "mix_jobs"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    monkeypatch.setattr(app_module, "_MIX_WORK_DIR", work_root)
    client = TestClient(app_module.app)
    store = Store(db)

    # work/<job>/s0/src.mp4  +  tts mp3(비트별) + 최종영상
    work = work_root / "j1"
    (work / "s0").mkdir(parents=True)
    _mk_video(work / "s0" / "src.mp4", 6)
    t0 = work / "tts" / "beat_0.mp3"; t0.parent.mkdir(parents=True); _mk_audio(t0, 2.0)
    t1 = work / "tts" / "beat_1.mp3"; _mk_audio(t1, 1.5)
    final = work / "final.mp4"; _mk_video(final, 4)

    store.create_mix_job("j1", ["https://www.instagram.com/reel/AAA111/"], 20, "free")
    store.update_mix_job("j1", status="done", video_path=str(final), seo={
        "title": "제목입니다", "tags": ["#샘플"]}, edit_plan={
        "structure": "free", "beats": [
            {"beat_idx": 0, "role": "훅", "narration": "첫 장면이에요", "tts_path": str(t0),
             "primary": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0}},
            {"beat_idx": 1, "role": "본문", "narration": "둘째 장면", "tts_path": str(t1),
             "primary": {"video_id": "s0", "seg_id": "s0-1", "start": 2.0, "end": 3.5}}]})
    return client


def test_export_zip_full(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/export/j1")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"
    assert "attachment" in r.headers.get("content-disposition", "")
    zf = zipfile.ZipFile(__import__("io").BytesIO(r.content))
    names = set(zf.namelist())
    assert "final.mp4" in names
    assert any(n.startswith("sources/beat_00") for n in names)
    assert "tts/beat_00.mp3" in names and "tts/beat_01.mp3" in names
    assert "captions.srt" in names and "script.txt" in names and "seo.txt" in names
    # SRT 타이밍이 비트 tts 길이(2.0s)를 반영하는지
    srt = zf.read("captions.srt").decode("utf-8")
    assert "00:00:00,000 --> 00:00:02,000" in srt and "첫 장면이에요" in srt


def test_export_part_srt_only(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/export/j1?part=srt")
    assert r.status_code == 200
    zf = zipfile.ZipFile(__import__("io").BytesIO(r.content))
    assert set(zf.namelist()) == {"captions.srt"}


def test_export_404_when_no_plan(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    Store(app_module.DB_PATH).create_mix_job("empty", ["u0"], 20, "free")
    assert client.get("/api/mix/export/empty").status_code == 404


def test_capcut_manifest_and_asset(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    d = r.json()
    # 프로젝트명 = 목록서 알아보게 헤드카피(없으면 첫 대사)를 앞에 둔다(2026-07-21).
    # j1은 헤드카피가 없어 첫 비트 대사 "첫 장면이에요"가 앞에 온다.
    assert d["ok"] and d["project"].startswith("첫 장면이에요")
    # draft_content.json·meta는 텍스트 인라인
    assert "draft_content.json" in d["texts"] and "draft_meta_info.json" in d["texts"]
    draft = __import__("json").loads(d["texts"]["draft_content.json"])
    # 3트랙(영상/음성/자막) + 에셋이 base 절대경로 참조
    assert {t["type"] for t in draft["tracks"]} == {"video", "audio", "text"}
    assert draft["materials"]["videos"][0]["path"].startswith("C:/capcutproject/CapCut Drafts/")
    # 에셋 URL이 실제로 파일을 준다
    names = {a["name"] for a in d["assets"]}
    assert any(n.endswith(".mp4") for n in names) and any(n.endswith(".mp3") for n in names)
    a = d["assets"][0]
    ra = client.get(a["url"])
    assert ra.status_code == 200 and len(ra.content) > 0


def test_capcut_needs_base(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    assert client.get("/api/mix/capcut/j1").status_code == 400   # base 없음


def test_video_download_attachment(monkeypatch, tmp_path):
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/video/j1?dl=1")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    assert r.headers["content-type"] == "video/mp4"
    # dl 없으면 인라인(첨부 아님)
    r2 = client.get("/api/mix/video/j1")
    assert "attachment" not in r2.headers.get("content-disposition", "")
