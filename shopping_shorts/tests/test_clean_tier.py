"""자막제거 등급(기본/Smart Pro) — 2026-09-16.

지키려는 것 셋:
  ① 기본은 **옛 작업과 서명이 같다** — 등급 기능이 생겼다고 기존 청소본이 무효가 되면
     멀쩡한 작업이 전부 재청소되어 돈이 나간다.
  ② 고급은 **다른 파일**이다 — 안 갈리면 기본으로 만든 결과를 고급인 줄 알고 재사용한다.
  ③ 초당 과금 안전판 — 상한보다 길면 **보내기 전에** 막는다.
"""
import pytest

from shopping_shorts import mix_pipeline as mp
from shopping_shorts import vmake_client as vc


def _plan():
    return {"beats": [{"primary": {"video_id": "s1", "start": 1, "end": 5},
                       "target_seconds": 3}]}


class TestTier:
    def test_기본은_옛_편성서명_그대로(self):
        plan = _plan()
        assert mp._clean_sig({"edit_plan": plan}) == mp._plan_signature(plan)

    def test_등급이_다르면_청소본_파일이_갈린다(self):
        plan = _plan()
        basic = mp._clean_sig({"edit_plan": plan})
        pro = mp._clean_sig({"edit_plan": plan, "clean_tier": "pro"})
        assert basic != pro, "고급인데 기본 청소본을 재사용하면 돈만 내고 결과가 그대로다"

    def test_모르는_값은_기본으로_떨어진다(self):
        assert mp.clean_tier_of({}) == vc.TIER_BASIC
        assert mp.clean_tier_of({"clean_tier": "ultra"}) == vc.TIER_BASIC
        assert mp.clean_tier_of({"clean_tier": "pro"}) == vc.TIER_PRO

    def test_편성이_바뀌면_등급과_무관하게_갈린다(self):
        a = mp._clean_sig({"edit_plan": _plan(), "clean_tier": "pro"})
        other = _plan()
        other["beats"][0]["primary"]["end"] = 9
        b = mp._clean_sig({"edit_plan": other, "clean_tier": "pro"})
        assert a != b


class TestLegacyKey:
    def test_60007만_legacy로_본다(self):
        assert vc.is_legacy_key("[60007] only supports the legacy Skill")
        assert not vc.is_legacy_key("connection reset by peer")

    def test_소진판정과_섞이지_않는다(self):
        """넓게 잡으면 잔액 소진을 '옛날 키'로 오해해 엉뚱한 안내가 나간다."""
        no_credit = "[60002] You don't have enough credits for this API."
        assert vc.is_no_credit(no_credit)
        assert not vc.is_legacy_key(no_credit)


class TestLengthGuard:
    def test_상한보다_길면_보내기_전에_막는다(self, monkeypatch):
        monkeypatch.setattr(mp, "_probe_seconds", lambda p: 200.0)
        sent = []
        monkeypatch.setattr(mp, "remove_subtitles",
                            lambda *a, **k: sent.append(a) or "x.mp4")
        with pytest.raises(RuntimeError) as e:
            mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4")
        assert "너무 깁니다" in str(e.value)
        assert not sent, "상한을 넘겼는데 VMake로 나갔다 — 초당 과금이라 돈이 그대로 나간다"

    def test_길이를_못_재면_막지_않는다(self, monkeypatch):
        """가드는 아는 것만 막는다 — 못 쟀다고 멈추면 멀쩡한 작업이 통째로 선다."""
        monkeypatch.setattr(mp, "_probe_seconds", lambda p: None)
        monkeypatch.setattr(mp, "remove_subtitles", lambda *a, **k: "out.mp4")
        assert mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4") == "out.mp4"

    def test_등급이_그대로_전달된다(self, monkeypatch):
        monkeypatch.setattr(mp, "_probe_seconds", lambda p: 30.0)
        seen = {}
        def _fake(video_path, key, out_path=None, tier=None):
            seen["tier"] = tier
            return "out.mp4"
        monkeypatch.setattr(mp, "remove_subtitles", _fake)
        mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4", tier=vc.TIER_PRO)
        assert seen["tier"] == vc.TIER_PRO


class TestPreprocessRetry:
    """VMake 30029(파일 준비 실패) → 딱 한 번 재인코딩해 다시 보낸다 — 2026-09-17."""

    def _setup(self, monkeypatch, results):
        calls = []
        monkeypatch.setattr(mp, "_probe_seconds", lambda p: 20.0)
        monkeypatch.setattr(mp, "_reencode_for_vmake", lambda p: "in_reenc.mp4")

        def fake(src, key, out_path=None, tier=None):
            calls.append(src)
            r = results.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        monkeypatch.setattr(mp, "remove_subtitles", fake)
        return calls

    def test_30029면_재인코딩본으로_한번_더_보낸다(self, monkeypatch):
        calls = self._setup(monkeypatch, [RuntimeError("code 30029"), "out.mp4"])
        assert mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4", tier=vc.TIER_PRO) == "out.mp4"
        assert calls == ["in.mp4", "in_reenc.mp4"]

    def test_재인코딩본도_실패하면_더_안_돌고_올린다(self, monkeypatch):
        calls = self._setup(monkeypatch, [RuntimeError("30029"), RuntimeError("30029")])
        with pytest.raises(RuntimeError):
            mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4")
        assert len(calls) == 2, "무한 재시도하면 안 된다"

    def test_다른_오류는_재인코딩하지_않는다(self, monkeypatch):
        calls = self._setup(monkeypatch, [RuntimeError("network down")])
        with pytest.raises(RuntimeError):
            mp._vmake_clean("in.mp4", ["ak:sk"], "out.mp4")
        assert calls == ["in.mp4"]


def test_옛키로_고급실패는_키미등록으로_안내하지_않는다():
    """2026-09-17 박진우(cid 341): 키 등록돼 있는데 '아직 키를 등록하지 않으셨다'가 떴다."""
    from shopping_shorts.app import clean_failure_kind
    e = "고급 자막제거(Smart Pro)는 VMake 새 API 키가 필요합니다. VMake 대시보드에서 'Switch to New API'로 전환한 뒤 다시 시도해 주세요."
    assert clean_failure_kind(e) == "need_new_api_key"
    assert clean_failure_kind("자막 지우기 API 키가 필요합니다") == "need_own_key"


class TestProLock:
    """예전 키로 고급을 못 고르게 서버에서 막는다 — 2026-09-17 사장님 "고급으로 누르면 안 되게"."""

    def _job(self, tier="pro"):
        return {"job_id": "j1", "customer_id": 174, "subtitle_removal": True,
                "clean_tier": tier, "edit_plan": {"beats": []}}

    def test_예전키면_409(self, monkeypatch):
        import shopping_shorts.app as a
        monkeypatch.setattr(a, "_clean_pro_ready", lambda st, cid: False)
        monkeypatch.setattr(a.mix_pipeline, "clean_final_path_for_plan", lambda j, w: None)
        r = a._pro_block_or_none(None, self._job())
        assert r is not None and r.status_code == 409

    def test_모르면_막지_않는다(self, monkeypatch):
        import shopping_shorts.app as a
        monkeypatch.setattr(a, "_clean_pro_ready", lambda st, cid: None)
        monkeypatch.setattr(a.mix_pipeline, "clean_final_path_for_plan", lambda j, w: None)
        assert a._pro_block_or_none(None, self._job()) is None

    def test_이미_고급_청소본이_있으면_막지_않는다(self, monkeypatch):
        import shopping_shorts.app as a
        monkeypatch.setattr(a, "_clean_pro_ready", lambda st, cid: False)
        monkeypatch.setattr(a.mix_pipeline, "clean_final_path_for_plan", lambda j, w: "x.mp4")
        assert a._pro_block_or_none(None, self._job()) is None

    def test_기본은_막지_않는다(self, monkeypatch):
        import shopping_shorts.app as a
        monkeypatch.setattr(a, "_clean_pro_ready", lambda st, cid: False)
        assert a._pro_block_or_none(None, self._job("basic")) is None
