"""11-05 사장님 '긴 소재는 부분만' · Jev: 롱폼 소재는 통째 받아쓰기 대신 유튜브 자막 → 없으면 앞 BENCH_ASR_MAX_SEC 만(김미향 #7001 8분22초)."""
import subprocess
from pathlib import Path

from tools.calcopy.engine import yt_fetch as YF
from tools.calcopy.hybrid import runner_ops as RO


def _mp4(p: Path, sec: int):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"sine=d={sec}", "-f", "lavfi", "-i", f"color=s=64x64:d={sec}",
                    "-shortest", "-c:v", "libx264", "-c:a", "aac", str(p)], check=True, stdin=subprocess.DEVNULL)


def test_short_bench_is_fully_transcribed(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(RO, "asr", lambda p, engine=None: seen.append(Path(p).name) or [{"t0": 0, "t1": 1, "text": "x"}])
    m = tmp_path / "bench.mp4"; _mp4(m, 3)
    lines, how = RO.bench_lines(m, None, 30.0)
    assert seen == ["bench.mp4"] and how == "받아쓰기"


def test_long_bench_uses_youtube_subs(tmp_path, monkeypatch):
    monkeypatch.setattr(RO, "asr", lambda *a, **k: (_ for _ in ()).throw(AssertionError("롱폼인데 통째 받아쓰기")))
    monkeypatch.setattr(RO, "vtt_words", lambda p: [[0.5, "안녕"], [4.0, "하세요"]])
    lines, how = RO.bench_lines(tmp_path / "bench.mp4", tmp_path / "bench.ko.vtt", 502.0)
    assert how == "유튜브 자막" and lines


def test_long_bench_without_subs_transcribes_head_only(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(RO, "asr", lambda p, engine=None: seen.append(Path(p)) or [])
    m = tmp_path / "bench.mp4"; _mp4(m, 6)
    monkeypatch.setattr(YF, "BENCH_ASR_MAX_SEC", 2)
    lines, how = RO.bench_lines(m, None, 502.0)
    assert seen and seen[0].name == "bench_head.wav" and "앞 2초" in how
