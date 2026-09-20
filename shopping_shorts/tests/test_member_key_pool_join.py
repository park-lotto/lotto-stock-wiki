# -*- coding: utf-8 -*-
"""회원이 등록한 Gemini 키가 **실제 로테이션까지** 닿아야 한다 (2026-08-27).

★사고: 사장님이 고객들에게 "구글 키를 등록하라"고 안내한 참인데, 실측하니
    합류 전  config=19  comment_gen=19
    합류 후  config=21  comment_gen=19      ← 회원 키가 안 들어감
  `from shopping_shorts.config import SHORTS_GEMINI_KEYS`는 **값 복사**라,
  config에서 재할당해도 그 모듈들은 옛 목록을 계속 본다.
  모든 모듈이 comment_gen._current_key_and_idx()로 키를 받으므로,
  **등록해도 어느 경로에서도 안 쓰였다** — 조용히 새는 종류의 버그다.
"""
import sys

import pytest

import shopping_shorts.config as cfg


@pytest.fixture(autouse=True)
def _restore():
    before = list(cfg.SHORTS_GEMINI_KEYS)
    yield
    cfg.refresh_member_gemini_keys([])
    cfg.SHORTS_GEMINI_KEYS = before
    cfg._push_pool_to_importers(before)


class Test회원키가_로테이션까지_닿는다:
    def test_comment_gen이_회원키를_본다(self):
        """★로테이션(_current_key_and_idx)이 쓰는 목록이다 — 여기 없으면 아무 데도 없다."""
        from shopping_shorts import comment_gen as cg
        cfg.refresh_member_gemini_keys(["MEM_A"])
        assert "MEM_A" in cg.SHORTS_GEMINI_KEYS

    def test_복사해간_모듈이_전부_따라온다(self):
        mods = {}
        for name in cfg._POOL_IMPORTERS:
            __import__("shopping_shorts." + name)
            mods[name] = sys.modules["shopping_shorts." + name]
        cfg.refresh_member_gemini_keys(["MEM_B"])
        for name, m in mods.items():
            assert "MEM_B" in m.SHORTS_GEMINI_KEYS, f"{name}이 옛 목록을 본다"

    def test_사장님_키가_앞이다(self):
        """★인덱스 기반 소진 상태와 짝이 어긋나면 안 된다 — 회원이 넣고 빼도
        앞쪽 인덱스의 의미가 변하면 엉뚱한 키가 잠긴다."""
        owner = list(cfg._OWNER_GEMINI_KEYS)
        cfg.refresh_member_gemini_keys(["MEM_C"])
        assert cfg.SHORTS_GEMINI_KEYS[:len(owner)] == owner

    def test_중복은_한_번만(self):
        owner = list(cfg._OWNER_GEMINI_KEYS)
        dup = owner[0] if owner else "MEM_D"
        cfg.refresh_member_gemini_keys([dup, "MEM_E"])
        assert cfg.SHORTS_GEMINI_KEYS.count(dup) == 1

    def test_빈_목록이면_사장님_키만(self):
        cfg.refresh_member_gemini_keys([])
        assert cfg.SHORTS_GEMINI_KEYS == list(cfg._OWNER_GEMINI_KEYS)


class Test명단이_썩지_않게:
    def test_복사해가는_모듈이_전부_명단에_있다(self):
        """★새 모듈이 같은 import를 쓰면 조용히 빠진다 — 그때 이 테스트가 잡는다."""
        import pathlib
        import re
        root = pathlib.Path(cfg.__file__).parent
        missing = []
        for p in root.glob("*.py"):
            if p.name in ("config.py",):
                continue
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"^from\s+shopping_shorts\.config\s+import\s+.*SHORTS_GEMINI_KEYS",
                         txt, re.MULTILINE):
                if p.stem not in cfg._POOL_IMPORTERS:
                    missing.append(p.stem)
        assert not missing, (
            "이 모듈들이 SHORTS_GEMINI_KEYS를 값으로 복사해 가는데 _POOL_IMPORTERS에 "
            f"없다 — 회원 키가 안 닿는다: {missing}")


# ── 2026-08-31 실사고: 웹은 합류하는데 워커는 한 번도 안 했다 ────────────────

def test_워커_작업경로가_합류를_부른다():
    """★합류가 app.py의 startup 이벤트에만 걸려 있었다. 그런데 영상 제작 job은
    worker.py(별도 프로세스)에서 돈다 — FastAPI를 안 띄우니 startup이 없다.
    실측: 웹 유닛엔 [keypool] 로그가 찍히는데 **워커 유닛 12개엔 24시간 0건**.
    회원 키 49개가 등록만 된 채 놀았고, 고객 5명이 제작을 못 했다.

    기동 시 1회가 아니라 **작업마다** 불러야 한다 — 워커는 별도 프로세스라
    웹에서 키를 등록해도 신호가 안 온다."""
    import inspect

    from shopping_shorts import worker
    assert "resync_pools" in inspect.getsource(worker.run_one), (
        "워커가 회원 키를 합류시키지 않는다 — 제작 job이 사장님 키만 쓰게 된다")


def test_합류규칙은_keypool_한곳이다():
    """app이 _POOL_REFRESHERS 사본을 다시 가지면 두 벌이 돼 어긋난다(0순위-B)."""
    import inspect

    from shopping_shorts import app, keypool, keyroute
    assert not hasattr(app, "_POOL_REFRESHERS"), (
        "app에 합류 규칙 사본이 되살아났다 — keypool 한 곳이어야 한다")
    assert "keypool" in inspect.getsource(app._resync_pools)
    assert set(keypool._POOL_REFRESHERS) == set(keyroute.POOLED), (
        "대상 서비스를 손으로 또 적으면 keyroute와 어긋난다")


def test_합류가_회원키를_그대로_넘긴다(monkeypatch):
    """전역을 실제로 바꾸지 않는다 — 뒤에 도는 테스트가 밟는다(단독 통과 = 오염)."""
    from shopping_shorts import config, keypool, keyroute

    seen = {}
    monkeypatch.setattr(config, "refresh_member_gemini_keys",
                        lambda p: (seen.__setitem__("gemini", list(p)), (0, len(p)))[1])
    monkeypatch.setattr(config, "refresh_member_youtube_keys", lambda p: (0, len(p)))

    class _Store:
        def get_pooled_keys(self, svc):
            return ["ZZ_MEMBER_1"] if svc == keyroute.SVC_GEMINI else []

    keypool.resync_pools(_Store())
    assert seen.get("gemini") == ["ZZ_MEMBER_1"], "회원 키가 합류 함수에 안 넘어갔다"


def test_합류함수가_두_풀을_모두_채운다():
    """제미니 풀은 두 벌이다 — SHORTS(태깅·댓글)와 key_vault(제작소 대본).
    한쪽만 채우면 회원 키가 절반의 경로에서만 쓰인다."""
    import inspect

    from shopping_shorts import config
    src = inspect.getsource(config.refresh_member_gemini_keys)
    assert "SHORTS_GEMINI_KEYS" in src
    assert "set_member_keys" in src, "제작소가 쓰는 key_vault 풀에 안 밀어 넣는다"
