import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent.parent
CSS = (BASE / "static" / "theme.css").read_text(encoding="utf-8")
HTML = (BASE / "static" / "produce.html").read_text(encoding="utf-8")


def test_theme_tokens_defined():
    # theme.css는 produce.html 인라인 :root와 겹치는 토큰(--bg/--panel/--line/--txt/--sub/--gold)을
    # 재정의하지 않는다 — 신규 토큰만 소유한다.
    for tok in ("--mint:#3ee0bf", "--aurora"):
        assert tok in CSS, tok
    # 겹쳤을 새-브랜드 값(딥다크 배경·오브done 골드)은 :root 토큰이 아니라
    # 신규 컴포넌트 클래스의 리터럴 hex로만 존재해야 한다.
    for literal in ("#070b14", "#facc6b"):
        assert literal in CSS, literal


def test_theme_does_not_redefine_page_tokens():
    import re
    root_block = re.search(r":root\s*\{([^}]*)\}", CSS)
    assert root_block, "theme.css :root block missing"
    for tok in ("--bg", "--panel", "--line", "--txt", "--sub", "--gold"):
        assert f"{tok}:" not in root_block.group(1), tok


def test_theme_component_classes():
    for cls in (".orbbar", ".orb", ".skm-card", ".cta-shine", ".stat-tile", ".strip", ".thea", ".aurora-bg"):
        assert cls in CSS, cls


def test_produce_links_theme_and_brands():
    assert 'href="theme.css' in HTML          # 링크(캐시버전 ?v= 허용)
    assert "숏템메이커" in HTML                 # 리브랜딩
    assert 'class="aurora-bg"' in HTML         # 배경 요소


# ── Task 2: 오브 단계바 — 라벨 rename + 매칭 단계 삽입 ──────────────
def test_orb_labels_and_mapping():
    assert '"영상/대본"' in HTML and '"화면 붙이기"' in HTML and '"완성"' in HTML
    assert "ORB_TO_PANEL" in HTML and "STEP_LABELS" in HTML
    assert '"자막제거"' not in HTML.split("STEP_LABELS")[1][:200]  # 자막제거는 오브 라벨 아님


def test_orbbar_class_used():
    assert 'class="orbbar"' in HTML or "'orbbar'" in HTML or '"orbbar"' in HTML


@pytest.mark.skipif(not shutil.which("node"), reason="node 필요")
def test_produce_js_syntax_ok():
    js = "\n".join(re.findall(r"<script>(.*?)</script>", HTML, re.S))
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(js)
        path = f.name
    r = subprocess.run(["node", "--check", path], stdin=subprocess.DEVNULL, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
