# -*- coding: utf-8 -*-
"""대본 스타일 추천 순서 — 근거 없는 틀이 위로 오면 안 된다 (2026-08-24).

사장님 제보: "ai추천도 너무 이상하게 추천을한다 / 안맞게"

라이브 실측으로 원인이 나왔다: 스타일 스파인 11개의 `perf_score`가 **전부 0.0**이라
`ORDER BY perf_score DESC, id DESC`의 첫 키가 죽고 사실상 **id DESC**(최근 등록순)로
돌았다. 그래서 히트작 근거가 **0편**인 무지후회형(62)·정체의문형(61)이 1·2위로 추천되고,
23편(발명품형)·12편(단정 명령형)짜리가 아래에 깔렸다 — 순서가 정확히 거꾸로였다.
"""
from shopping_shorts.store import style_spine_rank

# 2026-08-24 라이브 실측값(서버 reference.db)
LIVE = [
    {"id": 62, "name": "무지후회형", "perf_score": 0.0, "source_count": 0},
    {"id": 61, "name": "정체의문형", "perf_score": 0.0, "source_count": 0},
    {"id": 60, "name": "유튜브 발명품형", "perf_score": 0.0, "source_count": 23},
    {"id": 56, "name": "유튜브 오용형", "perf_score": 0.0, "source_count": 4},
    {"id": 53, "name": "단정 명령형", "perf_score": 0.0, "source_count": 12},
]


def test_근거가_많은_틀이_먼저_추천된다():
    """★perf_score가 전부 0이어도 히트작 근거(source_count)로 갈린다."""
    ranked = sorted(LIVE, key=style_spine_rank)
    assert [s["name"] for s in ranked[:2]] == ["유튜브 발명품형", "단정 명령형"]
    # auto_style이 집는 상위 2개에 근거 0편짜리가 끼면 안 된다
    assert all(s["source_count"] > 0 for s in ranked[:2])


def test_근거_0편은_뒤로_밀린다():
    ranked = sorted(LIVE, key=style_spine_rank)
    tail = [s["name"] for s in ranked[-2:]]
    assert set(tail) == {"무지후회형", "정체의문형"}


def test_perf_score가_살아나면_그게_우선이다():
    """성과 되먹임이 채워지면 근거 편수보다 그쪽을 먼저 본다(지금은 전부 0이라 안 쓰인다)."""
    rows = [dict(s) for s in LIVE]
    for s in rows:
        if s["id"] == 62:          # 근거 0편이지만 실제 성과가 좋다면
            s["perf_score"] = 9.9
    assert sorted(rows, key=style_spine_rank)[0]["name"] == "무지후회형"


def test_동점이면_순서가_재현된다():
    """같은 입력에 같은 순서 — 추천이 새로고침마다 흔들리면 안 된다."""
    same = [{"id": i, "name": "s%d" % i, "perf_score": 0.0, "source_count": 0}
            for i in (1, 2, 3)]
    once = [s["name"] for s in sorted(same, key=style_spine_rank)]
    twice = [s["name"] for s in sorted(list(reversed(same)), key=style_spine_rank)]
    assert once == twice == ["s3", "s2", "s1"]


def test_값이_비어도_죽지_않는다():
    """perf_score·source_count가 None이어도 정렬이 터지면 안 된다(옛 행)."""
    rows = [{"id": 1, "name": "a", "perf_score": None, "source_count": None},
            {"id": 2, "name": "b", "perf_score": 0.0, "source_count": 5}]
    assert [s["name"] for s in sorted(rows, key=style_spine_rank)] == ["b", "a"]
