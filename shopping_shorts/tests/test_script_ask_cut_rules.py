"""처음 대본·재료 질문 = 장면 맞추기 검사 범위(10-27 사장님 "시험 범위를 모르고 시험 본다"): 반려 사유 전수(reject_catalog — 회원 6편·개발 4편)에서
재사용 39·남의 쇼츠 34·컷 중앙 17·A-B-A 6·훅 3 의 규칙이 처음 질문 11편 모두에 없고 고치기 질문(FIX_ALL)에만 있었다.
형식마다(쇼핑형·해외원본형·연예인형) 처음 질문에 같은 규칙 목록과 재료 샷 구간이 실려야 한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.calcopy.hybrid import flow as F  # noqa: E402

CASES = [("두유노판", "쇼핑형"), ("잇템로그판_v2", "해외원본형"), ("키치잇판", "연예인형")]
SHOTS = {"a.mp4": [[0.0, 1.33], [1.33, 3.23], [3.23, 3.5], [3.5, 9.17]]}


def _ask(v, fmt):
    st = {"version": v, "fmt": fmt, "research_md": "", "log": [], "_msheets": {"list": [], "sheets": [], "shots": SHOTS}}
    return F._script_ask(st)["ask"]


def test_first_ask_carries_every_cut_rule():
    for v, fmt in CASES:
        ask = _ask(v, fmt)
        for r in F.CUT_RULES:
            assert r in ask, f"{v}({fmt}): 처음 질문에 장면 규칙이 없다 — {r[:30]}"


def test_first_ask_carries_material_shots_and_rhythm_numbers():
    ask = _ask("두유노판", "쇼핑형")
    assert "a.mp4: 0.0~1.33, 1.33~3.23, 3.5~9.17" in ask          # 0.8초 미만 구간(3.23~3.5)은 뺀다
    assert "중앙값" in ask and "첫 0.1~3초" in ask                # 판 rhythm(두유노판 cut_median·hook_cuts_3s) — 검사기와 같은 값


def test_fix_question_uses_same_rule_list():
    for r in F.CUT_RULES:
        assert r in F.FIX_ALL


def test_first_ask_carries_script_audit_numbers():
    """판 script.audit 숫자(줄 수·글자·길이)도 처음 질문에 — 10-27 반려 전수: 잇템로그판 줄 글자 4~26·길이 26~31초가 질문에 없었다."""
    from tools.calcopy.hybrid import script_audit as SA, styles as STY
    for v, fmt in CASES:
        ask = _ask(v, fmt)
        st = STY.load(v)
        for r in (st.get("script") or {}).get("audit") or []:
            t = SA.rule_text(r, st)
            if r["kind"] not in ("engine", "sibling_repeat"):
                assert t, f"{v}: 규칙 {r['kind']} 를 글로 못 옮긴다"
                assert t in ask, f"{v}: 처음 질문에 '{t[:30]}' 가 없다"


def test_people_ok_only_for_shopping_format():
    """10-27 사장님 '영상 안에 사람 등장 괜찮은데 왜 반려 · 제품 관련 있는 건 괜찮지': 쇼핑형은 남의 얼굴 반려 안 함(대사·제품 대조는 그대로),
    연예인형·해외원본형은 그대로 반려(98 #38 광고 모델이 연예인으로 보임)."""
    assert F._other_faces({"fmt": "쇼핑형"}) is False
    assert F._other_faces({"fmt": "해외원본형"}) is True and F._other_faces({"fmt": "연예인형"}) is True
    shop, foreign = _ask("두유노판", "쇼핑형"), _ask("잇템로그판_v2", "해외원본형")
    assert F.PEOPLE_OK in shop and F.FACE_RULE not in shop
    assert F.FACE_RULE in foreign and F.PEOPLE_OK not in foreign


def test_runner_skips_face_scan_when_told(monkeypatch, tmp_path):
    from tools.calcopy.hybrid import runner_ops as R
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "m.jpg").write_bytes(b"x")
    monkeypatch.setattr(R, "_cut_faces", lambda *a, **k: 2)
    T = {"cuts": [{"src": "m.jpg", "ss": 0, "dur": 1.0, "line": "L0"}]}
    assert R.source_rule_scan(tmp_path, T, set(), faces=True)
    assert R.source_rule_scan(tmp_path, T, set(), faces=False) == []


def test_photo_files_hidden_when_version_bans_photos(monkeypatch):
    """10-27 메이블린·쉐딩: 사진 0% 판인데 '쓸 수 있는 파일'에 prod_*.jpg 를 줘 사진 컷·A-B-A 반려."""
    monkeypatch.setattr(F, "_all_dims", lambda st: {"a.mp4": [1080, 1920], "prod_1_0.jpg": [600, 600]})
    ctx = F._src_rule_ctx({"version": "잇템로그판_v2"})
    assert "a.mp4" in ctx and "prod_1_0.jpg" not in ctx


def test_alt_product_rule_in_first_ask():
    """10-27 메이블린·TV: 비슷한 제품이면 밝히는 줄(script_audit.alt_disclosed)이 처음 질문에 없어 대본 반려."""
    from tools.calcopy.hybrid import script_audit as SA
    st = {"version": "두유노판", "fmt": "쇼핑형", "research_md": "", "log": [], "_msheets": {"list": [], "sheets": [], "shots": {}},
          "product": {"mode": "alt", "name": "x"}}
    assert SA.ALT_SAY_RULE in F._script_ask(st)["ask"]
    st["product"] = {"mode": "exact", "name": "x"}
    assert SA.ALT_SAY_RULE not in F._script_ask(st)["ask"]
