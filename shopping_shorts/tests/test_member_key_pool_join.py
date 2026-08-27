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
