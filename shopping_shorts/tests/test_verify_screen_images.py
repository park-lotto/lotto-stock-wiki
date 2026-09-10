import copy
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from shopping_shorts import edit_plan as ep, screen_verify as sv


class Settings:
    def __init__(self, values=None):
        self.values = values if values is not None else {"screen_verify_enabled": "1"}

    def get_setting(self, key, default=""):
        return self.values.get(key, default)


@pytest.fixture
def material(tmp_path):
    thumb = tmp_path / "seg_thumbs" / "s1.jpg"
    thumb.parent.mkdir()
    Image.new("RGB", (24, 24), "red").save(thumb)
    beat = {"beat_idx": 0, "narration": "red object", "fit": 5,
            "primary": {"seg_id": "s1", "video_id": "s0", "start": 0, "end": 2}}
    segs = {"s1": dict(beat["primary"], scene_desc="blue object")}
    return tmp_path, beat, segs, thumb.read_bytes()


def test_image_wins_and_both_judgments_are_logged(material):
    """★2026-09-10 계약 변경: 그림이 있으면 **글자는 묻지 않는다**(칸당 2회 → 1회).
    라이브 240칸 대조에서 둘이 갈리면 언제나 그림이 맞았다 — 글자를 남길 이유가
    그 대조뿐이었고 끝났다. 그림을 못 구한 칸만 종전대로 글자로 본다(아래 폴백 테스트).
    """
    work, beat, segs, image = material
    before = copy.deepcopy(beat)
    calls = []

    def image_call(prompt, schema, data):
        assert data == image
        assert "blue object" not in prompt
        calls.append(1)
        return {"ok": True, "why": "red"}

    out = ep.verify_beat_screens([beat], segs, store=Settings(), work=work,
        call=lambda *a: {"ok": False, "why": "blue"}, image_call=image_call, job_id="j")
    assert out[0]["fit"] == 5 and out[0]["primary"] == beat["primary"]
    assert beat == before and calls == [1]
    record = json.loads((work / "screen_verify.jsonl").read_text(encoding="utf-8"))
    assert record["calls"] == 1 and record["text"] is None   # 글자는 안 물었다
    assert record["job_id"] == "j" and record["image"]["ok"] is True


@pytest.mark.parametrize("values", [{}, {"screen_verify_enabled": "0"},
                                     {"verify_screens_enabled": "1"}])
def test_default_off_does_not_even_read_image(material, monkeypatch, values):
    work, beat, segs, _ = material
    monkeypatch.setattr(sv, "frame", lambda *a: pytest.fail("frame read while OFF"))
    assert ep.verify_beat_screens([beat], segs, store=Settings(values), work=work) == [beat]
    assert ep.verify_beat_screens([beat], segs, work=work) == [beat]


@pytest.mark.parametrize("result", [None, {}, {"ok": "false"}, RuntimeError("model down")])
def test_bad_image_response_is_fail_open(material, result):
    work, beat, segs, _ = material

    def fail(*args):
        if isinstance(result, Exception):
            raise result
        return result

    assert ep.verify_beat_screens([beat], segs, store=Settings(), work=work,
        call=lambda *a: {"ok": False}, image_call=fail) == [beat]


def test_missing_or_corrupt_image_falls_back_to_text(material, capsys):
    work, beat, segs, _ = material
    (work / "seg_thumbs" / "s1.jpg").write_bytes(b"broken")
    out = ep.verify_beat_screens([beat], segs, store=Settings(), work=work,
        call=lambda *a: {"ok": False}, image_call=lambda *a: pytest.fail("image call"))
    assert out[0]["fit_evidence"] == "verify_failed"
    assert "이미지 확보 실패" in capsys.readouterr().err


def test_existing_video_extract_uses_shared_thumb_function(material, monkeypatch):
    from shopping_shorts import frame_extract
    work, beat, segs, image = material
    (work / "seg_thumbs" / "s1.jpg").unlink()
    source = work / "s0" / "source.mp4"
    source.parent.mkdir()
    source.write_bytes(b"existing video")

    def extract(src, dest, seg, filename):
        assert src == source and seg == segs["s1"]
        out = dest / filename
        out.write_bytes(image)
        return out

    monkeypatch.setattr(frame_extract, "extract_seg_thumb", extract)
    assert sv.frame(segs["s1"], "s1", work) == image


def test_same_input_cached_changed_narration_rechecked(material):
    work, beat, segs, _ = material
    calls = []

    def judge(*args):
        calls.append(1)
        return {"ok": len(calls) > 1}

    def verify(beats):
        return ep.verify_beat_screens(beats, segs, store=Settings(), work=work,
                                      call=judge, image_call=judge)

    # 그림만 묻는다 → 호출 수는 칸당 1회(2026-09-10 계약 변경).
    out = verify([beat])
    assert out[0]["fit"] == 2
    assert verify(out) == out and len(calls) == 1      # 같은 입력은 다시 안 묻는다
    out[0]["narration"] = "changed"
    changed = verify(out)
    assert len(calls) == 2 and changed[0]["fit"] == 5
    assert "fit_evidence" not in changed[0]


def test_sdk_receives_one_real_image_part(material, monkeypatch):
    from shopping_shorts import frame_script
    image = material[-1]
    captured = {}

    def generate(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(text='{"ok":true}')

    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr(frame_script, "_call_with_key_rotation", lambda fn, **kw: fn(client, "model"))
    assert sv.image_call("prompt", ep._SCREEN_VERIFY_SCHEMA, image) == {"ok": True}
    assert len(captured["contents"]) == 2
    part = captured["contents"][1]
    assert part.inline_data.data == image and part.inline_data.mime_type == "image/jpeg"


@pytest.mark.parametrize("manual", [False, True])
def test_store_verifies_after_final_fill_and_sources(manual, monkeypatch):
    from shopping_shorts import store as st
    calls = []

    class JobStore(Settings):
        def get_mix_job(self, jid):
            return {"extract": {"s0": {"segments": [
                {"seg_id": "s1", "start": 0, "end": 2, "scene_desc": "red"}]}}}

    def fill(beats, seg_map):
        calls.append("fill")
        return [dict(b, primary={"seg_id": "final"}) for b in beats]

    def verify(beats, seg_map, **kwargs):
        calls.append("verify")
        assert beats[0]["primary"]["seg_id"] == "final"
        assert kwargs["job_id"] == "job"
        return [dict(b, verify_why="checked") for b in beats]

    monkeypatch.setattr(ep, "_fill_beat_screen_time", fill)
    monkeypatch.setattr(ep, "verify_beat_screens", verify)
    plan = {"beats": [{"narration": "red", "narration_manual": manual,
                        "primary": {"seg_id": "s1"}}]}
    out = st._ensure_screen_time(plan, JobStore(), "job")
    assert calls == ["fill", "verify"] and out["beats"][0]["verify_why"] == "checked"
