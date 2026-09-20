# -*- coding: utf-8 -*-
"""캡컷 내보내기 — 완성본을 컷별로 잘라 쓴다 (2026-08-27 사장님 B안 확정).

★배경: 캡컷은 '소스 파일 + 타임라인 트림' 구조라 소스별 청소본을 전제로 짜여 있었다.
  2단계를 완성본 1편 청소로 바꾸자 그 맵이 비어 **원본이 나가 자막이 살아났다**.

★A안(캡컷 때만 소스별 재청소)과 B안(완성본을 잘라 쓰기) 중 사장님이 B를 골랐다.
    A: 컷을 원본 범위 밖으로 늘릴 수 있다. 대신 5P + 몇 분(1편에 10P가 된다).
    B: 늘리기는 못 한다. 대신 추가 과금 0·대기 0 — '1편 1회 차감' 원칙이 지켜진다.
"""
from pathlib import Path

import pytest

from shopping_shorts import mix_pipeline as mp


def _timeline():
    return [{"beat_idx": 0, "t0": 0.0, "dur": 3.0},
            {"beat_idx": 1, "t0": 3.0, "dur": 4.5},
            {"beat_idx": 2, "t0": 7.5, "dur": 2.0}]


def _plan():
    return {"beats": [
        {"beat_idx": 0, "target_seconds": 3.0,
         "primary": {"video_id": "s0", "start": 10.0, "end": 13.0},
         "alternates": [{"video_id": "s1", "start": 2.0, "end": 4.0}]},
        {"beat_idx": 1, "target_seconds": 4.0,
         "primary": {"video_id": "s1", "start": 0.0, "end": 4.0},
         "alternates": [], "scene_override": [{"video_id": "s2", "start": 1.0, "end": 5.0}]},
        {"beat_idx": 2, "target_seconds": 2.0,
         "primary": {"video_id": "s2", "start": 5.0, "end": 7.0}, "alternates": []},
    ]}


class Test완성본_컷별분할:
    def test_비트마다_조각을_만든다(self, monkeypatch, tmp_path):
        calls = []
        def fake_run(cmd, **kw):
            calls.append(cmd)
            Path(cmd[-1]).write_text("clip" * 500)      # 1024바이트 넘게
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        clips = mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)
        assert set(clips) == {"cc0", "cc1", "cc2"}
        assert len(calls) == 3

    def test_자르는_위치가_타임라인_그대로(self, monkeypatch, tmp_path):
        """★렌더가 쓰는 t0·dur을 그대로 써야 조각이 화면과 안 어긋난다."""
        seen = []
        def fake_run(cmd, **kw):
            seen.append((cmd[cmd.index("-ss") + 1], cmd[cmd.index("-t") + 1]))
            Path(cmd[-1]).write_text("clip" * 500)
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)
        assert seen == [("0.000", "3.000"), ("3.000", "4.500"), ("7.500", "2.000")]

    def test_VMake를_부르지_않는다(self, monkeypatch, tmp_path):
        """★B안의 핵심 — 다시 지우는 게 아니라 있는 걸 자른다(추가 과금 0)."""
        def boom(*a, **k):
            raise AssertionError("VMake를 부르면 안 된다")
        monkeypatch.setattr(mp, "remove_subtitles", boom)
        monkeypatch.setattr(mp, "_charge_clean", boom)
        def fake_run(cmd, **kw):
            Path(cmd[-1]).write_text("clip" * 500)
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)

    def test_이미_잘라둔_건_다시_안_자른다(self, monkeypatch, tmp_path):
        n = []
        def fake_run(cmd, **kw):
            n.append(1); Path(cmd[-1]).write_text("clip" * 500)
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)
        mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)
        assert len(n) == 3, "두 번째 호출에서 또 잘랐다"

    def test_편성이_바뀌면_다시_자른다(self, monkeypatch, tmp_path):
        """★버그헌트 P1-3. 종전 파일명엔 서명이 없어 편성을 고쳐도 **옛 조각**이 나갔다.

        오류가 안 나므로 고객은 '고쳤는데 안 바뀜'만 본다 — 조용한 실패라 더 나쁘다.
        위 `test_이미_잘라둔_건_다시_안_자른다`는 같은 편성만 봐서 이걸 못 잡았다.
        """
        n = []
        def fake_run(cmd, **kw):
            n.append(1); Path(cmd[-1]).write_text("clip" * 500)
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)
        assert len(n) == 3
        # 비트 길이를 바꾼다 = 다른 편성. 조각도 달라져야 한다.
        changed = [dict(r) for r in _timeline()]
        changed[1]["dur"] = 6.0
        mp.split_final_into_beat_clips("/x/final.mp4", changed, tmp_path)
        assert len(n) == 4, "편성이 바뀌었는데 옛 조각을 그대로 썼다"

    def test_빈_조각은_예외(self, monkeypatch, tmp_path):
        def fake_run(cmd, **kw):
            Path(cmd[-1]).write_text("")        # 0바이트
            class R: returncode = 0
            return R()
        monkeypatch.setattr(mp.subprocess, "run", fake_run)
        with pytest.raises(RuntimeError):
            mp.split_final_into_beat_clips("/x/final.mp4", _timeline(), tmp_path)


class Test조각기준_편집안:
    def test_각_비트가_자기_조각을_통째로_쓴다(self):
        clips = {"cc0": "/w/cc0.mp4", "cc1": "/w/cc1.mp4", "cc2": "/w/cc2.mp4"}
        out = mp.plan_using_beat_clips(_plan(), clips, _timeline())
        b0 = out["beats"][0]
        assert b0["primary"]["video_id"] == "cc0"
        assert b0["primary"]["start"] == 0.0

    def test_길이는_조각_실제길이(self):
        """★target_seconds(4.0)가 아니라 timeline의 dur(4.5)여야 한다 — 안 그러면 어긋난다."""
        clips = {"cc1": "/w/cc1.mp4"}
        out = mp.plan_using_beat_clips(_plan(), clips, _timeline())
        assert out["beats"][1]["primary"]["end"] == 4.5

    def test_alternates와_편성은_접힌다(self):
        """조각이 이미 그 화면을 담고 있다 — 남기면 캡컷이 없는 파일을 찾는다."""
        clips = {"cc0": "/w/cc0.mp4", "cc1": "/w/cc1.mp4", "cc2": "/w/cc2.mp4"}
        out = mp.plan_using_beat_clips(_plan(), clips, _timeline())
        for b in out["beats"]:
            assert b["alternates"] == []
            assert "scene_override" not in b

    def test_원본_편집안은_안_건드린다(self):
        """캡컷 내보내기가 DB의 편집안을 망가뜨리면 안 된다."""
        plan = _plan()
        mp.plan_using_beat_clips(plan, {"cc0": "/w/cc0.mp4"}, _timeline())
        assert plan["beats"][0]["primary"]["video_id"] == "s0"
        assert plan["beats"][0]["alternates"], "원본이 비워졌다"

    def test_조각이_없는_비트는_그대로_둔다(self):
        out = mp.plan_using_beat_clips(_plan(), {"cc0": "/w/cc0.mp4"}, _timeline())
        assert out["beats"][1]["primary"]["video_id"] == "s1"
