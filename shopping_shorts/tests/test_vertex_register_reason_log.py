"""버텍스 등록 거절 사유가 서버 로그에 남는다 — 키 내용은 절대 안 남는다(2026-10-01 관제 050).

종전엔 422 숫자만 남아 "고객 다들 등록 실패"의 원인(조직 정책 키 생성 차단)을 서버에서 못 갈랐다.
"""
import json
import types

from shopping_shorts import app as appmod
from shopping_shorts import vertex_route

SECRET = "-----BEGIN PRIVATE KEY-----\nSECRETSECRET\n-----END PRIVATE KEY-----\n"
SA = {"type": "service_account", "project_id": "proj-test-1", "client_email": "x@proj-test-1.iam.gserviceaccount.com",
      "private_key": SECRET}


def _req(cid=77):
    return types.SimpleNamespace(state=types.SimpleNamespace(customer_id=cid))


def test_모양_거절_사유가_로그에_남는다(monkeypatch, capsys):
    monkeypatch.setattr(appmod.keycrypt, "enabled", lambda: True)
    r = appmod.api_vertex_register(_req(), {"json": "AIzaSy-이건-API키-모양"})
    assert r.status_code == 422
    err = capsys.readouterr().err
    assert "[vertex_register] 거절(모양) cid=77" in err
    assert "JSON 형식이 아닙니다" in err
    assert "AIzaSy" not in err, "붙여넣은 내용을 로그에 찍으면 안 된다"


def test_구글확인_거절_사유가_로그에_남고_키는_안_남는다(monkeypatch, capsys):
    monkeypatch.setattr(appmod.keycrypt, "enabled", lambda: True)
    monkeypatch.setattr(vertex_route, "verify_sa",
                        lambda info, model_name=None: (False, "권한이 없습니다 — 역할을 추가해 주세요"))
    r = appmod.api_vertex_register(_req(), {"json": json.dumps(SA)})
    assert r.status_code == 422
    err = capsys.readouterr().err
    assert "[vertex_register] 거절(구글확인) cid=77 project=proj-test-1: 권한이 없습니다" in err
    assert "SECRETSECRET" not in err and "PRIVATE KEY" not in err


# ── 2026-10-01 관제 053: 결제 미연결(HTTP 403)이 "역할 추가"로 오진되던 것 ──
def test_결제_미연결_403은_결제_문구로_나온다():
    e = Exception("403 PERMISSION_DENIED. {'error': {'code': 403, 'message': 'This API method requires billing "
                  "to be enabled. Please enable billing on project #123', 'status': 'PERMISSION_DENIED', "
                  "'details': [{'reason': 'BILLING_DISABLED'}]}}")
    msg = vertex_route._explain(e)
    assert "결제 계정" in msg and "역할" not in msg


def test_진짜_권한_403은_역할_문구에_결제확인도_같이_안내():
    e = Exception("403 PERMISSION_DENIED. Permission 'aiplatform.endpoints.predict' denied on resource")
    msg = vertex_route._explain(e)
    assert "Agent Platform 사용자" in msg and "5분" in msg and "결제" in msg


def test_구글확인_실패시_원문이_로그에_남는다(monkeypatch, capsys):
    import sys as _s
    class _C:
        class models:
            @staticmethod
            def generate_content(**kw):
                raise Exception("403 PERMISSION_DENIED. This API method requires billing to be enabled. BILLING_DISABLED")
    monkeypatch.setattr("google.genai.Client", lambda **kw: _C())
    monkeypatch.setattr("google.oauth2.service_account.Credentials.from_service_account_info", lambda *a, **k: object())
    ok, msg = vertex_route.verify_sa(SA)
    assert not ok and "결제 계정" in msg
    err = capsys.readouterr().err
    assert "[vertex_verify] project=proj-test-1 구글원문: 403 PERMISSION_DENIED" in err
    assert "SECRETSECRET" not in err
