"""내보내기 엔드포인트 배선 검증 (job → 경로 → zip → 응답).

유닛(test_export_bundle)은 순수 로직·zip을 보지만, 실 사고는 배선(저장위치≠읽기위치)에서 난다.
여기선 실제 job을 시딩하고 work 폴더에 실 mp4/mp3를 두고 HTTP로 호출해 zip이 나오는지 본다.
"""
from shopping_shorts import capcut_draft as _cd
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


def test_capcut_carries_caption_style(monkeypatch, tmp_path):
    """★고객 제보(2026-08-28) "캡컷으로 보내니 템플릿은 안 따라온다".

    DB에 저장된 자막 스타일이 **API 왕복을 거쳐** draft에 실리는지 못 박는다.
    생성기만 고치고 호출부에서 안 넘기면 화면은 그대로다 —
    실제로 종전엔 app.py가 caption_style을 넘기지 않았다(참조 0건).
    """
    client = _seed(monkeypatch, tmp_path)
    # ★스타일 전달은 기본 꺼짐이다(2026-08-28 "캡컷 파일이 안 열린다" 긴급 차단).
    #   켠 상태의 동작을 보는 테스트이므로 여기서 스위치를 올린다.
    Store(app_module.DB_PATH).set_setting("capcut_style_on", "1")
    Store(app_module.DB_PATH).update_mix_job("j1", caption_style={
        "color": "#ffcc00", "size": 70, "outline": True, "outline_color": "#000000",
        "outline_w": 9, "shadow": True, "shadow_color": "#111111", "shadow_d": 4})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    t = draft["materials"]["texts"][0]
    assert t["text_color"] == "#ffcc00", f"글자색이 캡컷까지 안 갔다: {t['text_color']}"
    assert t["font_size"] > _cd._CC_BASE_FONT_SIZE, f"크기가 기본 그대로다: {t['font_size']}"
    assert t["border_color"] == "#000000", "외곽선이 안 갔다"
    assert t["has_shadow"] is True, "그림자가 안 갔다"
    assert t["type"] == "subtitle", "캡션이 아니라 텍스트가 됐다"


def test_capcut_without_style_still_exports(monkeypatch, tmp_path):
    """스타일이 없어도 내보내기는 종전대로 된다(회귀 0)."""
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    t = draft["materials"]["texts"][0]
    assert t["text_color"] == "#ffffff" and t["font_size"] == round(_cd._CC_BASE_FONT_SIZE, 2)


def test_capcut_carries_watermark(monkeypatch, tmp_path):
    """★고객 제보 2단계: 꾸미기 워터마크(채널 닉네임)가 캡컷까지 간다."""
    client = _seed(monkeypatch, tmp_path)
    # ★스타일 전달은 기본 꺼짐이다(2026-08-28 "캡컷 파일이 안 열린다" 긴급 차단).
    #   켠 상태의 동작을 보는 테스트이므로 여기서 스위치를 올린다.
    Store(app_module.DB_PATH).set_setting("capcut_style_on", "1")
    Store(app_module.DB_PATH).update_mix_job("j1", deco={
        "watermark": {"text": "캡틴살림꾼", "color": "#ffffff", "size": 30, "alpha": 0.6}})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    wm = [m for m in draft["materials"]["texts"] if m["type"] == "text"]
    assert wm and "캡틴살림꾼" in wm[0]["content"], "워터마크가 캡컷까지 안 갔다"
    assert len([t for t in draft["tracks"] if t["type"] == "text"]) == 2, "자막과 같은 트랙에 섞였다"


def test_capcut_carries_deco_frame(monkeypatch, tmp_path):
    """★고객 제보 3단계: 꾸미기 틀(채널명 바·제목)이 캡컷 타임라인에 얹힌다.

    PNG를 굽는 곳은 mix_pipeline._template_layer 한 곳이다(미리보기·렌더와 같은 그림).
    여기서는 그 함수를 가짜 PNG로 대신해 **배관**(굽기 → 복사 → 절대경로 → 트랙)을 본다.
    """
    client = _seed(monkeypatch, tmp_path)
    # ★스타일 전달은 기본 꺼짐이다(2026-08-28 "캡컷 파일이 안 열린다" 긴급 차단).
    #   켠 상태의 동작을 보는 테스트이므로 여기서 스위치를 올린다.
    Store(app_module.DB_PATH).set_setting("capcut_style_on", "1")
    png = tmp_path / "frame_src.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 40)     # 내용은 안 본다(복사만 확인)
    monkeypatch.setattr(app_module.mix_pipeline, "_template_layer",
                        lambda tpl, first_beat_dur=0: {"_abspath": str(png), "alpha": 1})
    Store(app_module.DB_PATH).update_mix_job("j1", deco={
        "template": {"span": "full", "frame": {"preset": "sul_lucky", "channel": "테스트채널"}}})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    d = r.json()
    draft = __import__("json").loads(d["texts"]["draft_content.json"])
    ph = [m for m in draft["materials"]["videos"] if m["type"] == "photo"]
    assert ph, "꾸미기 틀이 캡컷까지 안 갔다"
    assert ph[0]["path"].startswith("C:/capcutproject/CapCut Drafts/"), \
        f"절대경로가 아니다(상대경로는 Media Not Found로 확정 기각됐다): {ph[0]['path']}"
    # 실제 파일이 draft 폴더에 복사돼 프론트가 받아갈 수 있어야 한다
    assert any(a["name"] == "deco_frame.png" for a in d["assets"]), \
        f"틀 PNG가 에셋 목록에 없다: {[a['name'] for a in d['assets']]}"


def test_capcut_survives_broken_template(monkeypatch, tmp_path):
    """★틀 하나 때문에 내보내기가 막히면 안 된다 — 틀만 빠지고 나머지는 그대로."""
    client = _seed(monkeypatch, tmp_path)

    def boom(tpl, first_beat_dur=0):
        raise RuntimeError("틀 굽기 실패")

    monkeypatch.setattr(app_module.mix_pipeline, "_template_layer", boom)
    Store(app_module.DB_PATH).update_mix_job("j1", deco={"template": {"span": "full"}})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, "틀이 깨졌다고 내보내기가 통째로 막혔다"
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    assert {t["type"] for t in draft["tracks"]} == {"video", "audio", "text"}


def test_capcut_style_is_on_by_default(monkeypatch, tmp_path):
    """★기본 켜짐으로 되돌림(2026-08-30). 08-28 긴급차단은 원인을 잘못 짚었다.

    배포 이력 실측: 고객 실패 3건(20:43·21:33·21:59)은 전부 스타일 코드가 **라이브에
    올라가기 전**(첫 라이브 22:06:12)에 났다. 스타일이 돌던 37분 동안 캡컷 내보내기
    요청은 0건이었다 — 즉 고객이 못 연 draft는 스타일이 만든 것이 아니다.
    (진짜 결함은 조각 캐시 서명 누락과 남의 PC 폰트 경로였고, 둘 다 함께 고쳤다.)
    """
    client = _seed(monkeypatch, tmp_path)
    Store(app_module.DB_PATH).update_mix_job("j1", caption_style={"color": "#ffcc00", "size": 70},
                                             deco={"watermark": {"text": "채널"}})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    t = draft["materials"]["texts"][0]
    assert t["text_color"] == "#ffcc00", "자막 색이 안 따라갔다"
    assert [tr["type"] for tr in draft["tracks"]] == ["video", "audio", "text", "text"], \
        "워터마크 트랙이 안 생겼다"


def test_capcut_style_can_be_turned_off(monkeypatch, tmp_path):
    """되돌릴 일이 생기면 설정 한 곳(capcut_style_off=1)으로 끈다 — 배포 없이 막는 길."""
    client = _seed(monkeypatch, tmp_path)
    st = Store(app_module.DB_PATH)
    st.update_mix_job("j1", caption_style={"color": "#ffcc00", "size": 70},
                      deco={"watermark": {"text": "채널"}})
    st.set_setting("capcut_style_off", "1")
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    assert draft["materials"]["texts"][0]["text_color"] == "#ffffff", "껐는데 스타일이 갔다"
    assert [tr["type"] for tr in draft["tracks"]] == ["video", "audio", "text"], \
        "껐는데 트랙이 늘었다"


# ── 최종렌더에 있던 재료가 API 왕복을 거쳐 캡컷까지 간다(2026-08-30 전구간 점검) ──
# 생성기만 고치고 app.py에서 안 넘기면 화면은 그대로다 — 실제로 caption_style이
# 그랬다(2026-08-28). 그래서 배선까지 못 박는다.

def test_capcut_carries_bgm(monkeypatch, tmp_path):
    """🎵 제작소에서 올린 배경음악이 캡컷 오디오 트랙에 실린다(종전 0건)."""
    client = _seed(monkeypatch, tmp_path)
    work = tmp_path / "mix_jobs" / "j1"
    _mk_audio(work / "bgm.mp3", 5.0)      # deco.bgm.file 은 work/<file>에 저장된다
    Store(app_module.DB_PATH).update_mix_job("j1", deco={
        "bgm": {"file": "bgm.mp3", "volume": 25}})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    d = r.json()
    draft = __import__("json").loads(d["texts"]["draft_content.json"])
    bgm = [m for m in draft["materials"]["audios"] if m["path"].endswith("bgm.mp3")]
    assert bgm, "배경음악이 캡컷까지 안 갔다"
    seg = next(s for t in draft["tracks"] if t["type"] == "audio"
               for s in t["segments"] if s["material_id"] == bgm[0]["id"])
    assert seg["volume"] == 0.25, f"볼륨이 안 따라갔다: {seg['volume']}"
    # 음원 파일도 실제로 받아진다(에셋 URL이 살아 있어야 프론트가 폴더에 쓴다)
    url = next(a["url"] for a in d["assets"] if a["name"] == "bgm.mp3")
    assert client.get(url).status_code == 200


def test_capcut_carries_headcopy(monkeypatch, tmp_path):
    """✍ 머리카피가 투명 PNG로 구워져 캡컷 영상 트랙에 얹힌다(종전 0건).

    ★캡컷 텍스트로 옮기지 않는 이유는 clip.transform 좌표계가 아직 미실측이기 때문.
      PNG는 풀캔버스라 좌표 변환이 필요 없다(꾸미기 틀과 같은 방법).
    """
    client = _seed(monkeypatch, tmp_path)
    Store(app_module.DB_PATH).update_mix_job("j1", headcopy={
        "text": "이거 하나로 끝", "color": "#ffcc00", "size": 80, "x": 50, "y": 20})
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200, r.text
    d = r.json()
    draft = __import__("json").loads(d["texts"]["draft_content.json"])
    hc = [m for m in draft["materials"]["videos"]
          if m["path"].endswith("headcopy.png")]
    assert hc, "머리카피가 캡컷까지 안 갔다"
    seg = next(s for t in draft["tracks"] if t["type"] == "video"
               for s in t["segments"] if s["material_id"] == hc[0]["id"])
    # 렌더와 같은 구간: 마지막 비트(t0=2.0s) 전까지
    assert seg["target_timerange"] == {"start": 0, "duration": 2_000_000}
    assert "headcopy.png" in {a["name"] for a in d["assets"]}


def test_capcut_still_exports_without_extras(monkeypatch, tmp_path):
    """재료가 하나도 없어도 종전대로 3트랙이 나온다(회귀 0)."""
    client = _seed(monkeypatch, tmp_path)
    r = client.get("/api/mix/capcut/j1", params={"base": "C:/capcutproject/CapCut Drafts"})
    assert r.status_code == 200
    draft = __import__("json").loads(r.json()["texts"]["draft_content.json"])
    assert {t["type"] for t in draft["tracks"]} == {"video", "audio", "text"}
