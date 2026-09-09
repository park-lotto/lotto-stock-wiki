# -*- coding: utf-8 -*-
"""자막제거 전/후 비교 — 편성이 바뀐 뒤에도 **같은 장면**이어야 한다 (2026-09-03).

실측 job fb62adf0aad0: 10:23 청소 → 16:03~16:27 장면편집 30회 → 편성 서명이 달라졌다
(1f7b5a9f… → cb6f4cd7…, 길이 22.55초 → 20.42초). 화면은 **지금 편성**의 컷 시각을
**옛 청소본**에 대서 BEFORE 줄무늬 셔츠 여성 / AFTER 보라 옷 여성이 나란히 떴다.

처방: 청소본 옆에 그때 편성을 스냅샷(final_clean_{sig}.plan.json)으로 남기고,
비교는 clean_compare_clips 한 곳이 "어느 파일을 어느 편성으로 펼지"를 정한다.
"""
import json
from pathlib import Path

from shopping_shorts import mix_pipeline as mp


def _beat(idx, secs, mats):
    m = [{"video_id": v, "seg_id": f"{v}-{i}", "start": s, "end": e}
         for i, (v, s, e) in enumerate(mats)]
    return {"beat_idx": idx, "target_seconds": secs, "primary": m[0], "alternates": m[1:]}


def _plan_a():
    return {"beats": [_beat(0, 2.0, [("s0", 0.0, 5.0)]),
                      _beat(1, 2.0, [("s1", 3.0, 9.0)]),
                      _beat(2, 2.0, [("s0", 10.0, 15.0)])]}


def _plan_b():
    """비트 하나를 지운 뒤 — 시간축이 통째로 당겨진다."""
    return {"beats": [_beat(0, 2.0, [("s1", 3.0, 9.0)]),
                      _beat(1, 2.0, [("s0", 10.0, 15.0)])]}


_SD = {"s0": 20.0, "s1": 20.0}


def _mk_clean(work, plan, snapshot=True):
    sig = mp._plan_signature(plan)
    f = work / f"final_clean_{sig}.mp4"
    f.write_bytes(b"0" * 2048)
    if snapshot:
        mp._save_clean_plan_snapshot(work, sig, plan)
    return f


class Test스냅샷저장:
    def test_청소본_옆에_편성이_남는다(self, tmp_path):
        sig = mp._plan_signature(_plan_a())
        mp._save_clean_plan_snapshot(tmp_path, sig, _plan_a())
        p = tmp_path / f"final_clean_{sig}.plan.json"
        assert p.exists()
        assert json.loads(p.read_text(encoding="utf-8"))["beats"][0]["beat_idx"] == 0

    def test_한번_남긴_것은_덮어쓰지_않는다(self, tmp_path):
        sig = "abc"
        mp._save_clean_plan_snapshot(tmp_path, sig, {"beats": [{"beat_idx": 7}]})
        mp._save_clean_plan_snapshot(tmp_path, sig, {"beats": []})
        assert json.loads((tmp_path / "final_clean_abc.plan.json").read_text())["beats"][0]["beat_idx"] == 7

    def test_clean_fn이_스냅샷을_부른다(self):
        """★호출부 검사 — 함수만 있고 아무도 안 부르면 옛 증상 그대로다."""
        import inspect
        src = inspect.getsource(mp._final_clean_fn)
        assert src.count("_save_clean_plan_snapshot(") >= 2, "재사용·신규 두 경로 모두 스냅샷을 남겨야 한다"


class Test짝맞춤(object):
    def _job(self, plan):
        return {"edit_plan": plan, "urls": ["u0", "u1"], "clean_status": "ready"}

    def test_지금_편성_청소본이_있으면_stale_아님(self, tmp_path, monkeypatch):
        monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: _SD)
        f = _mk_clean(tmp_path, _plan_a())
        r = mp.clean_compare_clips(self._job(_plan_a()), tmp_path)
        assert r["stale"] is False and r["plan_used"] == "current"
        assert r["clean_path"] == str(f)
        assert r["clips"] and r["clips"][0]["video_id"] == "s0"

    def test_편성이_바뀌면_스냅샷_편성으로_좌우를_편다(self, tmp_path, monkeypatch):
        """★이번 버그의 핵심. 옛 청소본을 지금 편성 시각으로 읽으면 딴 장면이다."""
        monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: _SD)
        f = _mk_clean(tmp_path, _plan_a())
        r = mp.clean_compare_clips(self._job(_plan_b()), tmp_path)   # 편성은 B로 바뀜
        assert r["stale"] is True and r["plan_used"] == "snapshot"
        assert r["clean_path"] == str(f)
        # 청소본(A 편성)에서 s1은 2.0초부터다 — B 편성(0.0초)이 아니라.
        s1 = next(c for c in r["clips"] if c["video_id"] == "s1")
        assert abs(s1["fin"] - 2.0) < 0.05, f"옛 청소본 시간축이 아니다: {s1}"
        assert abs(s1["src"] - 3.0) < 0.05

    def test_스냅샷이_없으면_clips_None_stale_True(self, tmp_path, monkeypatch):
        """틀린 그림 대신 사실을 말할 수 있게 — 호출부가 404(reason=stale)로 낸다."""
        monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: _SD)
        _mk_clean(tmp_path, _plan_a(), snapshot=False)
        r = mp.clean_compare_clips(self._job(_plan_b()), tmp_path)
        assert r["stale"] is True and r["clips"] is None

    def test_소스별_청소본_경로는_대상_아님(self, tmp_path):
        r = mp.clean_compare_clips({"edit_plan": _plan_a(), "clean_sources": {"s0": "x"}}, tmp_path)
        assert r["clips"] is None and r["stale"] is False

    def test_컷마다_한_장_si가_붙는다(self, tmp_path, monkeypatch):
        """'5장면밖에 안 나온다' — 소스 수가 아니라 컷 수만큼 넘긴다."""
        monkeypatch.setattr(mp, "_src_durs_for", lambda job, work: _SD)
        _mk_clean(tmp_path, _plan_a())
        r = mp.clean_compare_clips(self._job(_plan_a()), tmp_path)
        assert len(r["clips"]) >= 3 and [c["si"] for c in r["clips"][:3]] == [0, 1, 0]
        assert [c["ci"] for c in r["clips"]] == list(range(len(r["clips"])))


class Test호출부:
    def test_app이_정본_함수를_쓰고_ci를_받는다(self):
        src = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
        i = src.find("def api_produce_mix_clean_thumb(")
        assert i > 0
        window = src[i:i + 6000]
        assert "clean_compare_clips(" in window, "비교 짝은 정본 함수 한 곳에서 와야 한다"
        assert "ci: int = -1" in window
        assert '"reason": "stale"' in window
        assert 'src = _clean_path or job.get("clean_video_path")' in window, \
            "AFTER 파일은 판정이 고른 파일이어야 한다(clean_video_path는 옛 편성일 수 있다)"
        assert '"/api/produce/mix/clean_clips/{job_id}"' in src

    def test_화면이_컷_목록을_받아_넘긴다(self):
        html = (Path(__file__).resolve().parents[1] / "static" / "produce.html").read_text(encoding="utf-8")
        assert "/api/produce/mix/clean_clips/" in html
        assert "장면 '+(ci+1)+' / '+n" in html
        assert "CLEAN_STALE" in html
