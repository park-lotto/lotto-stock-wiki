"""last_run 저장 상한과 **자르는 기준** — 조회수 기준으로 자른다(2026-08-30 사장님 지시).

배경: 유튜브 last_run이 상한 8,000에 정확히 걸려 있었고, 자를 때 최신순으로만 잘라
신설 축(오용형 67·차량템 68·장비템 106)이 부스러기만 남았다.
사장님 지시: "상한올려 / 자를땐 조회수기준 안나온것들로".

★자르기 기준을 조회수로 바꿀 때 반드시 지켜야 하는 것(실측 2026-08-30):
  나이대별 조회수 중앙값이 0-1일 1,420 vs 5-10일 4,775 — **갓 올라온 영상은 구조적으로
  조회수가 낮다**. 순수 조회수순으로 자르면 오늘 올라온 영상이 조회수를 벌기도 전에
  잘려나가, 랭킹이 옛날 영상만 남는 박제가 된다.
  → 신선분(NEW_GRACE_HOURS 이내)은 조회수와 무관하게 보호한다.
"""
from shopping_shorts.store import Store


def _it(sc, views, age):
    return {"shortcode": sc, "views": views, "age_hours": age}


def test_cap_raised_above_8000():
    """상한을 올렸다 — 8,000에 딱 걸려 신설 축이 잘려나가던 자리."""
    assert Store.LAST_RUN_MAX_ITEMS > 8000


def test_trim_keeps_high_views_drops_low():
    """자르는 기준은 조회수 — '안 나온 것들'(조회수 낮은 것)이 잘린다."""
    items = [_it(f"s{i}", views=i, age=500) for i in range(100)]
    kept = Store._trim_for_store(items, cap=10)
    got = {i["shortcode"] for i in kept}
    assert got == {f"s{i}" for i in range(90, 100)}, "조회수 상위 10개만 남아야 한다"


def test_trim_protects_fresh_regardless_of_views():
    """★갓 올라온 영상은 조회수가 낮아도 안 자른다(조회수를 벌 시간이 없었다)."""
    old_hits = [_it(f"old{i}", views=1_000_000, age=200) for i in range(10)]
    fresh_low = [_it("fresh", views=3, age=1)]
    kept = Store._trim_for_store(old_hits + fresh_low, cap=10)
    assert "fresh" in {i["shortcode"] for i in kept}, "신선분은 조회수 무관 보호"


def test_trim_no_duplicates():
    """보호분과 조회수 상위가 겹쳐도 중복으로 담기지 않는다."""
    items = [_it("a", 100, 1), _it("b", 50, 500), _it("c", 10, 2)]
    kept = Store._trim_for_store(items, cap=3)
    codes = [i["shortcode"] for i in kept]
    assert len(codes) == len(set(codes))


def test_trim_under_cap_keeps_everything():
    """상한 미만이면 아무것도 안 버린다."""
    items = [_it(f"s{i}", views=i, age=500) for i in range(5)]
    assert len(Store._trim_for_store(items, cap=100)) == 5


def test_trim_handles_missing_views_and_age():
    """views/age_hours가 없어도 죽지 않는다(실측 8,000건 중 4건이 views 없음)."""
    items = [_it("a", 100, 10), {"shortcode": "b"}, {"shortcode": "c", "views": None}]
    kept = Store._trim_for_store(items, cap=2)
    assert len(kept) == 2
    assert "a" in {i["shortcode"] for i in kept}, "값 있는 히트가 우선"


def test_save_last_run_platform_applies_views_trim(tmp_path):
    """저장 경로가 실제로 이 기준을 쓴다(유튜브가 타는 길)."""
    st = Store(str(tmp_path / "t.db"))
    cap = Store.LAST_RUN_MAX_ITEMS
    items = ([_it(f"hit{i}", views=9_000_000, age=300) for i in range(cap)]
             + [_it("loser", views=1, age=300)])
    st.save_last_run_platform("youtube", items, "2026-08-30T00:00:00+00:00")
    got, _ = st.load_last_run_platform("youtube")
    assert len(got) == cap
    assert "loser" not in {i["shortcode"] for i in got}, "조회수 최하위가 잘려야 한다"


# ── 조회수가 없는 플랫폼(쓰레드·핀터레스트) 안전장치 ──────────────────
# 실측(2026-08-30 라이브): views 보유 = 유튜브 7,993/8,000 · 인스타 145/145 ·
#   **쓰레드 0/229 · 핀터레스트 0/2,259**. 핀터레스트는 merge로 계속 쌓여
#   언젠가 상한에 닿는데, views가 전부 0이면 조회수 정렬은 **동률**이라
#   순서가 사실상 임의가 된다 → 그때는 최신순(옛 규칙)으로 자르는 게 맞다.

def test_trim_falls_back_to_newest_when_no_views():
    """views가 아무에게도 없으면 최신순으로 자른다(쓰레드·핀터레스트).

    ★목록을 **섞어서** 넣는다 — 정렬된 채로 넣으면 파이썬 sort가 안정정렬이라
      아무것도 안 해도 통과해 버려서, 실제 버그를 못 잡는다(2026-08-30 실제로
      이 테스트가 통과하는데 코드는 t7·t8 같은 옛 항목을 남기고 있었다)."""
    import random
    items = [{"shortcode": f"s{i}", "age_hours": float(i)} for i in range(100)]
    random.Random(0).shuffle(items)
    kept = Store._trim_for_store(items, cap=10)
    got = {i["shortcode"] for i in kept}
    assert got == {f"s{i}" for i in range(10)}, "가장 최신 10건이 남아야 한다"


def test_trim_without_views_or_age_keeps_order():
    """views·age_hours 둘 다 없으면(핀터레스트) 원래 순서 앞쪽을 남긴다 — 임의로 섞지 않는다."""
    items = [{"shortcode": f"s{i}"} for i in range(100)]
    kept = Store._trim_for_store(items, cap=10)
    assert [i["shortcode"] for i in kept] == [f"s{i}" for i in range(10)]
