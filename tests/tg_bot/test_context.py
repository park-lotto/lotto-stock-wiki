from tg_bot.context import extract


def test_produce_url에서_job을_뽑는다():
    t = "영상이 안 만들어져요 https://shoppingshorts.duckdns.org/produce?job=abc123"
    assert extract(t)["job_id"] == "abc123"


def test_job_id_파라미터_이름도_받는다():
    t = "https://shoppingshorts.duckdns.org/produce?job_id=xyz789&step=3"
    assert extract(t)["job_id"] == "xyz789"


def test_주소가_없으면_job은_None():
    assert extract("그냥 안 돼요")["job_id"] is None


def test_주소_자체도_보관한다():
    t = "여기요 https://example.com/a?b=1 확인해주세요"
    assert extract(t)["urls"] == ["https://example.com/a?b=1"]


def test_주소가_없으면_빈_목록():
    assert extract("안녕하세요")["urls"] == []


def test_원문은_그대로_남는다():
    assert extract("  안 돼요  ")["text"] == "안 돼요"


def test_None을_넣어도_죽지_않는다():
    r = extract(None)
    assert r["job_id"] is None and r["urls"] == [] and r["text"] == ""
