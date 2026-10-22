"""관제 254 — 일본어 장면꾸미기 훅 두 줄·자막 나누기, 원본(plain)은 처음부터 자막만."""
import json
from pathlib import Path

from shopping_shorts.template_copy import scene_text, split_hook
from shopping_shorts.video_assemble import _caption_segments

ROOT = Path(__file__).resolve().parents[2]


def test_ja_hook_splits_into_two_lines():
    h1, h2 = split_hook("イタリアも驚いた天才的発明品。")
    assert h1 and h2 and not h2.endswith("。")
    assert h1 + h2 == "イタリアも驚いた天才的発明品"


def test_ja_support_has_no_double_mark():
    t = scene_text({"text": "イタリアも驚いた天才的発明品。"})
    assert "。?" not in t["bodyTitle"] and t["bodyTitle"].endswith("？")


def test_korean_hook_unchanged():
    assert split_hook("미국 천재가 만들어 떼돈 번 기발한 제품의 정체") == ("미국 천재가 만들어 떼돈 번", "기발한 제품의 정체")


def test_ja_caption_not_cut_after_no_and_short():
    segs = _caption_segments("しかも食器棚で重ねられなかった普通のカップとは違って")
    assert not any(s.endswith("普通の") or s.endswith("普通") for s in segs)
    segs = _caption_segments("ゴミばかり増えてウンザリしていた状態を丈夫なコップとして再利用できるように変えたんです")
    assert max(len(s) for s in segs) <= 12


def _rows(name, pre):
    s = (ROOT / "out" / name).read_text(encoding="utf-8")
    return json.loads(s[len(pre):].strip().rstrip(";"))


def test_plain_template_has_caption_only():
    for name, pre in (("precision20-data.js", "PRECISION20="), ("continuous20-data.js", "window.CONTINUOUS20=")):
        plain = next(p for p in _rows(name, pre) if p["id"] == "plain")
        for k in ("hook", "body", "frame"):
            binds = [l.get("bind") for l in (plain.get(k) or {}).get("lines", [])]
            assert set(binds) <= {"caption"}, (name, k, binds)
