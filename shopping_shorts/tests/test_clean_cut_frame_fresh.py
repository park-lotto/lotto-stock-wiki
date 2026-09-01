# -*- coding: utf-8 -*-
"""컷 미리보기가 **청소본**에서 뜨는가 — 편성이 그대로일 때만 (2026-09-01).

★사고(사장님 제보): "자막제거 완료했는데 장면꾸미기에서 자막이 그대로 나옴".
  09-01에 '꾸미기 컷이 3단계와 다른 장면으로 뜨던 것'을 고치면서, 컷 프레임을
  **늘 원본에서** 뜨게 했다. 완성본 청소본은 좌표계가 달라 옛 편성의 엉뚱한 장면이
  나올 수 있었기 때문이다. 그 대가로 자막제거를 켠 작업의 컷 카드에 원본 자막이
  전부 살아났다.
  진짜 판단은 "좌표계가 지금 편성과 맞는가"이고, 그건 청소본 파일명에 박힌 편성
  서명(final_clean_{sig}.mp4)으로 **대조할 수 있다**. 여기를 고정한다.
"""
import os
from pathlib import Path

from shopping_shorts import app as A
from shopping_shorts import mix_pipeline as MP


def _plan(n=3, t=10.0):
    return {"beats": [{"beat_idx": i, "target_seconds": t,
                       "primary": {"video_id": f"s{i}", "start": 0.0, "end": 10.0},
                       "alternates": []} for i in range(n)]}


def _job(work, plan):
    cvp = Path(work) / "clean_preview.mp4"
    cvp.write_text("x")
    sig = MP._plan_signature(plan)
    f = Path(work) / f"final_clean_{sig}.mp4"
    f.write_text("y" * 2048)
    os.utime(f, (1, 1))                       # 청소본이 더 새것
    return {"clean_sources": None, "clean_status": "ready",
            "clean_video_path": str(cvp), "edit_plan": plan}


class Test청소본_신선도:
    def test_편성_그대로면_신선하다(self, tmp_path):
        plan = _plan()
        assert MP.clean_final_matches_plan(_job(tmp_path, plan), tmp_path) is True

    def test_편성이_바뀌면_안신선하다(self, tmp_path):
        job = _job(tmp_path, _plan())
        job["edit_plan"] = _plan(t=7.0)        # 컷 길이가 달라졌다 = 다른 그림
        assert MP.clean_final_matches_plan(job, tmp_path) is False, \
            "썩은 청소본을 쓰면 옛 편성의 엉뚱한 장면이 뜬다"

    def test_서명파일이_없으면_안신선하다(self, tmp_path):
        job = _job(tmp_path, _plan())
        next(Path(tmp_path).glob("final_clean_*.mp4")).unlink()
        assert MP.clean_final_matches_plan(job, tmp_path) is False

    def test_소스별_청소본은_항상_신선(self, tmp_path):
        cvp = Path(tmp_path) / "clean_preview.mp4"
        cvp.write_text("x")
        job = {"clean_sources": {"s0": "/c/s0.mp4"}, "clean_video_path": str(cvp)}
        assert MP.clean_final_matches_plan(job, tmp_path) is True


class Test컷프레임_출처:
    def _capture(self, monkeypatch):
        seen = {}

        def fake_run(cmd, **kw):
            class R:
                returncode = 0
                stdout = b""
            if "-i" not in cmd:          # ffprobe 등 — 길이는 모름(0.0)
                return R()
            seen["src"] = cmd[cmd.index("-i") + 1]
            Path(cmd[-1]).parent.mkdir(parents=True, exist_ok=True)
            Path(cmd[-1]).write_text("jpg")
            return R()
        import subprocess
        monkeypatch.setattr(subprocess, "run", fake_run)
        return seen

    def test_신선하면_컷도_청소본에서_뜬다(self, tmp_path, monkeypatch):
        seen = self._capture(monkeypatch)
        (tmp_path / "clean_preview.mp4").write_text("c")
        beat = _plan()["beats"][0]
        A._extract_beat_frame(tmp_path, beat, tmp_path / "o.jpg",
                              clean_final=str(tmp_path / "clean_preview.mp4"),
                              final_ratio=0.5,
                              seg_spec={"video_id": "s0", "start": 1.0},
                              clean_fresh=True)
        assert seen["src"].endswith("clean_preview.mp4"), \
            "컷을 원본에서 뜨면 자막제거를 켜도 꾸미기에 자막이 남는다"

    def test_안신선하면_원본에서_뜬다(self, tmp_path, monkeypatch):
        seen = self._capture(monkeypatch)
        (tmp_path / "clean_preview.mp4").write_text("c")
        (tmp_path / "s0").mkdir()
        (tmp_path / "s0" / "a.mp4").write_text("v")
        beat = _plan()["beats"][0]
        A._extract_beat_frame(tmp_path, beat, tmp_path / "o.jpg",
                              clean_final=str(tmp_path / "clean_preview.mp4"),
                              final_ratio=0.5,
                              seg_spec={"video_id": "s0", "start": 1.0},
                              clean_fresh=False)
        assert seen["src"].endswith("a.mp4"), "틀린 장면보다 자막 있는 정확한 장면이 낫다"
