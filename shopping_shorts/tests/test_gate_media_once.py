"""검수 단축 ①(10-26): 품질 관문이 잰 완성본 media_of 결과를 재현일치도가 그대로 쓴다 — 옛 코드는 판 리듬 안 def media() 가 인자 media 를 가려
재현일치도에 함수가 넘어가 media_of 를 다시 돌고, 캐시 열쇠에 함수 주소가 들어가 열쇠가 매번 바뀌었다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.engine import kal_analyze as K  # noqa: E402


def test_match_from_render_uses_given_media(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr(K, "media_of", lambda *a, **k: called.append(a) or {"cut_median": 9.9})
    given = {"cut_median": 1.23, "lufs": -14.0}
    seen = {}
    monkeypatch.setattr(K, "match_table", lambda bench, ours, om, bm, *a, **k: seen.setdefault("om", om) and {"verdict": "통과", "rows": []})
    import json
    R = tmp_path / "render"
    R.mkdir()
    (R / "자막표.json").write_text(json.dumps({"rows": []}), encoding="utf-8")
    (R / "timeline.json").write_text(json.dumps({"cuts": [], "end": 10.0}), encoding="utf-8")
    monkeypatch.setattr(K, "style_targets", lambda st: {})
    K.match_from_render({"name": "t", "bench": {}}, tmp_path, tmp_path, media=given)
    assert called == [] and seen["om"] is given


def test_gate_has_no_shadowing_media_def():
    src = (ROOT / "tools/calcopy/hybrid/quality_gate.py").read_text(encoding="utf-8")
    import re
    code = "\n".join(l.split("#")[0] for l in src.splitlines())
    assert not re.search(r"^\s+def media\(\):", code, re.M) and "str(media)" not in code
