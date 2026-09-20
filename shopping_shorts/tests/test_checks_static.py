from pathlib import Path

from shopping_shorts.checks import static_invariants as si
from shopping_shorts.checks.verdict import GREEN, RED, GRAY

REPO = Path(__file__).resolve().parents[2]


# ── check_step_arrays ────────────────────────────────────────────
def test_step_arrays_equal_length_on_real_file():
    html = (REPO / "shopping_shorts/static/produce.html").read_text(encoding="utf-8")
    assert si.check_step_arrays(html).verdict == GREEN


def test_step_arrays_detect_mismatch():
    html = (
        'const STEP_LABELS = ["a","b"];\n'
        'const STEP_SHORT = ["a"];\n'
        'const STEP_COLORS = [["x","y"],["x","y"]];\n'
        'const STEP_ICONS = ["p","p"];'
    )
    r = si.check_step_arrays(html)
    assert r.verdict == RED and "STEP_SHORT" in r.reason


def test_step_arrays_gray_when_not_found():
    r = si.check_step_arrays("<html>아무 배열도 없음</html>")
    assert r.verdict == GRAY


def test_step_arrays_survives_svg_bracket_lookalikes():
    """STEP_ICONS는 SVG path 문자열이라 대괄호 흉내(속성값 안 대괄호는 없지만 따옴표 중첩은 있다).
    비탐욕 정규식(.*?];)이었다면 여기서 잘못 끊겨 거짓 빨강/회색이 났을 함정."""
    html = (
        'const STEP_LABELS = ["a","b"];\n'
        'const STEP_SHORT = ["a","b"];\n'
        'const STEP_COLORS = [["x","y"],["x","y"]];\n'
        'const STEP_ICONS = [\'<rect x="1" y="2"/>\', \'<path d="M1 2"/>\'];'
    )
    r = si.check_step_arrays(html)
    assert r.verdict == GREEN


# ── check_orb_permutation ────────────────────────────────────────
def test_orb_permutation_on_real_file():
    html = (REPO / "shopping_shorts/static/produce.html").read_text(encoding="utf-8")
    assert si.check_orb_permutation(html).verdict == GREEN


def test_orb_permutation_detects_duplicate():
    html = 'const ORB_TO_PANEL = [0, 1, 1];\nconst PANEL_BY_KEY = {a:0, b:1, c:2};'
    assert si.check_orb_permutation(html).verdict == RED


def test_orb_permutation_gray_when_not_found():
    r = si.check_orb_permutation("<html>없음</html>")
    assert r.verdict == GRAY


# ── check_reap_vs_deploy ─────────────────────────────────────────
def test_reap_vs_deploy_on_real_files():
    store = (REPO / "shopping_shorts/store.py").read_text(encoding="utf-8")
    dep = (REPO / "deploy/auto_deploy.sh").read_text(encoding="utf-8")
    assert si.check_reap_vs_deploy(store, dep).verdict == GREEN


def test_reap_vs_deploy_detects_inversion():
    dep = "task IN ('mix','render') AND datetime(heartbeat_at) > datetime('now','-5 minutes')"
    assert si.check_reap_vs_deploy("def reap_stale(self, minutes=6", dep).verdict == RED


def test_reap_vs_deploy_gray_when_not_found():
    r = si.check_reap_vs_deploy("아무 것도 없음", "아무 것도 없음")
    assert r.verdict == GRAY


# ── check_speech_rate_single ─────────────────────────────────────
def test_speech_rate_single_green_with_one_definition():
    py_sources = {"shopping_shorts/edit_plan.py": "_SYLLABLES_PER_SEC = 5.7\n"}
    assert si.check_speech_rate_single(py_sources).verdict == GREEN


def test_speech_rate_single_detects_duplicate_definition():
    """사보타주: 같은 상수 대입이 두 파일에 있으면 빨강이어야 한다."""
    py_sources = {
        "shopping_shorts/edit_plan.py": "_SYLLABLES_PER_SEC = 5.7\n",
        "shopping_shorts/backbone.py": "_SYLLABLES_PER_SEC = 5.7      # edit_plan과 동일\n",
    }
    r = si.check_speech_rate_single(py_sources)
    assert r.verdict == RED and "backbone.py" in r.reason


def test_speech_rate_single_ignores_comment_mentions():
    """주석 안에 '5.7'이 여러 번 나와도(설명문) 실제 대입문이 아니면 세지 않는다 — 오탐 방지."""
    py_sources = {
        "shopping_shorts/edit_plan.py": (
            "_SYLLABLES_PER_SEC = 5.7\n"
            "# 라이브 렌더 실측 8.19자/초 = 5.7 x 1.44\n"
        ),
        "shopping_shorts/script_gate.py": (
            "#   _SYLLABLES_PER_SEC(5.7, 성우 14명 실합성 측정) x _speech_speed()(라이브 배속 1.44).\n"
        ),
    }
    r = si.check_speech_rate_single(py_sources)
    assert r.verdict == GREEN and r.reason == "정의처 ['shopping_shorts/edit_plan.py']"


def test_speech_rate_single_gray_when_not_found():
    r = si.check_speech_rate_single({"a.py": "print(1)"})
    assert r.verdict == GRAY


# ── check_tts_path_single ────────────────────────────────────────
def test_tts_path_single_on_real_sources():
    py_sources = {
        str(p.relative_to(REPO)).replace("\\", "/"): p.read_text(encoding="utf-8", errors="replace")
        for p in (REPO / "shopping_shorts").glob("*.py")
    }
    assert si.check_tts_path_single(py_sources).verdict == GREEN


def test_tts_path_single_detects_duplicate():
    py_sources = {
        "shopping_shorts/mix_pipeline.py": "def _beat_tts_path(tts_dir, beat):\n    pass\n",
        "shopping_shorts/other.py": "def _beat_tts_path(tts_dir, beat):\n    pass\n",
    }
    r = si.check_tts_path_single(py_sources)
    assert r.verdict == RED


def test_tts_path_single_gray_when_not_found():
    r = si.check_tts_path_single({"a.py": "print(1)"})
    assert r.verdict == GRAY


# ── check_cut_count_rule ─────────────────────────────────────────
def test_cut_count_rule():
    ok = {"beats": [{"text": "a"}, {"text": "b"}], "cuts": [1, 2], "captions": ["a", "b"]}
    assert si.check_cut_count_rule(ok).verdict == GREEN
    bad = {"beats": [{"text": "a"}, {"text": "b"}], "cuts": [1], "captions": ["a", "b"]}
    assert si.check_cut_count_rule(bad).verdict == RED


def test_cut_count_rule_gray_when_field_missing():
    r = si.check_cut_count_rule({"beats": [{"text": "a"}]})
    assert r.verdict == GRAY


# ── run_all ───────────────────────────────────────────────────────
def test_run_all_returns_six_results():
    out = si.run_all(REPO)
    assert len(out) == 6
    assert all(r.layer == "L0" and r.signature.startswith("L0:") for r in out)
