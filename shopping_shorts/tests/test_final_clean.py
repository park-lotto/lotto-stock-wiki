# -*- coding: utf-8 -*-
"""자막제거를 **완성본 1편**에만 건다 (2026-08-26 사장님 지시).

★왜 (실측)
    VMake는 보낸 영상 1초당 약 9초를 쓴다(69초→632초 / 100초→1,692초, 08-26 실측).
    그런데 우리는 담아온 소스 전체(합쳐서 100~150초)를 보내고 있었다. 완성본은 30초다.
      지금:   100~150초를 보냄 → 15~22분
      완성본:  30초를 보냄     → 4~5분   ★크레딧은 똑같이 1콜
    사장님: "3단계에서 완성본 만들기 된 영상만 딱 자막제거 20~30초 하면 되잖아".

★화면 순서가 이미 그렇게 돼 있다 — 3단계(영상대본MIX·완성본 만들기) → 4단계(자막제거).
    완성본이 먼저 나오므로 그걸 청소하면 된다.

★재과금을 막는 열쇠: **편성 서명**.
    편성(어느 영상의 어느 구간을 어떤 순서로)이 그대로면 완성본도 같다 → 청소 결과를 재사용.
    장면을 진짜로 바꿨을 때만 다시 청소한다. 서명이 이 판단의 유일한 근거다.
"""
import pytest

from shopping_shorts.mix_pipeline import _plan_signature


def _plan(*clips):
    """clips: (video_id, start, end) 여러 개 → beats 1개짜리 편집안."""
    return {"beats": [{"beat_idx": 0, "target_seconds": 2.0,
                       "primary": {"video_id": v, "seg_id": f"{v}-0", "start": s, "end": e},
                       "alternates": []} for v, s, e in clips]}


class TestPlanSignature:
    def test_같은_편성은_같은_서명(self):
        a = _plan(("s0", 1.0, 3.0), ("s1", 5.0, 7.0))
        b = _plan(("s0", 1.0, 3.0), ("s1", 5.0, 7.0))
        assert _plan_signature(a) == _plan_signature(b)

    def test_구간이_달라지면_서명도_달라진다(self):
        a = _plan(("s0", 1.0, 3.0))
        b = _plan(("s0", 1.0, 4.0))          # 끝점이 1초 늘었다
        assert _plan_signature(a) != _plan_signature(b)

    def test_다른_영상을_쓰면_달라진다(self):
        a = _plan(("s0", 1.0, 3.0))
        b = _plan(("s9", 1.0, 3.0))
        assert _plan_signature(a) != _plan_signature(b)

    def test_순서가_바뀌면_달라진다(self):
        """★순서는 완성본을 바꾼다 — 집합으로 비교하면 순서 변경을 놓쳐 옛 청소본이 나간다."""
        a = _plan(("s0", 1.0, 3.0), ("s1", 5.0, 7.0))
        b = _plan(("s1", 5.0, 7.0), ("s0", 1.0, 3.0))
        assert _plan_signature(a) != _plan_signature(b)

    def test_길이가_바뀌면_달라진다(self):
        """컷 길이(target_seconds)가 바뀌면 완성본 길이가 달라진다 → 다시 청소해야 한다."""
        a = _plan(("s0", 1.0, 3.0))
        b = _plan(("s0", 1.0, 3.0))
        b["beats"][0]["target_seconds"] = 5.0
        assert _plan_signature(a) != _plan_signature(b)

    def test_장면편집_결과가_반영된다(self):
        """사람이 편성한 scene_override가 진짜 재료다 — 이게 서명에 안 들어가면
        장면을 바꿔도 옛 청소본이 그대로 나간다."""
        a = _plan(("s0", 1.0, 3.0))
        b = _plan(("s0", 1.0, 3.0))
        b["beats"][0]["scene_override"] = [
            {"video_id": "s2", "seg_id": "s2-1", "start": 9.0, "end": 12.0}]
        assert _plan_signature(a) != _plan_signature(b)

    def test_대사만_바뀌면_서명은_그대로(self):
        """대사는 **화면**을 안 바꾼다 → 완성본 그림이 같으니 다시 청소할 이유가 없다.
        (음성·자막은 따로 다시 만들어진다)"""
        a = _plan(("s0", 1.0, 3.0))
        b = _plan(("s0", 1.0, 3.0))
        b["beats"][0]["narration"] = "완전히 다른 대사"
        assert _plan_signature(a) == _plan_signature(b)

    def test_빈_편집안도_죽지_않는다(self):
        assert _plan_signature({}) == _plan_signature({"beats": []})
        assert isinstance(_plan_signature(None), str)


# ── 완성본 청소 clean_fn ────────────────────────────────────────────────────
from cryptography.fernet import Fernet

from shopping_shorts import mix_pipeline as mp
from shopping_shorts.store import Store


@pytest.fixture
def store(tmp_path, monkeypatch):
    from shopping_shorts import keycrypt
    monkeypatch.setattr(keycrypt, "_fernet", Fernet(Fernet.generate_key()))
    return Store(str(tmp_path / "t.db"))


def _job(plan):
    return {"job_id": "J", "edit_plan": plan, "customer_id": 0, "subtitle_removal": True}


def test_완성본을_한_번만_보낸다(store, tmp_path, monkeypatch):
    """★소스가 몇 개든 VMake 호출은 1회 — 이게 이번 변경의 전부다."""
    sent = []

    def fake_remove(src, key, out_path):
        sent.append(src)
        Path = type(tmp_path)
        open(out_path, "wb").write(b"x" * 4096)
        return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)

    plan = _plan(("s0", 1.0, 3.0), ("s1", 5.0, 7.0), ("s2", 9.0, 11.0))
    fn = mp._final_clean_fn(store, _job(plan), "J", tmp_path, "KEY", 0)
    mix_raw = tmp_path / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")

    out = fn(str(mix_raw))
    assert len(sent) == 1, f"소스 3개인데 VMake를 {len(sent)}번 불렀다"
    assert sent[0] == str(mix_raw), "완성본이 아니라 다른 걸 보냈다"
    assert out and open(out, "rb").read()


def test_편성이_그대로면_다시_안_청소한다(store, tmp_path, monkeypatch):
    """★재과금 방지의 핵심 — 같은 편성으로 다시 렌더해도 VMake를 또 부르지 않는다."""
    calls = []

    def fake_remove(src, key, out_path):
        calls.append(src)
        open(out_path, "wb").write(b"y" * 4096)
        return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)

    plan = _plan(("s0", 1.0, 3.0))
    job = _job(plan)
    mix_raw = tmp_path / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")

    mp._final_clean_fn(store, job, "J", tmp_path, "KEY", 0)(str(mix_raw))
    mp._final_clean_fn(store, job, "J", tmp_path, "KEY", 0)(str(mix_raw))
    assert len(calls) == 1, f"편성이 같은데 {len(calls)}번 청소했다(재과금)"


def test_편성이_바뀌면_다시_청소한다(store, tmp_path, monkeypatch):
    """장면을 진짜로 바꾸면 완성본이 달라지므로 다시 청소해야 한다 — 안 하면 옛 영상이 나간다."""
    calls = []

    def fake_remove(src, key, out_path):
        calls.append(out_path)
        open(out_path, "wb").write(b"z" * 4096)
        return out_path
    monkeypatch.setattr(mp, "remove_subtitles", fake_remove)

    mix_raw = tmp_path / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")

    mp._final_clean_fn(store, _job(_plan(("s0", 1.0, 3.0))), "J", tmp_path, "KEY", 0)(str(mix_raw))
    mp._final_clean_fn(store, _job(_plan(("s9", 4.0, 6.0))), "J", tmp_path, "KEY", 0)(str(mix_raw))
    assert len(calls) == 2, "편성을 바꿨는데 옛 청소본을 그대로 썼다"
    assert calls[0] != calls[1], "다른 편성인데 같은 파일에 덮어썼다"


def test_실패하면_환불한다(store, tmp_path, monkeypatch):
    """VMake가 실패했는데 포인트만 나가면 안 된다."""
    monkeypatch.setattr(mp, "remove_subtitles",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("VMake 실패")))
    refunds = []
    monkeypatch.setattr(mp, "_refund_clean", lambda st, cid, amt: refunds.append(amt))
    monkeypatch.setattr(mp, "_charge_clean", lambda st, cid, n: 500)

    mix_raw = tmp_path / "mix_raw.mp4"
    mix_raw.write_bytes(b"raw")
    fn = mp._final_clean_fn(store, _job(_plan(("s0", 1.0, 3.0))), "J", tmp_path, "KEY", 7)
    with pytest.raises(RuntimeError):
        fn(str(mix_raw))
    assert refunds == [500], f"환불이 안 됐다: {refunds}"
