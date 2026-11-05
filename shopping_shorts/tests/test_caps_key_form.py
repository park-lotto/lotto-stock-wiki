"""#4230·#4234(11-04 박영상): 대본 caps 덩어리 key:true(불린)가 배치 emph.word=True 로 넘어가 강조가 한 번도 안 칠해졌다(조용히).
key 꼴 = 그 덩어리 핵심 낱말(글자, briefs/script.md). 주인 = render_bench.caps_of — True = 덩어리 글 전체, 글자 아니면 뺀다."""
from tools.calcopy.hybrid import render_bench as RB


def test_key_true_는_덩어리_글_전체():
    c = RB.caps_of({"kind": "tts", "caps": [{"text": "정말 좋아요", "key": True}, {"text": "그냥", "key": "그냥"}]})
    assert c[0]["key"] == "정말 좋아요" and c[1]["key"] == "그냥"


def test_원음_caps_rel_도_같은_꼴():
    c = RB.caps_of({"kind": "orig", "caps_rel": [["와 대박", 0, 1, True], ["진짜", 1, 2, "진짜"]]})
    assert c[0]["key"] == "와 대박" and c[1]["key"] == "진짜"


def test_글자가_아닌_key_는_뺀다():
    c = RB.caps_of({"kind": "tts", "caps": [{"text": "좋아요", "key": 3}, {"text": "음", "key": False}]})
    assert "key" not in c[0] and "key" not in c[1]
