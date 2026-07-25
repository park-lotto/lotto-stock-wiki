# 관리자 회원 관리(2026-07-22): 정보수정 · 삭제 · 이메일 화이트리스트 관리자
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from shopping_shorts import app as appmod
from shopping_shorts.store import Store


def _setup(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(appmod, "_AUTH_ON", True)
    monkeypatch.setattr(appmod, "DASH_SECRET", "test-secret-xyz")
    appmod._ACCESS_SEEN.clear()
    s = Store(str(tmp_path / "t.db"))
    s.ensure_paywall_schema()
    return s


def _cookie(cid):
    exp = int(datetime.now(timezone.utc).timestamp()) + 3600
    return appmod._sign_session(cid, exp)


# ── store: 정보수정 ──
def test_update_customer_info_sets_name_phone(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("g_1", "pw12", email="a@b.com")   # 구글가입=이름·전화 없음
    assert s.get_customer(cid)["name"] is None
    s.update_customer_info(cid, "홍길동", "010-1234-5678")
    cust = s.get_customer(cid)
    assert cust["name"] == "홍길동" and cust["phone"] == "010-1234-5678"


def test_update_customer_info_none_keeps_other(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12", name="김철수", phone="010-1")
    s.update_customer_info(cid, None, "010-9999")            # 전화만 수정
    cust = s.get_customer(cid)
    assert cust["name"] == "김철수" and cust["phone"] == "010-9999"


# ── store: 삭제 ──
def test_delete_customer_removes_all(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("u", "pw12")
    s.add_payment(cid, 30000, "계좌", 30)
    s.record_access(cid, "1.1.1.1", "UA", "2026-07-22")
    s.usage_incr(cid, "render", "2026-07-22")
    s.create_mix_job("jdel01", ["u"], 30, "free", customer_id=cid)   # 콘텐츠(제작 job)
    s.delete_customer(cid)
    assert s.get_customer(cid) is None
    assert s.list_payments(cid) == []
    assert s.access_summary(cid, "2026-07-01") == {"ips": 0, "devices": 0}
    assert s.get_mix_job("jdel01") is None                           # 완전삭제=콘텐츠도 청소


def test_delete_endpoint_rejects_nonint_cid(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/customer/delete", json={"customer_id": "abc"})
    assert r.status_code == 400                                      # 잘못된 입력 거부


def test_delete_customer_ignores_owner(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.delete_customer(0)                                      # 사장님은 안 지운다(no-op, 예외X)


# ── 이메일 화이트리스트 관리자 ──
def test_is_admin_owner_and_whitelisted_email(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    admin_cid = s.create_customer("g_admin", "pw12", email="parklotto12@gmail.com")
    normal_cid = s.create_customer("g_norm", "pw12", email="someone@gmail.com")
    assert appmod._is_admin(0) is True                       # 사장님
    assert appmod._is_admin(admin_cid) is True               # 화이트리스트 이메일
    assert appmod._is_admin(normal_cid) is False             # 일반


def test_whitelisted_email_can_access_admin_api(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("g_admin", "pw12", email="parklotto12@gmail.com")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    r = c.get("/api/admin/customers")
    assert r.status_code == 200                              # 이메일 관리자도 admin API 접근
    assert any(cu.get("is_admin") for cu in r.json()["customers"])


def test_normal_customer_blocked_from_admin_api(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("g_norm", "pw12", email="nope@gmail.com")
    c = TestClient(appmod.app, cookies={"dash_auth": _cookie(cid)})
    assert c.get("/api/admin/customers").status_code == 403  # 일반 pro는 여전히 차단


# ── 엔드포인트: 수정·삭제 ──
def test_admin_update_endpoint(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("g_1", "pw12", email="a@b.com")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/customer/update",
                   json={"customer_id": cid, "name": "새이름", "phone": "010-7"})
    assert r.status_code == 200 and r.json()["ok"]
    assert s.get_customer(cid)["name"] == "새이름"


def test_admin_delete_endpoint(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    cid = s.create_customer("g_1", "pw12", email="a@b.com")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/customer/delete", json={"customer_id": cid})
    assert r.status_code == 200 and s.get_customer(cid) is None


def test_admin_delete_refuses_admin_account(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    admin_cid = s.create_customer("g_admin", "pw12", email="parklotto12@gmail.com")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    r = owner.post("/api/admin/customer/delete", json={"customer_id": admin_cid})
    assert r.status_code == 400                              # 관리자 계정 삭제 거부(락아웃 방지)
    assert s.get_customer(admin_cid) is not None


# ── /api/me가 이메일 관리자에게 is_admin=true (사이드바 관리페이지 버튼용) ──
def test_api_me_is_admin_for_email_admin(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    admin_cid = s.create_customer("g_admin", "pw12", email="parklotto12@gmail.com")
    normal_cid = s.create_customer("g_norm", "pw12", email="x@y.com")
    ca = TestClient(appmod.app, cookies={"dash_auth": _cookie(admin_cid)})
    cn = TestClient(appmod.app, cookies={"dash_auth": _cookie(normal_cid)})
    assert ca.get("/api/me").json()["is_admin"] is True
    assert cn.get("/api/me").json()["is_admin"] is False


# ── 관리자 지정/회수(스텝권한=관리자 동일) ──
def test_set_customer_admin_grants_is_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(appmod, "DB_PATH", str(tmp_path / "t.db"))
    s = Store(str(tmp_path / "t.db"))
    cid = s.create_customer("g_x", "pw12", email="x@y.com")
    assert appmod._is_admin(cid) is False
    s.set_customer_admin(cid, True)
    assert s.get_customer(cid)["admin"] is True
    assert appmod._is_admin(cid) is True          # 지정 관리자=권한 동일
    s.set_customer_admin(cid, False)
    assert appmod._is_admin(cid) is False


def test_set_admin_endpoint_and_refuses_code_admin(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    normal = s.create_customer("g_x", "pw12", email="x@y.com")
    codeadmin = s.create_customer("g_p", "pw12", email="parklotto12@gmail.com")
    owner = TestClient(appmod.app, cookies={"dash_auth": _cookie(0)})
    # 일반 계정 관리자 지정 성공
    r = owner.post("/api/admin/customer/set_admin", json={"customer_id": normal, "admin": True})
    assert r.status_code == 200 and appmod._is_admin(normal) is True
    # 지정 관리자도 admin API 접근 가능(권한 동일)
    c2 = TestClient(appmod.app, cookies={"dash_auth": _cookie(normal)})
    assert c2.get("/api/admin/customers").status_code == 200
    # 코드 고정 관리자는 UI로 변경 거부
    r2 = owner.post("/api/admin/customer/set_admin", json={"customer_id": codeadmin, "admin": False})
    assert r2.status_code == 400


# ── 관리자는 하루 렌더 상한(10) 없이 무제한 (2026-07-22 버그픽스) ──
def test_admin_render_unlimited(tmp_path, monkeypatch):
    s = _setup(tmp_path, monkeypatch)
    for i in range(15):                                     # 사장님(0) 15회 다 통과
        assert appmod.check_and_count(0, "render") is True, f"owner {i}회차"
    acid = s.create_customer("g_a", "pw12", email="parklotto12@gmail.com")
    for i in range(15):                                     # 이메일 관리자도 무제한
        assert appmod.check_and_count(acid, "render") is True, f"admin {i}회차"
    # 일반 pro는 여전히 10 상한
    pcid = s.create_customer("g_p", "pw12")
    s.set_plan(pcid, "pro")
    passed = sum(1 for _ in range(20) if appmod.check_and_count(pcid, "render"))
    assert passed == 10                                     # pro=10 유지
