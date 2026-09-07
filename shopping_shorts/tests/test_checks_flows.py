from shopping_shorts.checks import discover
from shopping_shorts.checks.flows import base
from shopping_shorts.checks.flows import flow_deco_roundtrip, flow_new_work_seed, flow_localstorage_old, flow_share_link_restart


def test_flows_discovered_have_contract():
    mods = discover.discover("flows")
    assert mods, "flow_*.py가 하나도 없다"
    for m in mods:
        assert {"name", "needs_worker", "timeout_s"} <= set(m.META) and callable(m.run)


def test_current_work_id_parses_query():
    class P:
        url = "http://x/produce?work=abc123&t=1"
    assert base.current_work_id(P()) == "abc123"
    P.url = "http://x/produce"
    assert base.current_work_id(P()) is None


def test_roundtrip_reports_which_stage_diverged():
    calls = {"local": ["A", "A", "B"], "server": ["A"]}

    class FakePage:
        url = "http://x/produce?work=w1"
        def reload(self, **kw): pass
        def wait_for_timeout(self, ms): pass
    class FakeSession:
        page = FakePage(); base_url = "http://x"
    r = base.roundtrip(FakeSession(), name="대본 왕복", signature="L2:script",
                       edit=lambda p: "A", read_local=lambda p: calls["local"].pop(0),
                       read_server=lambda s, w: calls["server"].pop(0),
                       go_away=lambda p: None, go_back=lambda p: None)
    assert r.verdict == "red" and "새로고침" in r.reason


# ── 4개 신규 흐름의 순수 로직 테스트(브라우저 없이 fake page로) ──

class FakeResp:
    def __init__(self, status=200, data=None):
        self.status = status
        self._data = data or {}
    def json(self):
        return self._data


class FakeLocator:
    def __init__(self, page, kind):
        self.page = page
        self.kind = kind
        self._text = None
    def get_by_text(self, text, exact=True):
        self._text = text
        return self
    @property
    def first(self):
        return self
    def click(self, timeout=None):
        if self.kind == "steps":
            self.page.current_step = self._text
        elif self.kind == "hccards":
            self.page.headcopy = self.page.next_headcopy
    def count(self):
        return self.page.card_count


class FakeErrors:
    def __init__(self, snap=None):
        self._snap = snap or {"pageerrors": [], "console_errors": [],
                              "client_error_posts": 0, "failed_responses": []}
    def reset(self):
        pass
    def snapshot(self):
        return self._snap


class FakePage:
    """4개 흐름이 실제로 호출하는 Playwright API 표면만 흉내낸다(왕복 판정 로직 검증용)."""
    def __init__(self, url="http://x/produce?work=w1"):
        self.url = url
        self.card_count = 1
        self.next_headcopy = {"text": "hc-A"}
        self.headcopy = None
        self.current_step = None
        self.step_labels_len = 10
        self.local_storage = {}
        self.script_state = ""
        self.seed = ""
        self.handoff_len = 0
        self.server_responses = {}   # url -> FakeResp
        self.request = _FakeRequest(self)
        self.new_work_clears = True  # ?new=1이 씨앗을 실제로 비우는가(app의 clearWork 흉내)

    def goto(self, url, wait_until=None):
        self.url = url
        if "new=1" in url and self.new_work_clears:
            self.script_state = ""; self.seed = ""; self.handoff_len = 0
    def reload(self, wait_until=None):
        pass
    def wait_for_timeout(self, ms):
        pass
    def fill(self, sel, val):
        if sel == "#scriptText":
            self.script_state = val
    def locator(self, sel):
        if sel == "#steps":
            return FakeLocator(self, "steps")
        if sel == "#hcCopyCards > *":
            return FakeLocator(self, "hccards")
        raise ValueError(sel)
    def evaluate(self, js, arg=None):
        if "STATE.headcopy" in js:
            return self.headcopy
        if "STEP_LABELS" in js:
            return self.step_labels_len
        if "localStorage.setItem" in js:
            for k, v in (arg or {}).items():
                self.local_storage[k] = v
            return None
        if "localStorage.removeItem" in js:
            for k in (arg or []):
                self.local_storage.pop(k, None)
            return None
        if "S2.seed" in js:
            return {"seed": self.seed, "script": self.script_state, "handoff": self.handoff_len}
        raise ValueError(js)


class _FakeRequest:
    def __init__(self, page):
        self.page = page
    def get(self, url):
        return self.page.server_responses.get(url, FakeResp(404, {}))


class FakeSession:
    def __init__(self, page, restart_web=None, errors=None):
        self.page = page
        self.base_url = "http://x"
        self.errors = errors or FakeErrors()
        if restart_web is not None:
            self.restart_web = restart_web


# flow_deco_roundtrip (B-11)
def test_deco_flow_green_when_matches_everywhere():
    page = FakePage()
    page.server_responses["http://x/api/produce/works/w1"] = FakeResp(
        200, {"settings": {"headcopy": {"text": "hc-A"}}})
    r = flow_deco_roundtrip.run(FakeSession(page))[0]
    assert r.verdict == "green"


def test_deco_flow_red_when_server_value_differs():
    page = FakePage()
    page.server_responses["http://x/api/produce/works/w1"] = FakeResp(
        200, {"settings": {"headcopy": {"text": "hc-DIFFERENT"}}})
    r = flow_deco_roundtrip.run(FakeSession(page))[0]
    assert r.verdict == "red"


def test_deco_flow_gray_when_no_cards():
    page = FakePage()
    page.card_count = 0
    r = flow_deco_roundtrip.run(FakeSession(page))[0]
    assert r.verdict == "gray" and "카드 0개" in r.reason


# flow_new_work_seed (B-13)
def test_new_work_seed_green_when_cleared():
    page = FakePage()
    page.new_work_clears = True   # 정상: ?new=1이 seed/script/handoff를 비운다
    r = flow_new_work_seed.run(FakeSession(page))[0]
    assert r.verdict == "green"


def test_new_work_seed_red_when_old_value_leaks():
    page = FakePage()
    page.new_work_clears = False  # 회귀 재현: ?new=1을 열어도 옛 값이 안 지워짐(B-13)
    page.seed = "옛시드"; page.handoff_len = 2
    r = flow_new_work_seed.run(FakeSession(page))[0]
    assert r.verdict == "red" and "남은 값" in r.reason


# flow_localstorage_old (B-14)
def test_localstorage_old_green_when_ui_unaffected():
    page = FakePage()
    page.step_labels_len = 10
    r = flow_localstorage_old.run(FakeSession(page))[0]
    assert r.verdict == "green"


def test_localstorage_old_red_when_step_count_broken():
    page = FakePage()
    page.step_labels_len = 3   # 옛 값이 화면을 깬 경우를 흉내
    r = flow_localstorage_old.run(FakeSession(page))[0]
    assert r.verdict == "red"


def test_localstorage_old_red_when_console_error():
    page = FakePage()
    r = flow_localstorage_old.run(
        FakeSession(page, errors=FakeErrors({"pageerrors": ["TypeError"], "console_errors": [],
                                             "client_error_posts": 0, "failed_responses": []})))[0]
    assert r.verdict == "red"


# flow_share_link_restart (B-40)
def test_share_flow_gray_without_restart_hook():
    class S:
        base_url = "http://x"; page = None
    r = flow_share_link_restart.run(S())[0]
    assert r.verdict == "gray" and "restart" in r.reason


def test_share_flow_gray_when_no_jobs():
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(200, {"ok": True, "works": []})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=lambda: None))[0]
    assert r.verdict == "gray" and "job" in r.reason


def test_share_flow_green_after_restart():
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(
        200, {"ok": True, "works": [{"job_id": "j1"}]})
    page.server_responses["http://x/api/share/link/j1"] = FakeResp(
        200, {"ok": True, "url": "http://x/s/sid123", "qr_svg": ""})
    restarted = {"n": 0}
    def restart():
        restarted["n"] += 1
        page.server_responses["http://x/s/sid123"] = FakeResp(200, {})
        page.server_responses["http://x/api/share/t/sid123"] = FakeResp(404, {"ok": False})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=restart))[0]
    assert r.verdict == "green" and restarted["n"] == 1


def test_share_flow_red_when_link_dies_after_restart():
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(
        200, {"ok": True, "works": [{"job_id": "j1"}]})
    page.server_responses["http://x/api/share/link/j1"] = FakeResp(
        200, {"ok": True, "url": "http://x/s/sid123", "qr_svg": ""})
    def restart():
        # 재시작 뒤 sid가 사라진 실사고 재현 — /s는 403(만료), /api/share/t도 403
        page.server_responses["http://x/s/sid123"] = FakeResp(403, {"ok": False})
        page.server_responses["http://x/api/share/t/sid123"] = FakeResp(403, {"ok": False})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=restart))[0]
    assert r.verdict == "red"


def test_share_flow_red_when_share_t_500s_after_restart():
    """리뷰 Important #1: /api/share/t가 500(서버 오류)이면 링크가 죽은 신호 — 초록 통과 금지."""
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(
        200, {"ok": True, "works": [{"job_id": "j1"}]})
    page.server_responses["http://x/api/share/link/j1"] = FakeResp(
        200, {"ok": True, "url": "http://x/s/sid123", "qr_svg": ""})
    def restart():
        page.server_responses["http://x/s/sid123"] = FakeResp(200, {})
        page.server_responses["http://x/api/share/t/sid123"] = FakeResp(500, {"ok": False})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=restart))[0]
    assert r.verdict != "green"
    assert r.verdict == "red"


def test_share_flow_skips_unfinished_jobs_to_find_shareable_one():
    """리뷰 Important #2: 첫 job이 렌더 전(404)이어도 다음 job을 훑어 완성본을 찾는다."""
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(
        200, {"ok": True, "works": [{"job_id": "unfinished"}, {"job_id": "done"}]})
    page.server_responses["http://x/api/share/link/unfinished"] = FakeResp(
        404, {"ok": False, "error": "완성 영상이 없어요"})
    page.server_responses["http://x/api/share/link/done"] = FakeResp(
        200, {"ok": True, "url": "http://x/s/sidDONE", "qr_svg": ""})
    def restart():
        page.server_responses["http://x/s/sidDONE"] = FakeResp(200, {})
        page.server_responses["http://x/api/share/t/sidDONE"] = FakeResp(404, {"ok": False})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=restart))[0]
    assert r.verdict == "green" and "sidDONE" in r.page


def test_share_flow_gray_with_reason_when_no_job_shareable_after_probing():
    """리뷰 Important #2: 완성본을 못 찾으면 회색 + 이유 명시(조용한 회색 금지)."""
    page = FakePage()
    page.server_responses["http://x/api/produce/works"] = FakeResp(
        200, {"ok": True, "works": [{"job_id": f"j{i}"} for i in range(3)]})
    for i in range(3):
        page.server_responses[f"http://x/api/share/link/j{i}"] = FakeResp(
            404, {"ok": False, "error": "완성 영상이 없어요"})
    r = flow_share_link_restart.run(FakeSession(page, restart_web=lambda: None))[0]
    assert r.verdict == "gray" and "3개" in r.reason and "판정 불가" in r.reason


# ---- run_flow: 빨간 결과에 증거 사진을 붙이는지(2026-09-07 리뷰 반영) ----

def test_run_flow_attaches_evidence_on_red(tmp_path, monkeypatch):
    from shopping_shorts.checks import sweep
    from shopping_shorts.checks.verdict import Result, RED

    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)

    class _Page:
        def screenshot(self, path):
            with open(path, "wb") as f:
                f.write(b"PNG")

    class _Session:
        page = _Page()

    class _Module:
        __name__ = "shopping_shorts.checks.flows.flow_fake"
        META = {"name": "가짜 흐름"}

        @staticmethod
        def run(session):
            return [Result("L2", "가짜 흐름", RED, reason="테스트용 실패", signature="L2:fake")]

    out = base.run_flow(_Session(), _Module())
    assert len(out) == 1 and out[0].verdict == RED
    assert out[0].evidence_dir
    assert (tmp_path / out[0].evidence_dir / "shot.png").is_file()


def test_run_flow_green_has_no_evidence(tmp_path, monkeypatch):
    from shopping_shorts.checks import sweep
    from shopping_shorts.checks.verdict import Result, GREEN

    monkeypatch.setattr(sweep, "EVIDENCE_ROOT", tmp_path)

    class _Page:
        def screenshot(self, path):
            raise AssertionError("초록인데 스크린샷을 찍음")

    class _Session:
        page = _Page()

    class _Module:
        __name__ = "shopping_shorts.checks.flows.flow_fake"
        META = {"name": "가짜 흐름"}

        @staticmethod
        def run(session):
            return [Result("L2", "가짜 흐름", GREEN, reason="정상", signature="L2:fake")]

    out = base.run_flow(_Session(), _Module())
    assert out[0].evidence_dir == ""
