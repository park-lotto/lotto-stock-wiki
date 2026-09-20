from tg_bot.reply import build, customer_line, table_loaded


def test_app의_변환표를_실제로_불러왔다():
    """★가드. 발췌가 실패하면 전부 폴백 문구가 되어 '조용히 나빠진다'.
    아래 문구 단언들만으로는 그걸 못 잡는다 — 이 테스트가 잡는다.
    (2026-09-02: 정규식이 자기 줄에 걸려 상수가 1글자로 잘린 적이 있다)"""
    assert table_loaded(), "app.py의 _user_facing_error를 못 가져왔다"


def test_실패한_작업은_원인을_먼저_보여준다():
    out = build("j1", {"status": "failed", "error": "gemini 키 소진"})
    assert "【원인】" in out
    assert "gemini 키 소진" in out


def test_고객문구를_함께_준다():
    out = build("j1", {"status": "failed", "error": "gemini 키 소진"})
    assert "【고객께 보낼 문구】" in out


def test_키소진은_app의_변환표와_같은_문구를_쓴다():
    """★app.py의 _user_facing_error를 그대로 부른다 — 베껴 적지 않는다(0순위-B).
    저쪽 표가 늘어나면 여기도 자동으로 따라간다."""
    assert "대본을 만드는 데 실패" in customer_line("gemini 키 소진")


def test_한도초과는_고객잘못이_아니라고_말한다():
    """app.py의 402/insufficient 규칙 — 우리 쪽 문제다."""
    assert "고객님 잘못이 아니" in customer_line("payment required 402")


def test_인스타_다운로드_실패도_변환된다():
    """★계획서에 없던 규칙 — import 방식이라 저절로 따라온다."""
    assert "영상을 가져오지 못했습니다" in customer_line("apify 다운로드 실패")


def test_ffmpeg_오류도_변환된다():
    assert "고객님 잘못이 아니" in customer_line("ffmpeg command '[...]' failed")


def test_모르는_오류는_일반문구로():
    assert customer_line("듣도보도 못한 오류") != ""


def test_성공한_작업은_원인칸이_없다():
    out = build("j1", {"status": "done"})
    assert "【원인】" not in out
    assert "정상" in out


def test_job_id가_제목에_들어간다():
    assert "j1" in build("j1", {"status": "done"})


def test_민감어가_있으면_조치를_권하지_않는다():
    """환불·결제는 잘못 답하면 분쟁이다(bot_qa._SENSITIVE 관례)."""
    out = build("j1", {"status": "failed", "error": "x"}, question="환불해주세요")
    assert "직접 확인" in out


def test_민감어가_없으면_경고가_안_붙는다():
    out = build("j1", {"status": "failed", "error": "x"}, question="영상이 안 돼요")
    assert "직접 확인" not in out
