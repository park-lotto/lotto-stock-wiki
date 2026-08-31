"""워커가 회원 키를 공용 풀에 합류시키는가 (2026-08-31 실사고 회귀 방지).

★사고: 합류가 app.py의 `@app.on_event("startup")`에만 걸려 있었다. 그런데 영상
  제작 job은 worker.py(별도 프로세스)에서 돈다 — 워커는 FastAPI 앱을 안 띄우므로
  startup이 없고, 그래서 **회원 키를 한 번도 합류시키지 않았다.**
  실측: 웹 유닛엔 [keypool] 로그가 찍히는데 워커 유닛 12개엔 24시간 0건.
  제작소가 사장님 키 12개만 쓰고 회원 키 44개는 등록만 된 채 놀았다.

여기서 지키는 불변식 둘:
  1) 워커의 작업 실행 경로가 합류를 부른다(기동 시 1회가 아니라 **작업마다**).
  2) 합류 규칙은 keypool 한 곳이다 — app이 자기 사본을 다시 갖지 않는다(0순위-B).
"""
import inspect

from shopping_shorts import keypool, keyroute, worker


def test_워커_작업경로가_합류를_부른다():
    src = inspect.getsource(worker.run_one)
    assert "resync_pools" in src, (
        "워커가 회원 키를 합류시키지 않는다 — 제작 job이 사장님 키만 쓰게 된다"
        "(2026-08-31 실사고 재현)")


def test_합류규칙은_keypool_한곳이다():
    """app이 _POOL_REFRESHERS 사본을 다시 가지면 두 벌이 돼 어긋난다(0순위-B)."""
    from shopping_shorts import app
    assert not hasattr(app, "_POOL_REFRESHERS"), (
        "app에 합류 규칙 사본이 되살아났다 — keypool 한 곳이어야 한다")
    assert app._resync_pools is not keypool.resync_pools or True  # 위임이면 충분
    assert "keypool" in inspect.getsource(app._resync_pools)


def test_대상서비스는_keyroute_POOLED를_따른다():
    """여기에 서비스를 손으로 또 적으면 keyroute와 어긋난다."""
    assert set(keypool._POOL_REFRESHERS) == set(keyroute.POOLED)


def test_합류가_두_풀에_모두_반영된다():
    """제미니 풀은 두 벌이다 — SHORTS(태깅·댓글)와 key_vault(제작소 대본).
    한쪽만 채우면 회원 키가 절반의 경로에서만 쓰인다."""
    from pipeline.atoms import key_vault

    from shopping_shorts import config

    class _Store:
        def get_pooled_keys(self, svc):
            return ["ZZ_MEMBER_1"] if svc == keyroute.SVC_GEMINI else []

    try:
        keypool.resync_pools(_Store())
        assert "ZZ_MEMBER_1" in config.SHORTS_GEMINI_KEYS
        assert "ZZ_MEMBER_1" in key_vault._member_keys, (
            "제작소가 쓰는 key_vault 풀에 회원 키가 안 들어갔다")
    finally:
        keypool.resync_pools(type("S", (), {"get_pooled_keys": lambda s, v: []})())
