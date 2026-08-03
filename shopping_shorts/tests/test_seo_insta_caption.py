"""인스타 캡션(2026-08-03 사장님 "폰으로 올리는 구조") — 생성 스키마 + 프론트 조립 그라운딩.

레퍼런스 공식(실계정 6장 실측): 경험담 본문 → ✔체크리스트 → 댓글 키워드 유도(DM·팔로우 조건·
숨김함 안내) → 해시태그. 폰에서 복사만 하면 되는 완성 덩어리가 목표다.
"""
import json
import pathlib
import re
import shutil
import subprocess

import pytest

from shopping_shorts import seo_generate

PRODUCE_HTML = pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html"


def test_schema_requires_insta_caption():
    assert "insta_caption" in seo_generate._SCHEMA["properties"]
    assert "insta_caption" in seo_generate._SCHEMA["required"]


def test_prompt_teaches_the_reference_formula():
    p = seo_generate._build_prompt({"given_script": "대본"}, None, None, None, None)
    for must in ("insta_caption", "체크리스트", "숨김함", "팔로우"):
        assert must in p, must


def test_insta_is_lockable():
    assert seo_generate._locked_value({"insta_caption": "캡션 본문"}, "insta") == "캡션 본문"
    assert "insta" in seo_generate._ONLY_LABELS


def _run_fallback(seo_js):
    node = shutil.which("node")
    if not node:
        pytest.skip("node 없음")
    html = PRODUCE_HTML.read_text(encoding="utf-8")
    m = re.search(r"function _instaCaption\(\).*?\n}\n", html, re.S)
    assert m, "_instaCaption을 produce.html에서 찾지 못함"
    script = f"let SEO = {seo_js};\n{m.group(0)}\nconsole.log(JSON.stringify(_instaCaption()));"
    out = subprocess.run([node, "-e", script], capture_output=True, text=True,
                         encoding="utf-8", errors="replace", timeout=30)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_front_prefers_generated_caption():
    assert _run_fallback('{"insta_caption": "AI가 만든 캡션"}') == "AI가 만든 캡션"


def test_front_assembles_fallback_for_old_jobs():
    """옛 job(insta_caption 없음)도 빈 칸이 아니라 기존 재료로 조립돼야 한다."""
    txt = _run_fallback(json.dumps({
        "hook_line": "김밥이 식어도 쫀득한 비법",
        "description": "밥에 한 숟갈 넣었더니 식어도 안 굳어요.",
        "comment_bait": "댓글에 '김밥' 남겨주세요",
        "hashtags": {"tiktok": ["김밥", "#주방꿀템"]},
    }, ensure_ascii=False))
    assert "김밥이 식어도 쫀득한 비법" in txt
    assert "댓글에 '김밥'" in txt
    assert "숨김함" in txt and "팔로우" in txt
    assert "#김밥" in txt and "#주방꿀템" in txt
