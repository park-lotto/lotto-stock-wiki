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


def test_alt_scene_fix_uses_product_video_when_photos_banned():
    """10-27 4회차 아크네스: 사진 0% 판에서 alt_scene_fix 가 원본 장면을 상품 사진으로 바꿔 사진 컷 반려 → 받아 온 제품 영상으로."""
    from tools.calcopy.hybrid import rules as RU
    st = _st("alt")
    st["material"] = {"files": [{"name": "prod_1_0.jpg"}, {"name": "V1.mp4"}]}
    st["_msheets"] = {"shots": {"V1.mp4": [[0.0, 0.5], [2.0, 6.0], [6.0, 9.5]]}}
    pool = F._alt_fill_pool(st)
    assert pool and all(isinstance(p, dict) and p["src"] == "V1.mp4" for p in pool) and pool[0]["ss"] == 2.2
    S = {"lines": [{"id": "O1", "kind": "orig"}, {"id": "L8", "kind": "tts"}]}
    M = {"cuts": {"L8": [{"src": "O1.mp4", "ss": 3.0}]}}
    assert RU.alt_scene_fix(S, M, {"O1.mp4"}, pool)
    assert M["cuts"]["L8"][0]["src"] == "V1.mp4" and not RU.alt_scene_problems(S, M, {"O1.mp4"})


def test_photo_fallback_only_when_no_product_video():
    """사장님 10-27 '그때만 상품 사진': 비슷한 제품 영상을 못 찾은 편만 원본 말 뒤 제품 줄에 사진 허용 — 계획 photo_gate 도 그 줄을 뺀다."""
    from tools.calcopy.hybrid import render_bench as RB, styles as STY
    st = _st("alt")
    st["material"] = {"files": [{"name": "prod_1_0.jpg", "w": 600, "h": 600}]}
    assert F._alt_photo_fallback(st) and "prod_1_0.jpg" in F._offer_dims(st)
    S = {"lines": [{"id": "O1", "kind": "orig"}, {"id": "L8", "kind": "tts"}, {"id": "L9", "kind": "tts"}]}
    assert F._photo_lines(S) == ["L8", "L9"]
    M = F._prep_material(st, S, {"cuts": {}})
    assert M.get("photo_lines") == ["L8", "L9"]
    T = {"end": 10.0, "cuts": [{"line": "L8", "src": "prod_1_0.jpg", "t0": 6.0, "t1": 8.0}, {"line": "L2", "src": "prod_1_0.jpg", "t0": 1.0, "t1": 2.0}]}
    style = STY.load("잇템로그판_v2")
    assert RB.photo_share(T["cuts"], 10.0, M["photo_lines"]) == 0.1           # L8 은 빼고 L2 만 센다
    assert RB.photo_gate(T, style, M)                                         # 예외 줄 밖 사진(L2)은 그대로 걸린다
    st["material"]["files"].append({"name": "V1.mp4"})                        # 제품 영상을 찾았으면 예외 없음
    assert not F._alt_photo_fallback(st) and "photo_lines" not in F._prep_material(st, S, {"cuts": {}})
