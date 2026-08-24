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
    # ★CTA 버킷은 2026-08-03부터 은행에서 안 뽑는다(형식 고정) — 부품 주입 확인은
    #   다른 버킷(훅)으로 한다. CTA는 아래에서 '형식 지시가 실렸는가'로 따로 본다.
    iid = s.add_pattern_item("hook", "와 이거 대박")
    s.set_pattern_item_status(iid, "approved")
    cid = s.add_pattern_item("cta", "프로필 바로가기 @someone")
    s.set_pattern_item_status(cid, "approved")
    ctx = BA.assemble_bank_context(s, "레시피")
    assert "학습된 아크" in ctx and "와 이거 대박" in ctx
    # 은행이 CTA 후보를 나열하면 모델이 그중에서 고른다 — 목록 대신 고정 형식만 실려야 한다.
    assert "@someone" not in ctx, "CTA 버킷 내용이 프롬프트로 샜다"
    assert "댓글에" in ctx, "CTA 고정 형식 지시가 빠졌다"


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


def test_은행블록은_소재를_우리것으로_못박는다(monkeypatch):
    """★2026-08-18 사장님 제보 "대본을 뽑으니 이상한 게 나온다".

    실측(work 3b8e5099a22e): 재료 3편이 전부 다이소 네일펜인데 A안이 통째로
    '주방 기름 가림막'으로 나왔다. 프롬프트 안에서 '주방 가림막'이라는 완성된 소재가
    나오는 자리는 winners_block의 금지 예시 문구 하나뿐이었다 — 모델이 그것을
    '우리 영상의 소재 선언'으로 읽을 수 있는 모양이었다.
    ①그 예시에서 구체 소재를 빼고 ②블록 맨 끝에서 소재를 [대본 1]로 못 박는다.
    """
    from shopping_shorts import bank_assemble

    class _S:
        def pick_spine_for_category(self, c): return {"name": "x", "situation_type": "y"}
        def list_pattern_items(self, **k): return []
        def list_pattern_sources(self, **k): return []

    monkeypatch.setattr(bank_assemble, "spine_charter", lambda s: "아크 블록")
    monkeypatch.setattr(bank_assemble, "parts_block", lambda s, k: "")
    monkeypatch.setattr(bank_assemble, "content_block", lambda s: "")
    monkeypatch.setattr(bank_assemble, "winners_block", lambda s, c: "")
    out = bank_assemble.assemble_bank_context(_S(), "홈템")
    assert "[대본 1]" in out, "우리 소재를 [대본 1]로 못 박는 문장이 빠졌다"
    assert out.rstrip().endswith("반려된다."), "못 박기는 **맨 끝**이어야 한다(마지막 지시가 가장 세다)"


def test_우승예시_금지문구에_구체소재가_없다():
    """금지 규칙이 스스로 소재를 흘리면 안 된다 — 그게 이번 사고의 통로였다."""
    import inspect
    from shopping_shorts import bank_assemble
    src = inspect.getsource(bank_assemble.winners_block)
    assert "주방 가림막" not in src, "금지 문구가 구체 소재를 단정하면 모델이 그것을 우리 소재로 읽는다"


def _fake_store():
    class _S:
        def pick_spine_for_category(self, c): return {"name": "x", "situation_type": "y"}
        def list_pattern_items(self, **k): return []
        def list_pattern_sources(self, **k): return []
    return _S()


def test_은행은_재료를_압도하지_못한다(monkeypatch):
    """★2026-08-18 사고의 물리적 원인 — 재료 750자 vs 은행 2,822자(3.8배).

    그 상태에선 은행 안의 구체 소재 하나만 있어도 대본이 그쪽으로 끌려간다
    (재료가 전부 네일펜인데 A안이 통째로 '주방 기름 가림막').
    예산을 넘으면 **뒤 블록부터 통째로** 뺀다 — 뒤로 갈수록 실제 문장이라 소재를 흘린다.
    """
    from shopping_shorts import bank_assemble as B
    monkeypatch.setattr(B, "spine_charter", lambda s: "뼈대" * 50)      # 100자
    monkeypatch.setattr(B, "parts_block", lambda s, k: "말버릇" * 100)   # 300자
    monkeypatch.setattr(B, "content_block", lambda s: "전개" * 200)      # 400자
    monkeypatch.setattr(B, "winners_block", lambda s, c: "ZZWIN" * 240)  # 1200자
    full = B.assemble_bank_context(_fake_store(), "홈템")
    tight = B.assemble_bank_context(_fake_store(), "홈템", source_chars=300)  # 예산 450자
    assert len(tight) < len(full), "예산을 걸었는데 안 줄었다"
    assert "ZZWIN" not in tight, "가장 소재를 흘리기 쉬운 뒤 블록부터 빠져야 한다"
    assert "뼈대" in tight, "스파인(뼈대)은 무슨 일이 있어도 남아야 한다"
    assert "[대본 1]" in tight, "못 박기는 잘려도 항상 붙어야 한다"


def test_예산을_안_주면_종전_그대로다(monkeypatch):
    """옛 호출부(source_chars 없음)는 동작이 바뀌면 안 된다 — 회귀 0."""
    from shopping_shorts import bank_assemble as B
    monkeypatch.setattr(B, "spine_charter", lambda s: "뼈대")
    monkeypatch.setattr(B, "parts_block", lambda s, k: "말버릇")
    monkeypatch.setattr(B, "content_block", lambda s: "전개")
    monkeypatch.setattr(B, "winners_block", lambda s, c: "우승예시")
    out = B.assemble_bank_context(_fake_store(), "홈템")
    for kw in ("뼈대", "말버릇", "전개", "우승예시"):
        assert kw in out


# ── 말 밀도 천장(2026-08-18 사장님: "계속 4초 이상 / 30초 이내가 릴스 기본") ──────────
# 히트작 실측 밀도(264~377자/30초)를 그대로 목표로 주면 우리 보이스 실측 8.19자/초로
# 32~46초짜리가 나온다. 길이는 플랫폼 규격이라 밀도보다 우선한다.

def test_density_target_capped_by_speech_speed():
    """천장은 그대로 — 말속도보다 빠른 대본은 없다.

    ★단위 주의(2026-08-24): DB `chars_per_30s`는 **raw**(공백 포함)로 쌓여 있고
      천장·판정은 **norm**(공백 제외)이다. density_target이 그 경계에서 환산한다
      (`script_gate.norm_chars_per_30s`). 그래서 여기 기대값도 norm으로 적는다.
    """
    from shopping_shorts.script_gate import (density_target, norm_chars_per_30s,
                                             SPEECH_CHARS_PER_SEC)
    cap = int(SPEECH_CHARS_PER_SEC * 30)
    # 히트작 실측 밀도는 환산해도 천장을 넘는다 → 천장이 이긴다
    assert density_target({"chars_per_30s": 377}, 30) == cap
    # 길이를 늘려 잡으면 천장도 같이 올라간다
    assert density_target({"chars_per_30s": 377}, 60) == int(SPEECH_CHARS_PER_SEC * 60)


def test_density_target_respects_styles_below_the_cap():
    """★천장 아래 스타일은 **제 값**을 지킨다 — 이게 스타일별 밀도가 사는 조건이다.

    2026-08-24 이전엔 raw 예산을 norm 천장과 견줘 **11개 스타일 100%가 천장에 잘렸다**
    (밀도를 240으로 적든 327로 적든 창이 똑같았다 = 스타일별 밀도가 죽어 있었다).
    """
    from shopping_shorts.script_gate import density_target, norm_chars_per_30s
    # raw 264 → norm 195 < 천장 222 → 잘리지 않는다
    assert density_target({"chars_per_30s": 264}, 30) == norm_chars_per_30s({"chars_per_30s": 264})
    # 서로 다른 밀도는 서로 다른 목표를 준다(같아지면 밀도가 죽은 것)
    assert density_target({"chars_per_30s": 240}, 30) != density_target({"chars_per_30s": 300}, 30)


def test_norm_chars_per_30s_converts_raw_to_norm():
    """DB(raw) → 판정(norm) 경계는 **이 함수 하나**다(0순위-B)."""
    from shopping_shorts.script_gate import norm_chars_per_30s, DEFAULT_CHARS_PER_30S
    assert norm_chars_per_30s({"chars_per_30s": 300}) == int(300 * 0.7395)
    assert norm_chars_per_30s({}) == DEFAULT_CHARS_PER_30S      # 값 없으면 기본값
    assert norm_chars_per_30s(None) == DEFAULT_CHARS_PER_30S



def test_gate_upper_bound_never_exceeds_speech_cap():
    """통과 상한(DENSITY_HI 1.4배)이 천장을 넘으면 '30초짜리'가 다시 42초가 된다."""
    from shopping_shorts import script_gate as g
    style = {"beat_roles": ["hook"], "chars_per_30s": 377}
    checks, _ = g.check(style, [{"role": "hook", "text": "가" * 300}], seconds=30)
    dens = [c for c in checks if c["name"].startswith("말 밀도")]
    assert dens and not dens[0]["ok"], "300자(=36.6초)가 30초 대본으로 통과했다"


def test_prompt_and_gate_use_the_same_target():
    """프롬프트가 시킨 글자수와 판정 기준이 다르면 '시킨 대로 썼는데 반려'가 난다."""
    from shopping_shorts.bank_assemble import style_block
    from shopping_shorts.script_gate import density_target
    style = {"name": "테스트", "beat_roles": ["hook", "cta"],
             "beat_chain": ["훅", "약속"], "chars_per_30s": 377}
    assert str(density_target(style, 30)) in style_block(style, seconds=30)


def test_est_seconds_matches_speech_constant():
    from shopping_shorts.script_gate import est_seconds, SPEECH_CHARS_PER_SEC
    assert est_seconds("") == 0.0
    assert est_seconds("가" * 82) == round(82 / SPEECH_CHARS_PER_SEC, 1)
    # 공백·문장부호는 안 센다(norm과 같은 규칙) — 화면이 같은 규칙으로 계산해야 수가 맞는다
    assert est_seconds("가 나, 다.") == est_seconds("가나다")


def test_screen_never_hardcodes_speech_speed():
    """화면이 자기 숫자로 초를 계산하면 판정(밀도 게이트)과 다른 초를 말한다(0순위-B).
    환산계수는 서버 응답(cps) 또는 draft.chars/draft.sec에서만 온다."""
    import pathlib
    html = (pathlib.Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
    i = html.index("function s2SecOf(")
    body = html[i:html.index("function s2RefreshSec(", i)]
    assert "8.19" not in body, "화면에 말속도 상수가 박혔다"
    assert "s2Cps()" in body


def test_gate_feedback_tells_direction_when_over():
    """넘쳤을 때 '채워라'라고 하면 모델이 더 길게 쓴다 — 방향을 반대로 말해야 한다."""
    from shopping_shorts import script_gate as g
    style = {"beat_roles": ["hook"], "chars_per_30s": 377}
    over, _ = g.check(style, [{"role": "hook", "text": "A" * 340}], seconds=30)
    fb = g.gate_feedback(over)
    assert "줄여라" in fb and "채워라" not in fb
    short, _ = g.check(style, [{"role": "hook", "text": "A" * 100}], seconds=30)
    assert "채워라" in g.gate_feedback(short)


def test_density_check_marks_over_flag():
    from shopping_shorts import script_gate as g
    style = {"beat_roles": ["hook"], "chars_per_30s": 377}
    c, _ = g.check(style, [{"role": "hook", "text": "A" * 340}], seconds=30)
    d = [x for x in c if x["name"].startswith("말 밀도")][0]
    assert d["over"] is True and "넘겼다" in d["detail"]
