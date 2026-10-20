# -*- coding: utf-8 -*-
"""모션 자산 작업대(관제 244) — 관리자 전용 자산 갤러리·판정·조립·렌더 길목.

못 박는 것:
1. 페이지·목록·판정·렌더·원본(ref)·작업물 길 전부 비관리자 403(정적 마운트로 뚫리지 않는다).
2. 목록은 장부 주인(mograph.ledger.load_parts)을 그대로 읽는다 — 화면이 따로 목록을 들고 있지 않다.
3. 판정은 장부 레코드의 verdicts[] 에 쌓이고 줄 수는 늘지 않는다 / 모르는 태그는 버린다 / good|bad 만.
4. 원본(ref) 서빙은 경로 탈출·허용 안 된 확장자를 막고, brand/ 는 팩 brand 폴더로 넘어간다.
5. 장면표: 할인가는 계산값만(iart 규칙), 장면 종류별 최소 길이, 줄 수에 따라 장면 종류가 줄어든다.
6. 조립: 작업 폴더 src/index.html 하나에 PLAN·길이가 박히고, 미리보기와 렌더가 같은 파일을 가리킨다.
브라우저·렌더 실측은 tools/mograph/check_bench.py 가 한다."""
import json
import pathlib

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts.mograph import ledger, plan, sources

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _client(monkeypatch, admin=True):
    if admin:
        monkeypatch.setattr(app_module, "_require_admin", lambda request: None)
    else:
        monkeypatch.setattr(app_module, "_require_admin",
                            lambda request: JSONResponse({"error": "관리자 전용"}, status_code=403))
    return TestClient(app_module.app)


@pytest.fixture
def ledger_tmp(tmp_path, monkeypatch):
    p = tmp_path / "parts.jsonl"
    p.write_text(json.dumps({"slug": "demo-scene", "kind": "scene", "label": "데모", "impl": {"pack": "cha-remix", "folder": "demo-scene"},
                             "license": {"status": "ref_only"}}, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(ledger, "PARTS", p)
    return p


def test_비관리자는_모든_길이_403(monkeypatch):
    c = _client(monkeypatch, admin=False)
    for url in ("/mograph_bench", "/mograph_bench.html", "/api/admin/mograph/parts", "/api/admin/mograph/works",
                "/api/admin/mograph/render/x", "/api/admin/mograph/out/x/out.mp4", "/api/admin/mograph/ref/cha-remix/x/index.html",
                "/api/admin/mograph/work/work-0123456789/src/index.html"):
        assert c.get(url).status_code == 403, url
    for url in ("/api/admin/mograph/verdict", "/api/admin/mograph/render", "/api/admin/mograph/work"):
        assert c.post(url, json={}).status_code == 403, url


def test_목록은_장부_주인을_그대로_읽는다(monkeypatch, ledger_tmp):
    c = _client(monkeypatch)
    j = c.get("/api/admin/mograph/parts").json()
    assert [p["slug"] for p in j["parts"]] == [p["slug"] for p in ledger.load_parts()] == ["demo-scene"]
    assert j["tags"] == list(ledger.VERDICT_TAGS)
    html = (ROOT / "shopping_shorts" / "static" / "mograph_bench.html").read_text(encoding="utf-8")
    assert "/api/admin/mograph/parts" in html and "parts.jsonl" not in html.split("<script>")[-1].split("const")[0]


def test_판정은_verdicts에_쌓이고_줄은_안_는다(monkeypatch, ledger_tmp):
    c = _client(monkeypatch)
    before = ledger_tmp.read_text(encoding="utf-8").count("\n")
    r = c.post("/api/admin/mograph/verdict", json={"slug": "demo-scene", "verdict": "good", "tags": ["세로안됨", "없는태그"], "note": "x"})
    assert r.status_code == 200 and r.json()["part"]["verdicts"][-1]["tags"] == ["세로안됨"]
    r = c.post("/api/admin/mograph/verdict", json={"slug": "demo-scene", "verdict": "bad"})
    assert r.status_code == 200
    rec = ledger.find_part("demo-scene")
    assert [v["verdict"] for v in rec["verdicts"]] == ["good", "bad"]
    assert ledger_tmp.read_text(encoding="utf-8").count("\n") == before
    assert c.post("/api/admin/mograph/verdict", json={"slug": "demo-scene", "verdict": "meh"}).status_code == 400
    assert c.post("/api/admin/mograph/verdict", json={"slug": "none", "verdict": "good"}).status_code == 404
    assert c.post("/api/admin/mograph/verdict", json={"slug": "../x", "verdict": "good"}).status_code == 400


def test_원본_서빙은_탈출을_막고_brand는_팩_폴더로(monkeypatch, tmp_path):
    ref = tmp_path / "ref"
    piece = ref / "remix-7-source" / "demo-scene"
    piece.mkdir(parents=True)
    (piece / "index.html").write_text("<html><head></head><body>x</body></html>", encoding="utf-8")
    (ref / "remix-7-source" / "brand").mkdir()
    (ref / "remix-7-source" / "brand" / "gsap.min.js").write_text("//gsap", encoding="utf-8")
    (ref / "secret.txt").write_text("no", encoding="utf-8")
    monkeypatch.setenv("MOGRAPH_REF_DIR", str(ref))
    c = _client(monkeypatch)
    r = c.get("/api/admin/mograph/ref/cha-remix/demo-scene/index.html")
    assert r.status_code == 200 and "window.__timelines=window.__timelines||{}" in r.text   # 미리보기용 한 줄
    assert c.get("/api/admin/mograph/ref/cha-remix/demo-scene/brand/gsap.min.js").status_code == 200
    assert c.get("/api/admin/mograph/ref/cha-remix/demo-scene/..%2F..%2Fsecret.txt").status_code in (400, 404)
    assert c.get("/api/admin/mograph/ref/cha-remix/demo-scene/secret.txt").status_code == 404      # .txt 허용 안 됨
    assert c.get("/api/admin/mograph/ref/cha-remix/nope/index.html").status_code == 404
    assert sources.piece_dir("cha-remix", "../demo-scene") is None


def test_장면표_할인가는_계산값만_장면별_최소길이():
    pl = plan.plan_from_lines(["훅", "상품", "가격", "특징", "끝"], {"price": 39900, "discount_pct": 35})
    assert pl["product"]["sale_price"] == 25940            # 39900×0.65=25935 → 10원 단위
    assert [s["type"] for s in pl["scenes"]] == ["hook", "product", "price", "features", "cta"]
    for s in pl["scenes"]:
        assert s["dur"] >= plan.MIN_BY_TYPE[s["type"]]
    assert pl["total"] == round(sum(s["dur"] for s in pl["scenes"]), 2)
    assert [s["type"] for s in plan.plan_from_lines(["a", "b"])["scenes"]] == ["hook", "cta"]
    assert [s["type"] for s in plan.plan_from_lines(["a"])["scenes"]] == ["hook"]
    assert [s["type"] for s in plan.plan_from_lines(list("abcdefg"))["scenes"]] == ["hook", "product", "price", "features", "features", "features", "cta"]
    with pytest.raises(ValueError):
        plan.plan_from_lines([])


def test_조립은_파일_하나에_길이와_장면표를_박는다(monkeypatch, tmp_path):
    from shopping_shorts.mograph import compose, render
    monkeypatch.setattr(render, "RENDERS_DIR", tmp_path / "renders")
    w = compose.build_work(["훅 한 줄", "상품 줄", "가격 줄"], {"name": "데모", "price": 10000, "discount_pct": 10}, "shop-basic")
    src = tmp_path / "renders" / w["id"] / "src"
    html = (src / "index.html").read_text(encoding="utf-8")
    assert 'data-duration="%s"' % w["plan"]["total"] in html and "__PLAN__" not in html
    assert '"sale_price": 9000' in html
    assert (src / "vendor" / "gsap.min.js").exists() and (src / "fonts" / "Pretendard-Bold.otf").exists()
    assert compose.load_work(w["id"])["total"] == w["plan"]["total"]
    # 같은 입력 → 같은 id(덮어씀), 다른 입력 → 다른 id
    assert compose.build_work(["훅 한 줄", "상품 줄", "가격 줄"], {"name": "데모", "price": 10000, "discount_pct": 10}, "shop-basic")["id"] == w["id"]
    assert compose.build_work(["다른 훅"], {}, "shop-basic")["id"] != w["id"]
    # 길목: 작업물 src 는 허용 확장자만, 작업 번호 꼴만
    c = _client(monkeypatch)
    assert c.get("/api/admin/mograph/work/%s/src/index.html" % w["id"]).status_code == 200
    assert c.get("/api/admin/mograph/work/%s/src/../work.json" % w["id"]).status_code in (400, 404)
    assert c.get("/api/admin/mograph/work/bad-id/src/index.html").status_code == 404


def test_사이드바_숏템팩_묶음에_작업대_항목():
    js = (ROOT / "shopping_shorts" / "static" / "sidebar.js").read_text(encoding="utf-8")
    assert '"/mograph_bench", admin: true' in js
