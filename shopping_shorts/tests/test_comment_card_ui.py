from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


# (옛 피팅룸 마크업 시험은 2026-10-01 삭제 — 관제 058 C1, 옛 6단계 HTML 제거)

def test_comment_card_ui_has_apply_preview_drag_upload_and_clear_handlers():
    for function_name in (
        "commentPickStyle",
        "commentUpdate",
        "commentUploadAvatar",
        "commentClear",
        "renderCommentPreview",
        "bindCommentDrag",
        "restoreCommentControls",
    ):
        assert f"function {function_name}(" in HTML or f"async function {function_name}(" in HTML


def test_comment_card_preview_uses_server_png_source_of_truth():
    assert "/api/produce/comment-card.png" in HTML
    assert "STATE.deco.comment_card" in HTML
    assert "commentCardPreview" in HTML
