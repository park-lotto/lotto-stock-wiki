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


def test_앞_글이_이미지여도_쿠팡링크가_접힌다():
    # 결함1 회귀 방지: prev media_kind=="video" 고정 조건이면 이미지 본문은 영영 못 접힌다.
    body = _p("A", "이거 실화냐", media="image")
    tail = _p("B", "link.coupang.com/a/img1", media="")
    out = merge_thread_tail([body, tail])
    assert len(out) == 1
    assert out[0]["coupang_url"] == "https://link.coupang.com/a/img1"


def test_3연속이면_중간_글_tail이_덮어써지지_않는다():
    # 결함2 회귀 방지: A(영상)+B(링크,접힘)+C(같은 사람, 영상 없음).
    # C가 out[-1]인 A에 다시 접히면 B가 채운 tail_caption이 사라진다.
    a = _p("A", "본문", media="video")
    b = _p("B", "link.coupang.com/a/bbb", media="")
    c = _p("C", "완전히 다른 이야기")
    out = merge_thread_tail([a, b, c])
    assert len(out) == 2
    assert out[0]["code"] == "A"
    assert "bbb" in out[0]["coupang_url"]
    assert out[0]["tail_caption"] == b["caption"]
    assert out[1]["code"] == "C"


def test_앞_글이_텍스트뿐이면_접히지_않는다():
    # 의도된 동작: 미디어 없는 본문은 재료로 안 쓰므로 접지 않는다.
    body = _p("A", "그냥 텍스트 본문", media="")
    tail = _p("B", "link.coupang.com/a/txt", media="")
    out = merge_thread_tail([body, tail])
    assert len(out) == 2
