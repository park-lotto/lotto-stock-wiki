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


# ── Task 4: 1단계 재구성 — 믹스탭 제거·자동담김·AI PICK·빈 상태 ──────────
def test_mix_tab_removed():
    # "우리 시스템으로 믹스" 탭·조합 생성 UI 제거
    assert "우리 시스템으로 믹스" not in HTML
    assert "SCRIPT_MODE_HTML" not in HTML or "mix:" not in HTML.split("SCRIPT_MODE_HTML")[1][:400]


def test_aipick_and_emptystate_present():
    assert "renderAiPick" in HTML and "renderEmptyState" in HTML
    assert "이 뼈대로 완전 새로운 대본을 만듭니다" in HTML
    assert "아직 담긴 영상이 없어요" in HTML
    assert "이대로 만들기 시작" in HTML          # ⚡ CTA
    assert 'class="cta-shine"' in HTML or "'cta-shine'" in HTML


def test_no_banned_copy():
    assert "복사가 아니에요" not in HTML
    # 브리프 원문 슬라이스(HTML.split('id="scriptModeBody"')[0])는 <head><style>의 keyframe
    # "100%{...}"(savedPop 등, 본문과 무관)까지 걸려 항상 거짓양성이 난다 — renderAiPick 카드를
    # 만드는 JS 구간만 정밀 검사한다(목업 v6의 "100% 새로운 대본을 만듭니다"를 배제 확인).
    start = HTML.index("function renderAiPick(")
    end = HTML.index("// ── AI PICK 끝 ──")
    assert "100%" not in HTML[start:end]


# ── Task 4 리뷰 수정: 거짓 카피 제거 + 모순 빈 상태 분리 ──────────
def test_aipick_hint_is_truthful():
    # 토글이 AI PICK을 바꾼다는 거짓 카피 제거(백엔드는 work_id만 보내 서버측 라이브러리
    # picks로 계산하지, 화면의 ✓ 토글 세트를 반영하지 않는다).
    assert "AI PICK이 바뀝니다" not in HTML
    assert "분석된 대본 중 완성도 1위를 골랐어요" in HTML


def test_footage_on_but_no_pick_state_distinct():
    # 재료(✓)는 담겨 있는데 그 대본을 아직 분석 못한 경우는 "아직 담긴 영상이 없어요"와
    # 다른 문구를 써야 한다 — 안 그러면 왼쪽 레일의 ✓카드와 모순돼 보인다.
    assert "renderNoScriptState" in HTML
    assert "담긴 영상의 대본을 아직 분석하지 못했어요" in HTML
    # refreshStep0이 hasFootage를 renderAiPick에 넘겨 null-pick 분기를 가른다.
    assert "renderAiPick(await r.json(), hasFootage)" in HTML


def test_pool_card_toggle_only():
    # renderPool()이 카드 5버튼(뽑기/담기/메인/정보채우기/✕)이 아니라 ✓뱃지 토글만 그린다.
    start = HTML.index("function renderPool(){")
    end = HTML.index("function previewMaterial")
    body = HTML[start:end]
    assert "toggleFootage(${i})" in body
    assert "openScriptModal(${i})" not in body
    assert "designateBackbone(${i})" not in body
    assert "removeFootage(${i})" not in body


# ── Task 5: 분석 극장(B) — ⚡시작 후 대기시간 실시간 해부 연출 ──────────
def test_theater_present_and_guarded():
    assert "playTheater" in HTML
    assert "원본 대본 해부" in HTML
    assert 'class="thea"' in HTML or "'thea'" in HTML
    assert "// ── 분석 극장 끝 ──" in HTML


def test_theater_host_element_present():
    assert 'id="theater"' in HTML


def test_theater_no_op_when_no_segments():
    # segments가 비었으면(구조 데이터 없음) 극장 host를 숨기고 return — 매칭 흐름을 막지 않는다.
    start = HTML.index("function playTheater(")
    end = HTML.index("// ── 분석 극장 끝 ──")
    body = HTML[start:end]
    assert "hidden = true" in body or "hidden=true" in body
    assert "return" in body


def test_theater_hides_on_mix_done():
    # 매칭 완료(ready_for_review) 또는 실패(failed) 시 극장 host를 숨긴다(pollMix에서 배선).
    start = HTML.index("async function pollMix(")
    end = HTML.index("async function loadMixReview(")
    body = HTML[start:end]
    assert "theater" in body and ("hidden = true" in body or "hidden=true" in body)
