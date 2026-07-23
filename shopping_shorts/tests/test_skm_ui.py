import json
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
# (v6 목업 정렬, 2026-07-23 후속) 자막제거가 헤드라인 오브로 복귀 — 8단계.
def test_orb_labels_and_mapping():
    assert '"영상/대본"' in HTML and '"화면 붙이기"' in HTML and '"완성"' in HTML
    assert "ORB_TO_PANEL" in HTML and "STEP_LABELS" in HTML
    # STEP_LABELS는 정확히 8개, 자막제거 포함(v6 목업과 정렬 — 더는 오브에서 안 빠진다)
    m = re.search(r"const STEP_LABELS\s*=\s*(\[[^\]]*\])", HTML)
    assert m, "STEP_LABELS 선언을 못 찾음"
    labels = json.loads(m.group(1))
    assert labels == ["영상/대본", "화면 붙이기", "자막제거", "음성", "꾸미기", "썸네일", "SEO", "완성"], labels


def test_orb_to_panel_mapping_v6():
    m = re.search(r"const ORB_TO_PANEL\s*=\s*(\[[^\]]*\])", HTML)
    assert m, "ORB_TO_PANEL 선언을 못 찾음"
    mapping = json.loads(m.group(1))
    assert mapping == [0, 7, 1, 2, 3, 4, 5, 6], mapping


def test_orbbar_class_used():
    assert 'class="orbbar"' in HTML or "'orbbar'" in HTML or '"orbbar"' in HTML


def test_panel0_title_is_video_script_not_studio():
    assert "1 · 영상/대본" in HTML
    assert "1 · 제작소" not in HTML


# ── v6 목업 정렬: renderSteps가 볼(숫자/✓)+라벨(항상 노출)+진행선(orbfill)을 그린다 ──
def test_render_steps_emits_v6_orb_markup():
    start = HTML.index("function renderSteps(){")
    end = HTML.index("// ── 오브바 끝 ──")
    body = HTML[start:end]
    assert "orbline" in body
    assert "orbfill" in body
    assert '"ball"' in body or "'ball'" in body
    assert '"lb"' in body or "'lb'" in body
    assert "label" in body  # 라벨 텍스트를 실제로 넣는다(hover 전용 title이 아니라)


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


def test_aipick_card_faithful_to_v6_mock():
    # final-mock-v6.html(36-52, 100-116행) 이식 확인 — who블록·수치타일·훅/디바이스 태그.
    assert ".aipick-who" in CSS and ".stt" in CSS
    start = HTML.index("function renderAiPick(")
    end = HTML.index("// ── AI PICK 끝 ──")
    body = HTML[start:end]
    assert "aipick-who" in body
    assert "why" in body


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


# ── Task 6: 2단계 "화면 붙이기"(매칭) 패널 — 위→아래 한 방향 ──────────
def test_match_panel_present():
    assert 'data-step="7"' in HTML
    assert "initMatch" in HTML
    assert "새 대본 고르기" in HTML and "장면 확인" in HTML
    assert "다음 (3" in HTML or "음성" in HTML   # 다음 단계 유도


def test_match_panel_hosts_mix_dom_not_panel0():
    # 매칭 결과 DOM(#mixCandidates/#mixReview/#mixPreviewPanel)이 패널0이 아니라 신규
    # 패널7 쪽으로 옮겨왔는지 — 패널0 섹션 본문에는 더는 없어야 한다.
    p0_start = HTML.index('<section class="panel" data-step="0">')
    p0_end = HTML.index('<section class="panel" data-step="1">')
    p0_body = HTML[p0_start:p0_end]
    assert 'id="mixCandidates"' not in p0_body
    assert 'id="mixReview"' not in p0_body
    p7_start = HTML.index('<section class="panel" data-step="7">')
    p7_end = HTML.index('<div class="nav">')
    p7_body = HTML[p7_start:p7_end]
    assert 'id="mixCandidates"' in p7_body
    assert 'id="mixReview"' in p7_body
    assert 'id="mixPreviewPanel"' in p7_body


def test_init_match_is_not_a_stub():
    # Task 2의 스텁 `function initMatch(){}`가 실구현으로 바뀌었는지.
    assert "function initMatch(){}" not in HTML
    start = HTML.index("function initMatch(")
    end = HTML.index("// ── 화면 붙이기 끝 ──")
    body = HTML[start:end]
    assert "MIX_JOB" in body


# ── Task 6 carried bug(Task 2 리뷰 Minor②): revertWork/_restoreWork의 cur 바운드가
# STEP_LABELS.length(오브 라벨 수=7)를 쓰면, 패널7(매칭)이 생겨 실제 패널 수가 8이 된
# 지금은 cur:7 복원이 범위 밖으로 오판돼 0으로 튕긴다. PANEL_COUNT(물리 패널 수)를 써야 한다.
def test_revert_and_restore_use_panel_count_not_step_labels_length():
    assert "const PANEL_COUNT" in HTML
    for start, end in (
        ("function revertWork(){", "async function _restoreWork(workId){"),
        ("async function _restoreWork(workId){", "function _renderPreviewVideo(job){"),
    ):
        body = HTML[HTML.index(start):HTML.index(end)]
        assert "PANEL_COUNT" in body, f"{start} 바운드가 PANEL_COUNT를 안 쓴다"
        assert "STEP_LABELS.length" not in body, (
            f"{start}가 여전히 STEP_LABELS.length(오브 라벨 수)로 cur(패널 인덱스)를 바운드한다 "
            "— 매칭 패널(7) 복원이 범위 밖으로 오판돼 0으로 튕긴다")


@pytest.mark.skipif(not shutil.which("node"), reason="node 필요")
def test_revert_work_restores_matching_panel_step7(tmp_path):
    # revertWork()도 _restoreWork와 같은 클래스의 버그를 가졌다(Task2 리뷰 Minor②) — 실행 증거.
    start = HTML.index("function revertWork(){")
    end = HTML.index("async function _restoreWork(workId){")
    body = HTML[start:end]
    driver = r"""
    'use strict';
    let HANDOFF = [];
    const STATE = { script:'', script_src_idx:null, script_from_wiki:null };
    const PANEL_COUNT = 8;
    let cur = 0, MIX_JOB = null;
    function canGoNext(){ return true; }
    function setScriptMode(){}
    function renderPool(){}
    function syncFootageToMixUrls(){}
    function refreshFinalPeek(){}
    function renderSteps(){}
    function showPanel(){}
    function refreshNextBtn(){}
    function saveWork(){}
    let _prevCommitted = JSON.stringify({script:'대본', step:7});
    revertWork();
    console.log(JSON.stringify({cur}));
    """
    js = tmp_path / "t.js"
    js.write_text(body + driver, encoding="utf-8")
    out = subprocess.run(["node", str(js)], capture_output=True, text=True,
                         encoding="utf-8", errors="replace",
                         stdin=subprocess.DEVNULL, timeout=30)
    assert out.returncode == 0, out.stderr
    assert '"cur":7' in out.stdout.strip().splitlines()[-1], (
        "revertWork가 매칭 패널(step:7)로 되돌리지 못했다 — PANEL_COUNT 바운드 확인: " + out.stdout)
