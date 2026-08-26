"""썸네일 제목 추천기(thumb_title) — 대본→짧은 제목 후보.

네트워크·키풀은 건드리지 않는다. 프롬프트가 대본을 싣는지, 무키일 때 None으로
빠지는지(호출부가 502로 돌려주는 계약)만 잠근다.
"""
from shopping_shorts import thumb_title


def test_prompt_carries_script_and_is_thumbnail_flavored():
    job = {"given_script": "밥솥으로 만든 빵 진짜 미쳤다",
           "script_structure": {"tone": "반말"},
           "headcopy": {"text": "밥솥 빵"}}
    p = thumb_title._build_prompt(job)
    assert "밥솥으로 만든 빵 진짜 미쳤다" in p        # 대본이 실렸다
    assert "썸네일 제목" in p                          # SEO가 아니라 썸네일용 규격
    assert "검색용 긴 문장 금지" in p                  # 짧게 강제


def test_generate_returns_none_without_keys(monkeypatch):
    monkeypatch.setattr(thumb_title.key_vault, "get_live_keys_cascade", lambda g: [])
    assert thumb_title.generate({"given_script": "x"}) is None


# ── 수집 대본(부품은행) 참고 훅 주입 ────────────────────────────────
# 목적: 요약형 제목이 아니라 '스크롤을 멈추는' 제목이 나오게 하는 재료가 실제로 실리는지.

def _fake_bank(monkeypatch, bank):
    monkeypatch.setattr(thumb_title.script_engine, "load_bank", lambda *a, **k: bank)


def test_prompt_carries_collected_hooks(monkeypatch):
    _fake_bank(monkeypatch, {"hook": ["커피 찌꺼기 그냥 버리지 마세요"],
                             "surprise": ["친구가 깜짝 놀라더라구요"]})
    p = thumb_title._build_prompt({"given_script": "밥솥 빵"})
    assert "커피 찌꺼기 그냥 버리지 마세요" in p      # 수집된 훅이 참고로 실렸다
    assert "친구가 깜짝 놀라더라구요" in p
    assert "훅 장치" in p                              # 요약 금지 → 장치를 걸라는 지시


def test_prompt_forbids_copying_and_inventing_numbers(monkeypatch):
    """참고 훅을 준 순간 생기는 두 사고를 프롬프트가 막고 있는가.
    (실측: 세탁기 제목에 '그냥 버리지 마세요'가 그대로 나왔고, 대본에 없는 '3분 만에'가 나왔다)"""
    _fake_bank(monkeypatch, {"hook": ["그냥 버리지 마세요"], "surprise": []})
    p = thumb_title._build_prompt({"given_script": "밥솥 빵"})
    assert "그대로 가져다 쓰지 마라" in p
    assert "대본에 실제로 나온 숫자만" in p


def test_bank_rotates_by_seed_but_is_stable(monkeypatch):
    """다시 누르면 다른 조각이 보여야 같은 후보가 반복되지 않는다. 같은 seed면 항상 같다(재현성)."""
    _fake_bank(monkeypatch, {"hook": [f"훅{i}" for i in range(30)], "surprise": []})
    a0, a1 = thumb_title._bank_block(seed=0), thumb_title._bank_block(seed=1)
    assert a0 != a1
    assert a0 == thumb_title._bank_block(seed=0)


def test_no_bank_means_no_injection(monkeypatch):
    """은행이 비면 참고 블록 없이 종전대로 동작한다(무주입=회귀 0)."""
    _fake_bank(monkeypatch, {"hook": [], "surprise": []})
    assert thumb_title._bank_block() == ""
    assert "[참고 훅" not in thumb_title._build_prompt({"given_script": "밥솥 빵"})


def test_bank_failure_does_not_break_titles(monkeypatch):
    """은행 로드가 깨져도 제목 생성은 계속돼야 한다(참고는 있으면 좋은 것일 뿐)."""
    def boom(*a, **k):
        raise OSError("bank gone")
    monkeypatch.setattr(thumb_title.script_engine, "load_bank", boom)
    assert thumb_title._bank_block() == ""
    assert "밥솥 빵" in thumb_title._build_prompt({"given_script": "밥솥 빵"})


# -- 구분기호 → 줄바꿈 정규화 (2026-08-23) ----------------------------
# 사장님 지시: "썰네일 자동생성에 슬러시 표시 없애고 자동으로 두 줄로".
# 프롬프트로 '/'를 금지했지만 프롬프트는 보장이 아니다 — 모델이 기호를 넣어도
# 캔버스에 글자로 그려지지 않도록 생성 결과를 한 곳에서 정규화한다.

def test_prompt_forbids_separator_chars():
    """프롬프트가 '/'로 나누지 말라고 명시하고, 예시에도 ' / '가 없다."""
    p = thumb_title._build_prompt({"given_script": "x"})
    assert "구분기호를 절대 쓰지 마라" in p
    assert " / " not in p.split("[대본]")[0]     # 지시문 구간에 슬래시 예시가 없다


def test_normalize_turns_separators_into_linebreak():
    """'/'·'|' 구분은 줄바꿈으로 바뀜다 — 썰네일에 기호가 안 보이게."""
    f = thumb_title._normalize_title
    assert f("매일 면도 상처 / 남편이 괴로워요") == "매일 면도 상처NL남편이 괴로워요".replace("NL", "\n")


def test_normalize_keeps_real_linebreak_and_single_line():
    f = thumb_title._normalize_title
    assert f("윗줄\n아랫줄") == "윗줄\n아랫줄"     # 이미 줄바꿈이면 그대로
    assert f("한 줄 제목") == "한 줄 제목"                 # 한 줄은 건들지 않는다


def test_normalize_does_not_break_slash_inside_word():
    """24/7처럼 붙어있는 슬래시는 구분자가 아니다 — 띄어쓰기로 갈라야 구분자."""
    f = thumb_title._normalize_title
    assert f("24/7 돌아가요") == "24/7 돌아가요"


def test_normalize_collapses_and_trims():
    f = thumb_title._normalize_title
    assert f("  윗줄  \n\n  아랫줄  ") == "윗줄\n아랫줄"   # 빈줄·양끝 공백 정리
    assert f("한줄\n두줄\n세줄").count("\n") == 2      # 세 줄까지는 보존(임의로 안 자른다)


def test_generate_normalizes_model_output(monkeypatch):
    """모델이 '/'를 넘겨도 generate()가 걸러낸다(프론트가 받기 전에)."""
    class _Resp:
        text = '{"titles":[{"text":"윗줄 / 아랫줄","why":"반전"}]}'

    class _Models:
        def generate_content(self, **kw):
            return _Resp()

    class _Client:
        models = _Models()

    monkeypatch.setattr(thumb_title.key_vault, "get_live_keys_cascade", lambda g: ["k1"])
    monkeypatch.setattr(thumb_title.key_vault, "get_client_for_key", lambda k: _Client())
    out = thumb_title.generate({"given_script": "x"})
    assert out[0]["text"] == "윗줄\n아랫줄"
    assert "/" not in out[0]["text"]
