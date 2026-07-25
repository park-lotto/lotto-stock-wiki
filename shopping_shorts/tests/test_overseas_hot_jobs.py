import shopping_shorts.overseas_hot_jobs as job
from datetime import datetime, timezone


def test_run_collects_ranks_and_saves(monkeypatch, tmp_path):
    now = datetime(2026, 7, 25, 12, 0, tzinfo=timezone.utc)
    published = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_fetch(subreddit, category="", sort="rising", **kw):
        return [{"source": "reddit", "post_id": subreddit + sort, "shortcode": subreddit + sort,
                 "subreddit": subreddit, "title": "t", "permalink": "https://p",
                 "media_url": "https://m", "media_platform": "tiktok", "thumbnail": "",
                 "ups": 500, "num_comments": 10, "published_at": published, "category": category}]

    monkeypatch.setattr(job.reddit_source, "fetch_subreddit", fake_fetch)
    monkeypatch.setattr(job.gap_check, "gap_badge", lambda title, **kw: "🔥선점가능")
    monkeypatch.setattr(job, "load_seeds", lambda: {"뷰티": {"subreddits": ["beauty"], "seed_accounts": []}})
    monkeypatch.setattr(job, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(job, "_now", lambda: now)

    job._run()
    from shopping_shorts.store import Store
    items, _ = Store(str(tmp_path / "t.db")).load_overseas_feed()
    assert items, "피드에 항목이 저장돼야 한다"
    assert all("grade" in it and "category" in it for it in items)
    assert items[0]["category"] == "뷰티"
    assert items[0]["gap_badge"] == "🔥선점가능"   # 선점뱃지 부여됨


def test_start_is_idempotent_while_running(monkeypatch):
    monkeypatch.setattr(job, "_run", lambda: __import__("time").sleep(0.2))
    job._JOB.update(status="idle", started=0.0)
    r1 = job.start()
    r2 = job.start()
    assert r1["status"] == "running" and r2["status"] == "running"


def test_merge_rotate_dedupes_new_by_shortcode():
    # 같은 서브레딧이 여러 카테고리에 겹치면 같은 포스트가 중복 수집된다 →
    # shortcode당 score 최고 1개만 남아야 한다(UI·cap·스냅샷 중복 방지).
    new = [
        {"shortcode": "dup", "category": "살림/생활꿀템", "score": 0.2},
        {"shortcode": "dup", "category": "가전템", "score": 0.9},
        {"shortcode": "solo", "category": "뷰티", "score": 0.5},
    ]
    out = job._merge_rotate([], new, cap=120)
    ids = [i["shortcode"] for i in out]
    assert ids.count("dup") == 1 and "solo" in ids
    dup = next(i for i in out if i["shortcode"] == "dup")
    assert dup["score"] == 0.9   # score 최고가 남음
