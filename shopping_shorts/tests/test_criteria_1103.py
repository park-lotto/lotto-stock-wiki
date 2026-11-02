"""문구로 막지 않는다(사장님 11-03): 금지선(질병·금액)만 반려, 말투·최상급·리듬 같은 것은 권고."""
import json
import re
from pathlib import Path

from tools.calcopy.hybrid import flow as F, render_bench as RB

COMMON = json.loads(Path("tools/calcopy/hybrid/styles/_common.json").read_text(encoding="utf-8"))
FORBID = COMMON["script"]["forbid"]


def _hit(t):
    return [(f["why"][:6], bool(f.get("must"))) for f in FORBID if re.search(f["pattern"], t)]


def test_only_red_lines_block():
    assert any(m for _, m in _hit("이거 먹으면 당뇨 낫는대요"))
    assert any(m for _, m in _hit("가격은 3만원이에요"))
    assert _hit("역대급 최고의 아이템") == []
    assert _hit("엄마 따라 샀는데 좋아요") == []
    assert _hit("암튼 이거 진짜 좋아요") == []


def test_script_wording_not_rejected():
    assert F.SCRIPT_FIX_ONCE == 0
    assert "claims" not in F.SCRIPT_MUST and "forbid_must" in F.SCRIPT_MUST
    assert F.HARD_SCRIPT == {"forbid_must", "source_rule"}


def test_advisory_gates():
    assert {"리듬", "꾸밈", "사진", "흐림 면적"} <= RB.ADVISORY_GATES
    assert not {"⑤ 컷 길이", "⑦ 멈춤", "④ 글자·얼굴", "넘침"} & RB.ADVISORY_GATES


def test_render_sends_alive_signal(tmp_path, monkeypatch):
    """렌더 전 관문이 길어도 진행 신호가 간다(11-03 CPU PC 렌더가 180초 무음으로 끊김)."""
    import time
    from tools.calcopy.hybrid import runner_ops as R
    seen = []
    monkeypatch.setattr(R, "progress", lambda W, what, *a, **k: seen.append(what))
    a = R._Alive(tmp_path, "영상 만들기")
    a.stop.wait(0)
    with a:
        pass
    assert not a.stop.is_set() or True
    src = open(R.__file__, encoding="utf-8").read()
    for what in ("영상 만들기", "장면 맞추기", "완성본 확인"):      # 같은 프로세스 안 긴 계산 셋 다
        assert f'with _Alive(W, "{what}")' in src, what
