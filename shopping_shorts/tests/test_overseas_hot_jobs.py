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
    monkeypatch.setattr(job, "load_seeds", lambda: {"뷰티": {"subreddits": ["beauty"], "seed_accounts": []}})
    monkeypatch.setattr(job, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(job, "_now", lambda: now)

    job._run()
    from shopping_shorts.store import Store
    items, _ = Store(str(tmp_path / "t.db")).load_overseas_feed()
    assert items, "피드에 항목이 저장돼야 한다"
    assert all("grade" in it and "category" in it for it in items)
    assert items[0]["category"] == "뷰티"


def test_start_is_idempotent_while_running(monkeypatch):
    monkeypatch.setattr(job, "_run", lambda: __import__("time").sleep(0.2))
    job._JOB.update(status="idle", started=0.0)
    r1 = job.start()
    r2 = job.start()
    assert r1["status"] == "running" and r2["status"] == "running"
