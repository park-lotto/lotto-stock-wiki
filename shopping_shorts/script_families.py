# -*- coding: utf-8 -*-
"""대본 갈래(스파인 fit_categories) 판정 — 여러 모듈이 같이 쓰는 한 곳(0순위-B).

INSTA_CATEGORIES는 원래 app.py에만 있었다. 장면꾸미기(scene_style)·렌더(mix_pipeline)도
'인스타 대본인가'를 알아야 해서 여기로 옮겼다 — app.py는 이 값을 가져다 쓴다.
"""

# ★인스타 조립 경로를 켜는 '기계용 이름'들(설명은 app.py의 옛 자리 주석 참조).
INSTA_CATEGORIES = ("다이소형", "금지경고형", "사회증거형",
                    "지인증언형", "권유지시형", "물건발견형", "정체의문형", "무지후회형",
                    # ★나열형(2026-08-21) — 한 제품을 파는 게 아니라 여러 제품을 훑는다.
                    "나열형")


def first_line_is_title(store, job):
    """대본 첫 줄이 '제목'인가. 인스타 대본은 첫 줄부터 말하는 대본이라 False(2026-09-25 사장님
    "인스타틀은 처음 장면부터 대본이 나와야"). 썰 대본(첫 줄=제목 문장)·갈래를 모르는 대본은 True(종전 그대로)."""
    from .sfx_pack import script_family
    try:
        fam = script_family(store, job)
    except Exception:      # noqa: BLE001 — 판정 실패는 종전 동작
        return True
    return not any(c in INSTA_CATEGORIES for c in fam)


def mark_plan(store, job, plan):
    """plan 사본에 title_line 표식을 붙여 돌려준다 — _beat_timeline이 타임라인으로 넘기고
    scene_style.context_for가 읽는다. 원본 plan(DB 값)은 건드리지 않는다."""
    return {**(plan or {}), "title_line": first_line_is_title(store, job)}
