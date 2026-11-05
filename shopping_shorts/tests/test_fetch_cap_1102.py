"""관제 304 F — 받기 강제 상한(긴 변 1920)·벤치 720·받기 기록. 판단 주인 = engine/yt_fetch.cap_fmt · 값 주인 = yt_fetch.Q_CAP."""
import json

from tools.calcopy.engine import yt_fetch as YF


def test_cap_is_shared_with_media_download():
    from shopping_shorts import media_download as MD
    assert MD._Q_CAP == YF.Q_CAP == "[width<=1920][height<=1920]"


def test_every_chain_gets_cap_on_video_only():
    out = YF.cap_fmt("137+ba[ext=m4a]/bv*[height>=1080]+ba/bv*[height>=720]+ba/b")
    for alt in out.split("/"):
        head = alt.split("+")[0]
        assert "<=" in head, alt
    assert "ba[ext=m4a]" in out and "ba[ext=m4a][" not in out      # 소리 칸은 그대로


def test_cap_keeps_section_chain_and_preview():
    assert all("<=" in a.split("+")[0] for a in YF.cap_fmt(YF.FMT_SECTION_1080).split("/"))
    assert all("<=" in a for a in YF.cap_fmt(YF.FMT_PREVIEW_360).split("/"))


def test_cap_twice_is_same():
    a = YF.cap_fmt("bv*+ba/b")
    assert YF.cap_fmt(a) == a


def test_audio_only_untouched():
    assert YF.cap_fmt("bestaudio[ext=m4a]/bestaudio") == "bestaudio[ext=m4a]/bestaudio"


def test_cap_args_changes_only_f_value():
    args = ["-f", "bv*+ba/b", "--merge-output-format", "mp4", "https://youtu.be/x"]
    out = YF.cap_args(args)
    assert out[1] == YF.cap_fmt("bv*+ba/b") and out[2:] == args[2:]
    assert YF.cap_args(["-J", "https://youtu.be/x"]) == ["-J", "https://youtu.be/x"]


def test_ytdlp_entrance_applies_cap(monkeypatch):
    got = {}

    def fake(cmd, *a):
        got["cmd"] = cmd
        return YF.Result(0, "", "", 0.0)
    monkeypatch.setattr(YF, "_ytdlp_once", fake)
    YF.ytdlp(["-f", "bv*+ba/b", "/tmp/x.mp4"])
    assert any("width<=1920" in str(x) for x in got["cmd"])


def test_dash_pick_refuses_4k():
    def f(fid, w, h, codec="avc1.640028"):
        return {"protocol": "https", "ext": "mp4", "url": "u", "format_id": fid, "vcodec": codec, "acodec": "none", "width": w, "height": h}
    info = {"formats": [f("313", 3840, 2160), f("137", 1920, 1080),
                        {"protocol": "https", "ext": "m4a", "url": "u", "format_id": "140", "vcodec": "none", "acodec": "mp4a", "abr": 128}]}
    v, a, _ = YF.dash_pick(info)
    assert v["format_id"] == "137" and a["format_id"] == "140"
    info2 = {"formats": [f("315", 2160, 3840), f("299", 1080, 1920)]}
    assert YF.dash_pick(info2)[0]["format_id"] == "299"


def test_bench_720_and_material_1080():
    from tools.calcopy.hybrid import runner_ops as RO
    a = RO.bench_fmt_args(False)
    assert "[width<=1280][height<=1280]" in a[1] and "res:720" in " ".join(str(x) for x in a)
    b = RO.bench_fmt_args(True)
    assert "[width<=1920][height<=1920]" in b[1] and "[width<=1280]" not in b[1] and "res:1080" in " ".join(str(x) for x in b)


def test_foreign_flow_asks_material_bench():
    from tools.calcopy.hybrid import flow as F
    st = {"ref": "https://youtu.be/x", "version": "x", "log": [], "tries": {}}
    orig = F._fmt
    try:
        F._fmt = lambda s: "해외원본형"
        assert F.ph_bench(st, {}, {}, {})["do"][0]["material"] is True
        F._fmt = lambda s: "연예인형"
        assert "material" not in F.ph_bench(st, {}, {}, {})["do"][0]
    finally:
        F._fmt = orig


def test_bench_as_source_links_only_1080(tmp_path):
    from tools.calcopy.hybrid import runner_ops as RO
    bd = tmp_path / "bench"; bd.mkdir()
    (bd / "bench.mp4").write_bytes(b"x" * 100)
    (bd / "bench.info.json").write_text(json.dumps({"id": "abc"}), encoding="utf-8")
    (bd / "bench.cap.json").write_text(json.dumps({"material": False}), encoding="utf-8")
    dst = tmp_path / "abc.mp4"
    assert RO.bench_as_source(tmp_path, "abc", dst) is False and not dst.exists()      # 720 벤치는 재료로 안 쓴다
    (bd / "bench.cap.json").write_text(json.dumps({"material": True}), encoding="utf-8")
    assert RO.bench_as_source(tmp_path, "other", dst) is False                         # 다른 영상
    assert RO.bench_as_source(tmp_path, "abc", dst) is True and dst.stat().st_size == 100


def test_fetch_note_records_size_res_time(tmp_path, monkeypatch):
    import subprocess
    monkeypatch.setenv("SHORTEM_HOME", str(tmp_path))
    p = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=red:s=640x360:d=0.2:r=30", "-pix_fmt", "yuv420p", str(p)], check=True, stdin=subprocess.DEVNULL)
    r = YF.fetch_note(p, "시험", 1.26, "https://youtu.be/x", log=lambda s: None)
    assert (r["w"], r["h"]) == (640, 360) and r["sec"] == 1.3 and r["mb"] >= 0
    row = json.loads((tmp_path / "받기기록.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert row["file"] == "v.mp4" and row["how"] == "시험"
