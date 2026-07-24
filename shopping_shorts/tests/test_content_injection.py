"""전개 템플릿 주입(2026-07-23): 근거·갈등·감정 슬롯 템플릿을 자동승인+생성 프롬프트 주입.
지금까지 말투(훅·어미)만 실리고 이야기 전개 912개가 대기로 놀던 걸 살린다."""
import tempfile
from pathlib import Path
from shopping_shorts.store import Store
from shopping_shorts import bank_assemble


def _store():
    return Store(Path(tempfile.mkdtemp()) / "t.db")


def test_auto_approve_content_buckets():
    s = _store()
    for b in ("evidence", "conflict", "emotion"):
        s.add_pattern_item(b, "{인물}이 {행위}하니 {결과}", slot_role="template")
    s.add_pattern_item("hook", "이거 실화냐")            # 스타일은 별도
    n = s.auto_approve_content_buckets()
    assert n == 3
    assert len(s.list_pattern_items(bucket="evidence", status="approved")) == 1
    # 스타일은 content 승인이 안 건드림.
    assert len(s.list_pattern_items(bucket="hook", status="approved")) == 0


def test_content_block_injects_templates():
    s = _store()
    s.add_pattern_item("evidence", "{인물}이 {행위}하니 {결과}", slot_role="template")
    s.add_pattern_item("conflict", "{인물}이 {문제}로 곤란", slot_role="template")
    s.auto_approve_content_buckets()
    block = bank_assemble.content_block(s)
    assert "학습된 전개 패턴" in block
    assert "근거 대는 법" in block and "갈등·문제 설정" in block
    assert "(인물)이 (행위)하니 (결과)" in block          # 중괄호 소독됨


def test_content_block_empty_when_none():
    assert bank_assemble.content_block(_store()) == ""     # 승인 없으면 무주입(회귀0)


def test_assemble_includes_content():
    s = _store()
    s.add_pattern_item("emotion", "{인물}이 {반응}하며 놀람", slot_role="template")
    s.add_pattern_item("hook", "이거 실화냐")
    s.auto_approve_style_buckets(); s.auto_approve_content_buckets()
    ctx = bank_assemble.assemble_bank_context(s, "레시피")
    assert "학습된 전개 패턴" in ctx                        # 전개 블록 포함
    assert "이거 실화냐" in ctx                             # 말투 블록도 그대로
