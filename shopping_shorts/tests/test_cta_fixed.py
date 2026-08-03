"""CTA는 '댓글에 OO 남겨주세요'로 고정(2026-08-03 사장님 지시).

무슨 일이 있었나(실측 job 23208dec38e6): 후보 대사가 **"비결 궁금하시면 프로필 링크
확인해주세요"**로 끝났다. 부품은행의 CTA 목록에 남의 채널에서 수확한 '프로필 👉 @아이디'
계열이 섞여 있었고, 모델이 그걸 골라 **우리에게 없는 유입 경로**를 안내했다.

두 겹으로 막는다: ①은행에서 CTA 버킷을 빼고 형식을 프롬프트에 못박음(bank_assemble)
②그래도 새면 코드가 CTA 비트 대사를 갈아끼움(_ensure_cta_beat).
"""
from shopping_shorts import bank_assemble, edit_plan


def test_detector_accepts_comment_cta_variants():
    """어미 흔들림은 허용한다 — 고정하려는 건 유입 경로지 말투가 아니다."""
    for t in ("댓글에 '점토' 남겨주세요", "댓글에 '신발'이라고 적어주세요",
              "댓글 달아주세요", "궁금하면 아래 댓글에 남기세요"):
        assert edit_plan._has_comment_cta(t), t


def test_detector_rejects_other_funnels():
    """★프로필·바로가기는 우리에게 없는 경로다 — 반드시 걸러야 한다."""
    for t in ("비결 궁금하시면 프로필 링크 확인해주세요",
              "프로필 바로가기 @home_pick",
              "지금 바로 확인해보세요",
              "직접 해보시면 놀라실 거예요"):
        assert not edit_plan._has_comment_cta(t), t


def test_bank_block_has_no_cta_list():
    """은행이 CTA 후보를 나열하면 모델이 그중에서 고른다 — 목록 자체를 없앴다."""
    class _FakeStore:
        def list_pattern_items(self, bucket=None, **kw):
            return [{"text": f"프로필 👉 @someone_{bucket}", "perf": {}}]

    blk = bank_assemble.parts_block(_FakeStore())
    assert "· CTA:" not in blk, "은행이 여전히 CTA 목록을 준다"
    assert "@someone_cta" not in blk, "CTA 버킷 내용이 새어나왔다"
    assert "댓글에" in blk, "고정 형식 지시가 빠졌다"


def _cand(cta_text, story):
    return {"plan": {"beats": [
        {"role": "훅", "narration": "낡은 집 고민이죠?", "primary": {"seg_id": "s0-1"}},
        {"role": "CTA", "narration": cta_text, "primary": {"seg_id": "s0-2"}},
    ]}, "story": story}


def test_cta_narration_is_replaced_when_funnel_is_wrong():
    """★CTA 비트가 있어도 유도 문구가 없으면 대사를 갈아끼운다.

    비트를 새로 붙이지 않는 이유: 화면이 하나 더 필요해지고 길이도 늘어난다."""
    c = _cand("지금 바로 확인해보세요.", {"cta_line": "댓글에 '점토' 남겨주세요"})
    n_before = len(c["plan"]["beats"])
    edit_plan._cta_fix_narration(c)
    beats = c["plan"]["beats"]
    assert len(beats) == n_before, "비트 수가 늘었다(대사만 갈아끼워야 한다)"
    assert edit_plan._has_comment_cta(beats[-1]["narration"]), beats[-1]["narration"]


def test_cta_built_from_keyword_when_cta_line_also_lacks_funnel():
    """cta_line마저 유도가 없으면 키워드로 직접 만든다 — 유도가 통째로 빠지면 안 된다."""
    c = _cand("직접 해보세요.", {"cta_line": "지금 확인해보세요", "cta_keyword": "점토"})
    edit_plan._cta_fix_narration(c)
    got = c["plan"]["beats"][-1]["narration"]
    assert edit_plan._has_comment_cta(got), got
    assert "점토" in got


def test_good_cta_is_left_alone():
    """이미 정상인 CTA는 건드리지 않는다(회귀0)."""
    good = "집안 보수가 필요하면 댓글에 '점토' 남겨주세요"
    c = _cand(good, {"cta_line": "다른 문구"})
    edit_plan._cta_fix_narration(c)
    assert c["plan"]["beats"][-1]["narration"] == good


def test_lengthen_judgement_is_not_polluted():
    """★생성 단계에서 CTA를 갈아끼우면 안 된다 — 후보 길이가 바뀌어 길이 재생성
    판단('전부 짧은가')이 오염된다(실측: test_scene_first_lengthen 2건이 그렇게 깨졌다).
    `_ensure_cta_beat`(생성 단계)은 CTA가 **있으면** 손대지 않아야 한다."""
    beats = [
        {"role": "훅", "narration": "곰팡이요", "primary": {"seg_id": "s0-1"}},
        {"role": "cta", "narration": "댓글요", "primary": {"seg_id": "s0-2"}},
    ]
    out = edit_plan._ensure_cta_beat(beats, {"cta_line": "댓글에 '점토' 남겨주세요"})
    assert out[-1]["narration"] == "댓글요", "생성 단계에서 CTA 대사가 바뀌었다"


# ── 중간 CTA 중복 제거(2026-08-03 사장님: "CTA가 두 번씩 반복됨") ──────────
# 실측 job e72379132e7b: 결과 비트가 "...정보 필요하시면 댓글에 '김밥' 남겨주세요"로
# 끝나고 다음 CTA 비트가 또 댓글 유도 — 같은 말이 두 번 나갔다.

def test_strip_mid_cta_removes_comment_cta_from_non_cta_beats():
    c = {"plan": {"beats": [
        {"role": "결과", "narration": "식어도 갓 만든 것처럼 맛있거든요. 정보 필요하시면 댓글에 '김밥' 남겨주세요.",
         "primary": {"seg_id": "s0-1"}},
        {"role": "CTA", "narration": "궁금하시면 댓글에 '김밥' 남겨주세요.", "primary": {"seg_id": "s0-2"}},
    ]}}
    edit_plan._strip_mid_cta(c)
    beats = c["plan"]["beats"]
    assert not edit_plan._has_comment_cta(beats[0]["narration"]), beats[0]["narration"]
    assert "맛있거든요" in beats[0]["narration"], "CTA 아닌 문장까지 지워졌다"
    assert edit_plan._has_comment_cta(beats[1]["narration"]), "진짜 CTA 비트는 건드리면 안 된다"


def test_strip_mid_cta_keeps_beat_when_everything_is_cta():
    """남는 문장이 없으면 원문 유지 — 빈 비트를 만드는 것보다 중복이 낫다."""
    c = {"plan": {"beats": [
        {"role": "결과", "narration": "댓글에 '김밥' 남겨주세요.", "primary": {"seg_id": "s0-1"}},
        {"role": "CTA", "narration": "댓글에 '김밥' 남겨주세요.", "primary": {"seg_id": "s0-2"}},
    ]}}
    edit_plan._strip_mid_cta(c)
    assert c["plan"]["beats"][0]["narration"] == "댓글에 '김밥' 남겨주세요."
