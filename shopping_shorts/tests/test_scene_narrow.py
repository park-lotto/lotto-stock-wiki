# -*- coding: utf-8 -*-
"""장면 1차 좁히기 — Gemini에 묻기 전 무료 필터 (2026-09-08).

■ 왜 이 테스트가 있나
장면 라이브러리 자동매칭은 한 번 **꺼진 적이 있다**. mix_pipeline 주석:
    "켜고 끄는 스위치가 없어 자산이 하나라도 등록돼 있으면 **모든 영상에 무조건**
     적용됐다(당시 12개 등록). 사장님 지시('장면 라이브러리 없애, 안 쓰니까')"
서버에 실제로 남아 있는 12개는 튀김·삼겹살·서랍장·세탁기·감자튀김이다(2026-09-08
실측). 캠핑 의자 영상에 감자튀김 컷이 붙는 것이 그때의 사고다.

여기서 못박는 것은 하나다 — **말과 화면이 안 겹치면 아무것도 안 붙는다.**
아래 자산 dict는 서버 scene_assets에서 실제로 읽어온 5행을 그대로 옮긴 것이다.
"""
from shopping_shorts import scene_match


def _a(aid, subject, desc, kws, role="훅"):
    return {"id": aid, "asset_type": "clip", "source_origin": "짜집기", "role": role,
            "subject": subject, "scene_desc": desc, "keywords": kws,
            "media_path": f"/x/{aid}.mp4"}


# 서버 실측 5행(2026-09-08) — 손으로 지어낸 값이 아니다.
LIVE_ASSETS = [
    _a(1, "튀김 요리", "대나무 바구니에 담긴 노란색의 동그란 튀김 요리가 가득 담겨 있다.",
       ["튀김", "대나무 바구니", "요리", "간식", "접사"], role="본문"),
    _a(2, "냉동 삼겹살", "사람의 손이 비닐봉지 안에 든 냉동 삼겹살을 잡고 열어 보여주고 있다.",
       ["냉동고기", "삼겹살", "비닐포장", "손", "식재료"]),
    _a(3, "흰색 수납 가구(서랍장)", "밝은 방 창가 옆에 흰색의 깔끔한 수납 가구가 서 있다.",
       ["수납장", "인테리어", "가구", "창가", "화이트"]),
    _a(4, "분해된 세탁기 내부", "한 사람이 분해된 세탁기의 내부 드럼을 손으로 가리키고 있다.",
       ["세탁기", "가전제품", "분해", "청소", "내부구조"], role="반응"),
    _a(5, "감자튀김", "납작하게 썬 감자튀김이 나무 바구니 안에 가득 담겨 있다.",
       ["감자요리", "튀김", "간식", "바구니", "접사"]),
]


def _plan(*lines):
    return {"beats": [{"beat_idx": i, "role": "hook" if i == 0 else "info",
                       "narration": t} for i, t in enumerate(lines)]}


def test_무관한_대본에는_아무것도_안_붙는다():
    """★옛 사고의 재발 방지 — 캠핑 의자 영상에 감자튀김 컷이 붙으면 안 된다."""
    plan = _plan("캠핑 의자 접었다 폈다 하는 게 이렇게 편할 줄이야",
                 "무게가 가벼워서 한 손으로 든다")
    assert scene_match.narrow(LIVE_ASSETS, plan) == []


def test_맞는_대본에는_맞는_것만_남는다():
    plan = _plan("감자튀김 이렇게 하면 바삭하게 됩니다",
                 "튀김 바구니에 담아 간식으로")
    got = {a["id"] for a in scene_match.narrow(LIVE_ASSETS, plan)}
    assert got == {1, 5}, f"튀김·감자튀김만 남아야 하는데 {got}"


def test_대본이_없으면_붙일_근거도_없다():
    assert scene_match.narrow(LIVE_ASSETS, {"beats": []}) == []
    assert scene_match.narrow(LIVE_ASSETS, {}) == []


def test_한_번_겹치는_것은_통과시키지_않는다():
    """min_hits=2 — 어간 2글자가 우연히 한 번 겹치는 것으로 붙이면 오배치가 는다."""
    plan = _plan("바구니에 빨래를 담았다")        # '바구니'만 겹친다
    assert scene_match.narrow(LIVE_ASSETS, plan) == []


def test_좁히기가_매칭_전체를_막는다():
    """narrow가 0을 돌려주면 소재 패스도 역할 패스도 아무것도 안 붙어야 한다.

    역할 패스(_role_pass)는 Gemini를 안 쓰고 역할표만 보므로, 좁히기가 없으면
    **제품과 무관하게** 붙는다 — 옛 사고의 직접 경로다. 같은 목록을 쓰는지 본다.
    """
    plan = _plan("캠핑 의자가 정말 편하다")
    out = scene_match.match_scene_assets(plan, LIVE_ASSETS,
                                         vault_call=lambda *a, **k: None)
    assert all("cutaway" not in b for b in out["beats"])
