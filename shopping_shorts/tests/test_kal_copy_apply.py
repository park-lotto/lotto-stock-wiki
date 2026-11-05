"""kal copy·apply·뜯기 칸 — 개정안 kal v2 채택(관제 319, 11-06).
copy-04 strict 모르는 키 · copy-05 확정 뒤 save 거절·fix_value why 필수·판 번호 · apply-05 freeze · apply-06 cleanup
apply-09 upload_pack · apply-17 칸 하나 · tteutgi-13 인트로·엔딩 · tteutgi-26 구간별 음량
"""
import json
from pathlib import Path

import numpy as np
import pytest

from shopping_shorts.calcopy_frame import schema
from tools.calcopy.engine import kal, preset_save, upload_pack, analyze, audio_comp


def test_copy04_strict_unknown_key():
    F = {"canvas": [1080, 1920], "layers": [{"kind": "bg", "rgb": [0, 0, 0]}], "made_from": {"x": 1}}
    schema.validate(F, strict=True)                           # 기록 칸(made_from)은 통과
    F["mystery"] = 1
    schema.validate(F)                                        # 기본 = 종전(조용히 정규화)
    with pytest.raises(schema.FrameError, match="모르는 키"):
        schema.validate(F, strict=True)


def test_copy05_apply05_freeze(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({"sources": []}), encoding="utf-8")
    mp4 = tmp_path / "f.mp4"
    mp4.write_bytes(b"v")
    with pytest.raises(ValueError):
        preset_save.freeze(tmp_path, str(mp4), "미달", "x")
    M = preset_save.freeze(tmp_path, str(mp4), "통과", "시청 판정")
    assert M["frozen_at"] and M["version"] == 1 and M["reference"]["sha256"] and M["history"][-1]["what"] == "freeze"
    with pytest.raises(ValueError, match="확정"):
        preset_save.save({}, {}, tmp_path, "s", "t")
    with pytest.raises(ValueError, match="why"):
        preset_save.fix_value(tmp_path, "a", 1, "")


def test_apply06_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    monkeypatch.setattr(kal, "DATA", tmp_path / "d")
    S = kal.State("s", "@s", None, 2, None)
    b = tmp_path / "d/s"
    (b / "kal/frames_a/strips").mkdir(parents=True)
    (b / "kal/frames_a/x.jpg").write_bytes(b"1")
    (b / "src").mkdir()
    (b / "src/a.mp4").write_bytes(b"1")
    r = kal.cleanup(S)
    assert r["removed"] >= 1 and not (b / "kal/frames_a").exists() and (b / "src/a.mp4").exists()


def test_apply09_upload_pack():
    assert upload_pack.check("충격 실화 #쇼츠") and "미끼" in upload_pack.check("충격 실화 #쇼츠")[0]
    assert upload_pack.check("좋은 글") == ["해시태그 0개 — 판 범위 1~5"]
    assert upload_pack.check("좋은 글 #a #b") == []
    assert upload_pack.check("좋은 글 #a #a")


def test_apply17_one_cell():
    assert kal.one_cell_check({"upgrades": [{"cell": "caption.font"}]}) == []
    assert kal.one_cell_check({"upgrades": [{"cell": "caption.font"}, {"cell": "bgm"}]})
    assert kal.one_cell_check({"upgrades": [{"cell": "timing.x"}]})


def test_tteutgi13_intro_outro():
    r = analyze.intro_outro([[0.0, 1.2], [5.0, 6.0], [18.9, 20.0]], 20.0)
    assert r["intro"]["len"] == 1.2 and r["outro"]["t0"] == 18.9
    assert analyze.intro_outro([[5.0, 6.0]], 20.0) == {"intro": None, "outro": None}


def test_tteutgi26_seg_loudness():
    lv = np.full(500, -60.0)
    lv[0:100] = -20.0       # 0~2초 나레
    lv[200:300] = -30.0     # 4~6초 원음
    segs = [{"start": 0.0, "end": 2.0, "kind": "narration"}, {"start": 4.0, "end": 6.0, "kind": "source"}]
    r = audio_comp.seg_loudness(lv, segs)
    assert r["narration"] > r["source"] > r["gap_floor"]


def test_copy04_strict_layer_key():
    F = {"canvas": [1080, 1920], "layers": [{"kind": "bg", "rgb": [0, 0, 0], "glow_px": 3}]}
    with pytest.raises(schema.FrameError, match="layers\[0\].glow_px"):
        schema.validate(F, strict=True)


def test_apply01_preset_pack(tmp_path):
    from tools.calcopy.engine import preset_pack
    d = tmp_path / "p"
    (d / "sources").mkdir(parents=True)
    (d / "frame.json").write_text('{"a": 1}', encoding="utf-8")
    (d / "sources/s.json").write_text('{"b": 2}', encoding="utf-8")
    (d / "_hand").mkdir()
    (d / "_hand/x.json").write_text("{}", encoding="utf-8")
    r1 = preset_pack.pack(d, tmp_path / "a.zip")
    r2 = preset_pack.pack(d, tmp_path / "b.zip")
    assert r1["ok"] and r1["n"] == 2 and (tmp_path / "a.zip").read_bytes() == (tmp_path / "b.zip").read_bytes()   # 결정적
    (d / "manifest.json").write_text('{"src": "C:/숏템_칼카피/x"}', encoding="utf-8")
    r3 = preset_pack.pack(d, tmp_path / "c.zip")
    assert not r3["ok"] and "절대경로" in r3["bad"][0] and not (tmp_path / "c.zip").exists()


def test_verify49_tear_ours_reuses_by_sha(tmp_path, monkeypatch):
    monkeypatch.setattr(kal, "ROOT", tmp_path)
    S = kal.State("s", "@s", None, 2, None)
    mp4 = tmp_path / "o.mp4"
    mp4.write_bytes(b"o")
    n = []

    def fake(m, out, llm=None, materials=True):
        n.append(materials)
        Path(out).mkdir(parents=True, exist_ok=True)
        (Path(out) / "뜯기.json").write_text(json.dumps({"audio": {"transcript": {"segments": [{"start": 0, "end": 1, "text": "가"}]}}}), encoding="utf-8")
    monkeypatch.setattr(analyze, "analyze", fake)
    assert kal.tear_ours(S, str(mp4))["segments"] and kal.tear_ours(S, str(mp4))["segments"] and n == [True]
