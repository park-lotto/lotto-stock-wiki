# -*- coding: utf-8 -*-
"""대본 갈래(유형) 판정 — **한 벌만** 둔다(0순위-B). app.py(대본 생성)와 sfx_pack(효과음팩)이 같이 쓴다.

갈래 이름은 스파인의 fit_categories다(categorize.KEYWORDS의 이름과 같아야 한다 — 어긋나면 조용히 죽는다).
"""

# 썰(오용형) — 원래 용도를 뒤집는 이야기
SUL_CATEGORIES = ("오용형",)
# 은폐형(spine "유튜브 「이건 바로 OO」") — 정체를 숨겼다 밝히는 이야기(2026-08-21 썰과 분리)
CONCEAL_CATEGORIES = ("제품정체형",)
# 발명품형(spine "유튜브 「OO 개발자도 무릎 탁」") — 왜 태어났고 뭐가 대단한가(2026-08-20 신설)
INVENTION_CATEGORIES = ("발명품형",)
# 유튜브 썰채널 계열 전체 = 위 세 갈래(효과음팩이 켜지는 대본)
YOUTUBE_SUL_FAMILY = SUL_CATEGORIES + CONCEAL_CATEGORIES + INVENTION_CATEGORIES


def is_context(category, spines, names):
    """이 생성이 `names` 틀인가 — 항목 카테고리와 스파인 fit_categories를 **둘 다** 본다.

    ★2026-08-19 라이브 실측으로 고침(처음엔 위키 항목 category만 봤다 = **영영 안 켜짐**).
      `오용형`·`제품정체형`은 **스파인의 fit_categories**다(id 56·55). 위키 항목의
      category는 홈템·기타·레시피 같은 소재 분류라, 라이브 113건 중 오용형은 **0건**이었다.
      categorize.py는 이 이름을 항목 카테고리로도 쓸 수 있으므로 둘 다 본다.
    """
    if (category or "").strip() in names:
        return True
    for sp in (spines or []):
        if not isinstance(sp, dict):
            continue
        for f in (sp.get("fit_categories") or []):
            if str(f).strip() in names:
                return True
    return False
