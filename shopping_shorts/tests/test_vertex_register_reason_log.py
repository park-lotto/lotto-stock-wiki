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
