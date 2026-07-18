"""phrase_durs_from_words — 대본↔ASR 정렬로 각 자막 구절의 실제 표시시간."""
import shopping_shorts.caption_sync as cs
from shopping_shorts.video_assemble import _caption_segments


def _w(word, s, e): return {"word": word, "start": s, "end": e}


def test_len_matches_segments_and_sums_total():
    narr = "귤은 손으로 까요 이제 시작합니다"
    words = [_w("귤은", 0.0, 0.4), _w("손으로", 0.4, 0.9), _w("까요", 0.9, 1.4),
             _w("이제", 2.0, 2.3), _w("시작합니다", 2.3, 3.0)]
    durs = cs.phrase_durs_from_words(narr, words, 3.0)
    assert durs is not None
    assert len(durs) == len(_caption_segments(narr))
    assert abs(sum(durs) - 3.0) < 1e-6
    assert all(d >= 0 for d in durs)


def test_caption_follows_voice_not_charcount():
    # 두 구절, 두번째가 글자수는 적지만 실제로는 늦게(2.0초) 시작 → 첫 구절이 길어야.
    # (narr는 _caption_segments가 실제로 2구절로 쪼개는 문장으로 선택:
    #  '이거 때문에 대박'은 3어절/9자 이하라 _CAP_TARGET·_CAP_MAX_WORDS 안에 들어가
    #  1구절로 합쳐져 버려 이 테스트의 전제(두 구절)를 깬다 — 실측 후 교체.)
    narr = "이거 진짜 완전 대박"
    words = [_w("이거", 0.0, 0.3), _w("진짜", 0.3, 0.6), _w("완전", 0.6, 1.0),
             _w("대박", 2.0, 2.5)]
    durs = cs.phrase_durs_from_words(narr, words, 2.5)
    segs = _caption_segments(narr)
    assert len(segs) == 2
    assert len(durs) == len(segs)
    # '대박' 구절은 2.0에 시작 → 그 앞 구절(들)의 합이 2.0에 가깝다.
    assert abs(sum(durs[:-1]) - 2.0) < 0.05


def test_filler_insertion_absorbed():
    # ASR이 앞에 추임새 '와'를 넣어도(대본엔 없음) 정렬이 밀리지 않는다.
    narr = "요새 이거 유행이에요"
    words = [_w("와", 0.0, 0.2), _w("요새", 0.2, 0.6), _w("이거", 0.6, 1.0),
             _w("유행이에요", 1.0, 1.8)]
    durs = cs.phrase_durs_from_words(narr, words, 1.8)
    assert durs is not None and len(durs) == len(_caption_segments(narr))


def test_low_confidence_returns_none():
    # ASR이 완전히 딴 소리 → 매칭률 낮음 → None(호출부가 글자수로 폴백).
    narr = "귤은 손으로 까요"
    words = [_w("사과", 0.0, 0.5), _w("바나나", 0.5, 1.0), _w("포도", 1.0, 1.5)]
    assert cs.phrase_durs_from_words(narr, words, 1.5) is None


def test_empty_words_returns_none():
    assert cs.phrase_durs_from_words("귤은 까요", [], 1.0) is None
