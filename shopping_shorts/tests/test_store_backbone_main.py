"""믹스 job의 backbone_main(사장님이 UI에서 고른 메인/백본 소스 인덱스) 저장·조회.
기본 None(자동 선정), 정수면 그대로. get_mix_job이 새 키로 돌려준다."""
import tempfile
from pathlib import Path
from shopping_shorts.store import Store


def _store():
    d = tempfile.mkdtemp()
    return Store(Path(d) / "t.db")


def test_backbone_main_default_none():
    s = _store()
    s.create_mix_job("j1", ["u1", "u2"], 30, "free")
    assert s.get_mix_job("j1")["backbone_main"] is None


def test_backbone_main_stored_and_read():
    s = _store()
    s.create_mix_job("j2", ["u1", "u2", "u3"], 30, "free", backbone_main=2)
    assert s.get_mix_job("j2")["backbone_main"] == 2


def test_backbone_main_zero_index_preserved():
    # 0은 유효 인덱스 — falsy라고 None으로 뭉개면 안 된다.
    s = _store()
    s.create_mix_job("j3", ["u1", "u2"], 30, "free", backbone_main=0)
    assert s.get_mix_job("j3")["backbone_main"] == 0
