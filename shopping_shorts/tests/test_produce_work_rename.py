"""작업 이름 바꾸기(2026-08-17) — 사장님 "내 작업에 작업명 수정할수있게".

목록이 '(제목 없음)' 여러 줄이라 어느 게 뭔지 구분이 안 됐다. 자동 제목은 대본 앞 20자인데
대본을 아직 안 뽑은 작업엔 재료가 없기 때문이다(실측: 서버 최근 5건 중 4건이 script 0자).

★이 파일이 지키는 핵심 규칙 — **직접 지은 이름은 대본을 고쳐도 안 지워진다**(사장님 결정).
  자동 제목이 사용자 지정 이름을 덮으면 "이름을 바꿨는데 되돌아간다"가 된다.
  제목 판정은 store._work_title **한 곳**에만 있다(CLAUDE.md 0순위-B: 같은 판단을 두 번
  적으면 반드시 어긋난다) — API도 클라이언트도 제목을 계산하지 않는다.
"""
import pytest

from shopping_shorts.store import WORK_TITLE_MAX, Store, _work_title


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


# ── 제목 판정(단일 출처) ────────────────────────────────────────────
def test_auto_title_is_script_head_when_no_manual_name():
    """종전 동작 회귀 — 이름을 안 지었으면 대본 앞 20자 그대로."""
    src = "아침마다 밀가루 빵 먹는다고 엄마한테 혼났는데"
    assert _work_title({"script": src}) == src[:20]


def test_manual_name_wins_over_script():
    assert _work_title({"script": "대본 내용", "title_manual": "요거트케이크 A안"}) == "요거트케이크 A안"


def test_blank_manual_name_falls_back_to_script():
    """공백뿐인 이름은 '안 지은 것'으로 본다 — 목록에 빈 줄이 뜨면 안 된다."""
    assert _work_title({"script": "대본 내용", "title_manual": "   "}) == "대본 내용"


def test_manual_name_is_capped():
    assert len(_work_title({"title_manual": "가" * 100})) == WORK_TITLE_MAX


def test_non_dict_state_does_not_raise():
    """★값의 모양을 확인하고 부른다 — 이 앱은 dict/str 혼동으로 500을 세 번 냈다
    (handoff/장면라벨.md). 모르는 모양이 와도 죽지 않고 빈 제목."""
    assert _work_title(None) == ""
    assert _work_title("문자열") == ""


# ── 이름 바꾸기 ────────────────────────────────────────────────────
def test_rename_changes_title_and_returns_it(store):
    wid = store.upsert_produce_work(None, {"script": "감자 레시피 대본"})
    assert store.rename_produce_work(wid, "감자 A안") == "감자 A안"
    assert store.get_produce_work(wid)["title"] == "감자 A안"


def test_renamed_title_survives_script_edit(store):
    """★이 테스트가 이 기능의 존재 이유다.

    title 컬럼만 고치고 state를 안 고치면, 다음 저장(upsert_produce_work)이 state를 보고
    제목을 다시 계산해 **되돌아간다**. 그래서 rename은 state_json까지 함께 고친다.
    """
    wid = store.upsert_produce_work(None, {"script": "처음 대본"})
    store.rename_produce_work(wid, "내가 지은 이름")

    state = store.get_produce_work(wid)["state"]
    state["script"] = "완전히 다른 대본으로 갈아엎었다"
    store.upsert_produce_work(wid, state)

    got = store.get_produce_work(wid)
    assert got["title"] == "내가 지은 이름"          # 이름은 지켜지고
    assert got["state"]["script"] == "완전히 다른 대본으로 갈아엎었다"   # 대본은 실제로 바뀐다


def test_empty_name_restores_auto_title(store):
    """이름을 지우면 자동 제목으로 되돌아간다 — 별도 '해제' API를 만들지 않은 이유."""
    wid = store.upsert_produce_work(None, {"script": "감자 레시피 대본"})
    store.rename_produce_work(wid, "감자 A안")
    assert store.rename_produce_work(wid, "") == "감자 레시피 대본"
    assert "title_manual" not in store.get_produce_work(wid)["state"]


def test_rename_shows_in_list(store):
    """목록은 title 컬럼을 읽는다(state_json을 안 싣는다) — 컬럼도 같이 갱신돼야 보인다."""
    wid = store.upsert_produce_work(None, {"script": "감자"})
    store.rename_produce_work(wid, "최종본")
    assert store.list_produce_works()[0]["title"] == "최종본"


def test_rename_preserves_other_state(store):
    """state를 통째로 갈아끼우지 않는다 — 담은 영상·job 연결이 날아가면 안 된다."""
    wid = store.upsert_produce_work(
        None, {"script": "대본", "handoff": [{"url": "u1"}]}, job_id="job1", step=3)
    store.rename_produce_work(wid, "이름")
    got = store.get_produce_work(wid)
    assert got["state"]["handoff"] == [{"url": "u1"}]
    assert got["job_id"] == "job1" and got["step"] == 3


# ── 소유권(다른 고객의 작업을 건드리지 않는다) ──────────────────────
def test_rename_rejects_other_customers_work(store):
    """get/delete와 같은 결 — 예외를 던지지 않고 None을 준다(API가 404로 바꾼다)."""
    wid = store.upsert_produce_work(None, {"script": "내 대본"}, customer_id=7)
    assert store.rename_produce_work(wid, "해킹", customer_id=999) is None
    assert store.get_produce_work(wid, customer_id=7)["title"] == "내 대본"


def test_rename_missing_work_returns_none(store):
    assert store.rename_produce_work("없는id", "이름") is None
