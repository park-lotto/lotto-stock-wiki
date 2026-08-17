from shopping_shorts.threads_parse import merge_thread_tail


def _p(code, caption, username="u", media="video", posted="2026-08-17T05:00:00+00:00"):
    return {"code": code, "username": username, "caption": caption,
            "media_kind": media, "posted_at": posted}


def test_뒤_글의_쿠팡링크가_앞_글로_접힌다():
    body = _p("A", "나 지금까지 헛고생함", posted="2026-08-17T05:00:00+00:00")
    tail = _p("B", "🔽 링크 link.coupang.com/a/fYY", media="",
              posted="2026-08-17T05:01:00+00:00")
    out = merge_thread_tail([body, tail])
    assert len(out) == 1
    assert out[0]["code"] == "A"
    assert out[0]["coupang_url"] == "https://link.coupang.com/a/fYY"
    assert "링크" in out[0]["tail_caption"]


def test_다른_사람_글은_안_접는다():
    body = _p("A", "본문", username="u1")
    tail = _p("B", "link.coupang.com/a/x", username="u2", media="")
    out = merge_thread_tail([body, tail])
    assert len(out) == 2


def test_영상이_있는_글끼리는_안_접는다():
    # 둘 다 독립된 재료다. 접으면 하나를 잃는다.
    out = merge_thread_tail([_p("A", "본문1"), _p("B", "본문2")])
    assert len(out) == 2


def test_쿠팡링크가_없으면_필드가_빈다():
    out = merge_thread_tail([_p("A", "본문")])
    assert out[0]["coupang_url"] == ""
    assert out[0]["tail_caption"] == ""
