"""관제 216 — 배포 재시작에 끊긴 1단계 분석 시도를 되돌린다(store.autoload_release_interrupted)."""
from shopping_shorts.store import Store


def _st(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_방금_시작해_끊긴_시도는_되돌린다(tmp_path):
    s = _st(tmp_path)
    s.autoload_mark_attempt("a"); s.autoload_mark_attempt("a")
    assert s.autoload_release_interrupted(600) == 1
    assert s.autoload_attempts(["a"])["a"] == 1


def test_오류로_끝난_시도는_그대로(tmp_path):
    s = _st(tmp_path)
    s.autoload_mark_attempt("b"); s.autoload_mark_error("b", "403")
    assert s.autoload_release_interrupted(600) == 0
    assert s.autoload_attempts(["b"])["b"] == 1


def test_오래전_시도는_그대로(tmp_path):
    s = _st(tmp_path)
    s.autoload_mark_attempt("c")
    with s._conn() as c:
        c.execute("UPDATE produce_autoload SET updated_at=datetime('now','-2 hours')")
    assert s.autoload_release_interrupted(600) == 0
    assert s.autoload_attempts(["c"])["c"] == 1
