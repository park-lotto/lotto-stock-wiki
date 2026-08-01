"""대본 고도화 v2 — 어미 유형·감각어 채점 + 훅 중복 + 말투 재생성 게이트(2026-07-30).

사장님 제보: "~했어요 단문으로만 끊긴다. '~하는 거 있죠?/~하더라구요' 같은 생생한 말투를
원하는데 적용이 안 된다."

실측 진단(라이브 job 후보 9개 전량):
- 프롬프트엔 어미 지시가 이미 있었다(07-29). 안 지켜진 게 아니라 **검사가 헛돌았다**:
  tone_score가 '끝 2음절'을 봐서 세요/네요/어요/래요를 서로 다른 어미로 셌고,
  전부 '~요'로 끝나는 대본이 0.71로 임계 0.5를 통과했다.
- 감각어 지시도 있었지만 채점에 없어 형용사 0개짜리도 만점이었다.
- 감점만 있고 재생성이 없어, 후보가 전부 밋밋해도 그중 최선이 그대로 나갔다.

여기서 못 박는 것: 위 세 구멍이 다시 열리지 않게 한다.
"""
import pytest

from shopping_shorts import edit_plan, tone_score


# ── 1. 어미를 '음절'이 아니라 '유형'으로 본다 ────────────────────────────
def test_all_yo_endings_are_not_diverse():
    """★뿌리 회귀: 실제로 나갔던 대본. 전부 '~요'인데 예전엔 0.71로 통과했다."""
    real = ("찌꺼기 버리지 마세요.\n방마다 쿠키가 있네요.\n커피향이 나서 물어봤어요.\n"
            "찌꺼기로 만든 방향제래요.\n습기 잡는 꿀팁이라 오래 써요.\n비법은 댓글 남겨주세요.")
    assert tone_score.ending_diversity(real) < 0.5, "전부 ~요인데 다양하다고 판정하면 안 된다"


def test_lively_endings_are_diverse():
    """사장님이 원한 말투는 통과해야 한다(과잉 감점 방지)."""
    good = ("커피 찌꺼기 그냥 버리지 마세요.\n방마다 쿠키가 걸려 있는 거 있죠?\n"
            "홈카페 찌꺼기로 만든 거라지 뭐예요.\n집에 오자마자 저도 찍어봤거든요.\n"
            "곰팡이 없이 은은한 향이 퍼지더라구요.")
    assert tone_score.ending_diversity(good) >= 0.5


@pytest.mark.parametrize("sent,expected", [
    ("방마다 쿠키가 걸려 있는 거 있죠", "QUESTION"),
    ("향이 퍼지더라구요", "LIVE"),
    ("저도 찍어봤거든요", "LIVE"),
    ("만든 거라지 뭐예요", "LIVE"),
    ("그냥 버리지 마세요", "IMPERATIVE"),
    ("정말 좋아하네요", "PLAIN"),
    ("바로 만들어봤어요", "PLAIN"),
])
def test_ending_type_classification(sent, expected):
    assert tone_score.ending_type(sent) == expected


def test_plain_majority_is_penalized():
    """밋밋한 평서가 과반이면 감점 — 프롬프트의 '절반 넘기지 마라'와 짝."""
    plain = "좋아요.\n편해요.\n빨라요.\n깨끗해요.\n만족해요."
    assert "평서과다" in " ".join(tone_score.score_conversational(plain)["flags"])


def test_no_lively_ending_is_flagged():
    plain = "이걸 샀어요.\n집에 왔어요.\n바로 써봤어요.\n좋았어요."
    assert "생생어미0" in tone_score.score_conversational(plain)["flags"]


# ── 2. 감각어를 센다(사장님: "감각어를 풍부하게") ──────────────────────
def test_sensory_counts_real_words_not_intensifiers():
    """'너무·정말·진짜'는 감각어가 아니라 강조어다 — 실측에서 부사 대부분이 이것이었다."""
    p = tone_score.sensory_profile("입에서 사르르 녹고 폭신한 게 정말 너무 진짜 좋아요")
    assert {"사르르", "폭신"} <= set(p["hits"])
    assert p["intensifiers"] == 3
    assert "정말" not in p["hits"]


def test_short_onomatopoeia_needs_word_boundary():
    """1음절 의태어는 경계를 봐야 오탐이 없다('확인'의 '확'은 감각어가 아니다)."""
    assert "확" not in tone_score.sensory_profile("확인해 주세요")["hits"]
    assert "확" in tone_score.sensory_profile("냄새가 확 퍼져요")["hits"]


def test_zero_sensory_is_flagged():
    """★프롬프트가 감각어를 요구하는데 채점이 안 보면 지시가 무시된다(형용사 0개도 만점이었다)."""
    flat = ("이 제품을 샀습니다만 좋아요.\n사용이 편해요.\n결과도 만족스러워요.\n"
            "다들 한번 써보시면 좋겠어요.\n가격도 괜찮아요.")
    assert "감각어0" in tone_score.score_conversational(flat)["flags"]


def test_rich_sensory_scores_higher_than_flat():
    flat = "향이 좋아요. 냄새가 사라져요. 기분이 좋아요. 다들 만족해요."
    rich = "향긋한 냄새가 확 퍼져요. 꿉꿉하던 게 싹 빠지더라구요. 보송해진 게 느껴지는 거 있죠?"
    assert tone_score.score_conversational(rich)["score"] > \
           tone_score.score_conversational(flat)["score"]


# ── 3. 훅 중복(실사고) ────────────────────────────────────────────────
def test_hook_not_duplicated_when_slightly_different():
    """★실사고 재현(07-30 job 9d03ee74): hook과 beats[0]이 따옴표·수식어만 달라도
    예전 완전일치 검사를 빠져나가 훅이 두 번 붙었다."""
    n = '친구가 이거 보더니 "진짜 곱네" 하더라고요'
    h = "친구가 이거 보더니 곱네 하더라고요"
    assert edit_plan._lead_with_hook(n, h) == n


def test_hook_still_prepended_when_genuinely_different():
    """중복만 막는 것이지 훅 얹기 기능 자체를 죽이면 안 된다."""
    out = edit_plan._lead_with_hook("방마다 쿠키가 있어요", "0원으로 집안 냄새 잡는 법")
    assert out.startswith("0원으로 집안 냄새 잡는 법")
    assert "방마다 쿠키가 있어요" in out


def test_hook_identical_is_not_duplicated():
    n = "커피 찌꺼기 그냥 버리지 마세요"
    assert edit_plan._lead_with_hook(n, n) == n


# ── 4. 말투 재생성 게이트 ─────────────────────────────────────────────
def test_tone_gate_threshold_exists():
    assert 0 < edit_plan._TONE_GATE <= 1


def test_cand_tone_reads_beat_narrations():
    """게이트 판정이 실제 비트 나레이션을 읽는가(빈 후보는 0)."""
    good = {"plan": {"beats": [
        {"narration": "방마다 쿠키가 걸려 있는 거 있죠?"},
        {"narration": "홈카페 찌꺼기로 만든 거라지 뭐예요."},
        {"narration": "은은한 향이 퍼지더라구요."}]}}
    flat = {"plan": {"beats": [
        {"narration": "이걸 샀어요."}, {"narration": "좋아요."},
        {"narration": "만족해요."}, {"narration": "추천해요."}]}}
    assert edit_plan._cand_tone(good) > edit_plan._cand_tone(flat)
    assert edit_plan._cand_tone({"plan": {"beats": []}}) == 0.0


def test_generator_accepts_tone_boost():
    """재생성 경로가 부르는 인자가 실제로 존재해야 한다(하네스가 계약을 발명하지 않게)."""
    import inspect
    assert "tone_boost" in inspect.signature(edit_plan._scene_first_candidates).parameters


def test_candidate_quality_joins_beats_as_sentences():
    """★비트를 공백으로 이으면 마침표 없는 후보가 1문장으로 세어져 무조건 통과했다
    (실측 job e9e74aea). 줄바꿈으로 이어 비트 경계를 문장 경계로 만든다."""
    import shopping_shorts.edit_plan as ep
    src = inspect_source(ep._candidate_quality)
    assert '"\\n".join' in src, "비트 join이 줄바꿈이 아니면 어미 다양성이 무력화된다"


def inspect_source(fn):
    import inspect
    return inspect.getsource(fn)


# ── 5. 구조 교정(2026-07-30 백테스트로 드러난 결함) ────────────────────
def test_cta_moved_to_last():
    """★실측 job d01f6567: CTA 뒤에 '보충' 비트가 붙어 영상이 CTA로 안 끝났다."""
    beats = [{"beat_idx": 0, "role": "훅", "narration": "훅"},
             {"beat_idx": 1, "role": "CTA", "narration": "댓글에 '커피' 남겨주세요"},
             {"beat_idx": 2, "role": "보충", "narration": "끈 달아 걸어두면 됩니다"}]
    out = edit_plan._fix_beat_structure(beats)
    assert edit_plan._is_cta(out[-1]), "CTA가 마지막이어야 한다"
    assert [b["beat_idx"] for b in out] == [0, 1, 2], "재배치 후 beat_idx를 다시 매겨야 한다"


def test_cta_already_last_is_untouched():
    beats = [{"beat_idx": 0, "role": "훅", "narration": "훅"},
             {"beat_idx": 1, "role": "CTA", "narration": "댓글 남겨주세요"}]
    assert [b["role"] for b in edit_plan._fix_beat_structure(beats)] == ["훅", "CTA"]


def test_banmal_cta_is_fixed():
    """★실측 job e9e74aea/b3959fbc: CTA가 '남겨줘'로 반말이 됐다(존댓말 톤 깨짐)."""
    beats = [{"beat_idx": 0, "role": "훅", "narration": "훅"},
             {"beat_idx": 1, "role": "CTA", "narration": "비법 궁금하면 댓글에 커피 남겨줘"}]
    out = edit_plan._fix_beat_structure(beats)
    assert out[-1]["narration"].endswith("남겨주세요")


def test_long_beat_drops_stale_caption_lines():
    """긴 비트는 자막줄을 무효화해 3~4어절 규칙으로 다시 끊기게 한다(문장은 안 지운다)."""
    long_n = "가" * 60
    beats = [{"beat_idx": 0, "role": "해결", "narration": long_n, "caption_lines": ["옛", "줄"]}]
    out = edit_plan._fix_beat_structure(beats)
    assert out[0]["caption_lines"] is None
    assert out[0]["narration"] == long_n, "이야기를 깨는 절단은 하지 않는다"


# ── 6. 죽은 키로 대본 생성이 통째로 포기되던 버그(2026-07-30 실측) ──────
def test_dead_key_errors_are_recognized():
    """★403 '권한 거부'가 분류에서 새서 _vault_call이 다음 키로 안 넘어가고 포기했다.

    실측: 캐스케이드 14키 중 12키가 멀쩡한데 403 키 하나 때문에 백테스트가 절반씩 실패.
    라이브에서도 그 키를 집으면 대본 생성이 죽고 옛 생성기로 조용히 폴백됐다.
    """
    real = Exception("403 PERMISSION_DENIED. {'error': {'code': 403, "
                     "'message': 'Your project has been denied access.', "
                     "'status': 'PERMISSION_DENIED'}}")
    assert edit_plan._is_dead_key_error(real)
    assert edit_plan._is_dead_key_error(Exception("401 UNAUTHENTICATED"))
    assert edit_plan._is_dead_key_error(Exception("API key not valid"))


def test_transient_errors_are_not_dead_keys():
    """일시적 오류(503·429)를 죽은 키로 표시하면 멀쩡한 키를 영구히 버린다."""
    assert not edit_plan._is_dead_key_error(Exception("503 UNAVAILABLE overloaded"))
    assert not edit_plan._is_dead_key_error(Exception("429 RESOURCE_EXHAUSTED"))


def test_vault_call_tries_next_key_after_dead_one(monkeypatch):
    """죽은 키 뒤에 살아있는 키가 있으면 결과를 받아내야 한다(포기 금지)."""
    kv = edit_plan.key_vault
    monkeypatch.setattr(kv, "get_live_keys_cascade", lambda g: ["DEAD", "LIVE"])
    monkeypatch.setattr(kv, "mark_exhausted", lambda *a, **k: None)
    monkeypatch.setattr(kv, "_owner_group", lambda k: "general", raising=False)

    class _Models:
        def __init__(self, key):
            self.key = key

        def generate_content(self, **kw):
            if self.key == "DEAD":
                raise Exception("403 PERMISSION_DENIED. denied access")
            class R:
                text = '{"ok": true}'
            return R()

    monkeypatch.setattr(kv, "get_client_for_key",
                        lambda key: type("C", (), {"models": _Models(key)})())
    assert edit_plan._vault_call("prompt", {}) == {"ok": True}


# ── 7. 긴 비트 분할(2026-07-30 백테스트: 55자 초과 26개 중 15개가 2문장) ──
def _beat(role, narr, n_alts=2, **kw):
    return dict({"beat_idx": 0, "role": role, "narration": narr,
                 "caption_lines": ["옛", "줄"],
                 "primary": {"seg_id": "s0-0"},
                 "alternates": [{"seg_id": f"s0-{i + 1}"} for i in range(n_alts)]}, **kw)


def test_long_two_sentence_beat_is_split_not_truncated():
    """★문장을 지우지 않는다 — 그 문장들이 오히려 가장 좋은 글이었다.

    2026-08-01 재설계: 화면(비트 개수)은 이제 절대 안 나눈다(슬롯 불변식 —
    _assign_timeline 재호출 시 화면 중복을 막기 위함, job 8226822c5b09 실측).
    두 문장은 그대로 한 비트에 남고, 자막줄만 무효화돼 다시 끊기게 한다."""
    a = "제빵기로 반죽했더니 찰기가 장난 아닌 거 있죠?"
    b = "오븐에 넣었더니 향긋한 냄새가 온 집안에 확 퍼지더라구요."
    beats = [_beat("훅", "커피 버리지 마세요", n_alts=0),
             _beat("해결", f"{a} {b}", n_alts=2),
             _beat("CTA", "댓글 남겨주세요", n_alts=0)]
    out = edit_plan._fix_beat_structure(beats)
    narrs = [x["narration"] for x in out]
    assert f"{a} {b}" in narrs, "문장을 지우거나 나누지 않고 한 비트에 유지해야 한다"
    assert len(out) == 3, f"비트 개수는 그대로여야 한다(화면 불변): {narrs}"
    i = narrs.index(f"{a} {b}")
    assert out[i]["caption_lines"] is None, "자막줄만 무효화돼야 한다"


def test_single_sentence_long_beat_is_not_split():
    """문장이 하나면 나눌 경계가 없다 — 그대로 둔다."""
    one = "가" * 80
    beats = [_beat("훅", "훅", n_alts=0), _beat("해결", one, n_alts=2)]
    out = edit_plan._fix_beat_structure(beats)
    assert [x["narration"] for x in out] == ["훅", one]


def test_no_split_when_only_one_clip():
    """컷이 하나면 나눠도 같은 화면이 두 번 나와 반복으로 보인다 → 그대로 둔다."""
    two = "앞 문장이 충분히 길어서 오십오자를 넘기게 만든다 그렇지요. 뒤 문장도 이어집니다."
    beats = [_beat("훅", "훅", n_alts=0), _beat("해결", two, n_alts=0)]
    assert len(edit_plan._fix_beat_structure(beats)) == 2


def test_hook_and_cta_are_never_split():
    """훅·CTA를 쪼개면 첫 임팩트와 마무리가 깨진다."""
    two = "앞 문장이 충분히 길어서 오십오자를 넘기게 만든다 그렇지요. 뒤 문장도 이어집니다."
    beats = [_beat("훅", two, n_alts=2), _beat("CTA", two, n_alts=2)]
    out = edit_plan._fix_beat_structure(beats)
    assert len(out) == 2, "훅·CTA는 분할 대상이 아니다"


def test_split_renumbers_beat_idx():
    a, b = "앞 문장이 아주 길어서 오십오자를 확실히 넘기도록 만든다.", "뒤 문장도 이어집니다."
    beats = [_beat("훅", "훅", n_alts=0), _beat("해결", f"{a} {b}", n_alts=2),
             _beat("CTA", "댓글 남겨주세요", n_alts=0)]
    out = edit_plan._fix_beat_structure(beats)
    assert [x["beat_idx"] for x in out] == list(range(len(out)))


def test_conform_cannot_reintroduce_banmal_cta():
    """★실측 회귀(2026-07-30): _ground_candidate에서 CTA 반말을 고쳐도, 그 뒤 도는
    _conform_overflow_beats(길이 압축)가 '남겨주세요'를 '남겨줘'로 되돌려 그대로 나갔다.
    압축 뒤에도 구조 교정이 걸리는지 못 박는다."""
    beats = [{"beat_idx": 0, "role": "훅", "narration": "훅 문장",
              "primary": {"seg_id": "a"}, "alternates": []},
             {"beat_idx": 1, "role": "CTA", "narration": "궁금하면 댓글에 필요 남겨줘",
              "primary": {"seg_id": "b"}, "alternates": []}]
    # conform이 반말로 압축한 직후 상태를 그대로 넣어도 교정돼야 한다(멱등 확인).
    out = edit_plan._fix_beat_structure(beats)
    assert out[-1]["narration"].endswith("남겨주세요")
    # 두 번 불러도 망가지지 않는다(_ground_candidate + conform 뒤 두 번 호출된다).
    again = edit_plan._fix_beat_structure(out)
    assert again[-1]["narration"].endswith("남겨주세요")
    assert len(again) == len(out)


def test_conform_path_is_followed_by_structure_fix():
    """배선 확인 — conform 호출 뒤에 _fix_beat_structure가 있어야 한다."""
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    i = src.index("_conform_overflow_beats")
    assert "_fix_beat_structure" in src[i:i + 600], "압축 뒤 교정이 빠졌다 — 반말 CTA가 되돌아온다"


# ── 8. 엔진 기본값 v3(2026-07-30 사장님 승인) ──────────────────────────
def test_default_engine_is_v3_with_bank():
    """기본 엔진이 은행을 실제로 주입해야 한다 — 켰다고 해놓고 무주입이면 무의미하다."""
    from shopping_shorts import script_engine as se
    eng = se.get()                      # 인자 없음 = 라이브 기본 경로
    assert eng.name == "v3" and eng.use_bank


def test_default_engine_injects_nonempty_block():
    """배포된 은행 파일로 실제 프롬프트 블록이 만들어지는가(빈 파일이면 실패)."""
    from shopping_shorts import script_engine as se
    block = se.get().extra_rules()
    assert "참고 부품" in block, "은행이 비어 프롬프트에 아무것도 안 실린다"
    assert "베끼" in block, "그대로 베끼기 금지 문구가 빠지면 드리프트가 재발한다"


def test_engine_can_be_rolled_back_by_name():
    """v2로 되돌리면 무주입 — 서버 환경변수만으로 즉시 롤백 가능해야 한다."""
    from shopping_shorts import script_engine as se
    assert se.get("v2").extra_rules() == ""


def test_generation_uses_default_engine(monkeypatch):
    """★배선 확인: build_scene_first_plan이 engine 인자 없이 불려도 은행이 프롬프트에 실린다.
    (하네스가 계약을 발명하지 않도록 실제 프롬프트 문자열을 붙잡아 확인한다)"""
    seen = {}

    def fake_call(prompt, schema, **kw):
        seen["prompt"] = prompt
        return {"candidates": []}

    seg = {"s0-0": {"video_id": "s0", "seg_id": "s0-0", "start": 0.0, "end": 2.0,
                    "text": "", "scene_desc": "", "motion_level": "MED"}}
    monkeypatch.setattr(edit_plan, "_build_inventory", lambda s: (seg, "인벤토리"))
    monkeypatch.setattr(edit_plan, "_vault_call", fake_call)
    edit_plan.build_scene_first_plan([{"video_id": "s0", "segments": [], "full_text": "x"}],
                                     "제품 설명", 30, n_candidates=3)
    assert "참고 부품" in seen.get("prompt", ""), "기본 경로에 은행이 안 실린다"


# ── 9. 말투 하한 — 밋밋한 후보가 추천으로 나가는 것 차단(2026-07-30) ────
def _mk_cand(narrs, score):
    return {"plan": {"beats": [{"narration": n} for n in narrs]},
            "score": score, "recommended": False}


def _pick(cands):
    """build_scene_first_plan 말미의 추천 선택 로직과 동일한 판정."""
    qualified = [i for i, c in enumerate(cands) if edit_plan._cand_tone(c) >= edit_plan._TONE_GATE]
    pool = qualified or range(len(cands))
    return max(pool, key=lambda i: cands[i]["score"])


_FLAT = ["이걸 샀어요.", "좋아요.", "만족해요.", "추천해요."]
_VIVID = ["방마다 쿠키가 걸려 있는 거 있죠?", "커피 찌꺼기로 만든 거라지 뭐예요.",
          "향긋한 냄새가 확 퍼지더라구요.", "보송해진 게 느껴지거든요."]


def test_vivid_candidate_wins_even_with_lower_score():
    """★핵심: 말투가 최종 점수의 15%뿐이라 밋밋한 후보가 이기던 것을 막는다."""
    cands = [_mk_cand(_FLAT, 0.90), _mk_cand(_VIVID, 0.70)]
    assert _pick(cands) == 1, "기준을 넘는 후보가 있으면 그 안에서 골라야 한다"


def test_score_still_decides_among_qualified():
    """기준을 넘는 후보가 여럿이면 종전 점수대로 고른다(매칭을 버리지 않는다)."""
    cands = [_mk_cand(_VIVID, 0.70), _mk_cand(_VIVID, 0.95)]
    assert _pick(cands) == 1


def test_falls_back_when_all_below_floor():
    """전부 미달이면 후보를 잃지 않고 종전대로 최고점을 고른다(재료 빈약한 소재 방어)."""
    cands = [_mk_cand(_FLAT, 0.60), _mk_cand(_FLAT, 0.85)]
    assert _pick(cands) == 1


def test_floor_is_wired_in_generation():
    """배선 확인 — 추천 선택에 하한이 실제로 걸려 있는가."""
    import inspect
    src = inspect.getsource(edit_plan.build_scene_first_plan)
    assert "qualified" in src and "_TONE_GATE" in src, "하한이 배선되지 않았다"


# ── 10. 분할 부작용 차단(2026-07-30 실물 확인) ─────────────────────────
def test_no_fragment_beats_from_split():
    """★실측 v6: 인용문을 쪼개 '진짜 맛있겠다'(7자)·'입가에 미소가 번지네'(11자)
    파편 비트가 생겨 화면이 뚝 끊겼다. 양쪽이 최소 길이를 넘을 때만 나눈다."""
    quote = "밀가루 없이 바나나 계란만 넣었더니 아이가 무슨 냄새냐며 달려와요. 진짜 맛있겠다"
    beats = [_beat("훅", "훅", n_alts=0), _beat("해결", quote, n_alts=2),
             _beat("CTA", "댓글 남겨주세요", n_alts=0)]
    out = edit_plan._fix_beat_structure(beats)
    assert all(len(x["narration"]) >= edit_plan._MIN_SPLIT_CHARS or "훅" in x["role"]
               or edit_plan._is_cta(x) for x in out), \
        f"파편 비트가 생겼다: {[(len(x['narration']), x['narration']) for x in out]}"


def test_split_respects_max_beats():
    """비트가 상한을 넘게 늘어나면 화면이 스타카토가 된다(실측: 6~7 지시인데 10개까지)."""
    long2 = "앞 문장이 충분히 길어서 오십오자를 확실히 넘기도록 만들어 둡니다. 뒤 문장도 충분히 깁니다요."
    beats = [_beat("훅", "훅", n_alts=0)]
    beats += [_beat(f"해결{i}", long2, n_alts=2) for i in range(6)]
    beats += [_beat("CTA", "댓글 남겨주세요", n_alts=0)]
    out = edit_plan._fix_beat_structure(beats)
    assert len(out) <= edit_plan._MAX_BEATS, f"비트가 {len(out)}개로 늘었다"


def test_longest_beat_is_split_first():
    """2026-08-01 재설계: 화면은 이제 절대 안 나뉜다 — 비트 개수는 몇 개가 길든 불변이다.
    (이전엔 분할 예산이 한 개뿐이면 가장 긴 비트를 먼저 나눴으나, 그 분할 자체를 제거했다.)"""
    short2 = "앞 문장이 오십오자를 살짝 넘기도록 적당히 길게 써 둡니다요. 뒤 문장입니다요."
    long2 = ("앞 문장이 아주아주 길어서 백자에 가깝게 늘려서 확실하게 가장 긴 비트가 되도록 "
             "만들어 둡니다요. 뒤 문장도 충분히 길게 이어서 씁니다요.")
    beats = [_beat("훅", "훅", n_alts=0), _beat("A", short2, n_alts=2),
             _beat("B", long2, n_alts=2), _beat("C", short2, n_alts=2),
             _beat("D", short2, n_alts=2), _beat("E", short2, n_alts=2),
             _beat("CTA", "댓글 남겨주세요", n_alts=0)]
    out = edit_plan._fix_beat_structure(beats)
    assert len(out) == 7, "비트 개수는 늘지 않아야 한다(화면 불변식)"
    assert sum(1 for x in out if x["role"] == "B") == 1, "B는 나뉘지 않고 하나로 남아야 한다"
