# -*- coding: utf-8 -*-
"""사장님 프로젝트 공유 차단 시각(2026-10-08 사장님, 관제 159).

"내꺼 1단계부터 3단계 모두 버텍스로 / 내일 13시부터는 각자 버텍스 API / 꼭 api를 고객꺼 다 끊어 그 시간 되면 /
(미등록은) 무료 제미니를 사용하게 하고 그것을 알려줘라". 판정 주인 = vertex_route.plan / on."""
from datetime import datetime, timedelta, timezone

import pytest

from shopping_shorts import vertex_route as vr

KST = timezone(timedelta(hours=9))
CUT = "2026-10-08T13:00:00+09:00"
BEFORE = datetime(2026, 10, 8, 12, 59, 59, tzinfo=KST)
AFTER = datetime(2026, 10, 8, 13, 0, 0, tzinfo=KST)
MEMBER, CUSTOMER, ADMIN = 7, 5, 0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    vr.reset_cache()
    monkeypatch.setattr(vr, "_read_settings", lambda: {
        vr.SETTING_ENABLED: "1", vr.SETTING_OPS: "script_generate,ai_match", vr.SETTING_MODEL: "",
        vr.SETTING_CUTOFF: CUT})
    monkeypatch.setattr(vr, "_is_admin", lambda cid: cid == ADMIN)
    monkeypatch.setattr(vr, "member_info", lambda cid: {"project_id": "p"} if cid == MEMBER else None)
    yield
    vr.reset_cache()


def test_관리자는_시각과_무관하게_전_op():
    for now in (BEFORE, AFTER):
        assert vr.plan(ADMIN, now=now) == "owner"
        assert all(vr.on(op, cid=ADMIN, now=now) for op in vr.OPS), now


def test_미등록_고객은_13시_전엔_설정된_op만_13시부터는_전부_끊긴다():
    assert vr.plan(CUSTOMER, now=BEFORE) == "shared"
    assert vr.on("script_generate", cid=CUSTOMER, now=BEFORE) is True
    assert vr.on("ai_match", cid=CUSTOMER, now=BEFORE) is True
    assert vr.on("frame_script", cid=CUSTOMER, now=BEFORE) is False     # 분석은 원래도 무료 키풀
    assert vr.on("story", cid=CUSTOMER, now=BEFORE) is False            # 새 op가 사장님 비용으로 새지 않는다
    assert vr.plan(CUSTOMER, now=AFTER) == "free"
    assert not any(vr.on(op, cid=CUSTOMER, now=AFTER) for op in vr.OPS)


def test_cid를_안_주면_지금_작업의_주인으로_판정한다(monkeypatch):
    """★주인 컨텍스트가 없는 호출은 keyctx 기본값 0(사장님)으로 잡힌다 — 여기서 새로 정하지 않는다(usage_meter 한 곳).
    그래서 '고객 작업인데 컨텍스트를 잃은 호출'은 13시 뒤에도 사장님 프로젝트로 간다(종전과 같은 성질, 실측은 live_check)."""
    monkeypatch.setattr(vr, "current_cid", lambda: CUSTOMER)
    assert vr.on("script_generate", now=BEFORE) is True
    assert not any(vr.on(op, now=AFTER) for op in vr.OPS)
    monkeypatch.setattr(vr, "current_cid", lambda: ADMIN)
    assert vr.on("frame_script", now=AFTER) is True


def test_등록_회원은_13시_전엔_둘만_13시부터는_전_op가_자기_프로젝트():
    assert vr.plan(MEMBER, now=BEFORE) == vr.plan(MEMBER, now=AFTER) == "member"
    assert vr.on("script_generate", cid=MEMBER, now=BEFORE) is True
    assert vr.on("frame_script", cid=MEMBER, now=BEFORE) is False
    assert all(vr.on(op, cid=MEMBER, now=AFTER) for op in vr.OPS)


def test_설정이_꺼져_있어도_등록_회원은_자기_것을_쓴다(monkeypatch):
    monkeypatch.setattr(vr, "_read_settings", lambda: {vr.SETTING_ENABLED: "", vr.SETTING_CUTOFF: CUT})
    assert vr.on("script_generate", cid=MEMBER, now=BEFORE) is True
    assert vr.on("script_generate", cid=ADMIN, now=BEFORE) is False      # 스위치 끔 = 사장님 프로젝트 안 씀
    assert vr.plan(CUSTOMER, now=BEFORE) == "free"


def test_차단_시각_설정값(monkeypatch):
    def cut(v):
        monkeypatch.setattr(vr, "_read_settings", lambda: {vr.SETTING_ENABLED: "1", vr.SETTING_CUTOFF: v})
    cut("off")
    assert vr.owner_cutoff() is None and vr.cutoff_passed(AFTER) is False
    cut("2026-10-08T13:00:00")                       # 시간대 없으면 한국시간
    assert vr.cutoff_passed(BEFORE) is False and vr.cutoff_passed(AFTER) is True
    monkeypatch.setattr(vr, "OWNER_CUTOFF_DEFAULT", CUT)
    cut("")                                          # 설정 없음 → 코드 기본값
    assert vr.cutoff_passed(AFTER) is True
    cut("엉뚱한 값")                                  # 못 읽는 값 → 기본값(조용히 '안 끊음'이 되면 안 된다)
    assert vr.cutoff_passed(AFTER) is True and vr.cutoff_passed(BEFORE) is False


def test_안내_본문은_무료_API_지연과_전환_시각을_말한다():
    b = vr.notice_body(CUSTOMER, now=BEFORE)
    assert "무료 제미나이 API" in b and "끊기고" in b and "오래" in b and "10월 8일 13시" in b and "버텍스" in b
    a = vr.notice_body(CUSTOMER, now=AFTER)
    assert "무료 제미나이 API" in a and "끊기고" in a and "오래" in a and "13시" not in a


def test_try_json_은_op_스위치를_지킨다(monkeypatch):
    class _R:
        text = '{"a": 1}'

    class _M:
        def generate_content(self, **kw):
            return _R()

    class _C:
        models = _M()
    monkeypatch.setattr(vr, "client", lambda *a, **k: _C())
    monkeypatch.setattr(vr, "current_cid", lambda: ADMIN)
    assert vr.try_json("structure", "p", {"type": "object"}) == (True, {"a": 1})
    monkeypatch.setattr(vr, "current_cid", lambda: CUSTOMER)
    monkeypatch.setattr(vr, "client", lambda *a, **k: pytest.fail("미등록 고객인데 Vertex를 불렀다"))
    assert vr.try_json("structure", "p", {"type": "object"}) == (False, None)


def test_새로_붙인_호출부가_자기_op로_부른다():
    """배선 확인 — 호출부가 사라지거나 op 이름이 OPS에 없으면 조용히 키풀로만 간다(on()이 False)."""
    import inspect
    from shopping_shorts import edit_plan, script_generate, story_tag, structure_analyze
    for fn, op in ((structure_analyze.analyze_structure, "structure"), (edit_plan._vault_call_once, "edit_plan"),
                   (edit_plan.detect_video_type, "edit_plan"), (script_generate.generate_variations, "script_aux"),
                   (script_generate._refine, "script_aux"), (script_generate.detect_subject, "script_aux")):
        assert 'try_json("%s"' % op in inspect.getsource(fn), fn.__name__
        assert op in vr.OPS
    assert 'vertex_op="story"' in inspect.getsource(story_tag.make_story) and "story" in vr.OPS


# ── 주인 미상 = 관리자가 아니다(관제 159) ─────────────────────────────────────────────────
def test_주인을_모르는_호출은_관리자로_치지_않는다(monkeypatch):
    """★고치기 전엔 주인 없는 호출이 keyctx 기본값 0(사장님)으로 잡혀 관리자 판정을 받았다 —
    그 상태로 '관리자는 전 op'를 켜면 주인을 잃은 고객 분석이 전부 사장님 유료 프로젝트로 간다."""
    monkeypatch.setattr(vr, "current_cid", lambda: None)
    assert vr.plan(now=BEFORE) == "shared"
    assert vr.on("script_generate", now=BEFORE) is True       # 종전 그대로
    assert vr.on("frame_script", now=BEFORE) is False         # 관리자 특례 없음
    assert vr.plan(now=AFTER) == "free"
    assert not any(vr.on(op, now=AFTER) for op in vr.OPS)


def test_current_cid는_주인이_명시되지_않으면_None():
    import contextvars
    import threading
    from shopping_shorts import keyctx, usage_meter
    out = {}

    def _run():
        def _inner():
            out["unknown"] = vr.current_cid()
            with keyctx.owner(0):
                out["owner0"] = vr.current_cid()
            with usage_meter.track(customer_id=551):
                out["tracked"] = vr.current_cid()
        contextvars.Context().run(_inner)        # 빈 컨텍스트 + 새 스레드(usage_meter는 threading.local)
    t = threading.Thread(target=_run)
    t.start()
    t.join()
    assert out == {"unknown": None, "owner0": 0, "tracked": 551}


def test_관리자가_자기_서비스계정을_등록해_둬도_전_op(monkeypatch):
    """실측 10-08: 사장님(0번)은 서버와 같은 프로젝트의 서비스계정을 회원 칸에도 등록해 뒀다 → plan은 member."""
    monkeypatch.setattr(vr, "member_info", lambda cid: {"project_id": "p"} if cid in (MEMBER, ADMIN) else None)
    assert vr.plan(ADMIN, now=BEFORE) == "member"
    assert all(vr.on(op, cid=ADMIN, now=BEFORE) for op in vr.OPS)
    assert vr.on("frame_script", cid=MEMBER, now=BEFORE) is False       # 일반 등록 회원은 13시부터


def test_예열_워커는_작업_주인을_밝힌다(monkeypatch):
    from shopping_shorts import prewarm
    monkeypatch.setattr(prewarm, "_run_prewarm", lambda *a, **k: vr.current_cid())
    assert prewarm.run_prewarm("sc", "https://x/y", customer_id="551") == 551
    assert prewarm.run_prewarm("sc", "https://x/y", customer_id="0") == 0


def test_자동분석_병렬_구간도_주인을_밝힌다():
    import inspect
    from shopping_shorts import app as app_mod
    src = inspect.getsource(app_mod.api_produce_autoload)
    assert "_um.track(customer_id=keyroute.as_cid(cid))" in src and "return _fetch_body(e)" in src
