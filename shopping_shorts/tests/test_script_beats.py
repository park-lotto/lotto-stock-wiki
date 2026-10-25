# -*- coding: utf-8 -*-
"""재미썸홈 대본 박자(고조 2~3·반전 1~2)·편끼리 첫마디 겹침 — script_audit.beats_count·sibling_repeat (사장님 10-25 규칙서 §2 8·8-1·8-2).
판 설정 = tools/calcopy/hybrid/styles/재미썸홈판.json script.audit(scope preset = preset_make 작품 대본만)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.calcopy.hybrid import script_audit as SA  # noqa: E402
from tools.calcopy.hybrid import styles as ST  # noqa: E402

RULES = {r["kind"]: r for r in ST.load("재미썸홈판")["script"]["audit"]}
CH = ROOT / "channel/evenshopping"


def _doc(texts, **kw):
    return {"채널": "재미썸홈", "preset": "channel/evenshopping/preset/숏템템플릿/manifest.json",
            "lines": [{"text": t, "tts": t, "role": f"r{i}"} for i, t in enumerate(texts)], **kw}


def test_beats_counted_by_line_head():
    d = _doc(["제목 줄 심지어 반전.", "요즘 난리 난 물건이 있는데,", "이게 말도 안 되는 게 한 번에 된다는 거.",
              "심지어 물에 넣어도 멀쩡한데,", "근데 진짜 충격적인 건 버려도 된다는 거.", "그래서 다들 난리라고."])
    got = SA.beats_count(d, RULES["beats"])
    assert len(got["고조"]) == 2 and len(got["반전"]) == 1      # 첫 줄(제목)의 '심지어'·'반전'은 안 센다


def test_beats_fail_when_flat():
    d = _doc(["제목.", "요즘 난리 난 물건이 있는데,", "이건 바로 물건.", "써 보면 편하다는 거.", "그래서 난리라고."])
    ok, why = SA.rule_check(RULES["beats"], d, {})
    assert not ok and "고조 0줄" in why and "반전 0줄" in why


def test_mid_line_connector_not_counted():
    d = _doc(["제목.", "화력이 세서 심지어 스테이크까지 구워내는데,"])
    assert SA.beats_count(d, RULES["beats"])["고조"] == []          # 줄 머리 14자 밖 '심지어'는 박자가 아니다


def test_version_from_doc_channel(tmp_path):
    p = tmp_path / "작품" / "대본.json"
    p.parent.mkdir()
    p.write_text(json.dumps(_doc(["a."]), ensure_ascii=False), encoding="utf-8")
    assert SA.version_of(p, None) == "재미썸홈판"                   # 옛 동작: 경로에 '재미썸홈' 없으면 잇썸홈판으로 잘못 잼


def _write(root, name, d):
    p = root / name / "대본.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


SAME = ["{x} 천재가 만든 물건의 정체.", "요즘 난리 난 {x} 있는데,", "이건 바로 {x}.", "이게 말도 안 되는 게 {x} 된다는 거.",
        "심지어 {x} 멀쩡한데,", "근데 진짜 충격적인 포인트는 {x} 버려도 된다고.", "그래서 요즘엔 {x} 난리라고."]


def test_sibling_repeat_catches_same_frame(tmp_path):
    a = _write(tmp_path, "작품1", _doc([s.format(x="빨대") for s in SAME], topic="빨대"))
    _write(tmp_path, "작품2", _doc([s.format(x="접시") for s in SAME], topic="접시"))
    r = SA.sibling_repeat(a, json.loads(a.read_text(encoding="utf-8")), RULES["sibling_repeat"], "재미썸홈판")
    assert r["n"] == 1 and r["worst"] > 0.25 and any("역할 순서" in b for b in r["bad"])


def test_sibling_repeat_passes_varied(tmp_path):
    a = _write(tmp_path, "작품1", _doc([s.format(x="빨대") for s in SAME], topic="빨대"))
    _write(tmp_path, "작품2", _doc(["접시 닦다 지친 천재의 발명품.", "지금 해외에서 조회수가 터진 양파 같은 접시가 있다는데,",
                                    "바로 겹겹 접시.", "더러워진 윗장만 떼면 새 접시가 나오고,", "근데 반전은 칼질해도 안 뚫린다는 거.",
                                    "도마까지 대신한다고."], topic="접시"))
    r = SA.sibling_repeat(a, json.loads(a.read_text(encoding="utf-8")), RULES["sibling_repeat"], "재미썸홈판")
    assert not r["bad"], r


def test_same_product_variants_not_compared(tmp_path):
    a = _write(tmp_path, "작품9_A", _doc([s.format(x="차") for s in SAME], topic="티인퓨저"))
    _write(tmp_path, "작품9_B", _doc([s.format(x="차") for s in SAME], topic="티인퓨저"))
    assert SA.sibling_repeat(a, json.loads(a.read_text(encoding="utf-8")), RULES["sibling_repeat"], "재미썸홈판")["n"] == 0


def test_real_episodes_6_7_8_fail():
    """사보타주 확인 — 사장님이 짚은 작품6·7·8(같은 8줄 틀)은 새 규칙에서 떨어져야 한다."""
    for n in ("작품6_취객선비잔", "작품7_신라미소소스볼", "작품8_호작도와인마개"):
        r = SA.audit(CH / n / "대본.json")
        assert r["version"] == "재미썸홈판"
        assert any(x["kind"] == "sibling_repeat" and not x["ok"] for x in r["rules"]), n


def test_hybrid_docs_not_in_scope(tmp_path):
    d = _doc(["제목.", "써 보면 편하다는 거."])
    d.pop("preset")
    p = _write(tmp_path, "재미썸홈판", d)
    assert not [x for x in SA.audit(p)["rules"] if x["kind"] in ("beats", "sibling_repeat")]
