"""Layer 2(프레임 대조 스팟체크) — 모델도 ffmpeg도 안 부른다.

지키는 계약 셋:
  ①대표 세그를 '아픈 순서'로 고른다(훅 → is_key → 완성/after), 중복 없이.
  ②판정과 묘사의 **짝이 절대 밀리지 않는다** — 밀리면 엉뚱한 화면을 채점한 셈이 된다.
  ③측정 실패는 None이다. **0.0으로 적지 않는다** — 0.0은 '화면이 전부 틀렸다'는 강한
    신호라, 실패를 0으로 기록하면 나중에 '태깅이 나빠졌다'는 거짓 결론이 나온다.
"""
from shopping_shorts import tag_qa_frames as F


def _seg(i, start=None, end=None, **kw):
    s = {"seg_id": f"s{i}", "start": i * 2.0 if start is None else start,
         "end": i * 2.0 + 2.0 if end is None else end,
         "scene_desc": f"장면 {i}", "shot_role": "사용중", "is_key": False}
    s.update(kw)
    return s


# ── ① 대표 세그 고르기 ────────────────────────────────────────────

def test_훅_실증_결과_순서로_고른다():
    segs = [_seg(0), _seg(1), _seg(2, is_key=True), _seg(3, shot_role="완성")]
    assert [i for i, _ in F.pick_segments(segs)] == [0, 2, 3]


def test_같은_세그가_두_조건에_걸려도_한_번만():
    """첫 세그가 is_key이기도 하면 중복 판정에 돈을 쓰면 안 된다.

    ★반환은 인덱스 오름차순이 아니라 **우선순위 순서**(훅→실증→결과)다. 여기서 정렬을
    요구했다가 테스트가 먼저 깨졌다 — 프레임 추출·판정이 같은 순서로 짝지어 돌기만 하면
    되므로 정렬은 계약이 아니다. 계약은 '중복 없음'이다."""
    segs = [_seg(0, is_key=True), _seg(1), _seg(2, shot_role="after")]
    picked = [i for i, _ in F.pick_segments(segs)]
    assert len(picked) == len(set(picked)) and 0 in picked and 2 in picked


def test_조건이_없으면_남은_세그로_채운다():
    """표본이 1개면 점수가 요동친다 — 조건에 안 맞아도 3개까지 채운다."""
    assert len(F.pick_segments([_seg(i) for i in range(5)])) == 3


def test_너무_짧은_세그는_안_고른다():
    """중간시각 프레임이 전환 순간에 걸려 엉뚱한 화면이 나온다."""
    picked = F.pick_segments([_seg(0, start=0.0, end=0.1), _seg(1), _seg(2)])
    assert all(s["seg_id"] != "s0" for _, s in picked)


def test_시간이_깨진_세그는_안_고른다():
    picked = F.pick_segments([_seg(0, start=None, end=None) | {"start": "?"}, _seg(1)])
    assert [i for i, _ in picked] == [1]


def test_세그가_없으면_빈_목록():
    assert F.pick_segments([]) == [] and F.pick_segments(None) == []


# ── ② 채점 ───────────────────────────────────────────────────────

def test_점수는_맞음1_부분05_틀림0의_평균():
    picked = [(0, _seg(0)), (1, _seg(1)), (2, _seg(2))]
    verdicts = [{"verdict": "맞음"}, {"verdict": "부분"}, {"verdict": "틀림"}]
    score, detail = F.score_verdicts(verdicts, picked)
    assert score == 0.5 and len(detail) == 3


def test_판정이_모자라면_겹치는_만큼만_센다():
    """없는 판정을 '맞음'으로 채우면 점수가 조용히 부풀어 기준선이 거짓이 된다."""
    picked = [(0, _seg(0)), (1, _seg(1)), (2, _seg(2))]
    score, detail = F.score_verdicts([{"verdict": "틀림"}], picked)
    assert score == 0.0 and len(detail) == 1      # 3장 중 1장만 판정 → 그 1장만


def test_이상한_verdict_값은_버린다():
    picked = [(0, _seg(0)), (1, _seg(1))]
    score, detail = F.score_verdicts([{"verdict": "글쎄"}, {"verdict": "맞음"}], picked)
    assert score == 1.0 and len(detail) == 1


def test_셀_수_있는_판정이_없으면_None():
    assert F.score_verdicts([], [(0, _seg(0))]) == (None, [])


def test_상세에_세그_인덱스가_남는다():
    """어느 장면이 틀렸는지 못 짚으면 추적에 못 쓴다."""
    _, detail = F.score_verdicts([{"verdict": "틀림", "reason": "배경 소품"}], [(7, _seg(7))])
    assert detail[0]["seg_index"] == 7 and "배경" in detail[0]["reason"]


# ── ③ spot_check 배선 (주입으로 모델·ffmpeg 대체) ──────────────────

def _frames_ok(video_path, picked, dest_dir):
    return [f"/tmp/{i}.jpg" for i, _ in picked], picked


def test_정상경로는_점수와_건수를_돌려준다():
    out = F.spot_check({"segments": [_seg(i) for i in range(3)]}, "/v.mp4", "/tmp",
                       _frames_fn=_frames_ok,
                       _judge_fn=lambda p, k: [{"verdict": "맞음"}] * len(k))
    assert out["frame_score"] == 1.0 and out["checked"] == 3


def test_프레임을_한_장도_못_뽑으면_None():
    out = F.spot_check({"segments": [_seg(0)]}, "/v.mp4", "/tmp",
                       _frames_fn=lambda *a: ([], []),
                       _judge_fn=lambda p, k: [{"verdict": "맞음"}])
    assert out is None                      # 0.0이 아니다


def test_모델이_실패하면_None():
    out = F.spot_check({"segments": [_seg(i) for i in range(3)]}, "/v.mp4", "/tmp",
                       _frames_fn=_frames_ok, _judge_fn=lambda p, k: [])
    assert out is None                      # 0.0이 아니다


def test_프레임이_일부만_뽑히면_그_세그만_채점한다():
    """★짝 밀림 방지의 핵심: 2번 프레임이 실패했는데 판정 3개를 그대로 zip하면
    3번 판정이 2번 묘사에 붙어 엉뚱한 장면을 채점하게 된다."""
    def half(video_path, picked, dest_dir):
        kept = picked[:1]
        return [f"/tmp/{i}.jpg" for i, _ in kept], kept
    out = F.spot_check({"segments": [_seg(i) for i in range(3)]}, "/v.mp4", "/tmp",
                       _frames_fn=half,
                       _judge_fn=lambda p, k: [{"verdict": "틀림"}] * len(k))
    assert out["checked"] == 1 and out["frame_score"] == 0.0


def test_세그가_없으면_모델을_아예_안_부른다():
    called = []
    out = F.spot_check({"segments": []}, "/v.mp4", "/tmp",
                       _frames_fn=_frames_ok,
                       _judge_fn=lambda p, k: called.append(1) or [])
    assert out is None and not called       # 빈 추출에 돈 쓰지 않는다
