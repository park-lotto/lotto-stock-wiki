"""1기 챌린지 — 저장소."""
import pytest

from shopping_shorts.store import Store


@pytest.fixture()
def st(tmp_path):
    return Store(str(tmp_path / "t.db"))


def test_add_and_list_members(st):
    st.add_challenge_member(11, cohort="1기")
    st.add_challenge_member(22, cohort="1기")
    ms = st.list_challenge_members()
    assert [m["customer_id"] for m in ms] == [11, 22]
    assert ms[0]["cohort"] == "1기"
    assert ms[0]["active"] == 1


def test_add_member_twice_is_idempotent(st):
    st.add_challenge_member(11)
    st.add_challenge_member(11)
    assert len(st.list_challenge_members()) == 1


def test_is_challenge_member(st):
    st.add_challenge_member(11)
    assert st.is_challenge_member(11) is True
    assert st.is_challenge_member(99) is False


def test_deactivate_member_hides_from_active_list(st):
    st.add_challenge_member(11)
    st.set_challenge_member_active(11, False)
    assert st.is_challenge_member(11) is False
    assert st.list_challenge_members(active_only=False)[0]["active"] == 0
    assert st.list_challenge_members() == []


def test_reactivate_member(st):
    """해제했다가 다시 등록하면 살아난다(행을 새로 만들지 않는다)."""
    st.add_challenge_member(11)
    st.set_challenge_member_active(11, False)
    st.add_challenge_member(11)
    assert st.is_challenge_member(11) is True
    assert len(st.list_challenge_members(active_only=False)) == 1


def test_add_submission_returns_id_and_lists(st):
    sid = st.add_challenge_submission(
        customer_id=11, url="https://youtu.be/abc", platform="youtube",
        shortcode="abc", dedup_key="sc:abc", submit_day="2026-08-24")
    assert sid > 0
    rows = st.list_challenge_submissions(customer_id=11)
    assert len(rows) == 1
    assert rows[0]["url"] == "https://youtu.be/abc"
    assert rows[0]["submit_day"] == "2026-08-24"
    assert rows[0]["fetch_status"] == "pending"


def test_duplicate_dedup_key_rejected_for_same_member(st):
    st.add_challenge_submission(11, "https://youtu.be/abc", "youtube",
                                "abc", "sc:abc", "2026-08-24")
    dup = st.add_challenge_submission(11, "https://youtube.com/shorts/abc", "youtube",
                                      "abc", "sc:abc", "2026-08-25")
    assert dup == 0          # 0 = 중복이라 저장 안 함
    assert len(st.list_challenge_submissions(customer_id=11)) == 1


def test_same_video_allowed_for_different_members(st):
    """다른 사람이 같은 영상을 낸 것은 별개다(중복 판정은 사람 단위)."""
    assert st.add_challenge_submission(11, "https://youtu.be/abc", "youtube",
                                       "abc", "sc:abc", "2026-08-24") > 0
    assert st.add_challenge_submission(22, "https://youtu.be/abc", "youtube",
                                       "abc", "sc:abc", "2026-08-24") > 0


def test_update_submission_meta_marks_ok(st):
    sid = st.add_challenge_submission(11, "https://youtu.be/abc", "youtube",
                                      "abc", "sc:abc", "2026-08-24")
    st.update_challenge_submission_meta(
        sid, title="제목", thumb="https://x/t.jpg", channel="채널",
        views=1234, likes=10, comments=3, fetch_status="ok")
    row = st.list_challenge_submissions(customer_id=11)[0]
    assert row["title"] == "제목"
    assert row["views"] == 1234
    assert row["fetch_status"] == "ok"


def test_update_meta_leaves_unspecified_fields_alone(st):
    """None인 것은 안 건드린다 — 한쪽만 고칠 때 다른 쪽을 지우면 안 된다."""
    sid = st.add_challenge_submission(11, "https://youtu.be/abc", "youtube",
                                      "abc", "sc:abc", "2026-08-24")
    st.update_challenge_submission_meta(sid, title="제목", views=100, fetch_status="ok")
    st.update_challenge_submission_meta(sid, views=200)
    row = st.list_challenge_submissions(customer_id=11)[0]
    assert row["views"] == 200
    assert row["title"] == "제목"          # 안 지워졌다
    assert row["fetch_status"] == "ok"     # 안 지워졌다


def test_failed_fetch_keeps_the_row(st):
    """★수집이 실패해도 제출 자체는 살아 있어야 한다 — 카운트가 새면 안 된다."""
    sid = st.add_challenge_submission(11, "https://vt.tiktok.com/x", "tiktok",
                                      "", "url:vt.tiktok.com/x", "2026-08-24")
    st.update_challenge_submission_meta(sid, fetch_status="failed")
    rows = st.list_challenge_submissions(customer_id=11)
    assert len(rows) == 1
    assert rows[0]["fetch_status"] == "failed"


def test_list_all_submissions_across_members(st):
    st.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-24")
    st.add_challenge_submission(22, "https://youtu.be/b", "youtube", "b", "sc:b", "2026-08-24")
    assert len(st.list_challenge_submissions()) == 2


def test_list_submissions_filtered_by_day_range(st):
    st.add_challenge_submission(11, "https://youtu.be/a", "youtube", "a", "sc:a", "2026-08-20")
    st.add_challenge_submission(11, "https://youtu.be/b", "youtube", "b", "sc:b", "2026-08-24")
    st.add_challenge_submission(11, "https://youtu.be/c", "youtube", "c", "sc:c", "2026-08-30")
    got = st.list_challenge_submissions(start="2026-08-22", end="2026-08-26")
    assert [r["shortcode"] for r in got] == ["b"]
