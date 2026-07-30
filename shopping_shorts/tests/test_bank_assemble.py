from shopping_shorts import bank_assemble as BA
from shopping_shorts.store import Store


def test_sanitize_removes_braces():
    out = BA._sanitize("가격은 {price}원")
    assert "{" not in out and "}" not in out and "(" in out


def test_winners_block_ranks_by_views_and_prefers_category(tmp_path):
    """우승대본 few-shot: 같은 카테고리 우선 + 조회수 상위. 없으면 ''."""
    s = Store(str(tmp_path / "t.db"))
    assert BA.winners_block(s, "홈템") == ""   # 소스 없으면 빈 문자열
    s.add_pattern_source("insta", "u1", "홈템 저조회 대본 " * 5, product_category="홈템",
                         perf={"views": 100})
    s.add_pattern_source("insta", "u2", "홈템 대박 대본 " * 5, product_category="홈템",
                         perf={"views": 500000})
    s.add_pattern_source("insta", "u3", "레시피 대본 " * 5, product_category="레시피",
                         perf={"views": 999999})
    block = BA.winners_block(s, "홈템", k=2)
    assert "검증된 우승 대본" in block
    # 같은 카테고리(홈템)가 먼저, 그 안에서 조회수 높은 게 예시1
    i_big = block.find("홈템 대박")
    i_small = block.find("홈템 저조회")
    assert 0 < i_big < i_small
    # 다른 카테고리(레시피)는 홈템 2개로 채워졌으니 안 들어간다
    assert "레시피 대본" not in block


def test_winners_block_same_category_only_no_cross_contamination(tmp_path):
    """다른 카테고리 우승작은 절대 안 섞인다(청양고추 오염 방지). 같은 카테고리 없으면 ''."""
    s = Store(str(tmp_path / "t.db"))
    # 레시피 소스에 고유 sentinel 토큰(지시문엔 없는 단어)을 심어 오염 여부를 검사
    s.add_pattern_source("insta", "u1", "레시피 ZZQSENTINEL 대본 " * 5, product_category="레시피",
                         perf={"views": 999999})
    # 홈템 우승작이 하나도 없다 → 레시피로 채우지 말고 아예 비워야 한다
    assert BA.winners_block(s, "홈템") == ""
    # 카테고리 불명(빈 값)이면 오염 위험 → 무주입
    assert BA.winners_block(s, "") == ""
    assert BA.winners_block(s, None) == ""
    # 홈템 우승작을 넣으면 그것만 나온다(레시피 sentinel은 절대 안 섞임)
    s.add_pattern_source("insta", "u2", "홈템 주방 대본 " * 5, product_category="홈템",
                         perf={"views": 100})
    block = BA.winners_block(s, "홈템")
    assert "홈템 주방" in block and "ZZQSENTINEL" not in block


def test_winners_block_braces_sanitized(tmp_path):
    s = Store(str(tmp_path / "t.db"))
    s.add_pattern_source("insta", "u", "대본 {price}원 " * 5, product_category="홈템",
                         perf={"views": 10})
    assert "{" not in BA.winners_block(s, "홈템")


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
