"""사진(jpg)은 ffprobe 길이 칸이 없을 수 있다 — probe 가 죽지 않는다(10-27 run4 a편 쿠팡 사진 2장 KeyError → 제품 사진 0장)."""
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import common as C  # noqa: E402


def test_probe_without_duration(monkeypatch):
    monkeypatch.setattr(C, "run", lambda *a, **k: types.SimpleNamespace(stdout=json.dumps({"streams": [{"width": 1000, "height": 1000}], "format": {}})))
    assert C.probe("x.jpg") == (1000, 1000, 0.0)
