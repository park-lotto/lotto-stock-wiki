# -*- coding: utf-8 -*-
"""기간·역대 탭에도 강도 지표를 채운다(2026-08-17 실사고).

증상은 "이번 주 터진 것을 누른 뒤 명예의전당을 눌러도 안 넘어간다 / 지표·카테고리도
안 먹는다"였고 버퍼 문제처럼 보였다. 실제 원인은 브라우저 콘솔에 딱 한 줄:
    TypeError: Cannot read properties of undefined (reading 'toFixed')
        at render (index.html:1509) ← i.speed.toFixed(1)
기간(hits_since)·역대(archive_hits) 항목은 build_items를 안 거쳐 speed가 없는데
화면이 무조건 불러, **첫 카드에서 render가 죽고 화면이 이전 상태로 얼어붙었다.**
"""
from shopping_shorts.ranking import fill_intensity


def test_지표가_없으면_채워준다():
    it = {"comments": 100, "views": 1000, "followers": 500, "upload_ts": "2026-08-16T00:00:00+00:00"}
    fill_intensity([it])
    assert it["density"] == 0.1            # 댓글/조회수
    assert it["fan_density"] == 0.2        # 댓글/팔로워
    assert isinstance(it["speed"], float)  # 댓글/경과시간


def test_발행시각이_깨져도_예외가_안_난다():
    """아카이브 20만 건엔 시각이 비거나 모양이 깨진 것이 섞여 있다.

    여기서 터지면 또 화면 전체가 죽는다 — 결측 하나가 페이지를 멈추면 안 된다.
    """
    for bad in ("", "몰라", None, "2026-13-99"):
        it = {"comments": 7, "views": 0, "upload_ts": bad}
        fill_intensity([it])
        assert it["age_hours"] == 0
        assert it["speed"] == 7.0          # 경과시간 모르면 댓글 수 그대로


def test_이미_있는_값은_안_건드린다():
    """수집 경로가 계산한 값이 늘 우선 — 여기서 덮으면 두 값이 갈린다(0순위-B)."""
    it = {"comments": 100, "views": 1000, "speed": 3.3, "density": 0.9, "fan_density": 0.5}
    fill_intensity([it])
    assert (it["speed"], it["density"], it["fan_density"]) == (3.3, 0.9, 0.5)


def test_조회수_0이면_0으로_나눗셈_안_한다():
    it = {"comments": 5, "views": 0, "followers": 0}
    fill_intensity([it])
    assert it["density"] == 0.0 and it["fan_density"] == 0.0


def test_화면이_쓰는_키가_전부_채워진다():
    """render가 참조하는 키에 None이 남으면 또 toFixed에서 죽는다."""
    it = {"comments": 1}
    fill_intensity([it])
    for k in ("speed", "density", "fan_density", "delta", "accel", "views", "likes", "followers"):
        assert it[k] is not None, k


def test_썸네일_이름을_화면_기준으로_맞춘다():
    """화면은 i.thumbnail을 읽는데 기간·역대는 thumb으로 준다 → 카드가 전부 검게 빈다."""
    it = {"comments": 1, "thumb": "https://x/y.jpg"}
    fill_intensity([it])
    assert it["thumbnail"] == "https://x/y.jpg"


def test_이미_thumbnail이_있으면_안_덮는다():
    it = {"comments": 1, "thumbnail": "원본", "thumb": "다른것"}
    fill_intensity([it])
    assert it["thumbnail"] == "원본"
