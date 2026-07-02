import pytest
from pipeline.people.build_brain import render_live_stance, render_speech_log, update_markers


def _atom(**kw):
    base = {"date": "2026-06-30", "source_name": "태린이아빠 주식투자",
            "sector": "조선", "asset": "HD현대중공업",
            "content_type": "stance", "signal": "bullish",
            "content": "조선 비중 확대 유지."}
    base.update(kw)
    return base


def test_render_live_stance_includes_asset_and_date():
    out = render_live_stance([_atom()])
    assert "HD현대중공업" in out
    assert "2026-06-30" in out


def test_render_speech_log_includes_content():
    out = render_speech_log([_atom(content="현금 30%까지 늘렸다.")])
    assert "현금 30%까지 늘렸다." in out


def test_update_markers_replaces_only_inside_marker():
    page = (
        "# 태린이아빠\n\n## 1. 철학\n수급빈집(수동 뼈대).\n\n"
        "## 5. 라이브 스탠스\n"
        "<!-- AUTO:live_stance -->\n(옛 내용)\n<!-- /AUTO:live_stance -->\n"
    )
    out = update_markers(page, {"live_stance": "- 새 스탠스"})
    assert "수급빈집(수동 뼈대)." in out       # 수동 뼈대 보존
    assert "- 새 스탠스" in out                # 자동 갱신됨
    assert "(옛 내용)" not in out              # 옛 자동내용 제거


def test_update_markers_idempotent():
    page = "<!-- AUTO:x -->\nold\n<!-- /AUTO:x -->\n"
    once = update_markers(page, {"x": "content"})
    twice = update_markers(once, {"x": "content"})
    assert once == twice


def test_update_markers_missing_key_unchanged():
    page = "<!-- AUTO:a -->\nkeep\n<!-- /AUTO:a -->\n"
    out = update_markers(page, {"b": "irrelevant"})
    assert "keep" in out


def test_render_speech_log_includes_source_name():
    out = render_speech_log([_atom(source_name="태린이아빠 주식투자")])
    assert "태린이아빠 주식투자" in out


def test_update_markers_handles_backslash_body():
    page = "<!-- AUTO:test -->\nold\n<!-- /AUTO:test -->\n"
    body = r"- 종목 \1 \g 테스트 C:\path"
    out = update_markers(page, {"test": body})
    # Should not raise exception and literal backslash text should appear
    assert r"\1" in out
    assert r"\g" in out
    assert r"C:\path" in out
    assert "old" not in out
