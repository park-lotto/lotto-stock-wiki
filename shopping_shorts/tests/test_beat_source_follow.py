"""대본 문장의 '출처 장면'을 따라간다(2026-08-18).

사장님: "다른 영상들의 대본을 참고하면 좋은 게, 그 대본에 장면을 사용하면 좋다."

2단계가 문장마다 src_seg(어느 대목을 보고 썼는지)를 남기고, 3단계가 그 장면을 1순위로
붙인다. 지금까지는 그 연결이 끊겨 있어 3단계가 처음부터 다시 짐작했다.
★배선 위치는 저장 출구 — 계획을 만드는 경로가 여럿이라 만드는 쪽마다 적으면
  반드시 한 곳이 빠진다(오늘만 다섯 번 반복됐다).
"""
from shopping_shorts import store as S


def _seg_map():
    m = {}
    for i in range(4):
        sid = "A-%d" % i
        m[sid] = {"seg_id": sid, "video_id": "A", "start": i * 3.0, "end": i * 3.0 + 3.0,
                  "scene_desc": "장면 %d" % i, "text": "말 %d" % i}
    return m


def _beats():
    return [{"role": "hook", "narration": "훅", "target_seconds": 3.0,
             "primary": {"seg_id": "A-0", "video_id": "A", "start": 0.0, "end": 3.0},
             "alternates": []}]


def test_출처_장면을_1순위로_쓴다():
    out = S._apply_beat_sources(_beats(), {"beat_sources": [{"role": "hook", "seg": "A-2"}]}, _seg_map())
    assert out[0]["primary"]["seg_id"] == "A-2"
    assert out[0].get("src_seg_applied") == "A-2"


def test_원래_화면은_버리지_않는다():
    """재고를 버리면 화면 채우기가 손해를 본다 — 대안으로 살려 둔다."""
    out = S._apply_beat_sources(_beats(), {"beat_sources": [{"role": "hook", "seg": "A-2"}]}, _seg_map())
    assert any(a.get("seg_id") == "A-0" for a in out[0]["alternates"])


def test_지어낸_번호는_무시한다():
    """모델이 없는 번호를 적을 수 있다 — 실재하는 것만 쓴다(환각 방어)."""
    out = S._apply_beat_sources(_beats(), {"beat_sources": [{"role": "hook", "seg": "없는-99"}]}, _seg_map())
    assert out[0]["primary"]["seg_id"] == "A-0"


def test_출처가_없으면_아무것도_안_한다():
    """옛 대본·무자막 소스는 src_seg가 없다 — 종전 그대로 = 회귀 0."""
    b = _beats()
    assert S._apply_beat_sources(b, {}, _seg_map()) is b
    assert S._apply_beat_sources(b, {"beat_sources": []}, _seg_map()) is b


def test_역할로_짝짓는다():
    """순서만 믿으면 비트 수가 다를 때 엉뚱한 칸에 붙는다."""
    out = S._apply_beat_sources(_beats(), {"beat_sources": [{"role": "cta", "seg": "A-2"}]}, _seg_map())
    assert out[0]["primary"]["seg_id"] == "A-0", "역할이 다른데 붙었다"
