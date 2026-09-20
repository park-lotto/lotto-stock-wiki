# -*- coding: utf-8 -*-
"""관리자 목록 응답 점검 (2026-08-23).

★왜 생겼나: /api/admin/customers가 settings 테이블을 통째로 실어
   응답이 6.25MB가 됐다(last_run::youtube 하나가 5MB). fetch 4.4초 +
   파싱 1.8초 동안 화면은 "승인 대기 0명 / 고객 0명"으로 보여서,
   사장님이 '가입자가 없다'고 오해할 수 있는 상태였다.
   고객 155명 데이터는 75KB뿐이었다 — 무거운 건 전부 운영 로그였다.
"""
import re
from pathlib import Path


SRC = Path(__file__).resolve().parents[1]


def _app_text():
    return (SRC / "app.py").read_text(encoding="utf-8")


def _admin_html():
    return (SRC / "static" / "admin.html").read_text(encoding="utf-8")


def test_admin_customers_does_not_dump_all_settings():
    """★설정을 통째로 실으면 안 된다. 운영 로그가 응답에 섞여 화면이 멈춘다."""
    t = _app_text()
    i = t.index('@app.get("/api/admin/customers")')
    # ★고정 길이(2600자)로 자르면 함수가 조금만 길어져도 검사 범위 밖으로 나간다.
    #   2026-08-29에 실제로 그랬다(일괄 한도 조회가 들어가며 본문이 늘었다).
    #   함수 끝(다음 라우트 데코레이터)까지를 본문으로 잡는다.
    nxt = t.find("\n@app.", i + 10)
    body = t[i:nxt if nxt > 0 else i + 4000]
    assert '"settings": st.all_settings()' not in body, (
        "관리자 목록이 settings 전체를 보낸다 — last_run::* 같은 운영 로그까지 딸려간다")
    assert "_ADMIN_SETTING_KEYS" in body, "화면이 쓰는 키로 좁혀야 한다"


def test_front_setting_fields_are_all_savable():
    """★화면에 입력칸이 있는데 서버 화이트리스트에 없으면 **조용히 저장이 무시된다.**
    실제로 trial_grant_points가 그 상태였다(2026-08-23 발견) — 사장님이 체험
    지급 포인트를 바꿔도 값이 안 들어갔다."""
    front = set(re.findall(r"\['([a-z_]+)','", _admin_html()))
    assert front, "admin.html에서 SETTING_FIELDS를 못 읽었다 — 이 테스트를 고쳐라"

    t = _app_text()
    i = t.index("_ADMIN_SETTING_KEYS = {")
    block = t[i:t.index("}", i) + 1]
    server = set(re.findall(r'"([a-z_]+)"', block))

    missing = sorted(front - server)
    assert not missing, (
        "화면엔 입력칸이 있는데 서버가 저장을 거부하는 설정: %s" % missing)


def test_admin_page_shows_loading_not_empty():
    """★빈 목록과 '아직 안 왔음'을 구분해야 한다.
    구분이 없으면 로딩 중 화면이 '고객 0명'과 똑같이 보인다."""
    h = _admin_html()
    assert h.count("불러오는 중") >= 2, "승인대기·고객 표 둘 다 초기 상태가 필요하다"


def test_admin_load_failure_is_visible():
    """★실패를 삼키면 안 된다. 조용히 0명으로 남으면 아무도 원인을 못 찾는다."""
    h = _admin_html()
    assert re.search(r"load\(\)\s*\.catch", h), (
        "첫 load() 실패가 화면에 표시되지 않는다")
