"""관제263 10-26 — 원본·재료 '쓸 구간만 받기'.
이미숙 원본 uOj3ix7qCj8(2233초)는 HLS 없이 DASH 만 → `--download-sections`(ffmpeg 가 주소를 직접 읽음)가 형식 셋 다 0B 로 멈춰 통째 722MB.
고친 길: engine/yt_fetch.dash_sections = DASH mp4 의 sidx(조각 목차)로 쓸 구간 조각 바이트만 받는다 · runner c_origin_get 은 조각 시각(t0)을 그대로 offset 으로.
구간이 안 되면 통째로 되돌아가되 경보 1줄(warn)."""
import struct
from pathlib import Path

from tools.calcopy.engine import yt_fetch as YF
from tools.calcopy.hybrid import runner_ops as RO


def _box(typ: bytes, body: bytes) -> bytes:
    return struct.pack(">I4s", 8 + len(body), typ) + body


def _fake_dash(seg_sizes, seg_dur=90000, scale=90000):
    """ftyp + moov + sidx(v0) — 조각 크기 seg_sizes, 조각 길이 seg_dur/scale 초."""
    ftyp = _box(b"ftyp", b"dash\x00\x00\x00\x00iso6")
    moov = _box(b"moov", b"\x00" * 40)
    body = bytes([0, 0, 0, 0]) + struct.pack(">IIIIHH", 1, scale, 0, 0, 0, len(seg_sizes))
    for s in seg_sizes:
        body += struct.pack(">III", s, seg_dur, 0x90000000)
    sidx = _box(b"sidx", body)
    return ftyp + moov + sidx, len(ftyp) + len(moov)


def test_dash_index_reads_sidx(monkeypatch):
    head, init_end = _fake_dash([1000, 2000, 3000])
    monkeypatch.setattr(YF, "_range_get", lambda url, h, a, b, timeout=60: (head + b"\x00" * 10000)[a:b + 1])
    init, refs = YF.dash_index("u", {})
    assert len(init) == init_end
    base = len(head)
    assert refs == [(0.0, 1.0, base, base + 999), (1.0, 2.0, base + 1000, base + 2999), (2.0, 3.0, base + 3000, base + 5999)]
    assert YF._segs_for(refs, [(1.2, 1.4)]) == [1]
    assert YF._segs_for(refs, YF._merge_spans([(1.5, 2.2), (0.1, 0.3)], 0.0)) == [0, 1, 2]


def test_dash_pick_quality_rule():
    f = lambda i, w, h, vc, fps=30: {"format_id": i, "protocol": "https", "ext": "mp4", "url": "x", "width": w, "height": h, "vcodec": vc, "acodec": "none", "fps": fps}
    aud = {"format_id": "140", "protocol": "https", "ext": "m4a", "url": "x", "vcodec": "none", "acodec": "mp4a", "abr": 129}
    v, a, _ = YF.dash_pick({"formats": [f("399", 1920, 1080, "av01"), f("299", 1920, 1080, "avc1.64002A"), f("136", 1280, 720, "avc1"), aud]})
    assert v["format_id"] == "299" and a["format_id"] == "140"          # 같은 1080 이면 avc1(디코딩 가벼움)
    v, _, _ = YF.dash_pick({"formats": [f("401", 3840, 2160, "av01"), f("299", 1920, 1080, "avc1"), aud]})
    assert v["format_id"] == "401"                                       # 가능하면 최고
    v, _, why = YF.dash_pick({"formats": [f("136", 1280, 720, "avc1"), aud]})
    assert v is None and "화질 미달" in why                               # 가로 720p 는 안 받는다 → 다음 길
    v, _, _ = YF.dash_pick({"formats": [f("136", 720, 1280, "avc1"), aud]})
    assert v["format_id"] == "136"                                       # 세로 720p 허용


def _fake_download(tmp, meta=None, dur=20.0):
    def dl(W, ids, sections, prefix="", pad=20.0, log=print):
        p = Path(W) / "src" / f"{ids[0]}.mp4"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * 2000)
        if meta:
            import json
            p.with_suffix(".sections.json").write_text(json.dumps(meta), encoding="utf-8")
        dl.pad = pad
        return [p]
    return dl


def test_origin_get_uses_dash_t0_and_pad(monkeypatch, tmp_path):
    from tools.calcopy.hybrid import screen
    dl = _fake_download(tmp_path, {"how": "dash_range", "t0": 116.049, "map": [[0.0, 116.049, 135.902]]})
    monkeypatch.setattr(screen, "download", dl)
    monkeypatch.setattr(RO, "dims", lambda p: {"name": Path(p).name, "dur": 19.85, "w": 1920, "h": 1080})
    monkeypatch.setattr(RO, "origin_offset", lambda *a, **k: (_ for _ in ()).throw(AssertionError("받아쓰기로 재면 안 된다")))
    r = RO.c_origin_get(tmp_path, {"vid": "uOj3ix7qCj8", "a": 119, "b": 131, "ts": []})
    assert r["offset"] == 116.049 and r["measured"] is True and "warn" not in r
    assert dl.pad == RO.SECTION_PAD == 2.0


def test_origin_get_whole_fallback_warns(monkeypatch, tmp_path):
    from tools.calcopy.hybrid import screen
    monkeypatch.setattr(screen, "download", _fake_download(tmp_path))
    monkeypatch.setattr(RO, "dims", lambda p: {"name": Path(p).name, "dur": 2233.4, "w": 1920, "h": 1080})
    r = RO.c_origin_get(tmp_path, {"vid": "uOj3ix7qCj8", "a": 119, "b": 131, "ts": []})
    assert r["offset"] == 0.0 and r["warn"] and r["warn"][0].startswith("[경보] 구간 받기 실패 → 통째로")
    r2 = RO.c_origin_get(tmp_path, {"vid": "uOj3ix7qCj8", "a": 0, "b": 2233, "ts": [], "full": True})
    assert "warn" not in r2                                              # 통째를 원한 호출은 경보 아님


def test_download_sections_tries_dash_first(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(YF, "dash_sections", lambda url, spans, dst, pad=2.0, log=print: seen.append(pad) or {"t0": 1.0})
    monkeypatch.setattr(YF, "sections_bad", lambda: True)               # ffmpeg 길이 멈춘 PC 여도 DASH 조각 길은 탄다
    r = YF.download_sections("https://www.youtube.com/watch?v=x", [(1, 2)], tmp_path / "x.mp4", pad=2.0)
    assert r is not None and r.returncode == 0 and seen == [2.0]
