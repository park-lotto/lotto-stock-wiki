"""작업파일 스토어 — 제작소 작업을 서버에 남긴다(스펙 §4.1).

사장님 제보: "뒤로가기 하니까 작업물이 지워지는데 ... 내일 다시 들어와도 기록남고
그대로 진행할수있게 해줘야한다."

★mix_jobs를 재활용하지 않는 이유: urls_json·structure가 NOT NULL이라 **매칭 전 작업을
못 담는다**(실측: 서버 job 21건 중 매칭 전 작업은 0건). 억지로 빈 값을 넣으면 "매칭 안 된
job"이라는 유령이 생겨 run_mix_job·pollMix가 실제 job으로 오인한다.
"""
import pytest

from shopping_shorts.store import LEGACY_CUSTOMER_ID, Store


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_upsert_creates_and_returns_work_id(store):
    wid = store.upsert_produce_work(None, {"script": "감자 레시피 대본", "handoff": []})
    assert wid
    got = store.get_produce_work(wid)
    assert got["state"]["script"] == "감자 레시피 대본"
    assert got["step"] == 0
    assert got["job_id"] is None


def test_upsert_same_id_updates_not_duplicates(store):
    wid = store.upsert_produce_work(None, {"script": "처음"})
    same = store.upsert_produce_work(wid, {"script": "고침"}, step=2)
    assert same == wid
    assert store.get_produce_work(wid)["state"]["script"] == "고침"
    assert store.get_produce_work(wid)["step"] == 2
    assert len(store.list_produce_works()) == 1


def test_title_comes_from_script_head(store):
    wid = store.upsert_produce_work(None, {"script": "가" * 50})
    # 목록에 뜨는 이름은 서버가 대본 앞머리에서 뽑는다 — 클라이언트가 보내면 어긋난다(스펙 §4.6)
    assert store.get_produce_work(wid)["title"] == "가" * 20


def test_title_empty_script_does_not_crash(store):
    wid = store.upsert_produce_work(None, {"handoff": [{"url": "https://x/1"}]})
    assert store.get_produce_work(wid)["title"] == ""


def test_job_id_is_a_bridge_not_required(store):
    wid = store.upsert_produce_work(None, {"script": "대본"}, job_id="job-9", step=1)
    got = store.get_produce_work(wid)
    assert got["job_id"] == "job-9"
    assert got["step"] == 1


def test_list_is_recent_first_and_capped(store):
    ids = [store.upsert_produce_work(None, {"script": f"s{i}"}) for i in range(25)]
    # 같은 초에 만들어져도 순서가 서야 한다 — updated_at만으로는 동률이 생긴다
    for i in ids[-3:]:
        store.upsert_produce_work(i, {"script": "touch"})
    rows = store.list_produce_works(limit=20)
    assert len(rows) == 20
    assert rows[0]["work_id"] in ids[-3:]
    assert "state" not in rows[0]   # 목록은 가볍게 — state_json은 안 싣는다


def test_get_missing_returns_none(store):
    assert store.get_produce_work("없는id") is None


def test_delete_removes_it(store):
    wid = store.upsert_produce_work(None, {"script": "지울것"})
    assert store.delete_produce_work(wid) is True
    assert store.get_produce_work(wid) is None
    assert store.delete_produce_work(wid) is False


def test_customer_isolation(store):
    a = store.upsert_produce_work(None, {"script": "고객0"}, customer_id=LEGACY_CUSTOMER_ID)
    store.upsert_produce_work(None, {"script": "고객7"}, customer_id=7)
    rows = store.list_produce_works(customer_id=LEGACY_CUSTOMER_ID)
    assert [r["work_id"] for r in rows] == [a]


def test_migration_on_existing_db(tmp_path):
    """기존 DB(테이블 없음)에 새로 붙어도 생긴다 — 서버 DB는 이미 job 21건이 들어있다."""
    p = tmp_path / "old.db"
    Store(p)                      # 1차: 스키마 생성
    s2 = Store(p)                 # 2차: 같은 DB 재오픈 — CREATE IF NOT EXISTS라 안 깨져야
    wid = s2.upsert_produce_work(None, {"script": "재오픈"})
    assert s2.get_produce_work(wid)["state"]["script"] == "재오픈"


def test_does_not_touch_mix_jobs(store):
    """작업 저장이 job 파이프라인을 오염시키지 않는다(스펙 §6)."""
    store.upsert_produce_work(None, {"script": "대본"}, job_id="job-1")
    with store._conn() as c:
        assert c.execute("SELECT COUNT(*) FROM mix_jobs").fetchone()[0] == 0


def test_partial_update_preserves_job_and_step(store):
    """★안 보낸 필드는 건드리지 않는다. 예전엔 파이썬 기본값이 UPDATE에 그대로 박혀
    job_id·step이 조용히 초기화됐다 — 작업 유실을 막으려는 기능이 유실을 만들던 자리."""
    wid = store.upsert_produce_work(None, {"script": "s"}, job_id="job-123", step=3)
    store.upsert_produce_work(wid, {"script": "s edited"})   # job_id·step 재전송 안 함
    got = store.get_produce_work(wid)
    assert got["job_id"] == "job-123", "부분 저장이 job_id를 지웠다"
    assert got["step"] == 3, "부분 저장이 step을 되감았다"
    assert got["state"]["script"] == "s edited"


def test_explicit_none_clears_job(store):
    """명시적 None은 진짜로 지운다 — 재매칭으로 job이 무효가 되면 끊어야 한다."""
    wid = store.upsert_produce_work(None, {"script": "s"}, job_id="job-123", step=3)
    store.upsert_produce_work(wid, {"script": "s"}, job_id=None)
    assert store.get_produce_work(wid)["job_id"] is None
    assert store.get_produce_work(wid)["step"] == 3   # step은 안 건드렸으니 그대로


def test_explicit_zero_step_really_rewinds(store):
    """★step=0을 **명시적으로** 넘기면 진짜 0이 된다 — 센티널과 falsy 0을 헷갈리면 안 된다.

    test_explicit_none_clears_job의 step쪽 대칭. 이게 없으면 `if step is not _UNSET`을
    `if step is not _UNSET and step`으로 '단순화'해도 스위트가 통째로 통과한다
    (재리뷰가 뮤테이션으로 실증: 그 뮤턴트가 14건을 다 뚫었다).
    실제로 필요한 순간: 복원이 게이트에 막혀 1단계로 되돌려질 때 step 0을 써야 한다."""
    wid = store.upsert_produce_work(None, {"script": "s"}, job_id="job-9", step=3)
    store.upsert_produce_work(wid, {"script": "s"}, step=0)
    got = store.get_produce_work(wid)
    assert got["step"] == 0, "명시적 step=0이 무시됐다 — 센티널이 falsy 0을 미지정으로 오인한다"
    assert got["job_id"] == "job-9"   # job_id는 안 보냈으니 그대로


def test_unknown_work_id_is_revived_not_dropped(store):
    """서버 DB가 갈아엎였는데 브라우저가 옛 work_id를 들고 있으면 그 id로 되살린다.
    조용히 버리면 사장님 작업이 사라진다."""
    same = store.upsert_produce_work("옛날id", {"script": "되살아남"})
    assert same == "옛날id"
    assert store.get_produce_work("옛날id")["state"]["script"] == "되살아남"


def test_upsert_does_not_overwrite_someone_elses_work(store):
    """★남의 work_id를 알아도 덮어쓸 수 없다. get/delete는 막는데 upsert만 뚫려 있었다
    (T2 재리뷰). 소유는 그대로인데 내용만 남의 것이 되던 자리."""
    wid = store.upsert_produce_work(None, {"script": "고객1의 대본"},
                                    job_id="job-1", step=3, customer_id=1)
    assert store.upsert_produce_work(wid, {"script": "고객2가 덮어씀"},
                                     job_id="job-EVIL", step=99, customer_id=2) is None
    got = store.get_produce_work(wid, customer_id=1)
    assert got["state"]["script"] == "고객1의 대본", "남이 내용을 덮어썼다"
    assert got["job_id"] == "job-1" and got["step"] == 3
