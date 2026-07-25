from shopping_shorts import bank_assemble as BA
from shopping_shorts.store import Store


def test_sanitize_removes_braces():
    out = BA._sanitize("가격은 {price}원")
    assert "{" not in out and "}" not in out and "(" in out


def test_spine_charter_and_none():
    txt = BA.spine_charter({"situation_type": "레시피", "emotion_arc": "의심→인정",
                            "beat_chain": ["훅", "전환", "해소"]})
    assert "레시피" in txt and "의심→인정" in txt and "훅 → 전환 → 해소" in txt
    assert BA.spine_charter(None) == ""


def test_spine_charter_sanitizes_braces():
    txt = BA.spine_charter({"situation_type": "가격{x}", "beat_chain": []})
    assert "{" not in txt


def test_parts_block_topk_only_approved(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    for i in range(7):
        iid = s.add_pattern_item("hook", f"훅사례{i}")
        s.set_pattern_item_status(iid, "approved")
    s.add_pattern_item("hook", "미승인훅")  # pending → 제외
    block = BA.parts_block(s, k=5)
    assert "훅사례" in block and "미승인훅" not in block
    # top-5만 (승인 7개 중 5개)
    assert block.count("훅사례") == 5


def test_assemble_empty_when_bank_empty(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    assert BA.assemble_bank_context(s, "레시피") == ""


def test_assemble_combines_spine_and_parts(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    sp = s.add_spine("아크", situation_type="레시피", fit_categories=["레시피"], status="approved")
    s.update_spine_stats(sp, source_count=3, perf_score=0.7)
    iid = s.add_pattern_item("cta", "댓글에 남겨주세요")
    s.set_pattern_item_status(iid, "approved")
    ctx = BA.assemble_bank_context(s, "레시피")
    assert "학습된 아크" in ctx and "댓글에 남겨주세요" in ctx


def test_empty_category_still_injects_general_spine(tmp_path):
    """★2026-07-23 실측 버그 회귀 — 자동유형 경로(category='')에서도 범용 스파인(fit_categories
    없음)이 아크로 주입돼야. 예전엔 `if category`가 falsy라 pick을 안 불러 스파인이 죽었다."""
    s = Store(str(tmp_path / "t.db"))
    sp = s.add_spine("범용아크", situation_type="반전", fit_categories=[], status="approved")
    s.update_spine_stats(sp, source_count=17, perf_score=0.9)
    ctx = BA.assemble_bank_context(s, "")          # 자동유형 경로가 넘기는 빈 category
    assert "학습된 아크" in ctx                      # 아크가 주입돼야(예전엔 '')
    snap = BA.bank_usage_snapshot(s, "")
    assert snap["spine_present"] is True            # 계측도 spine_present=True
