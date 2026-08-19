"""언어 분리 — 2026-08-14 사장님 "샤오홍슈에 있는 영상은 대본과 아예 닿지 않게 하라".

실측 근거(job 9423ef05385e): 소스 5개 중 4개가 샤오홍슈(한글 0·한자 341~480), 한국어는
인스타 1개(한글 154·한자 0)뿐인데 비트1 나레이션에 원문이 그대로 옮겨붙었다 —
"가게에서 Ciabatta 恰巴塔扭扭棒 사면 개당 10위안이나 한다길래…"(한자 6자 + 통화 '위안').

처방: 외국어 소스의 **말만** 지운다. 화면·특장점은 남겨 장면 재료로 계속 쓴다.
"""
from shopping_shorts import script_lang


def _kr():
    return {"video_id": "s0", "full_text": "이거 진짜 편해요 한 번 써보세요",
            "segments": [{"seg_id": "s0-0", "text": "이거 진짜 편해요",
                          "scene_desc": "손으로 누르는 장면"}],
            "structure": {"hook": "이거 진짜 편해요"}}


def _cn():
    return {"video_id": "s1", "full_text": "恰巴塔扭扭棒 只要十元 超级好吃 快来试试",
            "segments": [{"seg_id": "s1-0", "text": "恰巴塔扭扭棒 只要十元",
                          "scene_desc": "반죽을 꼬아 올리는 손",
                          "product_benefits": ["겉바속촉으로 구워진다"]}],
            "structure": {"hook": "恰巴塔扭扭棒"}}


def test_detects_chinese_source():
    assert script_lang.is_foreign(_cn()) is True


def test_korean_source_not_foreign():
    assert script_lang.is_foreign(_kr()) is False


def test_few_hanja_in_korean_not_foreign():
    """한국어 자막에 한자 한두 자(회사명·한자어)가 섞여도 외국어로 보지 않는다."""
    sc = {"video_id": "s0", "full_text": "삼성電子 신제품 진짜 좋아요 한번 보세요",
          "segments": []}
    assert script_lang.is_foreign(sc) is False


def test_mute_clears_speech_keeps_screen():
    """말(full_text·text·structure)만 지우고 화면·특장점은 남긴다."""
    out = script_lang.mute_foreign_speech([_kr(), _cn()])
    kr, cn = out
    assert kr["full_text"] == "이거 진짜 편해요 한 번 써보세요"       # 한국어는 불변
    assert cn["full_text"] == ""
    assert cn["segments"][0]["text"] == ""
    assert cn["structure"] == {}
    # ★화면·특장점은 살아있어야 — 장면 재료로 계속 쓴다
    assert cn["segments"][0]["scene_desc"] == "반죽을 꼬아 올리는 손"
    assert cn["segments"][0]["product_benefits"] == ["겉바속촉으로 구워진다"]


def test_original_not_mutated():
    """원본 dict는 건드리지 않는다(호출부가 같은 객체를 다른 데 쓰고 있을 수 있다)."""
    src = _cn()
    script_lang.mute_foreign_speech([src])
    assert src["full_text"].startswith("恰巴塔")
    assert src["segments"][0]["text"] != ""


def test_all_korean_returns_input_unchanged():
    """대상 0개면 입력 그대로(회귀 0)."""
    srcs = [_kr(), _kr()]
    assert script_lang.mute_foreign_speech(srcs) is srcs


def test_empty_input():
    assert script_lang.mute_foreign_speech([]) == []
    assert script_lang.mute_foreign_speech(None) is None


def test_all_foreign_still_muted():
    """전부 외국어여도 말은 지운다 — 대본은 특장점(한국어)으로만 쓰인다."""
    out = script_lang.mute_foreign_speech([_cn(), _cn()])
    assert all(s["full_text"] == "" for s in out)
    assert all(s["segments"][0]["product_benefits"] for s in out)
