"""해외원본형 + 비슷한 제품(alt)이면 그 제품 영상을 받아 재료에 더한다(사장님 10-27 '제품 영상 받아 오기').
3회차 실측: 원본 말 뒤 제품 줄은 원본 장면 금지·사진 금지·재료 영상 0개라 쓸 화면이 없어 비슷한 제품 편 3편이 사진 컷 반려."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402


def _st(mode):
    return {"version": "잇템로그판_v2", "fmt": "해외원본형", "log": [], "tries": {}, "read": {}, "bench": {"id": "B"},
            "origin": {"id": "O1", "files": [{"name": "O1.mp4"}]}, "origins": [{"id": "O1"}],
            "product": {"mode": mode, "name": "시슨드시 선크림 50ml 백탁없는", "product_id": "1"}, "research": {"keywords": ["sunscreen"]}}


def test_alt_flow_searches_picks_downloads_and_adds_material():
    st = _st("alt")
    do = F.f_material(st, {}, {}, {})["do"]
    sc = next(d for d in do if d["cmd"] == "screen")
    assert sc["queries"] and "시슨드시" in sc["queries"][0]
    r = F.f_material_got(st, {"stills": {"files": []}, "shots": {}, "screen": {"rows": [{"id": "V1"}, {"id": "O1"}], "sheets": []}}, {}, {})
    assert r == {"goto": "f_alt_ask"}
    r = F.f_alt_ask(st, {}, {}, {})
    assert r["then"] == "f_alt_pick" and r["review"][0]["id"] == "screen_pick"
    r = F.f_alt_pick(st, {}, {"screen_pick": {"chosen": [{"id": "V1"}, {"id": "O1"}]}}, {})
    assert [i["id"] for i in r["do"][0]["items"]] == ["V1"]          # 원본은 제품 영상 후보에서 뺀다
    r = F.f_alt_dl(st, {"dl": {"files": [{"name": "V1.mp4", "w": 1080, "h": 1920}]}}, {}, {})
    assert r == {"goto": "f_clean"} and any(f["name"] == "V1.mp4" for f in st["material"]["files"])


def test_exact_product_does_not_search():
    st = _st("exact")
    assert not any(d["cmd"] == "screen" for d in F.f_material(st, {}, {}, {})["do"])
    F.f_material_got(st, {"stills": {"files": []}, "shots": {}}, {}, {})
    assert F.f_alt_ask(st, {}, {}, {}) == {"goto": "f_clean"}
