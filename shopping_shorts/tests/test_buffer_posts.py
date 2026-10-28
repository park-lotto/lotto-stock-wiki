"""Buffer 예약 장부 — 중복 방지·취소 (2026-10-04 관제 114).

★왜 생겼나: 고객 340 유튜브·인스타에 같은 영상이 2개씩 올라갔다. Buffer 실측으로
  job c2e762780e08 이 5분 간격으로 같은 채널에 두 번 예약된 것을 확인했다 — 서버는
  예약을 적어 두지 않아 막을 근거도, 취소할 게시물 id도 없었다.
"""
import asyncio
import types

import pytest

from shopping_shorts import app as appmod
from shopping_shorts import buffer_api, buffer_posts


class FakeBuffer:
    """Buffer 대역. 게시물을 dict로 들고 createPost·post·deletePost만 흉내 낸다."""

    def __init__(self):
        self.posts = {}          # id → status
        self.created = 0
        self.down = False        # True면 조회가 네트워크 오류

    def schedule_video(self, key, channel_id, text, video_url, due_at=None, thumb_ms=0,
                       share_now=False, privacy=""):
        self.created += 1
        pid = f"p{self.created}"
        self.posts[pid] = "sent" if share_now else "scheduled"
        return {"id": pid, "dueAt": due_at or ""}

    def post_status(self, key, post_id):
        if self.down:
            raise buffer_api.BufferError("Buffer에 연결하지 못했습니다.")
        if post_id not in self.posts:
            raise buffer_api.BufferNotFound("없음")
        return {"id": post_id, "status": self.posts[post_id], "dueAt": "", "sentAt": "", "link": ""}

    def delete_post(self, key, post_id):
        if post_id not in self.posts:
            raise buffer_api.BufferNotFound("없음")
        del self.posts[post_id]


@pytest.fixture
def fb(monkeypatch):
    f = FakeBuffer()
    for n in ("schedule_video", "post_status", "delete_post"):
        monkeypatch.setattr(buffer_api, n, getattr(f, n))
    return f


def _db(tmp_path):
    return str(tmp_path / "t.db")


def test_recorded_channel_is_duplicate(tmp_path, fb):
    db = _db(tmp_path)
    fb.posts["a1"] = "scheduled"
    buffer_posts.record(db, 340, "job1", "yt", "a1", "2026-10-03T22:30:00Z")
    d = buffer_posts.already_scheduled(db, "k", 340, "job1", ["yt", "ig"])
    assert list(d) == ["yt"]                       # 인스타는 아직 안 걸었다
    assert buffer_posts.already_scheduled(db, "k", 340, "job2", ["yt"]) == {}   # 다른 영상
    assert buffer_posts.already_scheduled(db, "k", 999, "job1", ["yt"]) == {}   # 남의 예약


def test_sent_post_is_still_duplicate(tmp_path, fb):
    """이미 올라간 것도 중복이다 — 고객 사고는 '예약 1 + 즉시 게시 1'로도 났다."""
    db = _db(tmp_path)
    fb.posts["a1"] = "sent"
    buffer_posts.record(db, 340, "job1", "ig", "a1", share_now=True)
    assert "ig" in buffer_posts.already_scheduled(db, "k", 340, "job1", ["ig"])


def test_deleted_in_buffer_is_not_duplicate(tmp_path, fb):
    """고객이 Buffer에서 직접 지운 예약은 더는 막지 않는다."""
    db = _db(tmp_path)
    buffer_posts.record(db, 340, "job1", "yt", "gone1")       # Buffer에는 없다
    assert buffer_posts.already_scheduled(db, "k", 340, "job1", ["yt"]) == {}
    assert buffer_posts.sync(db, "k", 340, "job1") == []


def test_lookup_failure_keeps_record(tmp_path, fb):
    """못 물어본 것을 '지워졌다'로 적으면 살아 있는 예약이 중복 검사에서 빠진다."""
    db = _db(tmp_path)
    fb.posts["a1"] = "scheduled"
    buffer_posts.record(db, 340, "job1", "yt", "a1")
    fb.down = True
    assert "yt" in buffer_posts.already_scheduled(db, "k", 340, "job1", ["yt"])
    fb.down = False
    assert "yt" in buffer_posts.already_scheduled(db, "k", 340, "job1", ["yt"])


def test_cancel_deletes_scheduled_post(tmp_path, fb):
    db = _db(tmp_path)
    fb.posts["a1"] = "scheduled"
    buffer_posts.record(db, 340, "job1", "yt", "a1")
    buffer_posts.cancel(db, "k", 340, "a1")
    assert "a1" not in fb.posts                               # Buffer에서 사라졌다
    assert buffer_posts.sync(db, "k", 340, "job1") == []


def test_cancel_refuses_sent_post(tmp_path, fb):
    """올라간 글은 Buffer에서 지워도 SNS에 남는다 — '취소됐다'고 말하면 거짓이다."""
    db = _db(tmp_path)
    fb.posts["a1"] = "sent"
    buffer_posts.record(db, 340, "job1", "yt", "a1")
    with pytest.raises(buffer_posts.CancelError):
        buffer_posts.cancel(db, "k", 340, "a1")
    assert "a1" in fb.posts
    assert buffer_posts.sync(db, "k", 340, "job1")[0]["cancellable"] is False


def test_cancel_refuses_other_customers_post(tmp_path, fb):
    db = _db(tmp_path)
    fb.posts["a1"] = "scheduled"
    buffer_posts.record(db, 340, "job1", "yt", "a1")
    with pytest.raises(buffer_posts.CancelError):
        buffer_posts.cancel(db, "k", 85, "a1")
    assert "a1" in fb.posts


def test_facebook_gets_reel_type(monkeypatch):
    """페이스북은 type이 없으면 거절된다(라이브 실측 2026-10-03)."""
    monkeypatch.setattr(buffer_api, "_service_of", lambda key, cid: "facebook")
    assert buffer_api._post_metadata("k", "c") == {"facebook": {"type": "reel"}}


# ── 예약 요청 끝단: 두 번 눌러도 Buffer 게시물이 늘지 않는다 ─────────────────────────
def _schedule(tmp_path, monkeypatch, body, cust=340):
    monkeypatch.setattr(appmod, "DB_PATH", _db(tmp_path))
    monkeypatch.setattr(appmod, "_share_put", lambda job_id, ttl: "sid")
    monkeypatch.setattr(appmod.mix_pipeline, "ensure_faststart", lambda p: None)
    req = types.SimpleNamespace(state=types.SimpleNamespace(customer_id=cust),
                                base_url="http://x/")
    job = {"video_path": "v.mp4", "customer_id": cust}
    return asyncio.run(appmod._buffer_schedule_locked(
        req, body, "k", job, "job1", list(body["channel_ids"]), {}, "글",
        body.get("due_at"), 0, bool(body.get("share_now")), ""))


def test_second_schedule_does_not_create_posts(tmp_path, monkeypatch, fb):
    body = {"channel_ids": ["yt", "ig"], "due_at": "2026-10-03T22:30:00Z"}
    r1 = _schedule(tmp_path, monkeypatch, body)
    assert [x["ok"] for x in r1["results"]] == [True, True] and fb.created == 2
    r2 = _schedule(tmp_path, monkeypatch, body)               # 5분 뒤 같은 요청
    assert fb.created == 2                                    # ★Buffer 게시물이 늘지 않았다
    assert all(x.get("dup") for x in r2["results"])


def test_retry_after_partial_failure_only_fills_the_gap(tmp_path, monkeypatch, fb):
    """한 채널만 실패해 다시 눌렀을 때, 이미 성공한 채널이 또 올라가면 안 된다."""
    real = fb.schedule_video
    tries = []

    def flaky(key, channel_id, *a, **k):
        if channel_id == "fbk":
            tries.append(1)
            if len(tries) == 1:                               # 첫 번째만 거절
                raise buffer_api.BufferError("거절")
        return real(key, channel_id, *a, **k)
    monkeypatch.setattr(buffer_api, "schedule_video", flaky)
    body = {"channel_ids": ["yt", "ig", "fbk"]}
    r1 = _schedule(tmp_path, monkeypatch, body)
    assert [x["ok"] for x in r1["results"]] == [True, True, False]
    r2 = _schedule(tmp_path, monkeypatch, body)
    assert fb.created == 3                                    # 페이스북 하나만 새로
    assert sorted(x["channel_id"] for x in r2["results"] if x.get("dup")) == ["ig", "yt"]


def test_force_schedules_again(tmp_path, monkeypatch, fb):
    """고객이 '그래도 한 번 더'를 고르면 올린다 — 막는 게 아니라 묻는 것이다."""
    body = {"channel_ids": ["yt"]}
    _schedule(tmp_path, monkeypatch, body)
    _schedule(tmp_path, monkeypatch, dict(body, force=True))
    assert fb.created == 2
