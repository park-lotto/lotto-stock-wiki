from pathlib import Path


HTML = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")


def test_effect_tab_exposes_two_comment_styles_and_editor_fields():
    for marker in (
        'id="commentFxBox"',
        'data-comment-style="dark_social"',
        'data-comment-style="premium_pop"',
        'id="commentAuthor"',
        'id="commentAge"',
        'id="commentText"',
        'id="commentLikes"',
        'id="commentStart"',
        'id="commentDur"',
        'id="commentWidth"',
        'id="commentAvatar"',
    ):
        assert marker in HTML


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
