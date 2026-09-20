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


def test_개수가_다르면_역할로_짝짓는다():
    """개수가 다르면 자리를 믿을 수 없다 — 그때는 역할 이름으로만 짝짓는다.
    (비트 1개 vs 출처 2개: 자리로 이으면 엉뚱한 칸에 붙는다)"""
    srcs = [{"role": "cta", "seg": "A-2"}, {"role": "cta", "seg": "A-3"}]
    out = S._apply_beat_sources(_beats(), {"beat_sources": srcs}, _seg_map())
    assert out[0]["primary"]["seg_id"] == "A-0", "역할이 다른데 붙었다"


# ─────────────────────────────────────────────────────────────────────────
# 순서 폴백(2026-08-31) — 역할 이름이 두 단계에서 갈려 출처가 버려지던 것.
#
# 실측(라이브 44잡·출처 329건): 역할 이름 일치로 붙는 건 **23%뿐**이었다.
#   2단계가 쓰는 말: hook, escalation, reveal, result, origin, spread…
#   3단계가 쓰는 말: hook, problem, solution, benefit, demonstration…
# 우연히 같은 hook·cta만 통과하고 가운데는 전부 버려진다. 심하면 한쪽이 영어,
# 한쪽이 한글이라 0건인 잡도 있었다(40개 중 5개).
#
# ★역할 매칭을 없애지 않는다 — 비트 수가 다를 때 엉뚱한 칸에 붙는 걸 막는 장치다.
#   **비트 수가 같을 때만** 순서로 잇는다(실측 80%가 여기 해당). 그래야
#   i번째 문장 = i번째 출처가 보장된다.
# ─────────────────────────────────────────────────────────────────────────

def _beats3():
    """역할 이름이 3단계 어휘로 붙은 비트 3개."""
    out = []
    for i, role in enumerate(("hook", "problem", "solution")):
        sid = "A-%d" % i
        out.append({"role": role, "narration": "문장%d" % i, "target_seconds": 3.0,
                    "beat_idx": i,
                    "primary": {"seg_id": sid, "video_id": "A",
                                "start": i * 3.0, "end": i * 3.0 + 3.0},
                    "alternates": []})
    return out


def test_역할이름이_갈려도_비트수가_같으면_순서로_잇는다():
    """2단계 어휘(escalation·reveal)와 3단계 어휘(problem·solution)가 달라도
    비트 수가 같으면 i번째끼리 짝지어 출처를 살린다."""
    srcs = [{"role": "hook", "seg": "A-3"},
            {"role": "escalation", "seg": "A-2"},
            {"role": "reveal", "seg": "A-1"}]
    out = S._apply_beat_sources(_beats3(), {"beat_sources": srcs}, _seg_map())
    assert [b["primary"]["seg_id"] for b in out] == ["A-3", "A-2", "A-1"]
    assert [b.get("src_seg_applied") for b in out] == ["A-3", "A-2", "A-1"]


def test_비트수가_다르면_순서로_잇지_않는다():
    """개수가 다르면 i번째끼리 짝지을 근거가 없다 — 역할 매칭만 쓴다(엉뚱한 칸 방어)."""
    srcs = [{"role": "escalation", "seg": "A-3"},
            {"role": "reveal", "seg": "A-2"}]          # 2개 vs 비트 3개
    out = S._apply_beat_sources(_beats3(), {"beat_sources": srcs}, _seg_map())
    assert [b["primary"]["seg_id"] for b in out] == ["A-0", "A-1", "A-2"], "개수가 다른데 순서로 붙었다"


def test_개수가_같으면_이름이_겹쳐도_자리를_따른다():
    """★이름이 겹쳐도 **자리**가 이긴다 — 이름은 두 단계가 따로 지어 믿을 수 없다.

    실측 근거(라이브 80잡): 개수가 같은 37잡 중 **33잡은 역할결과 == 자리결과**라
    자리로 이어도 손해가 없다. 나머지 4잡은 역할 매칭이 **틀린** 쪽이었다 —
    job 36a02e5a에서 2단계 proof는 3번 칸, 3단계 proof는 5번 칸이라 이름으로 이으면
    다른 문장의 장면을 끌어온다. 순서가 곧 같은 문장이므로 자리가 정답이다.
    """
    srcs = [{"role": "solution", "seg": "A-3"},
            {"role": "hook", "seg": "A-2"},
            {"role": "problem", "seg": "A-1"}]         # 이름은 뒤섞여 있다
    out = S._apply_beat_sources(_beats3(), {"beat_sources": srcs}, _seg_map())
    assert [b["primary"]["seg_id"] for b in out] == ["A-3", "A-2", "A-1"]


def test_순서폴백도_지어낸_번호는_무시한다():
    srcs = [{"role": "x", "seg": "없는-99"},
            {"role": "y", "seg": "A-2"},
            {"role": "z", "seg": "A-1"}]
    out = S._apply_beat_sources(_beats3(), {"beat_sources": srcs}, _seg_map())
    assert out[0]["primary"]["seg_id"] == "A-0", "지어낸 번호가 붙었다"
    assert [b["primary"]["seg_id"] for b in out[1:]] == ["A-2", "A-1"]


def test_순서폴백은_토글로_끌_수_있다(monkeypatch):
    """켠 것/끈 것을 대조해 효과를 재고, 나빠지면 즉시 되돌린다."""
    monkeypatch.setenv("BEAT_SRC_ORDER", "off")
    srcs = [{"role": "escalation", "seg": "A-3"},
            {"role": "reveal", "seg": "A-2"},
            {"role": "origin", "seg": "A-1"}]
    out = S._apply_beat_sources(_beats3(), {"beat_sources": srcs}, _seg_map())
    assert [b["primary"]["seg_id"] for b in out] == ["A-0", "A-1", "A-2"], "껐는데 붙었다"
