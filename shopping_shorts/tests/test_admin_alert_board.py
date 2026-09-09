# -*- coding: utf-8 -*-
"""관리자 화면에 **미해결 경보 목록이 상주**하는가 (2026-09-06 사장님 "관리자 화면 키면 나오게").

여태는 sidebar.js의 토스트뿐이었다 — 안 읽은 것만 뜨고, 12초 뒤 사라지고, 한 번 읽으면
다시 안 뜬다(`shown[a.id]`·`a.read`). 그래서 자리를 비운 사이 지나간 사고는 못 본다.

라이브 실측 2026-09-06 15:45: 경보 20건 중 **미해결 13건**인데 화면 어디에도 목록이 없었다
(admin.html에 'alerts' 문자열이 0건). typecast 실패율 63% 같은 고객영향 사고가 토스트로
잠깐 떴다 사라지면 끝이었다.

여기서 못 박는 것:
1. 관리자 화면이 미해결 경보를 목록으로 그린다(등급 순: 고객영향 먼저).
2. 해결된 것은 목록에서 빠진다.
3. 목록에서 직접 닫을 수 있다(수동 해결 API) — 자동으로만 닫히면 손을 쓸 수 없다.
"""
import json
import pathlib
import shutil
import subprocess

import pytest
from fastapi.testclient import TestClient

from shopping_shorts import app as app_module
from shopping_shorts import ops_alert
from shopping_shorts.store import Store

ADMIN_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "admin.html"
NODE = shutil.which("node")


def _client(monkeypatch, tmp_path):
    db = tmp_path / "t.db"
    monkeypatch.setattr(app_module, "DB_PATH", db)
    return TestClient(app_module.app), Store(db)


# ── 서버: 수동 해결 API ────────────────────────────────────────────────────
def test_경보를_손으로_닫을_수_있다(monkeypatch, tmp_path):
    """자동(resolve_kind)으로만 닫히면 사장님이 확인한 사고를 목록에서 못 내린다."""
    client, store = _client(monkeypatch, tmp_path)
    # ★raise_alert는 pytest 안에선 **일부러 아무것도 안 한다**(ops_alert.py 첫머리
    #   PYTEST_CURRENT_TEST 가드 — 서버 크론이 매일 밤 pytest를 돌리는데 실패경로
    #   테스트가 진짜 운영사고 배너를 띄운 실사고가 있었다). 그래서 쪽지함에 직접 심는다.
    store.set_setting("ops_alerts", json.dumps([
        {"id": 111, "kind": "api_key_dead_typecast", "title": "typecast 키 사망",
         "grade": "운영주의", "read": False, "resolved": None}], ensure_ascii=False))
    al = ops_alert.list_alerts(store=store)
    assert al and not al[0].get("resolved"), al

    r = client.post("/api/admin/alerts/resolve", json={"id": al[0]["id"]})
    assert r.status_code == 200, r.text
    assert r.json().get("ok"), r.text

    after = ops_alert.list_alerts(store=store)
    assert after[0].get("resolved"), f"닫히지 않았다: {after[0]}"


def test_없는_id를_닫아도_터지지_않는다(monkeypatch, tmp_path):
    client, _ = _client(monkeypatch, tmp_path)
    r = client.post("/api/admin/alerts/resolve", json={"id": 999999})
    assert r.status_code == 200, r.text
    assert r.json().get("closed") == 0, r.text


# ── 화면: 상주 목록 ────────────────────────────────────────────────────────
_HARNESS = r"""
'use strict';
let _html = '';
const _box = { set innerHTML(v){ _html = v; }, get innerHTML(){ return _html; },
               style:{}, dataset:{} };
global.document = { getElementById: (id) => (id === 'alertBoard' ? _box : null) };
global.fetch = async () => ({ ok: true, json: async () => PAYLOAD });
"""
_DRIVER = r"""
(async () => { await renderAlertBoard();
  console.log(JSON.stringify({html: _html})); })();
"""


def _run_js(tmp_path, payload):
    src = ADMIN_HTML.read_text(encoding="utf-8")
    start = "async function renderAlertBoard()"
    assert start in src, "renderAlertBoard가 없다 — 상주 목록 미구현"
    # ★_abEsc도 함께 떼어온다 — 렌더가 그걸 부른다. 안 넣으면 ReferenceError가 나서
    #   "구현이 없다"처럼 보이는 가짜 실패가 된다.
    esc_start = "function _abEsc("
    assert esc_start in src, "_abEsc가 없다"
    ei = src.index(esc_start)
    esc = src[ei:src.index("\n", ei) + 1]
    i = src.index(start)
    j = src.index("\n}", i) + 2
    js = tmp_path / "t.js"
    js.write_text("const PAYLOAD = " + json.dumps(payload) + ";\n"
                  + _HARNESS + esc + src[i:j] + _DRIVER, encoding="utf-8")
    out = subprocess.run([NODE, str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


_ALERTS = {"ok": True, "alerts": [
    {"id": 1, "grade": "운영주의", "title": "typecast 키 사망", "auto": "다른 키로 계속 돕니다",
     "todo": "회원 키면 교체 안내", "read": True, "resolved": None},
    {"id": 2, "grade": "고객영향", "title": "typecast 최근 1시간 실패율 63%",
     "todo": "지금 확인 필요", "read": True, "resolved": None},
    {"id": 3, "grade": "운영주의", "title": "이미 해결된 것", "read": True, "resolved": 1788000000},
]}


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_읽은_것도_미해결이면_목록에_남는다(tmp_path):
    """★토스트와 다른 점 — read=true여도 조치 전이면 계속 보여야 한다."""
    got = _run_js(tmp_path, _ALERTS)
    assert "typecast 키 사망" in got["html"], got["html"][:400]
    assert "실패율 63%" in got["html"], got["html"][:400]


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_해결된_것은_목록에서_빠진다(tmp_path):
    got = _run_js(tmp_path, _ALERTS)
    assert "이미 해결된 것" not in got["html"], "해결된 경보가 목록에 남아 있다"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_고객영향이_먼저_온다(tmp_path):
    """급한 것부터 눈에 들어와야 한다 — 등급 순 정렬."""
    got = _run_js(tmp_path, _ALERTS)
    h = got["html"]
    assert h.index("실패율 63%") < h.index("typecast 키 사망"), "고객영향이 뒤로 밀렸다"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_할_일과_자동조치가_함께_보인다(tmp_path):
    got = _run_js(tmp_path, _ALERTS)
    assert "다른 키로 계속 돕니다" in got["html"], "자동 조치가 안 보인다"
    assert "회원 키면 교체 안내" in got["html"], "할 일이 안 보인다"


@pytest.mark.skipif(not NODE, reason="node 없음")
def test_미해결이_없으면_조용하다(tmp_path):
    """멀쩡할 땐 빈 상자를 띄우지 않는다 — 화면이 시끄러우면 진짜 사고를 못 본다."""
    got = _run_js(tmp_path, {"ok": True, "alerts": [
        {"id": 9, "grade": "운영주의", "title": "닫힌 것", "resolved": 1788000000}]})
    assert "닫힌 것" not in got["html"], got["html"][:200]
    assert got["html"].strip() == "" or "없" in got["html"], got["html"][:200]


# ── 배선: 화면을 열 때 실제로 불리는가 ────────────────────────────────────
# ★함수만 만들고 호출부를 안 넣으면 목록이 영영 안 뜬다. 이 코드베이스에서 여러 번
#   난 실패 모양이라(handoff 배선 누락 기록들) 호출 존재를 못 박는다.
def test_화면을_열_때_목록을_그린다():
    src = ADMIN_HTML.read_text(encoding="utf-8")
    body = src[src.index("async function renderAlertBoard()"):]
    # 정의부·closeAlert 안의 재호출 말고 **초기화 호출**이 따로 있어야 한다
    assert "DOMContentLoaded',renderAlertBoard" in body.replace(" ", ""), \
        "화면 로드 시 renderAlertBoard를 부르지 않는다 — 목록이 안 뜬다"


def test_주기적으로_다시_그린다():
    """사고는 화면을 켜둔 채로도 난다 — 새로고침해야 보이면 놓친다."""
    src = ADMIN_HTML.read_text(encoding="utf-8")
    assert "setInterval(renderAlertBoard" in src.replace(" ", ""), \
        "주기 갱신이 없다 — 켜둔 화면에서 새 사고를 못 본다"
