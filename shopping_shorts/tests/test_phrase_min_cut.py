# -*- coding: utf-8 -*-
"""구절 맞춤 컷 하한(phrase_min_cut, 2026-09-26 사장님 "자막 경계가 우선, 컷이 너무 짧으면 그 컷 뒤에까지").

자막 구절 경계는 그대로 두고 **화면 컷만** 하한 이상으로 묶는다. 표식이 없으면 종전과 같다(옛 job 회귀 0)."""
from shopping_shorts import video_assemble as va
from shopping_shorts import mix_pipeline as mp


def test_묶음은_하한을_넘길때만_새로_연다_꼬리는_붙인다():
    # 0.5 0.6 0.7 | 1.2 0.4 | 0.9 → 1.5초 하한: [0,0,0, 1,1, 2]? 꼬리 0.9는 1.5에 못 미쳐 앞에 붙는다
    assert va.phrase_cut_groups([0.5, 0.6, 0.7, 1.2, 0.4, 0.9], 1.5) == [0, 0, 0, 1, 1, 1]
    assert va.phrase_cut_groups([2.0, 2.0, 2.0], 1.5) == [0, 1, 2], "충분히 긴 구절은 그대로 1:1"
    assert va.phrase_cut_groups([0.5, 0.6, 0.7], 1.5) == [0, 0, 0], "다 합쳐도 짧으면 한 컷"
    assert va.phrase_cut_groups([0.5, 0.6, 0.7], 0) == [0, 1, 2], "하한 0 = 종전(구절=컷)"
    assert va.phrase_cut_groups([], 1.5) == []


def _beat(min_cut=None):
    b = {"narration": "여러분 오이 절대 냉장고에 그냥 두지 마세요 버리기 일쑤였는데 이 방법은 진짜",
         "caption_lines": ["여러분", "오이 절대", "냉장고에", "그냥 두지 마세요", "버리기 일쑤였는데", "이 방법은 진짜"]}
    if min_cut:
        b["phrase_min_cut"] = min_cut
    return b


def test_표식없으면_종전_그대로():
    durs = [0.4, 0.6, 0.5, 1.0, 1.1, 0.9]
    assert va.phrase_owners(_beat(), 6, durs=durs) == [0, 1, 2, 3, 4, 5]
    assert va.phrase_owners(_beat(), 3, durs=durs) == [0, 0, 1, 1, 2, 2]


def test_표식있으면_묶음단위로_담은_순서대로():
    durs = [0.4, 0.6, 0.5, 1.0, 1.1, 0.9]      # 묶음: [0.4+0.6+0.5=1.5] [1.0+1.1=2.1] [0.9→꼬리, 앞에 붙음]
    assert va.phrase_cut_groups(durs, 1.5) == [0, 0, 0, 1, 1, 1]
    # 조각 6개여도 컷은 2개 — 1번·2번 조각을 건너뛰지 않고 **담은 순서대로** 0, 1을 쓴다
    assert va.phrase_owners(_beat(1.5), 6, durs=durs) == [0, 0, 0, 1, 1, 1]
    assert va.phrase_owners(_beat(1.5), 3, durs=durs) == [0, 0, 0, 1, 1, 1]
    # durs를 안 주는 호출부(서명·대사 수정)는 종전 식 — 표식이 있어도 안 바뀐다
    assert va.phrase_owners(_beat(1.5), 3) == [0, 0, 1, 1, 2, 2]


def test_얼린짝이_있으면_묶음의_첫구절_짝을_따른다():
    b = _beat(1.5)
    b["phrase_sync"] = True
    b["primary"] = {"video_id": "v0", "start": 0.0, "end": 3.0}
    b["alternates"] = [{"video_id": "v1", "start": 0.0, "end": 3.0}, {"video_id": "v2", "start": 0.0, "end": 3.0}]
    va.ensure_clip_anchor(b, owners=[0, 0, 1, 1, 2, 2])
    assert b.get("clip_anchor"), "짝이 얼려져야 R2 경로를 탄다"
    durs = [0.4, 0.6, 0.5, 1.0, 1.1, 0.9]
    # 묶음 [0,1,2][3,4,5] → 첫 구절 짝 0, 3번 구절 짝 1 → 조각 2는 '안 나옴'(얼린 짝 존중)
    assert va.phrase_owners(b, 3, durs=durs) == [0, 0, 0, 1, 1, 1]
    # 하한 없이는 얼린 짝 그대로
    b.pop("phrase_min_cut")
    assert va.phrase_owners(b, 3, durs=durs) == [0, 0, 1, 1, 2, 2]


class _S:
    def __init__(self, v): self.v = v
    def get_setting(self, k, d=""): return self.v if k == "phrase_min_cut" else d


def test_설정_규약():
    assert mp._phrase_min_cut(_S(""), {"customer_id": 0}) == 0.0
    assert mp._phrase_min_cut(_S("1.5"), {"customer_id": 77}) == 1.5
    assert mp._phrase_min_cut(_S("admin"), {"customer_id": 0}) == 1.5
    assert mp._phrase_min_cut(_S("admin"), {"customer_id": 77}) == 0.0
    assert mp._phrase_min_cut(_S("admin:1.2"), {"customer_id": 0}) == 1.2
    assert mp._phrase_min_cut(_S("11,42:1.2"), {"customer_id": 42}) == 1.2
    assert mp._phrase_min_cut(_S("11,42:1.2"), {"customer_id": 43}) == 0.0


def test_표식은_한번만_달고_안_덮는다():
    plan = {"beats": [{"beat_idx": 0}, {"beat_idx": 1, "phrase_min_cut": 1.2}]}
    assert mp._apply_phrase_min_cut(plan, _S("admin:1.5"), {"customer_id": 0}) == 1
    assert [b["phrase_min_cut"] for b in plan["beats"]] == [1.5, 1.2]
    plan2 = {"beats": [{"beat_idx": 0}]}
    assert mp._apply_phrase_min_cut(plan2, _S("admin:1.5"), {"customer_id": 77}) == 0
    assert "phrase_min_cut" not in plan2["beats"][0]


def test_렌더가_묶음대로_컷을_낸다():
    # 실제 클립 계획: 표식 없으면 구절 6 → 컷 6, 표식 1.5면 조각이 이어 덮어 화면 전환 2번
    segs = [{"video_id": "v%d" % i, "start": 0.0, "end": 10.0} for i in range(6)]
    src = {"v%d" % i: 30.0 for i in range(6)}
    b0, b1 = _beat(), _beat(1.5)
    tts = 4.5
    c0 = va.plan_beat_clips_for(b0, tts, src, segs) if False else None
    p0 = va._plan_phrase_clips(b0, segs, tts, src) or []
    p1 = va._plan_phrase_clips(b1, segs, tts, src) or []
    assert len(p0) == 6 and len({c["video_id"] for c in p0}) == 6
    assert len(p1) == 6, "자막 구절은 그대로 6개"
    ids = [c["video_id"] for c in p1]
    changes = sum(1 for a, b in zip(ids, ids[1:]) if a != b)
    assert changes <= 2 and ids[0] == "v0", ids
    assert abs(sum(c["out_dur"] for c in p1) - tts) < 0.05
