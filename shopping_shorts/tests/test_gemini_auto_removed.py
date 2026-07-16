"""제미니 자동(주제만으로 대본 생성) 제거 봉인 — 2026-07-16.

mix 목록이 재생성 경로가 되면서 이 기능은 즐겨찾기 🔀이식 모드와 겹쳐 폐기됐다.
탭·라우트·생성함수 셋은 서로만 쓰던 폐쇄 묶음이라 뿌리째 지웠다.
이 테스트는 되살아나는 것을 막는다(부활시키려면 이 파일을 먼저 지워라).
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PRODUCE_HTML = ROOT / "static" / "produce.html"
APP_PY = ROOT / "app.py"
SCRIPT_GEN_PY = ROOT / "script_generate.py"


def test_produce_html_has_no_gemini_auto():
    text = PRODUCE_HTML.read_text(encoding="utf-8")
    assert 'data-mode="gemini"' not in text, "제미니 자동 탭이 남아 있다"
    assert "genGemini" not in text, "genGemini() 가 남아 있다"
    assert "gemDrafts" not in text, "gemDrafts 컨테이너가 남아 있다"
    assert "gemTopic" not in text, "gemTopic 입력칸이 남아 있다"


def test_app_has_no_gemini_route():
    text = APP_PY.read_text(encoding="utf-8")
    assert "/api/produce/script/gemini" not in text, "제미니 자동 라우트가 남아 있다"
    assert "api_produce_script_gemini" not in text, "라우트 핸들러가 남아 있다"


def test_script_generate_has_no_topic_mode():
    text = SCRIPT_GEN_PY.read_text(encoding="utf-8")
    assert "generate_from_topic" not in text, "generate_from_topic() 이 남아 있다"
    assert "_TOPIC_PROMPT" not in text, "_TOPIC_PROMPT 가 남아 있다"


def test_other_generators_survive():
    """과잉 삭제 방지 — 살아 있어야 할 형제 함수들."""
    text = SCRIPT_GEN_PY.read_text(encoding="utf-8")
    for name in ("generate_variations", "generate_mix", "refine_draft_rewrite", "_GEN_PROMPT", "_MIX_PROMPT"):
        assert name in text, f"{name} 이 실수로 지워졌다"
